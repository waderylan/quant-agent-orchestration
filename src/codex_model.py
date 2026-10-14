"""Subscription-backed Codex app-server transport; no credential handling."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from collections import deque
from pathlib import Path


def executable() -> str:
    command = shutil.which("codex")
    if command and Path(command).suffix.lower() in {".cmd", ".ps1"}:
        binaries = list(
            (Path(command).parent / "node_modules/@openai/codex").glob(
                "node_modules/@openai/codex-*/vendor/*/bin/codex.exe"
            )
        )
        if binaries:
            return str(binaries[0])
    if not command:
        raise RuntimeError(
            "Install Codex CLI and run codex login before asking questions."
        )
    return command


async def stream(
    prompt: str,
    tools: list[dict],
    handler,
    *,
    model: str | None = None,
    timeout: int = 180,
):
    """Yield model text and inspected tool events; close the process on cancellation."""
    process = await asyncio.create_subprocess_exec(
        executable(),
        "app-server",
        "-c",
        "project_doc_max_bytes=0",
        "-c",
        'web_search="disabled"',
        "-c",
        "features.shell_tool=false",
        "-c",
        "features.apply_patch_freeform=false",
        "-c",
        "features.multi_agent=false",
        "-c",
        "features.code_mode=false",
        "-c",
        "features.apps=false",
        "-c",
        "features.browser_use=false",
        "-c",
        "features.computer_use=false",
        "-c",
        "features.unified_exec=false",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        limit=4 * 1024 * 1024,
    )
    sequence = 0
    pending = deque()

    async def send(message):
        process.stdin.write((json.dumps(message) + "\n").encode())
        await process.stdin.drain()

    async def receive():
        line = await process.stdout.readline()
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
                    "cwd": tempfile.gettempdir(),
                    "environments": [],
                    "dynamicTools": tools,
                    "baseInstructions": "You are a filings research assistant, not a coding assistant. Answer the supplied research question using only the provided evidence and tools.",
                    "developerInstructions": "Use only the supplied research tools. Never access files, shell, web, or other tools. Do not address a named user. Stream the final research answer; put progress messages in commentary.",
                },
            )
            yield {
                "type": "trace",
                "data": {
                    "agent": "Filings Research",
                    "provider": "Codex subscription",
                    "model": started.get("model"),
                    "reason": "Historical filing research using local evidence",
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
        if process.returncode is None:
            process.kill()
        await process.wait()
