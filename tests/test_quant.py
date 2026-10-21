"""Protect generated execution, independent financial checks, lineage, and artifacts."""

import csv
import io
import json
from decimal import Decimal

import pytest

from src.analysis_artifacts import ArtifactStore
from src.quant_analysis import run_isolated, validate_results
from src.quant_workflow import QuantTools


def observation(value, metric="revenue", year=2025, **overrides):
    start, end = (
        ("2023-12-31", "2024-12-28") if year == 2024 else ("2024-12-29", "2025-12-27")
    )
    return {
        "value": value,
        "metric": metric,
        "company": "AMD",
        "fiscal_year": year,
        "period": "FY",
        "basis": "annual",
        "start": start,
        "end": end,
        "fiscal_start": start,
        "fiscal_end": end,
        "filed": "2026-02-04",
        "unit": "USD",
        "status": "available",
        "revision_basis": "original_report",
        "accounting_basis": "US GAAP consolidated",
        "warnings": [],
        "inputs": [],
        "conflicting_comparatives": [],
        "observation_id": f"{metric}-{year}",
        "accession": f"original-{year}",
        "document_id": f"amd-original-{year}",
        "snapshot_sha256": "0" * 64,
        "kind": "financial_observation",
        **overrides,
    }


@pytest.mark.asyncio
async def test_quant_can_cite_excluded_conflicts_without_calculating_them(tmp_path):
    from src.quant_workflow import quant_turn
    eligible = {"F1": observation(100, year=2024)}
    disputed = {**observation(150), "source_id": "F2", "status": "conflicting"}
    async def model(prompt, schema, handler, **kwargs):
        handler("report_outcome", {"status": "partial", "missing": ["FY2025 conflict requires resolution"]})
        yield {"type": "token", "data": "FY2025 observation exists but is conflicting [F2]; growth is excluded."}
    result = await quant_turn({"question": "Calculate AMD revenue growth", "companies": ["AMD"], "years": [2024, 2025], "financial_sources": eligible, "analysis_sources": {"F2": disputed}, "excluded_financial_inputs": [{"source_id": "F2", "status": "conflicting"}]}, lambda event: None, model_stream=model, artifacts=ArtifactStore(tmp_path))
    assert result["partial"] and not result.get("error") and not result["calculations"]
    assert result["analysis_sources"]["F2"]["status"] == "conflicting"
    assert result["reported_missing_outputs"] == ["FY2025 conflict requires resolution"]


def test_parent_net_margin_preserves_signed_income_and_positive_revenue():
    sources = {"F1": observation(-20, "net_income"), "F2": observation(100)}
    code = "results = [{'label': 'Parent net margin', 'kind': 'margin', 'inputs': ['F1', 'F2'], 'value': values['F1'] / values['F2'] * 100}]"
    result = validate_results(run_isolated(code, sources), sources)
    assert result[0]["value"] == "-20.0" and result[0]["metric"] == "net_margin"
    assert result[0]["source_ids"] == ["F1", "F2"]
    sources["F2"]["value"] = 0
    with pytest.raises(ValueError, match="positive"):
        validate_results(run_isolated("results = [{'label': 'Invalid', 'kind': 'margin', 'inputs': ['F1', 'F2'], 'value': 0 * values['F1'] + values['F2']}]", sources), sources)


@pytest.fixture
def sources():
    rows = {
        "F1": observation(100, year=2024),
        "F2": observation(150),
        "F3": observation(40, "gross_profit", 2024),
        "F4": observation(75, "gross_profit"),
        "F5": observation(-15, "operating_income"),
        "F6": observation(20, "operating_cash_flow", 2024),
        "F7": observation(30, "operating_cash_flow"),
    }
    return {sid: {**row, "source_id": sid} for sid, row in rows.items()}


GROWTH = "results=[{'label':'growth','kind':'growth','inputs':['F2','F1'],'value':(values['F2']/values['F1']-1)*100}]"


def test_generated_growth_margins_cash_flow_and_percentage_point_lineage(sources):
    code = """
growth = (values['F2'] / values['F1'] - 1) * 100
old_margin = values['F3'] / values['F1'] * 100
new_margin = values['F4'] / values['F2'] * 100
change = new_margin - old_margin
loss_margin = values['F5'] / values['F2'] * 100
cash_growth = (values['F7'] / values['F6'] - 1) * 100
results = [
 {'label':'Growth','kind':'growth','inputs':['F2','F1'],'value':growth},
 {'label':'Old margin','kind':'margin','inputs':['F3','F1'],'value':old_margin},
 {'label':'New margin','kind':'margin','inputs':['F4','F2'],'value':new_margin},
 {'label':'Margin change','kind':'difference','inputs':['C3','C2'],'value':change},
 {'label':'Loss margin','kind':'margin','inputs':['F5','F2'],'value':loss_margin},
 {'label':'Cash growth','kind':'growth','inputs':['F7','F6'],'value':cash_growth}
]
"""
    rows = validate_results(run_isolated(code, sources), sources)
    assert [Decimal(r["value"]) for r in rows] == [50, 40, 50, 10, -10, 50]
    assert rows[3]["unit"] == "percentage_points"
    assert rows[3]["source_ids"] == ["F1", "F2", "F3", "F4"]


