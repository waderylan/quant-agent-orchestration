"""Frozen live workers, shared MCP trace, citation checks and failure preservation."""

import json
from pathlib import Path

import pytest

from src.current_developments import current_turn, research_windows, LiveTools
from src.live_mcp import LiveGateway, search_arguments
from src.research_workflow import events, research_turn
from tests.test_supervisor import source

FIXTURE = json.loads((Path(__file__).parent / "fixtures/live_sources.json").read_text(encoding="utf-8"))
STATE = {"question": "What has happened at NVIDIA since its latest filing?", "companies": ["NVDA"], "years": [2025], "live_intent": "developments"}


def frozen(*, error=None):
    gateway = LiveGateway()
    metadata = {"server": {"name": FIXTURE["server"]}}
    for topic in ("news", "general"):
        body = {"error": error} if error else {"results": FIXTURE["results"]}
        gateway.store("tavily_search", search_arguments(["NVDA"], "NVIDIA update", topic), {"content": [{"type": "text", "text": json.dumps(body)}], "isError": bool(error)}, metadata, retrieved_at=FIXTURE["retrieved_at"])
    gateway.store("tavily_extract", {"urls": [FIXTURE["extract"]["url"]], "extract_depth": "basic"}, {"content": [{"type": "text", "text": json.dumps({"results": [FIXTURE["extract"]]})}]}, metadata, retrieved_at=FIXTURE["retrieved_at"])
    return gateway


def test_search_and_extract_share_identity_and_keep_the_supplied_publication_date():
    tools = LiveTools(STATE, frozen())
    common = {'retrieved_at': FIXTURE['retrieved_at'], 'snapshot_id': 'frozen'}
    tools.register({**common, 'tool': 'tavily_search', 'payload': {'structuredContent': {'results': FIXTURE['results']}}}, ['NVDA'])
    extracted = {**FIXTURE['extract'], 'published_date': None}
    tools.register({**common, 'tool': 'tavily_extract', 'payload': {'structuredContent': {'results': [extracted]}}}, ['NVDA'])
    assert len(tools.sources) == 2
    assert tools.sources['W1']['date_source'] == 'tavily'
    assert tools.sources['W1']['published_date'].startswith('2026-10-18')
    assert tools.sources['W1']['tool'] == 'tavily_extract'


def test_historical_reactions_use_the_selected_release_while_recent_ignores_fiscal_controls():
    from datetime import datetime, timezone, timedelta
    state = {'companies': ['QCOM'], 'years': [2024, 2025]}
    historical = research_windows({**state, 'request_plan': {'timeframe': 'reaction'}})['QCOM']
    assert historical == {'start_date': '2025-11-02', 'end_date': '2025-12-05'}
    recent = research_windows({**state, 'request_plan': {'timeframe': 'recent'}})['QCOM']
    assert recent['start_date'] == (datetime.now(timezone.utc).date() - timedelta(days=90)).isoformat()
    assert recent['end_date'] == datetime.now(timezone.utc).date().isoformat()


def test_output_windows_keep_historical_reactions_separate_from_recent_updates():
    state = {"companies": ["QCOM"], "years": [2024, 2025], "question": "Explain the earlier reactions and latest developments.", "request_plan": {"timeframe": "recent", "outputs": [
        {"id": "R1", "kind": "public_reaction", "timeframe": "reaction", "year": 2024},
        {"id": "R2", "kind": "current_developments", "timeframe": "recent"},
    ]}}
    tools = LiveTools(state, frozen())
    assert tools.output_windows["R1"]["QCOM"] == {"start_date": "2024-11-03", "end_date": "2024-12-06"}
    assert tools.output_windows["R2"]["QCOM"]["start_date"] > "2024-12-06"
    for output in ("R2", "R1"):
        tools("search_web", {"companies": ["QCOM"], "query": "Qualcomm update", "output_id": output})
        arguments = tools.events[-1]["data"]["arguments"]
        assert {k: arguments[k] for k in ("start_date", "end_date")} == tools.output_windows[output]["QCOM"]
    with pytest.raises(ValueError, match="output_id"):
        tools("search_web", {"companies": ["QCOM"], "query": "Qualcomm update", "output_id": "R99"})


