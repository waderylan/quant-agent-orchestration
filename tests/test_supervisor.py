"""Task selection, immutable typed handoffs, bounded recovery, and isolation."""

import asyncio
import copy

import pytest

from src.research_workflow import events
from src.supervisor import tasks_for, MAX_STEPS


FULL = "For Qualcomm FY2024-FY2025, compare revenue and margins, explain management drivers and risk changes, and report what has happened since the filing."


class Index:
    def coverage(self):
        return {"QCOM": [2024, 2025], "AMD": [2024, 2025]}


def source(sid="F1", value=100, company="QCOM"):
    return {
        "source_id": sid,
        "kind": "financial_observation",
        "status": "available",
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
        (FULL, ["data", "quant", "risk", "research", "current"]),
    ]
    for question, expected in cases:
        tasks, _ = tasks_for(question)
        assert [t.worker for t in tasks] == expected


def test_mixed_requests_keep_financial_work():
    cases = [
        ("Did AMD sales grow in FY2025 compared with FY2024?", ["data", "quant"]),
        ("Build AMD and NVIDIA consolidated GAAP operating margins; explain why adjusted earnings differ", ["data", "quant", "research"]),
        ("Commentary claims guaranteed upside; compare Intel annual risk language", ["risk"]),
        ("Compare Qualcomm risk changes and quote original filing wording", ["risk"]),
    ]
    for question, expected in cases:
        assert [t.worker for t in tasks_for(question)[0]] == expected
    _, plan = tasks_for("Compare Qualcomm cash conversion and risk changes")
    assert plan.required_calculations == ("ratio",)


def test_calendar_intervals_do_not_expand_fiscal_scope_and_q4_requires_derivation():
    from src.research_workflow import scope_error
    from src.request_routing import mentioned_years, mentioned_companies
    assert not scope_error("NVIDIA FY2024 covers 2023-01-30 through 2024-01-28; show revenue", ["NVDA"], [2024], {"NVDA": [2024]})
    assert mentioned_years("FY2024 facts retrieved October 16, 2026") == {2024}
    assert mentioned_years("Compare FY2023 and FY2024") == {2023, 2024}
    assert mentioned_companies("Compare NVIDIA and AMD. Exclude Intel, Qualcomm from the comparison") == ["NVDA", "AMD"]
    tasks, plan = tasks_for("How much revenue did NVIDIA report in Q4 FY2025 alone?")
    assert [t.worker for t in tasks] == ["data", "quant"] and plan.required_calculations == ("quarter",)
    disclosure = "For AMD FY2025, compare original 10-K MD&A with the separate 10-K/A. Explain the release adjusted operating-income headline against consolidated GAAP operating income. Keep original annual risk disclosures distinct."
    assert [task.worker for task in tasks_for(disclosure)[0]] == ["research"]


@pytest.mark.asyncio
async def test_explicit_exclusions_narrow_every_worker_before_generation():
    async def data(state, writer):
        assert state["companies"] == ["AMD"]
        return {"answer": "AMD revenue [F1].", "financial_sources": {"F1": source(company="AMD")}}
    es = [e async for e in events(Index(), "Show AMD reported revenue. Exclude Qualcomm.", ["AMD", "QCOM"], [2025], worker_overrides={"data": data})]
    assert es[-1]["data"]["status"] == "completed"
    assert {s["company"] for e in es if e["type"] == "sources" for s in e["data"]} == {"AMD"}


@pytest.mark.asyncio
async def test_prior_conversation_scope_requires_clarification_before_using_ui_defaults():
    es = await capture("Use the company and year from our previous conversation and say whether cash conversion improved")
    assert es[-1]["data"]["status"] == "needs_clarification"
    assert not any(e["type"] in ("sources", "tool") for e in es)


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

    async def current(state, writer):
        assert state["analysis_sources"]["C1"]["source_ids"] == ["F1"]
        return {"answer": "2026-10-18 · qualcomm.com · official: fixture event [W1].", "live_sources": {"W1": {"source_id": "W1", "kind": "live_source", "company": state["companies"][0], "url": "https://qualcomm.com/event", "publisher": "qualcomm.com", "source_tier": "official", "published_date": "2026-10-18", "freshness": "fresh", "snapshot_id": "fixture-live", "text": "Fixture event", "text_sha256": "fixture-hash", "inspection_url": "/api/live/fixture-live"}}}

    return dict(data=data, quant=quant, risk=risk, research=research, current=current)


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
async def test_filing_explanation_does_not_erase_checked_calculations():
    async def research(state, writer):
        return {"answer": "Filed business explanation [F1].", "research_sources": state["analysis_sources"]}
    overrides = {**workers(), "research": research}
    result = await capture("Compare Qualcomm revenue growth and explain management drivers", overrides=overrides)
    answer = next(e["data"] for e in reversed(result) if e["type"] == "answer")
    assert "Checked growth 10% [C1]" in answer and "Filed business explanation [F1]" in answer