@pytest.mark.parametrize(
    "code",
    [
        "import os",
        "x=__import__('os')",
        "x=values.__class__",
        "while True: pass",
        "x=[i for i in [1]]",
        "x=values['F1'] ** 100000000",
        "x=[1]*100000000",
        "values['F1']=999",
        "x=values['F99']",
        "x=1e100",
    ],
)
def test_execution_rejects_escape_resource_and_missing_input_attempts(sources, code):
    with pytest.raises(ValueError):
        run_isolated(code, sources)


@pytest.mark.parametrize(
    "expression,reason",
    [
        ("50", "lineage"),
        ("(values['F7']/values['F6']-1)*100", "lineage"),
        ("values['F2']/values['F1']*100", "recomputation"),
    ],
)
def test_independent_validation_rejects_coincidental_values_and_wrong_formulas(
    sources, expression, reason
):
    code = GROWTH.replace("(values['F2']/values['F1']-1)*100", expression)
    with pytest.raises(ValueError, match=reason):
        validate_results(run_isolated(code, sources), sources)


@pytest.mark.parametrize(
    "change",
    [
        {"company": "NVDA"},
        {"unit": "EUR"},
        {"basis": "quarter"},
        {"start": "2024-01-01"},
        {"revision_basis": "latest"},
        {"accounting_basis": "adjusted"},
        {
            "conflicting_comparatives": [
                {"accession": "revised", "filed": "2026-02-03", "value": 151}
            ]
        },
    ],
)
def test_incompatible_comparisons_are_rejected_before_publication(sources, change):
    sources["F2"].update(change)
    with pytest.raises(ValueError):
        validate_results(run_isolated(GROWTH, sources), sources)


def test_zero_denominator_and_actual_child_deadline_fail_explicitly(sources):
    sources["F1"]["value"] = 0
    with pytest.raises(ValueError, match="Zero denominator"):
        run_isolated(GROWTH, sources)
    with pytest.raises(ValueError, match="timed out"):
        run_isolated(GROWTH, sources, timeout=0.001)


def test_nested_result_metadata_cannot_expand_child_output(sources):
    code = "a=[1]\n" + "a=[a,a]\n" * 10 + GROWTH.replace("'growth','kind'", "a,'kind'")
    with pytest.raises(ValueError, match="scalar"):
        run_isolated(code, sources)


@pytest.mark.parametrize(
    "period,end,previous,previous_end,basis",
    [
        ("Q2", "2025-06-28", "Q1", "2025-03-29", "ytd"),
        ("Q3", "2025-09-27", "Q2", "2025-06-28", "ytd"),
        ("FY", "2025-12-27", "Q3", "2025-09-27", "annual"),
    ],
)
def test_cash_flow_quarter_derivations_require_adjacent_compatible_cumulative_inputs(
    period, end, previous, previous_end, basis
):
    sources = {
        "F1": observation(
            100, "operating_cash_flow", period=period, basis=basis, end=end
        ),
        "F2": observation(
            60, "operating_cash_flow", period=previous, basis="ytd", end=previous_end
        ),
    }
    code = "results=[{'label':'Quarter cash','kind':'quarter','inputs':['F1','F2'],'value':values['F1']-values['F2']}]"
    row = validate_results(run_isolated(code, sources), sources)[0]
    assert row["value"] == "40" and row["basis"] == "quarter"
    assert row["start"] > previous_end and row["end"] == end
    sources["F2"]["period"] = "Q0"
    with pytest.raises(ValueError, match="adjacent"):
        validate_results(run_isolated(code, sources), sources)


def test_53_week_comparison_retains_qualification(sources):
    sources["F1"].update(
        company="QCOM",
        start="2023-09-25",
        end="2024-09-29",
        warnings=["53-week FY2024; 52-week FY2025"],
    )
    sources["F2"].update(company="QCOM", start="2024-09-30", end="2025-09-28")
    assert validate_results(run_isolated(GROWTH, sources), sources)[0]["warnings"] == [
        "53-week FY2024; 52-week FY2025"
    ]


