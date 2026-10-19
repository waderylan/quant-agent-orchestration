"""Fixed routing precedence and requested worker sequences."""

import json
from pathlib import Path

import pytest

from src.request_routing import live_intent, price_request
from src.supervisor import tasks_for
from src.request_routing import PRICE_GAP
from src.research_workflow import events
from tests.test_supervisor import Index, source


@pytest.mark.parametrize("case", json.loads((Path(__file__).parent / "fixtures/live_routing.json").read_text(encoding="utf-8")), ids=lambda c: c["question"])
def test_live_routing(case):
    assert live_intent(case["question"]) == case["live_intent"]
    assert price_request(case["question"]) == case["price_gap"]
    assert [task.worker for task in tasks_for(case["question"])[0]] == case["workers"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mixed", [False, True])
async def test_price_gap_preserves_only_supported_data(mixed):
    called = []
    async def data(state, emit):
        called.append("data")
        return {"answer": "Reported revenue [F1].", "financial_sources": {"F1": source(company="AMD")}}
    question = "Show AMD FY2025 revenue and its current share price." if mixed else "What is AMD's stock price and P/E?"
    result = [e async for e in events(Index(), question, ["AMD"], [2025], worker_overrides={"data": data})]
    assert called == (["data"] if mixed else [])
    assert result[-1]["data"]["status"] == ("partial" if mixed else "coverage_gap")
    assert PRICE_GAP in result[-1]["data"]["missing_outputs"]
    assert not any(e["type"] == "trace" and e["data"].get("node") == "live_mcp" for e in result)