@pytest.mark.asyncio
async def test_review_repair_keeps_quant_when_it_removes_a_research_sentence(monkeypatch):
    monkeypatch.setenv("REQUEST_PLANNER", "semantic")
    sentence = "Checked growth 10% [C1] because an unsupported acquisition occurred [F1]."
    async def model(prompt, tools, handler, **kwargs):
        if kwargs["agent"] == "Request Planner":
            handler("submit_plan", {"outputs": [{"kind": "checked_calculations", "description": "Revenue growth"},
                {"kind": "filing_explanation", "description": "Filed drivers"}], "timeframe": "since_filing", "start_date": None, "end_date": None})
        else:
            handler("submit_coverage", {"results": [{"id": "R1", "addressed": True, "citations": ["C1"], "missing": ""},
                {"id": "R2", "addressed": False, "citations": [], "missing": "Filed driver evidence is missing"}],
                "missing_requests": [], "unsupported_claims": [sentence] if sentence in prompt else []})
        yield {"type": "token", "data": ""}
    async def research(state, writer):
        return {"answer": sentence, "research_sources": state["analysis_sources"]}
    result = [e async for e in events(Index(), "Calculate Qualcomm revenue growth and explain the filed drivers", ["QCOM"],
        [2024, 2025], model_stream=model, worker_overrides={**workers(), "research": research})]
    answer = next(e["data"] for e in reversed(result) if e["type"] == "answer")
    assert "Checked growth 10% [C1]" in answer and "unsupported acquisition" not in answer


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
        "current",
    ]
    assert termination["registered_evidence"]["F1"]["value"] == "100"
    assert termination["registered_evidence"]["F1"]["owner"] == "data"
    assert termination["registered_evidence"]["C1"]["source_ids"] == ["F1"]
    assert termination["registered_evidence"]["S1"]["fiscal_end"] == "2025-09-28"
    assert termination["registered_evidence"]["W1"]["owner"] == "current"
    assert termination["registered_evidence"]["W1"]["publisher"] == "qualcomm.com"
    assert es[-1]["data"]["status"] == "completed"


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


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("period", "Q3"), ("basis", "quarter"), ("currency", "EUR"), ("status", "conflicting"), ("freshness", "stale")])
async def test_period_metadata_changes_fail_handoff(field, value):
    overrides = workers()
    async def mutate_metadata(state, writer):
        changed = copy.deepcopy(state["financial_sources"]["F1"])
        changed[field] = value
        return {"answer": "Changed basis [F1].", "analysis_sources": {"F1": changed}}
    overrides["quant"] = mutate_metadata
    es = await capture("Calculate Qualcomm revenue growth", overrides=overrides)
    assert es[-1]["data"]["status"] == "partial"
    assert any(e["type"] == "trace" and "changed value/basis" in e["data"].get("reason", "") for e in es)


@pytest.mark.asyncio
async def test_real_deadline_cancels_owned_worker_and_retains_prior_findings(monkeypatch):
    import src.supervisor as supervisor
    monkeypatch.setattr(supervisor, "WORKER_TIMEOUT_SECONDS", .01)
    stopped = asyncio.Event()
    async def stalled(state, writer):
        try:
            await asyncio.sleep(60)
        finally:
            stopped.set()
    overrides = workers()
    overrides["risk"] = stalled
    es = await capture("Compare Qualcomm revenue and annual risk changes", overrides=overrides)
    assert stopped.is_set() and es[-1]["data"]["status"] == "partial"
    assert any("F1" in {s["source_id"] for s in e["data"]} for e in es if e["type"] == "sources")


@pytest.mark.asyncio
async def test_absent_inputs_skip_quant_without_claiming_worker_failure():
    async def absent(state, writer):
        return {"answer": "Reported inputs unavailable.", "financial_sources": {}, "partial": True, "missing_outputs": ["Original statements unavailable"]}
    es = await capture("Calculate Qualcomm revenue growth", overrides={"data": absent})
    assert es[-1]["data"]["status"] == "coverage_gap"
    assert not any(e["type"] == "trace" and e["data"].get("node") == "worker_failure" for e in es)


@pytest.mark.asyncio
async def test_conflicts_remain_inspectable_but_never_enter_quant_inputs():
    async def conflicting(state, writer):
        row = source()
        row["status"] = "conflicting"
        return {"answer": "Conflicting reported figure [F1].", "financial_sources": {"F1": row}, "partial": True}
    async def forbidden(state, writer):
        pytest.fail("Quant must not receive an unresolved conflicting observation")
    es = await capture("Calculate Qualcomm revenue growth", overrides={"data": conflicting, "quant": forbidden})
    assert es[-1]["data"]["status"] == "partial"
    assert [e["data"] for e in es if e["type"] == "sources"][-1][0]["status"] == "conflicting"