def test_q4_margin_uses_derived_numerator_and_denominator():
    sources = {
        "F1": observation(1000),
        "F2": observation(700, period="Q3", basis="ytd", end="2025-09-27"),
        "F3": observation(400, "gross_profit"),
        "F4": observation(
            280, "gross_profit", period="Q3", basis="ytd", end="2025-09-27"
        ),
    }
    code = """
revenue = values['F1'] - values['F2']
profit = values['F3'] - values['F4']
results = [
 {'label':'Q4 revenue','kind':'quarter','inputs':['F1','F2'],'value':revenue},
 {'label':'Q4 profit','kind':'quarter','inputs':['F3','F4'],'value':profit},
 {'label':'Q4 margin','kind':'margin','inputs':['C2','C1'],'value':profit/revenue*100}
]
"""
    rows = validate_results(run_isolated(code, sources), sources)
    assert [r["value"] for r in rows] == ["300", "120", "40.0"]
    assert rows[-1]["period"] == "Q4" and rows[-1]["start"] == "2025-09-28"
    invalid = code.replace("['C2','C1']", "['C2','F1']").replace(
        "profit/revenue*100", "profit/values['F1']*100"
    )
    with pytest.raises(ValueError, match="same fiscal interval"):
        validate_results(run_isolated(invalid, sources), sources)


def test_verified_artifacts_replay_and_tamper_detection(sources, tmp_path):
    tools = QuantTools(sources, ArtifactStore(tmp_path))
    tools("run_analysis", {"code": GROWTH})
    identity = tools.bundle_id
    bundle = tools.artifacts.load(identity)
    assert bundle["calculations"] == validate_results(
        run_isolated(bundle["code"], bundle["sources"]), bundle["sources"]
    )
    assert (
        bundle["chart_series"][0]["rows"][0]["value"]
        == bundle["calculations"][0]["value"]
    )
    table = list(
        csv.DictReader(
            io.StringIO(tools.artifacts.file(identity, "table.csv").read_text())
        )
    )
    assert table[0]["value"] == "50.0" and table[0]["source_ids"] == "F1 F2"
    assert (
        tools.artifacts.file(identity, "chart.png")
        .read_bytes()
        .startswith(b"\x89PNG\r\n\x1a\n")
    )
    assert (
        tools("inspect_calculation", {"source_id": "C1"})["formula"]
        == "(F2 / F1 - 1) * 100"
    )
    sources["F2"]["value"] = 999
    inspected = tools.artifacts.calculation(identity, "C1")
    assert inspected["input_sources"][0]["value"] == 150
    assert "/observations/F2" in inspected["input_sources"][0]["inspection_url"]
    (tmp_path / identity / "chart.png").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        tools.artifacts.file(identity, "chart.png")
    with pytest.raises(KeyError):
        tools.artifacts.load("../other")
    bundle["calculations"][0]["value"] = "999"
    (tmp_path / identity / "bundle.json").write_text(json.dumps(bundle))
    with pytest.raises(ValueError, match="checksum"):
        tools.artifacts.load(identity)


@pytest.mark.asyncio
async def test_graph_hands_data_to_quant_without_streaming_intermediate_answer(
    tmp_path, monkeypatch
):
    import src.quant_workflow as quant_module
    from src.research_workflow import events

    raw = [observation(100, year=2024), observation(150)]

    class Index:
        def coverage(self):
            return {"AMD": [2024, 2025]}

    class Store:
        def query(self, companies, years, **filters):
            return {
                "observations": [
                    r
                    for r in raw
                    if r["fiscal_year"] in years and r["metric"] in filters["metrics"]
                ],
                "gaps": [],
            }

    monkeypatch.setattr(quant_module, "ArtifactStore", lambda: ArtifactStore(tmp_path))
    roles = []

    async def model(prompt, schema, handler, **kwargs):
        role = kwargs["agent"]
        roles.append(role)
        handler("report_outcome", {"status": "complete", "missing": []})
        if role == "Financial Data":
            handler("query_financials", {"metrics": ["revenue"]})
            yield {"type": "tool", "data": {"name": "query_financials"}}
            yield {"type": "token", "data": "Intermediate figures [F1] [F2]."}
        else:
            handler("run_analysis", {"code": GROWTH})
            yield {"type": "tool", "data": {"name": "run_analysis"}}
            yield {"type": "token", "data": "Revenue growth was 50% [C1]."}

    result = [
        e
        async for e in events(
            Index(),
            "Calculate AMD FY2024 to FY2025 revenue growth",
            ["AMD"],
            [2024, 2025],
            financials=Store(),
            model_stream=model,
        )
    ]
    assert roles == ["Financial Data", "Financial Analysis / Quant"]
    assert (
        "".join(e["data"] for e in result if e["type"] == "token")
        == "Revenue growth was 50% [C1]."
    )
    assert result[-1]["data"]["status"] == "completed"
    assert any(e["type"] == "artifacts" for e in result)
    roles.clear()

    async def failed_data(*args, **kwargs):
        roles.append(kwargs["agent"])
        yield {"type": "token", "data": "Unverified inputs [F99]."}

    failed = [
        e
        async for e in events(
            Index(),
            "Calculate AMD FY2024 to FY2025 revenue growth",
            ["AMD"],
            [2024, 2025],
            financials=Store(),
            model_stream=failed_data,
        )
    ]
    assert roles == ["Financial Data"]
    assert failed[-1]["data"]["status"] == "failed"
    assert not any(e["type"] == "artifacts" for e in failed)


