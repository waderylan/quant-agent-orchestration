"""Protect ordinary queries, source extraction, bounded follow-up, and scope repair."""

import pytest

from src.analysis_artifacts import ArtifactStore
from src.filing_financials import qct_revenue_row
from src.request_routing import plan_request, mentioned_years
from src.research_workflow import events, scope_error

TABLE = """QCT revenue streams were as follows (in millions):

             2025       2024       2023
Handsets (1)  27,793     24,863     22,570
Automotive (2) 3,957      2,910      1,872
IoT (internet of things) (3) 6,617  5,423  5,940
Total QCT revenues 38,367 33,196 30,382
"""


@pytest.mark.parametrize(
    "question",
    [
        "What share of QCT revenue was automotive in FY2025?",
        "Show Qualcomm adjusted automotive revenue",
    ],
)
def test_component_routing_never_silently_changes_requested_definition(question):
    assert plan_request(question).worker == "research"


def test_single_year_earnings_level_is_not_two_year_growth_ranking():
    assert not plan_request(
        "Which company had the highest net income in FY2025?"
    ).earnings_ranking


def test_presentation_units_do_not_change_consolidated_revenue_capability():
    for units in ("in exact USD", "in millions", "in actual dollars"):
        assert (
            plan_request("Show AMD FY2025 consolidated GAAP revenue " + units).worker
            == "data"
        )
    assert (
        plan_request("Show NVIDIA FY2026 Q2-only revenue in exact USD").worker == "data"
    )


@pytest.mark.parametrize(
    "question,worker,component,share",
    [
        (
            "How much of qualcomm's revenue in fy2025 was from automotive?",
            "data",
            "automotive",
            True,
        ),
        ("What percentage of Qualcomm FY2025 revenue was IoT?", "data", "iot", True),
        ("Show Qualcomm FY2024 handsets revenue", "data", "handsets", False),
        ("Why did Qualcomm automotive revenue grow?", "research", None, False),
        ("How much was NVIDIA data center revenue?", "research", None, False),
        ("How much Qualcomm revenue was from licensing?", "research", None, False),
        ("Show Qualcomm royalty revenue", "research", None, False),
        ("How much revenue did AMD report in China?", "research", None, False),
        ("Show AMD adjusted EBITDA", "research", None, False),
        (
            "Show Qualcomm consolidated GAAP revenue then compare the two years numbers",
            "analysis_data",
            None,
            False,
        ),
        ("Calculate gross margin", "analysis_data", None, False),
        ("Show AMD Q2 operating cash flow", "analysis_data", None, False),
    ],
)
def test_routes_match_declared_financial_capabilities(
    question, worker, component, share
):
    plan = plan_request(question)
    assert (plan.worker, plan.revenue_component, plan.revenue_share) == (
        worker,
        component,
        share,
    )


def test_earnings_alias_and_scope_correction_keep_company_and_years_explicit():
    question = "which company had the largest earnings growth from 24 to 25? what is the number"
    assert plan_request(question).earnings_ranking
    assert mentioned_years(question) == {2024, 2025}
    assert "requested years" in scope_error(
        question, ["AMD"], [2025], {"AMD": [2024, 2025]}
    )
    error = scope_error(
        "Show Qualcomm FY2024 and FY2025 revenue",
        ["AMD"],
        [2024, 2025],
        {"AMD": [2024, 2025]},
    )
    assert "Selected companies: AMD" in error and "Qualcomm (QCOM)" in error


def test_table_parser_binds_original_year_column_unit_and_wrapped_title():
    row = qct_revenue_row(TABLE, 2025, "automotive")
    assert row["value"] == 3_957_000_000
    assert TABLE[row["start"] : row["end"]].strip().startswith("Automotive")
    assert "in millions" in row["quote"] and row["column_years"] == [2025, 2024, 2023]
    wrapped = TABLE.replace("QCT revenue streams", "QCT\n revenue streams").replace(
        "millions", "mi    llions"
    )
    assert qct_revenue_row(wrapped, 2024, "iot")["value"] == 5_423_000_000


@pytest.mark.parametrize(
    "body",
    [
        TABLE.replace("in millions", "in thousands"),
        TABLE.replace("2025       2024       2023", "2025 2024 Change"),
        TABLE.replace("2025       2024       2023", "2025 2024 2025 2024"),
        TABLE + TABLE,
        TABLE.replace("3,957      2,910      1,872", "3,957 2,910"),
    ],
)
def test_ambiguous_or_incompatible_tables_cannot_supply_arithmetic_inputs(body):
    with pytest.raises(ValueError):
        qct_revenue_row(body, 2025, "automotive")


