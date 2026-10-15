"""Capture actual SSE turns for compact, reproducible milestone demonstrations."""

import json
import time


async def capture_turn(client, question, companies, years):
    started, first_token, events, kind = time.perf_counter(), None, [], None
    async with client.stream(
        "POST",
        "/api/chat",
        json={
            "question": question,
            "companies": companies,
            "years": years,
        },
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                kind = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                if kind == "token" and first_token is None:
                    first_token = time.perf_counter() - started
                events.append({"type": kind, "data": data})
    return {
        "question": question,
        "answer": "".join(e["data"] for e in events if e["type"] == "token"),
        "sources": next((e["data"] for e in events if e["type"] == "sources"), []),
        "terminal": events[-1] if events else None,
        "trace": [e for e in events if e["type"] in ("trace", "tool", "error")],
        "seconds": round(time.perf_counter() - started, 3),
        "answer_token_ttft_seconds": round(first_token, 3)
        if first_token is not None
        else None,
    }