def test_explicit_windows_override_reaction_defaults_and_validate_scope():
    state = {"companies": ["QCOM"], "years": [2025], "request_plan": {"timeframe": "reaction"}}
    output = {"timeframe": "reaction", "year": 2025, "start_date": "2025-11-10", "end_date": "2025-11-20"}
    assert research_windows(state, output)["QCOM"] == {"start_date": "2025-11-10", "end_date": "2025-11-20"}
    with pytest.raises(ValueError, match="fiscal scope"):
        research_windows(state, {**output, "year": 2024})
    with pytest.raises(ValueError, match="follows"):
        research_windows(state, {**output, "end_date": "2025-11-01"})
    with pytest.raises(ValueError, match="Invalid research date"):
        research_windows(state, {**output, "start_date": "2025-02-30"})
    assert research_windows({**state, "request_plan": {"timeframe": "since_filing"}})["QCOM"]["start_date"] == "2025-11-06"


def test_output_timeframe_override_does_not_inherit_other_clauses_date_bounds():
    from datetime import datetime, timezone, timedelta
    state = {"companies": ["QCOM"], "years": [2025], "request_plan": {"timeframe": "specified", "start_date": "2025-11-01", "end_date": "2025-11-20"}}
    recent = research_windows(state, {"timeframe": "recent"})["QCOM"]
    today = datetime.now(timezone.utc).date()
    assert recent == {"start_date": (today - timedelta(days=90)).isoformat(), "end_date": today.isoformat()}
    assert research_windows(state, {"timeframe": "specified"})["QCOM"] == {"start_date": "2025-11-01", "end_date": "2025-11-20"}


def test_repeated_search_cannot_replace_extracted_body_or_its_date_provenance():
    tools = LiveTools(STATE, frozen())
    common = {"retrieved_at": FIXTURE["retrieved_at"]}
    row = FIXTURE["results"][0]
    def register(tool, identity, rows):
        return tools.register({**common, "tool": tool, "snapshot_id": identity, "payload": {"structuredContent": {"results": rows}}}, ["NVDA"])
    register("tavily_search", "search", [row])
    original = tools.sources["W1"]
    register("tavily_extract", "extract", [{**FIXTURE["extract"], "published_date": None}])
    extracted = tools.sources["W1"]
    result = register("tavily_search", "later-search", [{**row, "content": "NVIDIA short snippet."}])
    source = tools.sources["W1"]
    assert source["text"] == extracted["text"] and source["snapshot_id"] == "extract"
    assert source["date_snapshot_id"] == "search" and source["published_date"] == original["published_date"]
    assert len(original["observations"]) == 1 and len(extracted["observations"]) == 2 and len(source["observations"]) == 3
    assert source["observations"][0]["date_snapshot_id"] == "search"
    assert all("<untrusted_web_content>" in o["text"] for o in result["sources"][0]["observations"])


@pytest.mark.parametrize('mode', ['recent', 'specified', 'since_filing'])
def test_calendar_research_year_does_not_require_a_matching_fiscal_filing(mode):
    state = {'companies': ['QCOM'], 'years': [2025], 'request_plan': {'timeframe': mode}}
    output = {'timeframe': mode, 'year': 2026, 'start_date': '2026-06-01', 'end_date': '2026-10-19'}
    assert research_windows(state, output)['QCOM'] == {'start_date': '2026-06-01', 'end_date': '2026-10-19'}


class Responses:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    async def fetch(self, tool, arguments, **kwargs):
        self.calls.append((tool, arguments))
        body = next(self.responses)
        if "error" in body:
            return body
        return {"tool": tool, "snapshot_id": str(len(self.calls)), "retrieved_at": FIXTURE["retrieved_at"], "payload": {"structuredContent": body}}


@pytest.mark.asyncio
@pytest.mark.parametrize("followup", [{"results": []}, {"error": "timeout"}])
async def test_optional_failed_followup_keeps_supported_requested_findings_complete(followup):
    state = {**STATE, "request_plan": {"timeframe": "recent", "outputs": [{"id": "R1", "kind": "current_developments", "description": "Recent NVIDIA developments"}]}}
    gateway = Responses({"results": [FIXTURE["results"][0]]}, followup)
    async def model(prompt, schema, handler, **kwargs):
        handler("search_web", {"companies": ["NVDA"], "query": "NVIDIA update", "output_id": "R1"})
        handler("extract_page", {"url": FIXTURE["results"][0]["url"]})
        handler("report_outcome", {"status": "complete", "missing": []})
        yield {"type": "token", "data": "NVIDIA announced a product on October 18, 2026 [W1]."}
    emitted = []
    result = await current_turn(state, emitted.append, gateway=gateway, model_stream=model)
    assert not result["partial"] and not result["missing_outputs"]
    assert any(e["type"] == "trace" and e["data"].get("warnings") for e in emitted)


