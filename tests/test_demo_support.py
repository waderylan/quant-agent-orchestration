"""Demonstration reports retain authoritative streamed answers and evidence."""

import json

import httpx
import pytest

from scripts.demo_research import application_turn
from scripts.demo_support import capture_turn


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "partial"])
async def test_research_report_inspects_final_passages_and_retains_terminal_status(status):
    source = {"source_id": "S2", "document_id": "filing", "chunk_id": "chunk", "text": "Checked filing text", "company": "QCOM", "fiscal_year": 2025, "inspection_url": "/api/sources/chunk"}
    events = [
        ("token", "Obsolete claim [S1]"),
        ("sources", [{"source_id": "S1", "inspection_url": "/obsolete"}]),
        ("answer", "Corrected filing explanation [S2]. Checked calculation [C1]."),
        ("sources", [source, {"source_id": "F1"}, {"source_id": "C1"}]),
        ("complete", {"status": status}),
    ]
    frames = "".join(f"event: {kind}\ndata: {json.dumps(data)}\n\n" for kind, data in events)
    inspections = []

    def respond(request):
        if request.method == "POST":
            return httpx.Response(200, text=frames)
        inspections.append(request.url.path)
        assert request.url.path == source["inspection_url"]
        return httpx.Response(200, json={"text": source["text"]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond), base_url="http://fixture") as client:
        captured = await capture_turn(client, "Explain the filing", ["QCOM"], [2025])
        result = await application_turn(client, "QCOM", 2025, "Explain the filing")

    assert "events" not in captured
    assert captured["answer"] == result["answer"] == events[2][1]
    assert {s["source_id"] for s in captured["sources"]} == {"S2", "F1", "C1"}
    assert inspections == [source["inspection_url"]]
    assert result["inspections"] == [{"source_id": "S2", "document_id": "filing", "chunk_id": "chunk", "exact_passage": True, "correct_scope": True}]
    assert result["events"][-1] == {"type": "complete", "data": {"status": status}}
    assert result["passed"] is (status == "completed")
