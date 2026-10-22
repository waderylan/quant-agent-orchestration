"""Automatic risk checks preserve filing decisions and shared MCP provenance."""

import copy
import json

import pytest

from src.live_mcp import LiveGateway
from src.risk_live import RiskLiveChecks
from src.risk_summary import RiskTools, risk_turn
from tests.test_risk_summary import RiskIndex


def test_subject_navigation_returns_exact_spans_without_reclassifying():
    risks = RiskTools(RiskIndex(), ["AMD"], [2024, 2025])
    risks.prepare()
    result = risks("risk_pairs", {"comparison": "AMD:2024:2025", "query": "export restrictions"})
    assert result["total"] == 1 and result["pairs"][0]["alignment"] == "exact"
    assert "Export restrictions" in result["pairs"][0]["after_text"] and not risks.changes


class FrozenRiskGateway(LiveGateway):
    def __init__(self, *, rows=None, error=None):
        super().__init__(mode="frozen")
        self.rows = rows if rows is not None else [{"url": "https://www.amd.com/en/newsroom/press-releases/fixture.html", "title": "AMD export restriction update", "content": "Synthetic fixture: AMD reports export restrictions affected sales after its filing.", "published_date": "2026-03-10"}]
        self.error, self.calls = error, []

    async def fetch(self, tool, args, **kwargs):
        self.calls.append((tool, args, kwargs["agent"]))
        if self.error:
            return {"error": self.error}
        self.store(tool, args, {"structuredContent": {"results": self.rows}}, {"server": {"name": "tavily-mcp"}})
        return await super().fetch(tool, args, **kwargs)


def setup(monkeypatch, *, question="Compare AMD risks", **gateway_args):
    monkeypatch.delenv("RISK_LIVE_CHECK", raising=False)
    index = RiskIndex()
    for year in (2024, 2025):
        index.documents[str(year)]["source_date"] = f"{year + 1}-02-15"
    risks = RiskTools(index, ["AMD"], [2024, 2025])
    risks.prepare()
    state = dict(question=question, companies=["AMD"], years=[2024, 2025])
    gateway = FrozenRiskGateway(**gateway_args)
    return state, risks, gateway


def finding(risks, classification="changed"):
    comparison = next(iter(risks.comparisons.values()))
    pair = next(p for p in comparison["pairs"] if p["alignment"] == "exact")
    return dict(classification=classification, before=pair["before"], after=pair["after"], rationale="The export restriction warning remains material across both full inventories.")


@pytest.mark.parametrize("classification", ["added", "changed", "removed", "relocated", "unchanged"])
def test_all_registered_kinds_use_shared_search_after_the_actual_filing(monkeypatch, classification):
    state, risks, gateway = setup(monkeypatch)
    live = RiskLiveChecks(state, risks, gateway)
    change = finding(risks, classification)
    original = copy.deepcopy(change)
    result = live.check(change, "AMD export restrictions sales")
    assert change == original and result["source_ids"] == ["W1"]
    tool, arguments, agent = gateway.calls[0]
    assert (tool, agent) == ("tavily_search", "Risk Summary")
    assert arguments["start_date"] == "2026-02-16" and "time_range" not in arguments
    assert result["filed"] == "2026-02-15" and result["fiscal_end"] == "2025-12-31"
    assert live.web.events[0]["data"]["server"] == "tavily-mcp"
    assert live.web.sources["W1"]["source_tier"] == "official"
    live.check(change, "another query cannot repeat the same pair")
    assert len(gateway.calls) == 1


@pytest.mark.parametrize("question", ["Compare AMD risks; no web", "Use only the filings to compare AMD risks", "Compare AMD risks without news", "Compare AMD risks; don't search", "Compare AMD risks using the filings only", "Compare AMD risks using only the original annual filings", "Compare AMD risks; stick to the selected filings", "Compare AMD risks; don't browse"])
def test_explicit_no_web_prevents_even_cached_acquisition(monkeypatch, question):
    state, risks, gateway = setup(monkeypatch, question=question)
    live = RiskLiveChecks(state, risks, gateway)
    assert live.check(finding(risks))["status"] == "skipped"
    assert not gateway.calls and not live.missing


