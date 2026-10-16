"""Regressions for PM wording, completion, units, assumptions and numerical lineage."""

from decimal import Decimal

import pytest

from src.quant_analysis import run_isolated, validate_results
from src.quant_workflow import earnings_assessment, QuantTools
from src.request_routing import mentioned_companies, plan_request
from src.research_workflow import scope_error
from src.response_contract import OutcomeTools, checked_answer, normalize_citations


def source(value, metric, year=2025, company="AMD", **extra):
    start, end = (
        ("2024-12-29", "2025-12-27") if year == 2025 else ("2023-12-31", "2024-12-28")
    )
    return dict(
        value=value,
        metric=metric,
        company=company,
        fiscal_year=year,
        period="FY",
        basis="annual",
        start=start,
        end=end,
        fiscal_start=start,
        fiscal_end=end,
        filed="2026-02-04",
        unit="USD",
        status="available",
        revision_basis="original_report",
        accounting_basis="US GAAP consolidated",
        accession=f"original-{year}",
        document_id=f"{company}-{year}",
        observation_id=f"{company}-{year}-{metric}",
        warnings=[],
        inputs=[],
        conflicting_comparatives=[],
        **extra,
    )


def test_scope_respects_exclusions_and_historical_temporal_context():
    question = "Compare AMD and Intel FY2024-to-FY2025 operating income. Do not include NVIDIA or Qualcomm."
    assert mentioned_companies(question) == ["AMD", "INTC"]
    assert not scope_error(
        question,
        ["AMD", "INTC"],
        [2024, 2025],
        {"AMD": [2024, 2025], "INTC": [2024, 2025]},
    )
    historical = "Using only NVIDIA's FY2025 annual filing, describe current demand at that fiscal year-end."
    assert not scope_error(historical, ["NVDA"], [2025], {"NVDA": [2025]})
    assert scope_error("NVIDIA latest demand today", ["NVDA"], [2025], {"NVDA": [2025]})
    assert scope_error("Compare AMD and NVIDIA", ["AMD"], [2025], {"AMD": [2025]})
    assert mentioned_companies("Excluding NVIDIA, compare AMD and Intel.") == [
        "AMD",
        "INTC",
    ]
    assert not scope_error(
        historical + " Do not use live news.", ["NVDA"], [2025], {"NVDA": [2025]}
    )


def test_mixed_requests_preserve_calculation_and_explanation_tasks():
    plan = plan_request(
        "Show AMD FY2025 Q2 operating cash flow for the quarter alone and six months; compare and explain why they differ"
    )
    assert plan.worker == "analysis_data" and plan.synthesize
    assert plan_request(
        "Calculate AMD operating cash flow divided by net income"
    ).required_calculations == ("ratio",)
    plan = plan_request(
        "Compare Qualcomm automotive and IoT revenue against handsets and consolidated revenue; explain diversification"
    )
    assert (
        set(plan.revenue_components) == {"automotive", "iot", "handsets"}
        and plan.synthesize
    )
    assert (
        plan_request("Rank absolute dollar changes in net income growth").earnings_order
        == "dollars"
    )
    assert (
        plan_request(
            "Which company had the largest percentage growth in GAAP net income? Retain their dollar figures."
        ).earnings_order
        == "percentage"
    )
    assert (
        plan_request(
            "Show AMD China revenue in EUR using my assumed rate of 1 EUR = 1.10 USD"
        ).worker
        == "research"
    )


def test_citation_refusal_ranges_and_positive_unknown_claims_are_distinct():
    registered = {"S1": {}, "F1": {}, "F2": {}, "C1": {}}
    assert (
        normalize_citations(
            "Source [S999] is not a supplied source. Actual fact [S1].", registered
        )
        == "Source unverified identifier S999 is not a supplied source. Actual fact [S1]."
    )
    answer, refs = checked_answer(
        "Inputs [F1–F2]; result [C1].", registered, lambda e: None
    )
    assert answer == "Inputs [F1][F2]; result [C1]." and refs == {"F1", "F2", "C1"}
    _, refs = checked_answer(
        "[S999] is not a supplied source. Doubled revenue [S999].",
        registered,
        lambda e: None,
    )
    assert "S999" in refs
    assert (
        "invalid_citation_range"
        in checked_answer("Sources [F1-F999] [S1]", registered, lambda e: None)[1]
    )


