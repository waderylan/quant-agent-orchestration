"""Plan, per-step drafts and reviewed answer sections stay consistent with the final answer."""

import pytest

from src.research_workflow import events
from src.supervisor import SCOPE_ANSWER, compose, year_tip
from tests.test_supervisor import source

QUESTION = "Did AMD's operating margin improve from FY2024 to FY2025? Show the math, explain the reasons from its filings, then research what analysts liked and worried about when the results came out"
CROSSING = "Client demand drove the gain [S1].\n\nOutside research:\nAnalysts praised execution [W1]."


class Index:
    def coverage(self):
        return {"AMD": [2024, 2025], "NVDA": [2024, 2025]}


async def turn(monkeypatch, claims):
    monkeypatch.setenv("REQUEST_PLANNER", "semantic")

    async def model(prompt, tools, handler, **kwargs):
        if kwargs["agent"] == "Request Planner":
            handler("submit_plan", {"outputs": [
                {"kind": "checked_calculations", "description": "Calculate operating margins"},
                {"kind": "filing_explanation", "description": "Explain the margin change from filings"},
                {"kind": "public_reaction", "description": "Research analyst reaction"},
            ], "timeframe": "reaction", "start_date": None, "end_date": None})
        else:
            handler("submit_coverage", {"results": [
                {"id": "R1", "addressed": True, "citations": ["C1"], "missing": ""},
                {"id": "R2", "addressed": True, "citations": ["S1"], "missing": ""},
                {"id": "R3", "addressed": False, "citations": ["W1"], "missing": "No named analyst praise"},
            ], "missing_requests": [], "unsupported_claims": claims})
        yield {"type": "token", "data": ""}

    def worker(answer, sources):
        async def run(state, writer):
            for part in answer.split(" "):
                writer({"type": "token", "data": part + " "})
            return {"answer": answer, **sources}
        return run

    overrides = {
        "data": worker("Inputs [F1].", {"financial_sources": {"F1": source(company="AMD")}}),
        "quant": worker("Margin rose [C1].", {"analysis_sources": {"C1": source("C1", company="AMD")}}),
        "research": worker("Margin rose [C1]. Client demand drove the gain [S1].", {"research_sources": {"S1": source("S1", company="AMD")}}),
        "current": worker("Analysts praised execution [W1]. Unsupported praise.", {"live_sources": {"W1": source("W1", company="AMD")}}),
    }
    return [e async for e in events(Index(), QUESTION, ["AMD"], [2024, 2025], model_stream=model, worker_overrides=overrides)]


def first(es, kind):
    return next(i for i, e in enumerate(es) if e["type"] == kind)


@pytest.mark.asyncio
async def test_each_step_streams_its_own_draft_and_finalizes_in_reviewed_sections(monkeypatch):
    es = await turn(monkeypatch, ["Unsupported praise."])
    plan = next(e["data"] for e in es if e["type"] == "plan")
    assert [(o["id"], o["owner"]) for o in plan["outputs"]] == [("R1", "quant"), ("R2", "research"), ("R3", "current")]
    steps = {s["worker"]: s for s in plan["steps"]}
    assert [s["id"] for s in plan["steps"]] == ["worker-1", "worker-2", "worker-3", "worker-4"]
    assert steps["quant"]["after"] == ["worker-1"] and steps["quant"]["serves"] == ["R1"]
    assert "worker-2" in steps["data"]["feeds"] and steps["data"]["serves"] == []

    # Every step streams, tagged with the same ID as its Activity call; the legacy
    # token stream still carries only the last step.
    assert first(es, "plan") < first(es, "draft")
    running = {e["data"]["id"]: e["data"]["agent"] for e in es if e["type"] == "activity" and e["data"]["status"] == "running"}
    drafts = {}
    for e in es:
        if e["type"] == "draft":
            assert running[e["data"]["step"]] == e["data"]["agent"]
            drafts[e["data"]["step"]] = drafts.get(e["data"]["step"], "") + e["data"]["delta"]
    assert drafts["worker-1"].strip() == "Inputs [F1]." and set(drafts) == set(running) - {"plan", "review"}
    assert "".join(e["data"] for e in es if e["type"] == "token").strip() == "Analysts praised execution [W1]. Unsupported praise."
    finals = {e["data"]["step"]: e["data"]["markdown"] for e in es if e["type"] == "draft_final"}
    assert finals["worker-3"] == "Margin rose [C1]. Client demand drove the gain [S1]."

    result = next(e["data"] for e in es if e["type"] == "answer_sections")
    answer = next(e["data"] for e in reversed(es) if e["type"] == "answer")
    assert [s["id"] for s in result["sections"]] == ["worker-3", "worker-4"] and not result["fallback"]
    assert result["sections"][1]["removed"] == ["Unsupported praise."]
    assert answer.startswith(compose(result["sections"]) + "\n\nUnresolved outputs:")
    assert "Unsupported praise." not in answer
    folded = {f["id"]: f["reason"] for f in result["folded"]}
    assert "Financial analysis" in folded["worker-1"] and "From the filings" in folded["worker-2"]
    assert {"output": "R3", "text": "No named analyst praise", "source": "Answer Reviewer"} in result["gaps"]
    assert first(es, "answer_sections") < len(es) - 1 - [e["type"] for e in reversed(es)].index("answer") < first(es, "complete")


def test_a_one_year_selection_for_a_change_question_suggests_the_prior_year():
    coverage = {"INTC": [2024, 2025]}
    assert year_tip("why did intels gross margin drop", ["INTC"], [2025], coverage).startswith("Your question compares periods, but only FY2025 is selected. Also select FY2024")
    assert year_tip("what was intel revenue", ["INTC"], [2025], coverage) == ""
    assert year_tip("why did margin drop", ["INTC"], [2024, 2025], coverage) == ""
    assert year_tip("why did margin drop", ["INTC"], [2024], coverage) == ""


@pytest.mark.asyncio
async def test_an_investment_recommendation_gets_a_scope_answer_not_an_echo(monkeypatch):
    monkeypatch.setenv("REQUEST_PLANNER", "semantic")

    async def model(prompt, tools, handler, **kwargs):
        handler("submit_plan", {"outputs": [{"kind": "unsupported", "description": "Recommend whether to buy AMD or NVIDIA"}], "timeframe": "recent", "start_date": None, "end_date": None})
        yield {"type": "token", "data": ""}

    es = [e async for e in events(Index(), "should i buy amd or nvidia", ["AMD", "NVDA"], [2025], model_stream=model)]
    result = next(e["data"] for e in es if e["type"] == "answer_sections")
    assert result["status"] == "coverage_gap" and [s["id"] for s in result["sections"]] == ["supervisor"]
    assert result["sections"][0]["markdown"] == SCOPE_ANSWER
    assert es[-1]["data"]["status"] == "coverage_gap"


@pytest.mark.asyncio
async def test_claim_spanning_two_sections_falls_back_to_one_reviewed_answer(monkeypatch):
    es = await turn(monkeypatch, [CROSSING])
    result = next(e["data"] for e in es if e["type"] == "answer_sections")
    answer = next(e["data"] for e in reversed(es) if e["type"] == "answer")
    assert result["fallback"] and [s["id"] for s in result["sections"]] == ["answer"]
    assert result["sections"][0]["removed"] == [CROSSING]
    assert CROSSING not in answer and answer.startswith(compose(result["sections"]))
