"""Capability answers need no provider and do not swallow actual stock research."""

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
    "What can the buy-side agent do?",
    "Explain the capabilities of the financial data agent.",
    "What does Risk Summary do?",
    "Can the Buy-Side Analyst calculate forward P/E?",
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


def test_one_agent_answer_does_not_dump_every_role():
    answer = capability_request("What can the buy-side agent do?")["answer"]
    assert "**Buy-Side Analyst:**" in answer
    assert "**Risk Summary:**" not in answer
    assert "selected" in answer and "unverified" in answer


@pytest.mark.asyncio
async def test_mixed_capability_and_stock_request_preserves_both():
    class Index:
        def coverage(self):
            return {"QCOM": [2025]}

    async def buy(state, writer):
        assert state["question"] == "what is its stock price"
        return {"answer": "Dated QCOM price [S1].", "buy_sources": {"S1": {"source_id": "S1", "kind": "market_evidence", "company": "QCOM", "text": "dated quote"}}, "citation_verified": True}

    result = [event async for event in events(Index(), "What can the buy-side agent do, and what is its stock price?", ["QCOM"], [2025], worker_overrides={"buy": buy})]
    answer = next(event["data"] for event in reversed(result) if event["type"] == "answer")
    assert "**Buy-Side Analyst:**" in answer and "Dated QCOM price [S1]" in answer
    assert result[-1]["data"]["status"] == "completed"