def test_outcome_rejects_inconsistent_completion_and_preserves_missing_outputs():
    tools = OutcomeTools(lambda name, args: {"delegated": name})
    with pytest.raises(ValueError):
        tools("report_outcome", {"status": "complete", "missing": ["Broadcom"]})
    tools("report_outcome", {"status": "partial", "missing": ["Broadcom comparison"]})
    assert tools.missing == ["Broadcom comparison"]
    assert tools("inspect_source", {}) == {"delegated": "inspect_source"}


def test_cash_conversion_is_independently_checked_and_rejects_invalid_basis():
    sources = {
        "F1": source(7709000000, "operating_cash_flow"),
        "F2": source(4335000000, "net_income"),
    }
    code = "results=[{'label':'cash conversion','kind':'ratio','inputs':['F1','F2'],'value':values['F1']/values['F2']}]"
    rows = validate_results(run_isolated(code, sources), sources)
    assert Decimal(rows[0]["value"]) == Decimal(7709) / Decimal(4335)
    assert rows[0]["unit"] == "multiple"
    for invalid in (
        {"value": 0},
        {"value": -10},
        {"company": "NVDA"},
        {"end": "2025-09-27"},
        {"metric": "revenue"},
    ):
        modified = {**sources, "F2": {**sources["F2"], **invalid}}
        with pytest.raises(ValueError):
            validate_results(run_isolated(code, modified), modified)


def test_component_scenario_retains_approved_assumption_and_checked_chain():
    sources = {
        "F1": source(44284000000, "revenue", company="QCOM"),
        "F2": source(
            3957000000,
            "revenue_component",
            company="QCOM",
            component="automotive",
            parent_metric="revenue",
            parent_scope="consolidated",
            provenance="filing_revenue_table",
        ),
    }
    scenario = {
        "kind": "component",
        "component": "automotive",
        "factor": "2",
        "origin": "user",
    }
    code = """part=values['F2']*2
total=values['F1']+values['F2']
results=[{'label':'scenario part','kind':'scenario_scale','inputs':['F2'],'value':part},
{'label':'scenario total','kind':'scenario_total','inputs':['F1','F2'],'value':total},
{'label':'scenario share','kind':'scenario_share','inputs':['C1','C2'],'value':part/total*100}]"""
    rows = validate_results(run_isolated(code, sources), sources, scenario=scenario)
    assert [Decimal(row["value"]) for row in rows[:2]] == [7914000000, 48241000000]
    assert rows[2]["source_ids"] == ["F1", "F2"] and rows[2]["scenario"] == scenario
    assert abs(
        Decimal(rows[2]["value"]) - Decimal(7914) / Decimal(48241) * 100
    ) < Decimal("1e-8")
    with pytest.raises(ValueError, match="approved user assumption"):
        validate_results(run_isolated(code, sources), sources)
    with pytest.raises(ValueError, match="independent recomputation"):
        validate_results(
            run_isolated(code, sources), sources, scenario={**scenario, "factor": "3"}
        )


def test_fx_has_distinct_units_and_cannot_be_invented_by_generated_code():
    sources = {"F1": source(34639000000, "revenue")}
    scenario = {"kind": "currency", "usd_per_eur": "1.10", "origin": "user"}
    code = "results=[{'label':'FX scenario','kind':'currency','inputs':['F1'],'value':values['F1']/1.10}]"
    row = validate_results(run_isolated(code, sources), sources, scenario=scenario)[0]
    assert Decimal(row["value"]) == 31490000000 and row["unit"] == "EUR"
    assert row["scenario"] == scenario
    with pytest.raises(ValueError):
        validate_results(
            run_isolated(code, sources),
            sources,
            scenario={**scenario, "origin": "model"},
        )


