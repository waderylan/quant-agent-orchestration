"""Capture actual SSE turns for compact, reproducible milestone demonstrations."""

import json
import time
import asyncio


async def wait_ready(client):
    import httpx
    for _ in range(60):
        try:
            if (await client.get("/api/coverage")).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        await asyncio.sleep(.5)
    raise RuntimeError("Application readiness deadline exceeded")


async def capture_turn(client, question, companies, years, *, headers=None, include_events=False):
    started, first_token, events, kind = time.perf_counter(), None, [], None
    worker_returns = []
    async with client.stream(
        "POST",
        "/api/chat",
        json={
            "question": question,
            "companies": companies,
            "years": years,
        },
        headers=headers,
    ) as response:
        if response.is_error:
            await response.aread()
            response.raise_for_status()
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                kind = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                if kind == "token" and first_token is None:
                    first_token = time.perf_counter() - started
                events.append({"type": kind, "data": data})
                if kind == "trace" and data.get("node") == "worker_outcome":
                    worker_returns.append({"worker": data.get("worker"), "monotonic": time.perf_counter()})
    answer = ""
    for event in events:
        if event["type"] == "token":
            answer += event["data"]
        elif event["type"] == "answer":
            answer = event["data"]
    return {
        "question": question,
        "answer": answer,
        "sources": next((e["data"] for e in reversed(events) if e["type"] == "sources"), []),
        "terminal": events[-1] if events else None,
        "trace": [e for e in events if e["type"] in ("trace", "tool", "error")],
        "seconds": round(time.perf_counter() - started, 3),
        "request_started_monotonic": started,
        "request_finished_monotonic": time.perf_counter(),
        "worker_return_times": worker_returns,
        "answer_token_ttft_seconds": round(first_token, 3)
        if first_token is not None
        else None,
        **({"events": events} if include_events else {}),
    }
