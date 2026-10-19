"""Controlled request-local failures through the production POST/SSE route."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from main import app, TurnServices, turn_services
from tests.test_supervisor import FULL, Index, workers


@pytest.mark.asyncio
async def test_sse_capture_uses_final_combined_source_registry():
    from scripts.demo_support import capture_turn
    frames = "event: sources\ndata: [{\"source_id\":\"S1\"}]\n\nevent: answer\ndata: \"Combined [F1][S1]\"\n\nevent: sources\ndata: [{\"source_id\":\"F1\"},{\"source_id\":\"S1\"}]\n\nevent: complete\ndata: {\"status\":\"completed\"}\n\n"
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=frames)), base_url="http://fixture") as client:
        captured = await capture_turn(client, "Mixed request", ["QCOM"], [2025])
    assert {s["source_id"] for s in captured["sources"]} == {"F1", "S1"}


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["timeout", "conflict", "unsupported"])
async def test_api_preserves_safe_terminal_contract(monkeypatch, tmp_path, fault):
    monkeypatch.setattr(app.state, "index", Index(), raising=False)
    monkeypatch.setattr(app.state, "turns", asyncio.Semaphore(2), raising=False)
    monkeypatch.setattr(
        app.state,
        "financials",
        SimpleNamespace(path=tmp_path / "absent"),
        raising=False,
    )
    overrides = workers(
        failed="risk" if fault == "timeout" else None, conflict=fault == "conflict"
    )
    app.dependency_overrides[turn_services] = lambda: TurnServices(
        worker_overrides=overrides
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://fixture"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "question": FULL
                    if fault == "timeout"
                    else "Calculate Qualcomm revenue growth",
                    "companies": ["QCOM"],
                    "years": [2030] if fault == "unsupported" else [2024, 2025],
                },
            )
        assert (
            response.status_code == 200
            and "text/event-stream" in response.headers["content-type"]
        )
        blocks = [
            block.splitlines()
            for block in response.text.split("\n\n")
            if block.startswith("event:")
        ]
        parsed = [{"type": b[0][7:], "data": json.loads(b[1][6:])} for b in blocks]
        activity = [e["data"] for e in parsed if e["type"] == "activity"]
        assert activity and [p["elapsed_ms"] for p in activity] == sorted(p["elapsed_ms"] for p in activity)
        for identity in {p["id"] for p in activity}:
            points = [p for p in activity if p["id"] == identity]
            assert points[0]["status"] == "running" and points[-1]["status"] != "running"
            assert points[0]["agent"] == points[-1]["agent"]
        assert parsed[-1]["type"] == "complete"
        assert parsed[-1]["data"]["status"] == (
            "coverage_gap" if fault == "unsupported" else "partial"
        )
        if fault == "conflict":
            assert "999" not in [e["data"] for e in parsed if e["type"] == "answer"][-1]
    finally:
        app.dependency_overrides.pop(turn_services, None)
