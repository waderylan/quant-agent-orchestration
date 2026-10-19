"""Frozen live workers, shared MCP trace, citation checks and failure preservation."""

import json
from pathlib import Path

import pytest

from src.current_developments import current_turn
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
    assert sources["W3"]["tool"] == "tavily_extract"
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