def test_dollar_assessment_includes_loss_baselines_and_has_correct_winner():
    sources = {
        "F1": source(29760, "net_income", 2024, "NVDA"),
        "F2": source(72880, "net_income", 2025, "NVDA"),
        "F3": source(-18756, "net_income", 2024, "INTC"),
        "F4": source(-267, "net_income", 2025, "INTC"),
    }
    sources = {sid: {**row, "source_id": sid} for sid, row in sources.items()}
    code = "results=[{'label':'NVIDIA dollar change','kind':'difference','inputs':['F2','F1'],'value':values['F2']-values['F1']},{'label':'Intel dollar change','kind':'difference','inputs':['F4','F3'],'value':values['F4']-values['F3']}]"
    rows = validate_results(run_isolated(code, sources), sources)
    assessment = earnings_assessment(rows, sources, order="dollars")
    assert assessment["winners"][0]["company"] == "NVDA"
    assert assessment["excluded"] == [] and len(assessment["ranking"]) == 2


def test_successful_input_values_do_not_complete_a_requested_ratio(tmp_path):
    from src.analysis_artifacts import ArtifactStore

    sources = {
        "F1": source(7709, "operating_cash_flow"),
        "F2": source(4335, "net_income"),
    }
    tools = QuantTools(
        sources,
        ArtifactStore(tmp_path),
        request={
            "companies": ["AMD"],
            "years": [2025],
            "required_calculations": ["ratio"],
        },
    )
    with pytest.raises(ValueError, match="requested checked operation"):
        tools(
            "run_analysis",
            {
                "code": "results=[{'label':'input only','kind':'value','inputs':['F1'],'value':values['F1']}]"
            },
        )
    assert tools.bundle is None