def total_observation():
    return {
        "company": "QCOM",
        "fiscal_year": 2025,
        "period": "FY",
        "basis": "annual",
        "start": "2024-09-30",
        "end": "2025-09-28",
        "fiscal_start": "2024-09-30",
        "fiscal_end": "2025-09-28",
        "filed": "2025-11-05",
        "unit": "USD",
        "metric": "revenue",
        "value": 44_284_000_000,
        "status": "available",
        "kind": "financial_observation",
        "revision_basis": "original_report",
        "accounting_basis": "US GAAP consolidated",
        "accession": "original-2025",
        "document_id": "qcom-original",
        "form": "10-K",
        "version": "original",
        "canonical_url": "https://example.org/filing",
        "warnings": [],
        "inputs": [],
        "observation_id": "total-2025",
        "snapshot_sha256": "0" * 64,
    }


class FilingIndex:
    def __init__(self):
        self.documents = {
            "qcom-original": {
                **total_observation(),
                "source_date": "2025-11-05",
                "period_end": "2025-09-28",
                "extraction": {"text_sha256": "fixture-hash"},
            }
        }

    def coverage(self):
        return {"QCOM": [2025]}

    def text(self, doc):
        return TABLE

    def search(self, *args, **kwargs):
        return [self.inspect("row")]

    def inspect(self, identity):
        assert identity == "row"
        return {
            **self.documents["qcom-original"],
            "chunk_id": "row",
            "start": 0,
            "end": len(TABLE),
            "text": TABLE,
            "section": "other",
            "page": 71,
        }


@pytest.mark.asyncio
async def test_real_tool_graph_hands_missing_component_to_research_then_checked_quant(
    tmp_path, monkeypatch
):
    import src.quant_workflow as quant_module

    monkeypatch.setattr(quant_module, "ArtifactStore", lambda: ArtifactStore(tmp_path))

    class Store:
        def query(self, *args, **kwargs):
            return {"observations": [total_observation()], "gaps": []}

    roles = []

    async def model(prompt, schema, handler, **kwargs):
        roles.append(kwargs["agent"])
        if kwargs["agent"] == "Filings Research":
            source = handler("extract_revenue_component", {"source_id": "S1"})
            assert source["value"] == 3_957_000_000
            yield {"type": "tool", "data": {"name": "extract_revenue_component"}}
            yield {"type": "evidence", "data": source}
            pytest.fail(
                "Verified inputs must end this phase without awaiting unused prose"
            )
            yield {"type": "token", "data": "Hidden intermediate response"}
        else:
            handler(
                "run_analysis",
                {
                    "code": "results=[{'label':'automotive share','kind':'share','inputs':['F2','F1'],'value':values['F2']/values['F1']*100}]"
                },
            )
            yield {"type": "tool", "data": {"name": "run_analysis"}}
            yield {
                "type": "token",
                "data": "Automotive share was 8.94% [C1]; amount [F2].",
            }

    stream = [
        e
        async for e in events(
            FilingIndex(),
            "How much of qualcomm's revenue in fy2025 was from automotive?",
            ["QCOM"],
            [2025],
            financials=Store(),
            model_stream=model,
        )
    ]
    assert roles == ["Filings Research", "Financial Analysis / Quant"]
    assert stream[-1]["data"]["status"] == "completed"
    assert "Hidden" not in "".join(e["data"] for e in stream if e["type"] == "token")
    bundle_id = next(e["data"]["bundle_id"] for e in stream if e["type"] == "artifacts")
    frozen = ArtifactStore(tmp_path).calculation(bundle_id, "C1")["input_sources"][0]
    assert frozen["filing_evidence"]["row_label"] == "Automotive"
    assert "snapshot_url" not in frozen


@pytest.mark.asyncio
async def test_empty_structured_store_retrieves_filing_evidence_and_marks_partial():
    class EmptyStore:
        def query(self, *args, **kwargs):
            return {"observations": [], "gaps": [{"metric": "revenue"}]}

    async def model(prompt, schema, handler):
        assert "Structured input limitation" in prompt
        handler("inspect_source", {"source_id": "S1"})
        yield {
            "type": "token",
            "data": "A filing table is available [S1]; structured analysis is unavailable.",
        }

    result = [
        e
        async for e in events(
            FilingIndex(),
            "Show Qualcomm revenue",
            ["QCOM"],
            [2025],
            financials=EmptyStore(),
            model_stream=model,
        )
    ]
    assert result[-1]["data"]["status"] == "partial"
    assert not any(e["type"] == "artifacts" for e in result)
