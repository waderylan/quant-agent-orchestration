"""Task selection, immutable typed handoffs, bounded recovery, and isolation."""

import asyncio
import copy

import pytest

from src.research_workflow import events
from src.supervisor import tasks_for, MAX_STEPS


FULL = "For Qualcomm FY2024-FY2025, compare revenue and margins, explain management drivers and risk changes, and give a valuation brief with opposing evidence."


class Index:
    def coverage(self):
        return {"QCOM": [2024, 2025], "AMD": [2024, 2025]}


def source(sid="F1", value=100, company="QCOM"):
    return {
        "source_id": sid,
        "kind": "financial_observation",
        "company": company,
        "fiscal_year": 2025,
        "start": "2024-09-30",
        "end": "2025-09-28",
        "value": value,
        "unit": "USD",
        "accounting_basis": "US GAAP consolidated",
        "metric": "revenue",
        "observation_id": company + "-revenue",
        "inspection_url": "/api/financial/observations/frozen",
        "text": "Exact original financial figure",
    }


def test_selects_only_requested_workers_and_dependency_order():
    cases = [
        ("Explain Qualcomm business strategy", ["research"]),
        ("Show Qualcomm revenue", ["data"]),
        ("Calculate Qualcomm revenue growth", ["data", "quant"]),
        ("Compare Qualcomm risk changes", ["risk"]),
        ("Give Qualcomm stock price quote", ["buy"]),
        (FULL, ["data", "quant", "risk", "research", "buy"]),
    ]
    for question, expected in cases:
        tasks, _ = tasks_for(question)
        assert [t.worker for t in tasks] == expected


def workers(*, failed=None, conflict=False):
    async def data(state, writer):
        await asyncio.sleep(0)
        row = source(company=state["companies"][0])
        return {"answer": "Reported figure [F1].", "financial_sources": {"F1": row}}

    async def quant(state, writer):
        row = copy.deepcopy(state["financial_sources"]["F1"])
        if conflict:
            row["value"] = 999
        c = {
            "source_id": "C1",
            "kind": "calculation",
            "value": "10",
            "unit": "percent",
            "company": state["companies"][0],
            "start": row["start"],
            "end": row["end"],
            "source_ids": ["F1"],
            "inspection_url": "/api/analysis/frozen/calculations/C1",
            "formula": "checked growth",
        }
        return {
            "answer": "Checked growth 10% [C1].",
            "analysis_answer": "Checked growth 10% [C1].",
            "analysis_sources": {"C1": c, "F1": row},
        }

    async def risk(state, writer):
        if failed == "risk":
            raise TimeoutError("Injected risk worker deadline")
        s = {
            "source_id": "S1",
            "company": state["companies"][0],
            "fiscal_year": 2025,
            "fiscal_start": "2024-09-30",
            "fiscal_end": "2025-09-28",
            "kind": "filing_passage",
            "start": 100,
            "end": 200,
            "text": "Exact risk wording",
            "chunk_id": "risk-hash",
            "inspection_url": "/api/risks/original?start=100&end=200",
        }
        return {
            "answer": "Risk evidence [S1].",
            "risk_answer": "Risk evidence [S1].",
            "risk_sources": {"S1": s},
        }

    async def research(state, writer):
        assert state["analysis_sources"]["F1"]["value"] == 100
        assert state["analysis_sources"]["C1"]["value"] == "10"
        if failed != "risk":
            assert state["source_offset"] == 1
        return {
            "answer": "Explanation uses checked evidence [F1][C1].",
            "research_sources": state["analysis_sources"],
        }

    async def buy(state, writer):
        assert state["analysis_sources"]["C1"]["source_ids"] == ["F1"]
        return {
            "answer": "Valuation inputs remain missing [F1][C1].",
            "buy_sources": {
                **state["analysis_sources"],
                **state.get("risk_sources", {}),
            },
            "partial": True,
            "missing_outputs": ["Qualified estimate unavailable"],
        }

    return dict(data=data, quant=quant, risk=risk, research=research, buy=buy)


async def capture(question=FULL, *, overrides=None, company="QCOM", years=(2024, 2025)):
    return [
        e
        async for e in events(
            Index(),
            question,
            [company],
            list(years),
            worker_overrides=overrides or workers(),
        )
    ]


@pytest.mark.asyncio
async def test_five_worker_handoff_keeps_exact_values_dates_and_lineage():
    es = await capture()
    termination = next(
        e["data"]["task"]
        for e in es
        if e["type"] == "trace" and e["data"].get("node") == "termination"
    )
    assert termination["required_workers"] == [
        "data",
        "quant",
        "risk",
        "research",
        "buy",
    ]
    assert termination["registered_evidence"]["F1"]["value"] == "100"
    assert termination["registered_evidence"]["F1"]["owner"] == "data"
    assert termination["registered_evidence"]["C1"]["source_ids"] == ["F1"]
    assert termination["registered_evidence"]["S1"]["fiscal_end"] == "2025-09-28"
    assert (
        es[-1]["data"]["status"] == "partial"
        and "Qualified estimate unavailable" in es[-1]["data"]["missing_outputs"]
    )