def test_fx_cannot_silently_convert_a_different_registered_metric(tmp_path):
    from src.analysis_artifacts import ArtifactStore

    inputs = {
        "F1": source(34639000000, "revenue"),
        "F2": source(7709000000, "operating_cash_flow"),
    }
    request = {
        "question": "Show AMD revenue in EUR",
        "companies": ["AMD"],
        "years": [2025],
        "scenario": {"kind": "currency", "usd_per_eur": "1.10", "origin": "user"},
        "required_calculations": ["currency"],
    }
    tools = QuantTools(inputs, ArtifactStore(tmp_path), request=request)
    with pytest.raises(ValueError, match="requested financial metric"):
        tools(
            "run_analysis",
            {
                "code": "results=[{'label':'wrong metric FX','kind':'currency','inputs':['F2'],'value':values['F2']/1.10}]"
            },
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("partial", [False, True])
async def test_mixed_graph_preserves_checked_context_and_explicit_completeness(
    tmp_path, monkeypatch, partial
):
    import src.quant_workflow as quant_module
    from src.analysis_artifacts import ArtifactStore
    from src.research_workflow import events

    monkeypatch.setattr(quant_module, "ArtifactStore", lambda: ArtifactStore(tmp_path))
    rows = [source(7709, "operating_cash_flow"), source(4335, "net_income")]
    passage = {
        "chunk_id": "p1",
        "text": "Management describes cash generation.",
        "company": "AMD",
        "fiscal_year": 2025,
        "document_id": "amd-2025",
        "section": "mda",
    }

    class Index:
        def coverage(self):
            return {"AMD": [2025]}

        def search(self, *args, **kwargs):
            return [passage]

        def inspect(self, identity):
            assert identity == "p1"
            return passage

    class Store:
        def query(self, companies, years, **filters):
            return {
                "observations": [
                    row for row in rows if row["metric"] in filters["metrics"]
                ],
                "gaps": [],
            }

    roles = []

    async def model(prompt, schema, handler, **kwargs):
        role = kwargs.get("agent", "Filings Research")
        roles.append(role)
        if role == "Financial Data":
            handler(
                "query_financials", {"metrics": ["operating_cash_flow", "net_income"]}
            )
            handler("report_outcome", {"status": "complete", "missing": []})
            yield {"type": "tool", "data": {"name": "query_financials"}}
            yield {"type": "token", "data": "Intermediate inputs [F1][F2]."}
        elif role == "Financial Analysis / Quant":
            assert "checked_calculations only" in prompt
            handler(
                "run_analysis",
                {
                    "code": "results=[{'label':'conversion','kind':'ratio','inputs':['F1','F2'],'value':values['F1']/values['F2']}]"
                },
            )
            handler(
                "report_outcome",
                {
                    "status": "complete",
                    "missing": [],
                },
            )
            yield {"type": "token", "data": "Intermediate Quant result [C1]."}
        else:
            assert "cash_conversion" in prompt and "Checked financial context" in prompt
            assert '"value": "' in prompt and '"source_id": "C1"' in prompt
            handler("inspect_source", {"source_id": "S1"})
            handler(
                "report_outcome",
                {
                    "status": "partial" if partial else "complete",
                    "missing": ["Management bridge is unavailable"] if partial else [],
                },
            )
            yield {
                "type": "token",
                "data": "Research combines the checked ratio [C1] and filing explanation [S1].",
            }

    result = [
        event
        async for event in events(
            Index(),
            "Calculate AMD FY2025 operating cash flow divided by net income and explain why cash conversion matters",
            ["AMD"],
            [2025],
            financials=Store(),
            model_stream=model,
        )
    ]
    assert roles == ["Financial Data", "Financial Analysis / Quant", "Filings Research"]
    assert "Intermediate" not in "".join(
        e["data"] for e in result if e["type"] == "token"
    )
    assert {
        s["source_id"] for e in result if e["type"] == "sources" for s in e["data"]
    } == {"C1", "S1"}
    assert result[-1]["data"]["status"] == ("partial" if partial else "completed")
    if partial:
        assert result[-1]["data"]["missing_outputs"] == [
            "Management bridge is unavailable"
        ]


def test_invalid_ratio_year_preserves_other_checked_calculations(tmp_path):
    from src.analysis_artifacts import ArtifactStore
    inputs = {"F1": source(100, "operating_cash_flow"), "F2": source(20, "net_income"), "F3": source(-100, "net_income", 2024)}
    tools = QuantTools(inputs, ArtifactStore(tmp_path), request={"companies": ["AMD"], "years": [2024, 2025], "required_calculations": ["ratio"]})
    result = tools("run_analysis", {"code": "results=[{'label':'valid conversion','kind':'ratio','inputs':['F1','F2'],'value':values['F1']/values['F2']},{'label':'signed dollar change','kind':'difference','inputs':['F2','F3'],'value':values['F2']-values['F3']}]"})
    assert len(result["calculations"]) == 2 and tools.bundle_id
    assert tools.ratio_eligible == {("AMD", 2025)} and "FY2024" in tools.ratio_gaps[0]


@pytest.mark.asyncio
async def test_intermediate_quant_cannot_hide_missing_calculation(tmp_path):
    from src.analysis_artifacts import ArtifactStore
    from src.quant_workflow import quant_turn
    inputs = {"F1": source(100, "operating_cash_flow"), "F2": source(20, "net_income")}
    inputs = {sid: {**row, "source_id": sid} for sid, row in inputs.items()}
    async def model(prompt, schema, handler, **kwargs):
        handler("run_analysis", {"code": "results=[{'label':'conversion','kind':'ratio','inputs':['F1','F2'],'value':values['F1']/values['F2']}]"})
        handler("report_outcome", {"status": "partial", "missing": ["Requested year-over-year calculation remains unsupported"]})
        yield {"type": "token", "data": "Verified single-period ratio [C1]."}
    result = await quant_turn({"financial_sources": inputs, "companies": ["AMD"], "years": [2025], "question": "Calculate cash conversion", "worker_output": "checked_calculations"}, lambda e: None, model_stream=model, artifacts=ArtifactStore(tmp_path), emit_answer=False)
    assert result["partial"] and result["bundle_id"] and result["missing_outputs"] == ["Requested year-over-year calculation remains unsupported"]
