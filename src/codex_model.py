"""Subscription-backed Codex app-server transport; no credential handling."""

from __future__ import annotations

import asyncio
import json
import os
from collections import deque

from src.codex_transport import connection


async def stream(
    prompt: str,
    tools: list[dict],
    handler,
    *,
    model: str | None = None,
    timeout: int = 180,
    agent: str = "Filings Research",
    reason: str = "Historical filing research using local evidence",
):
    """Yield model text and inspected tool events; close the process on cancellation."""
    transport = connection()
    reader, writer = await transport.__aenter__()
    sequence = 0
    pending = deque()

    async def send(message):
        writer.write((json.dumps(message) + "\n").encode())
        await writer.drain()

    async def receive():
        line = await reader.readline()
        if not line:
            raise RuntimeError("Codex app-server closed before completing the answer.")
        return json.loads(line)

    async def request(method, params):
        nonlocal sequence
        sequence += 1
        await send({"id": sequence, "method": method, "params": params})
        while True:
            message = await receive()
            if message.get("id") == sequence and "method" not in message:
                if "error" in message:
                    raise RuntimeError(str(message["error"]))
                return message["result"]
            pending.append(message)

    try:
        async with asyncio.timeout(timeout):
            await request(
                "initialize",
                {
                    "clientInfo": {"name": "company_research", "version": "0.1.0"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            await send({"method": "initialized"})
            started = await request(
                "thread/start",
                {
                    "ephemeral": True,
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "model": model or os.getenv("RESEARCH_MODEL", "gpt-6.1-sol"),
                    "environments": [],
                    "dynamicTools": tools,
                    "baseInstructions": f"You are the {agent} specialist in a public-company research application. Follow the supplied role instructions using only the provided evidence and dynamic tools.",
                    "developerInstructions": "Use only the supplied dynamic tools. Never access files, shell, web, or other tools. Do not address a named user. Stream the final answer; put progress messages in commentary.",
                },
            )
            yield {
                "type": "trace",
                "data": {
                    "agent": agent,
                    "provider": "Codex subscription",
                    "model": started.get("model"),
                    "reason": reason,
                },
            }
            await request(
                "turn/start",
                {
                    "threadId": started["thread"]["id"],
                    "effort": "low",
                    "input": [{"type": "text", "text": prompt}],
                },
            )
            calls = 0
            phases = {}
            while True:
                message = pending.popleft() if pending else await receive()
                method, params = message.get("method"), message.get("params", {})
                if (
                    method == "item/started"
                    and params["item"]["type"] == "agentMessage"
                ):
                    phases[params["item"]["id"]] = params["item"].get("phase")
                elif method == "item/tool/call":
                    calls += 1
                    if calls > 8:
                        raise RuntimeError("Research tool budget exceeded (8 calls).")
                    name, arguments = params["tool"], params["arguments"]
                    yield {
                        "type": "tool",
                        "data": {"name": name, "arguments": arguments},
                    }
                    try:
                        result = await asyncio.to_thread(handler, name, arguments)
                        success = True
                    except (ValueError, KeyError) as error:
                        result, success = {"error": str(error)}, False
                    yield {"type": "evidence", "data": result}
                    await send(
                        {
                            "id": message["id"],
                            "result": {
                                "success": success,
                                "contentItems": [
                                    {"type": "inputText", "text": json.dumps(result)}
                                ],
                            },
                        }
                    )
                elif "id" in message and method:
                    await send(
                        {
                            "id": message["id"],
                            "error": {"code": -32601, "message": "Tool unavailable"},
                        }
                    )
                    raise RuntimeError(
                        f"Codex requested an unavailable operation: {method}"
                    )
                elif method == "item/agentMessage/delta":
                    if phases.get(params["itemId"]) != "commentary":
                        yield {"type": "token", "data": params["delta"]}
                elif method == "turn/completed":
                    turn = params["turn"]
                    if turn["status"] != "completed":
                        raise RuntimeError(
                            f"Codex turn {turn['status']}: {turn.get('error')}"
                        )
                    break
    finally:
        await transport.__aexit__(None, None, None)