@pytest.mark.asyncio
async def test_timeout_retains_trusted_findings_and_terminates():
    es = await capture(overrides=workers(failed="risk"))
    assert es[-1]["data"]["status"] == "partial" and any(
        "deadline" in g for g in es[-1]["data"]["missing_outputs"]
    )
    final = [e["data"] for e in es if e["type"] == "answer"][-1]
    assert "[C1]" in final and "Risk evidence" not in final


@pytest.mark.asyncio
async def test_conflicting_worker_rolls_back_all_evidence():
    es = await capture(
        "Calculate Qualcomm revenue growth", overrides=workers(conflict=True)
    )
    task = next(
        e["data"]["task"]
        for e in es
        if e["type"] == "trace" and e["data"].get("node") == "termination"
    )
    assert (
        task["registered_evidence"]["F1"]["value"] == "100"
        and "C1" not in task["registered_evidence"]
    )
    assert es[-1]["data"]["status"] == "partial"


@pytest.mark.asyncio
async def test_concurrent_turns_keep_separate_company_evidence_and_scope_gaps():
    a, b = await asyncio.gather(
        capture("Show Qualcomm revenue", company="QCOM"),
        capture("Show AMD revenue", company="AMD"),
    )
    for es, company in ((a, "QCOM"), (b, "AMD")):
        assert es[-1]["data"]["status"] == "completed"
        assert {
            s["company"] for e in es if e["type"] == "sources" for s in e["data"]
        } == {company}
    gap = await capture("Show Qualcomm FY2030 revenue", years=(2030,))
    assert gap[-1]["data"]["status"] == "coverage_gap"


@pytest.mark.asyncio
async def test_cancellation_reaches_owned_worker_without_terminal_success():
    entered, closed = asyncio.Event(), asyncio.Event()

    async def pending(state, writer):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            closed.set()

    async def consume():
        return await capture(
            "Explain Qualcomm strategy", overrides={"research": pending}
        )

    task = asyncio.create_task(consume())
    await asyncio.wait_for(entered.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(closed.wait(), timeout=5)


@pytest.mark.asyncio
async def test_missing_structured_source_uses_one_bounded_followup():
    async def absent(state, writer):
        return {
            "answer": "",
            "partial": True,
            "needs_evidence": {
                "kind": "structured_missing",
                "message": "Requested original observation missing",
            },
        }

    async def inspect(state, writer):
        return {
            "answer": "Filing establishes context, not a checked figure [S1].",
            "research_sources": {
                "S1": {
                    "source_id": "S1",
                    "company": "QCOM",
                    "kind": "filing_passage",
                    "chunk_id": "frozen",
                    "text": "Context",
                    "inspection_url": "/api/sources/frozen",
                }
            },
            "partial": True,
            "missing_outputs": ["Checked original financial figure unavailable"],
        }

    es = await capture(
        "Show Qualcomm revenue", overrides={"data": absent, "research": inspect}
    )
    task = next(
        e["data"]["task"]
        for e in es
        if e["type"] == "trace" and e["data"].get("node") == "termination"
    )
    assert task["steps"] == 2 and task["followups"] == 1 and task["steps"] <= MAX_STEPS
    assert es[-1]["data"]["status"] == "partial"


@pytest.mark.asyncio
async def test_source_less_clarification_is_not_false_completion():
    async def clarify(state, writer):
        return {
            "answer": "Which operating definition should this comparison use?",
            "clarification": True,
            "missing_outputs": ["Metric definition required"],
        }

    es = await capture(
        "Explain Qualcomm operating performance", overrides={"research": clarify}
    )
    assert (
        es[-1]["data"]["status"] == "needs_clarification"
        and not es[-1]["data"]["verified_citations"]
    )


@pytest.mark.asyncio
async def test_mutating_worker_cannot_poison_prior_evidence():
    overrides = workers()

    async def mutate(state, writer):
        state["financial_sources"]["F1"]["value"] = 999
        return {
            "answer": "Poisoned result [F1].",
            "analysis_sources": state["financial_sources"],
        }

    overrides["quant"] = mutate
    es = await capture("Calculate Qualcomm revenue growth", overrides=overrides)
    final_sources = [e["data"] for e in es if e["type"] == "sources"][-1]
    assert final_sources[0]["value"] == 100 and es[-1]["data"]["status"] == "partial"