def test_dates_tiers_and_empty_evidence_are_not_a_claim_of_no_event(monkeypatch):
    rows = [
        {"url": "https://reporter.example/amd", "content": "Synthetic AMD event reported March 2026.", "published_date": "2026-03-10"},
        {"url": "https://www.amd.com/old", "content": "Synthetic old AMD report.", "published_date": "2026-02-15"},
        {"url": "https://www.amd.com/undated", "content": "Synthetic undated AMD report."},
    ]
    state, risks, gateway = setup(monkeypatch, rows=rows)
    result = RiskLiveChecks(state, risks, gateway).check(finding(risks))
    assert result["source_ids"] == ["W1"] and result["sources"][0]["source_tier"] == "third_party"
    assert "not proof" in result["use"]
    state, risks, gateway = setup(monkeypatch, rows=[])
    live = RiskLiveChecks(state, risks, gateway)
    assert live.check(finding(risks))["status"] == "no_dated_evidence" and not live.missing


def test_distinct_subjects_on_the_same_full_sections_each_receive_a_check(monkeypatch):
    state, risks, gateway = setup(monkeypatch)
    live = RiskLiveChecks(state, risks, gateway)
    change = finding(risks)
    live.check(change, "export restrictions")
    live.check({**change, "rationale": "Customer concentration language adds a distinct new exposure in the same section pair."}, "customer concentration")
    assert len(gateway.calls) == 2


@pytest.mark.asyncio
async def test_worker_retains_filing_classifications_with_live_on_off_or_failed(monkeypatch):
    state, risks, gateway = setup(monkeypatch)
    answers = []
    async def model(prompt, schemas, handler, **kwargs):
        change = finding(handler, "relocated")
        result = handler("record_risk_change", {**change, "live_query": "AMD export restriction sales"})
        check = result["post_filing_check"]
        handler("report_outcome", {"status": "complete", "missing": []})
        text = f"Warning wording relocates [{change['before']}][{change['after']}]."
        if check["status"] == "results":
            text += f" AMD reported an export restriction impact [W1]."
        answers.append(text)
        yield {"type": "token", "data": text}
    results = []
    for enabled, error in ((True, None), (False, None), (True, "timeout")):
        emitted = []
        result = await risk_turn(risks.index, {**state, "risk_live_check": enabled}, emitted.append, model_stream=model, gateway=FrozenRiskGateway(error=error))
        results.append(result)
        assert result["risk_changes"] == [finding(risks, "relocated")]
    assert results[0]["risk_sources"] == results[1]["risk_sources"] == results[2]["risk_sources"]
    assert not results[0]["partial"] and not results[1]["partial"]
    assert results[2]["partial"] and "timeout" in json.dumps(results[2]["missing_outputs"])
    assert results[0]["live_sources"]["W1"]["agent"] == "Risk Summary"


@pytest.mark.asyncio
async def test_invalid_classification_never_searches_and_multi_issuer_w_ids_remain_unique(monkeypatch):
    state, risks, gateway = setup(monkeypatch)
    for year in (2024, 2025):
        key = f"intel-{year}"
        risks.index.documents[key] = {**copy.deepcopy(risks.index.documents[str(year)]), "company": "INTC", "document_id": key}
        risks.index.texts[key] = risks.index.texts[str(year)]
    async def model(prompt, schemas, handler, **kwargs):
        change = finding(handler, "relocated")
        with pytest.raises(ValueError):
            handler("record_risk_change", {**change, "before": "S99999"})
        with pytest.raises(ValueError, match="query"):
            handler("record_risk_change", {**change, "live_query": {"bad": "type"}})
        check = handler("record_risk_change", {**change, "live_query": "export restrictions"})["post_filing_check"]
        handler("report_outcome", {"status": "complete", "missing": []})
        yield {"type": "token", "data": f"Stable warning [{change['before']}][{change['after']}]. Post-filing fixture [{check['source_ids'][0]}]."}
    result = await risk_turn(risks.index, {**state, "companies": ["AMD", "INTC"]}, lambda e: None, model_stream=model, gateway=gateway)
    assert len(gateway.calls) == 2 and set(result["live_sources"]) == {"W1", "W2"}
    assert {s["company"] for s in result["live_sources"].values()} == {"AMD", "INTC"}