@pytest.mark.asyncio
async def test_zero_web_findings_remains_partial_despite_model_completion():
    state = {**STATE, "request_plan": {"timeframe": "recent", "outputs": [{"id": "R1", "kind": "current_developments"}]}}
    async def model(prompt, schema, handler, **kwargs):
        handler("search_web", {"companies": ["NVDA"], "query": "NVIDIA update"})
        handler("report_outcome", {"status": "complete", "missing": []})
        yield {"type": "token", "data": "Search returned no useful findings."}
    result = await current_turn(state, lambda e: None, gateway=Responses({"results": []}), model_stream=model)
    assert result["partial"] and any("No dated development" in gap for gap in result["missing_outputs"])


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit", [False, True])
async def test_undated_reaction_can_address_event_but_not_explicit_publication_interval(explicit):
    output = {"id": "R1", "kind": "public_reaction", "timeframe": "reaction", "year": 2025}
    if explicit:
        output.update(start_date="2025-02-20", end_date="2025-03-20")
    state = {**STATE, "request_plan": {"timeframe": "specified", "start_date": "2026-09-01", "end_date": "2026-10-19", "outputs": [output]}}
    row = {"url": "https://example.com/nvidia-reaction", "content": "NVIDIA's FY2025 earnings drew analyst commentary about AI demand.", "published_date": None}
    async def model(prompt, schema, handler, **kwargs):
        handler("search_web", {"companies": ["NVDA"], "query": "NVIDIA FY2025 earnings reaction"})
        handler("report_outcome", {"status": "complete", "missing": []})
        yield {"type": "token", "data": "An industry commentator discussed AI demand in NVIDIA's FY2025 earnings [W1]."}
    result = await current_turn(state, lambda e: None, gateway=Responses({"results": [row]}), model_stream=model)
    assert result["partial"] is explicit
    assert all("No dated development" not in gap for gap in result["missing_outputs"])


@pytest.mark.asyncio
@pytest.mark.parametrize("cite_reaction", [False, True])
async def test_mixed_reaction_and_recent_updates_require_each_outputs_window(cite_reaction):
    outputs = [{"id": "R1", "kind": "public_reaction", "timeframe": "reaction", "year": 2025}, {"id": "R2", "kind": "current_developments", "timeframe": "recent"}]
    state = {"question": "Explain Qualcomm earnings reactions and recent developments.", "companies": ["QCOM"], "years": [2024, 2025], "live_intent": "developments", "request_plan": {"timeframe": "recent", "outputs": outputs}}
    reaction = {"url": "https://example.com/earnings", "content": "Qualcomm's fiscal 2025 earnings prompted outside commentary.", "published_date": "2025-11-10"}
    recent = {"url": "https://example.com/update", "content": "Qualcomm announced a new product.", "published_date": "2026-10-18"}
    gateway = Responses({"results": [reaction]}, {"results": [recent]})
    async def model(prompt, schema, handler, **kwargs):
        assert '"output_windows"' in prompt and '"R1"' in prompt and '"R2"' in prompt
        for output in outputs:
            handler("search_web", {"companies": ["QCOM"], "query": "Qualcomm update", "output_id": output["id"]})
        handler("report_outcome", {"status": "complete", "missing": []})
        yield {"type": "token", "data": ("An outside commentator discussed Qualcomm's earnings [W1]. " if cite_reaction else "") + "Qualcomm announced a product in October 2026 [W2]."}
    result = await current_turn(state, lambda e: None, gateway=gateway, model_stream=model)
    assert result["partial"] is not cite_reaction
    assert gateway.calls[0][1]["end_date"] == "2025-12-05"
    assert gateway.calls[1][1]["start_date"] > "2025-12-05"