def component_sources():
    total = observation(1000)
    component = observation(
        80,
        "revenue_component",
        component="automotive",
        provenance="filing_revenue_table",
        parent_metric="revenue",
        parent_scope="consolidated",
    )
    return {"F1": {**total, "source_id": "F1"}, "F2": {**component, "source_id": "F2"}}


SHARE = "results=[{'label':'share','kind':'share','inputs':['F2','F1'],'value':values['F2']/values['F1']*100}]"


def test_share_recomputes_verified_component_and_preserves_executed_lineage():
    inputs = component_sources()
    row = validate_results(run_isolated(SHARE, inputs), inputs)[0]
    assert row["value"] == "8.00" and row["metric"] == "automotive_revenue_share"
    assert row["source_ids"] == ["F1", "F2"]


def test_verified_qct_total_share_uses_consolidated_denominator():
    inputs = component_sources()
    for source in inputs.values():
        source["company"] = "QCOM"
    inputs["F2"].update(metric="qct_revenue", component="qct_total")
    row = validate_results(run_isolated(SHARE, inputs), inputs)[0]
    assert row["value"] == "8.00" and row["metric"] == "qct_consolidated_revenue_share"
    inputs["F1"].update(metric="qct_revenue", provenance="filing_revenue_table")
    with pytest.raises(ValueError):
        validate_results(run_isolated(SHARE, inputs), inputs)


@pytest.mark.parametrize(
    "changes",
    [
        {"accession": "different-filing"},
        {"provenance": "model_claim"},
        {"parent_scope": "QCT"},
        {"metric": "operating_income"},
        {"value": -1},
        {"value": 1001},
        {"start": "2025-01-01"},
        {"revision_basis": "latest_restatement"},
        {"company": "QCOM"},
    ],
)
def test_share_rejects_unverified_scope_period_revision_or_invalid_part(changes):
    inputs = component_sources()
    inputs["F2"].update(changes)
    with pytest.raises(ValueError):
        validate_results(run_isolated(SHARE, inputs), inputs)


def test_ranking_checks_every_eligible_company_and_excludes_loss_baseline():
    from src.quant_workflow import earnings_assessment

    inputs = {
        "F1": observation(100, "net_income", 2024),
        "F2": observation(260, "net_income"),
        "F3": observation(100, "net_income", 2024, company="NVDA"),
        "F4": observation(240, "net_income", company="NVDA"),
        "F5": observation(-100, "net_income", 2024, company="INTC"),
        "F6": observation(-2, "net_income", company="INTC"),
    }
    inputs = {sid: {**source, "source_id": sid} for sid, source in inputs.items()}
    code = """results=[
{'label':'AMD','kind':'growth','inputs':['F2','F1'],'value':(values['F2']/values['F1']-1)*100},
{'label':'NVDA','kind':'growth','inputs':['F4','F3'],'value':(values['F4']/values['F3']-1)*100},
{'label':'Intel previous','kind':'value','inputs':['F5'],'value':values['F5']},
{'label':'Intel current','kind':'value','inputs':['F6'],'value':values['F6']}]
"""
    rows = validate_results(run_isolated(code, inputs), inputs)
    assessment = earnings_assessment(rows, inputs)
    assert assessment["winners"][0]["company"] == "AMD"
    assert assessment["excluded"][0]["company"] == "INTC"
    with pytest.raises(ValueError, match="every positive-baseline"):
        earnings_assessment(rows[1:], inputs)
    with pytest.raises(ValueError, match="both reported"):
        earnings_assessment(rows[:-1], inputs)
