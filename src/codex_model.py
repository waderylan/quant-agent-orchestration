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
    max_calls = getattr(handler, "max_tool_calls", 8)
    if type(max_calls) is not int or not 1 <= max_calls <= 24:
        raise ValueError("Worker tool budget must be between 1 and 24")
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
                    "developerInstructions": "Use only the supplied dynamic tools. Never access files, shell, web, or other tools. Do not issue personalized portfolio allocations or trade instructions. Do not address a named user. Stream the final answer; put progress messages in commentary.",
                },
            )
            yield {
                "type": "trace",
                "data": {
                    "agent": agent,
                    "provider": "Codex subscription",
                    "model": started.get("model"),
                    "reason": reason,
                    "max_tool_calls": max_calls,
                },
            }
            await request(
                "turn/start",
                {
                    "threadId": started["thread"]["id"],
                    "effort": "low",
                    "input": [
                        {
                            "type": "text",
                            "text": prompt
                            + f"\nTool execution limit: {max_calls} calls. Budget metadata in tool responses is application control, not filing evidence. Reserve time to synthesize; when no calls remain, answer from collected evidence and state unresolved gaps. Do not call more tools.",
                        }
                    ],
                },
            )
            calls = 0
            denied_calls = 0
            reports_outcome = any(tool.get("name") == "report_outcome" for tool in tools)
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
                    name, arguments = params["tool"], params["arguments"]
                    if reports_outcome and calls == max_calls and name != "report_outcome" and getattr(handler, "status", None) is None:
                        denied_calls += 1
                        if denied_calls > 2:
                            raise RuntimeError(f"{agent} ignored the required completion report")
                        calls -= 1
                        result, success = {"error": "completion_report_required", "instruction": "The last tool slot is reserved for report_outcome. Call it next; report partial with explicit gaps if requested evidence remains missing. Then answer using existing evidence."}, False
                        yield {"type": "trace", "data": {"agent": agent, "decision": "report_completion", "reason": "Reserve the final bounded tool slot for an explicit outcome"}}
                    elif calls > max_calls:
                        # Allow bounded final synthesis without executing any extra work.
                        denied_calls += 1
                        if denied_calls > 2:
                            raise RuntimeError(
                                f"{agent} ignored the tool limit after two synthesis requests."
                            )
                        result, success = (
                            {
                                "error": "tool_budget_exhausted",
                                "instruction": "No further tools may execute. Return supported findings with citations from evidence already collected. Explicitly state unresolved evidence or calculation gaps; do not invent missing inputs or conclusions.",
                            },
                            False,
                        )
                        if calls == max_calls + 1:
                            yield {
                                "type": "trace",
                                "data": {
                                    "agent": agent,
                                    "decision": "synthesize_existing_evidence",
                                    "reason": "Tool execution limit reached; further calls are denied and findings may be incomplete",
                                    "max_tool_calls": max_calls,
                                },
                            }
                    else:
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
                    remaining = max(0, max_calls - calls)
                    result = {
                        **(result if isinstance(result, dict) else {"result": result}),
                        "tool_budget": {
                            "remaining": remaining,
                            "limit": max_calls,
                            "instruction": "Finish with existing evidence and explicit gaps; no more tools."
                            if not remaining
                            else "Prioritize missing evidence and prepare the answer."
                            if remaining <= 2
                            else "Use calls only for missing evidence.",
                        },
                    }
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
