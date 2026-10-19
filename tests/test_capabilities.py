"""Capability answers need no provider and do not swallow research requests."""

import pytest

from src.capabilities import capability_request
from src.research_workflow import events


class NoServices:
    def coverage(self):
        pytest.fail("Self-description must not require company data")


@pytest.mark.asyncio
@pytest.mark.parametrize("question", [
    "What can you do?",
    "What does each agent do?",
    "What are your capabilities?",
    "How does the system work?",
    "What can the Current Developments agent do?",
    "Explain the capabilities of the financial data agent.",
    "What does Risk Summary do?",
    "What is each agent capable of?",
    "What is the whole system capable of?",
])
async def test_capability_answers_complete_without_any_external_work(question):
    async def forbidden(*args, **kwargs):
        pytest.fail("A capability answer must not invoke a model")
        yield

    result = [event async for event in events(NoServices(), question, ["QCOM"], [2025], model_stream=forbidden)]
    assert result[-1]["data"]["status"] == "completed"
    assert not result[-1]["data"]["verified_citations"]
    assert any(event["type"] == "answer" and "self-contained" in event["data"] for event in result)
    assert not any(event["type"] in ("tool", "sources", "error") for event in result)


@pytest.mark.parametrize("question", [
    "What can you tell me about Qualcomm's stock price?",
    "Can you show its stock price?",
    "What does Qualcomm do?",
    "Explain management's outlook and analyst expectations.",
])
def test_research_requests_keep_their_normal_route(question):
    assert capability_request(question) is None


@pytest.mark.asyncio
async def test_mixed_capability_and_price_request_retains_the_gap_without_workers():
    from src.request_routing import PRICE_GAP
    class Index:
        def coverage(self):
            return {"AMD": [2025]}
    async def forbidden(*args, **kwargs):
        pytest.fail("Capability and unsupported price clauses need no model")
        yield
    result = [e async for e in events(Index(), "What can the Current Developments agent do, and what is its stock price?", ["AMD"], [2025], model_stream=forbidden)]
    assert result[-1]["data"]["status"] == "coverage_gap"
    answer = next(e["data"] for e in reversed(result) if e["type"] == "answer")
    assert "Current Developments" in answer and PRICE_GAP in answer
    assert not any(e["type"] == "tool" for e in result)
