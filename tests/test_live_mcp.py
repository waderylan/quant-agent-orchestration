"""Live allowlist, request provenance, scrubbing and atomic credit stops."""

import json
from types import SimpleNamespace

import pytest

from src.live_mcp import LiveGateway, UsageLedger, sanitized


SEARCH = {"query": "NVIDIA company developments", "topic": "news", "search_depth": "basic", "max_results": 5, "include_raw_content": False, "time_range": "year"}


@pytest.mark.asyncio
async def test_gateway_rejects_tools_parameters_and_unsearched_extracts():
    gateway = LiveGateway()
    for tool, args in [("other", SEARCH), ("tavily_search", {**SEARCH, "include_answer": True}), ("tavily_search", {**SEARCH, "max_results": 6}), ("tavily_extract", {"urls": ["https://nvidia.com/unseen"], "extract_depth": "basic"})]:
        with pytest.raises(ValueError):
            await gateway.fetch(tool, args, request={}, agent="Current Developments", emit=lambda e: None)


def test_credentials_and_account_identity_are_scrubbed(monkeypatch):
    key = "synthetic-test-secret"
    monkeypatch.setenv("TAVILY_API_KEY", key)
    result = sanitized({"error": "https://mcp.example/mcp?tavilyApiKey=" + key + " " + key + " user@example.org", "tavilyApiKey": key})
    assert key not in json.dumps(result) and "user@example.org" not in json.dumps(result)
    assert "https://mcp.example" not in json.dumps(result)


@pytest.mark.asyncio
async def test_reservation_precedes_execution_and_monthly_stop(tmp_path, monkeypatch):
    ledger = UsageLedger()
    gateway = LiveGateway(mode="live", ledger=ledger)
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic-test-key")
    calls = []
    async def usage():
        ledger.observe_tavily_usage(594)
        return {"verified": True}
    async def session(stack):
        assert ledger.snapshot()["calls"][-1]["outcome"] == "reserved"
        calls.append("connected")
        async def call_tool(tool, args):
            return SimpleNamespace(model_dump=lambda **kw: {"content": [{"type": "text", "text": json.dumps({"results": [{"url": "https://nvidia.com/update", "content": "Dated event"}]})}]})
        return SimpleNamespace(call_tool=call_tool), {"server": {"name": "frozen-test-server"}, "tools": [{"name": "tavily_search", "inputSchema": {"properties": {"time_range": {}}}}]}
    monkeypatch.setattr(gateway, "tavily_usage", usage)
    monkeypatch.setattr(gateway, "_session", session)
    for attempt in range(3):
        if attempt:
            async def unavailable_usage():
                return {"verified": False, "reason": "usage endpoint HTTP 429"}
            monkeypatch.setattr(gateway, "tavily_usage", unavailable_usage)
        result = await gateway.fetch("tavily_search", SEARCH, request={}, agent="Current Developments", emit=lambda e: None, refresh=True)
        assert result.get("snapshot_id")
        if attempt:
            assert "HTTP 429" in result["usage_warning"]
    stopped = await gateway.fetch("tavily_search", SEARCH, request={}, agent="Current Developments", emit=lambda e: None, refresh=True)
    assert stopped["error"] == "monthly budget stop" and len(calls) == 3
    assert ledger.snapshot()["reserved_credits"] == 6
    frozen = LiveGateway(mode="frozen", path=gateway.path)
    snapshot = frozen.inspect(result["snapshot_id"])
    file = gateway.path / (result["snapshot_id"] + ".json")
    snapshot["payload"]["content"][0]["text"] = "tampered"
    file.write_text(json.dumps(snapshot))
    with pytest.raises(ValueError, match="checksum"):
        frozen.inspect(result["snapshot_id"])