@pytest.mark.asyncio
@pytest.mark.parametrize("claim", ["dated", "undated", "unregistered"])
async def test_current_sources_freshness_injection_and_citations(claim):
    called = []
    async def model(prompt, schema, handler, **kwargs):
        assert "untrusted_web_content" in prompt and "filing_anchors" in prompt
        assert {t["name"] for t in schema} == {"search_web", "extract_page", "inspect_live_source", "report_outcome"}
        result = handler("search_web", {"companies": ["NVDA"], "query": "NVIDIA update"})
        called.append("search")
        assert "<untrusted_web_content>" in result["sources"][0]["text"]
        with pytest.raises(ValueError, match="Unknown live source tool"):
            handler("unknown_tool", {})
        handler("extract_page", {"url": FIXTURE["extract"]["url"]})
        called.append("extract")
        handler("report_outcome", {"status": "complete", "missing": []})
        yield {"type": "token", "data": {"dated": "2026-10-18 · nvidia.com · official: NVIDIA announced a product [W1].", "undated": "NVIDIA currently has an announcement [W2].", "unregistered": "Unsupported claim [W99] and malformed [W0]."}[claim]}
    emitted = []
    result = await current_turn(STATE, emitted.append, gateway=frozen(), model_stream=model)
    assert called == ["search", "extract"]
    sources = result["live_sources"]
    assert sources["W1"]["source_tier"] == "official" and sources["W1"]["freshness"] == "fresh"
    assert sources["W2"]["source_tier"] == "third_party" and sources["W2"]["freshness"] == "undated"
    assert len(sources) == 2 and sources["W1"]["tool"] == "tavily_extract"
    if claim == "dated":
        assert not result["partial"]
    elif claim == "undated":
        assert result["partial"] and "A current-status claim lacks a dated source from the last 90 days." in result["missing_outputs"]
    else:
        assert result["partial"] and "[unverified source]" in result["answer"]


class Index:
    def coverage(self):
        return {"NVDA": [2025]}
    def search(self, *args, **kwargs):
        return [{"chunk_id": "fixture", "company": "NVDA", "fiscal_year": 2025, "text": "Filed export-control statement."}]
    def inspect(self, identity):
        return self.search()[0]


@pytest.mark.asyncio
async def test_same_mcp_tool_is_shared_in_distinct_worker_contexts():
    emitted = []
    async def model(prompt, schema, handler, **kwargs):
        role = kwargs.get("agent", "Filings Research")
        handler("search_web", {"companies": ["NVDA"], "query": "NVIDIA update", "topic": "general" if role == "Filings Research" else "news"})
        handler("report_outcome", {"status": "complete", "missing": []})
        yield {"type": "token", "data": "Filed statement [S1]. Official update [W1]." if role == "Filings Research" else "2026-10-18 · nvidia.com · official: announcement [W1]."}
    gateway = frozen()
    await current_turn(STATE, emitted.append, gateway=gateway, model_stream=model)
    await research_turn(Index(), {**STATE, "live_intent": "verify", "live_check": True}, emitted.append, gateway=gateway, model_stream=model)
    sharing = [e["data"] for e in emitted if e["type"] == "trace" and e["data"].get("node") == "live_mcp"]
    assert [(e["server"], e["tool"], e["agent"]) for e in sharing] == [("tavily-mcp", "tavily_search", "Current Developments"), ("tavily-mcp", "tavily_search", "Filings Research")]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing key", "429", "timeout", "off"])
async def test_live_failure_is_partial_and_retains_earlier_data(monkeypatch, failure):
    if failure in ("429", "timeout"):
        gateway = frozen(error=failure)
    else:
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        gateway = LiveGateway(mode="off" if failure == "off" else "live")
    async def data(state, emit):
        return {"answer": "Original revenue [F1].", "financial_sources": {"F1": source(company="NVDA")}}
    async def model(prompt, schema, handler, **kwargs):
        result = handler("search_web", {"companies": ["NVDA"], "query": "NVIDIA update"})
        assert "Live search unavailable:" in result["error"]
        handler("report_outcome", {"status": "partial", "missing": ["Live search unavailable: " + failure]})
        yield {"type": "token", "data": "Live search unavailable: " + failure}
    result = [e async for e in events(Index(), "Show NVIDIA revenue and what has happened since the filing.", ["NVDA"], [2025], worker_overrides={"data": data}, gateway=gateway, model_stream=model)]
    assert result[-1]["data"]["status"] == "partial"
    final = next(e["data"] for e in reversed(result) if e["type"] == "answer")
    assert "Original revenue [F1]" in final
    assert any(e["type"] == "sources" and any(s["source_id"] == "F1" for s in e["data"]) for e in result)
