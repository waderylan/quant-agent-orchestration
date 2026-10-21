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
async def test_usage_is_recorded_before_execution_and_never_blocks(tmp_path, monkeypatch):
    ledger = UsageLedger()
    gateway = LiveGateway(mode="live", ledger=ledger)
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic-test-key")
    calls = []
    async def session(stack):
        assert ledger.snapshot()["calls"][-1]["outcome"] == "started"
        calls.append("connected")
        async def call_tool(tool, args):
            return SimpleNamespace(model_dump=lambda **kw: {"content": [{"type": "text", "text": json.dumps({"results": [{"url": "https://nvidia.com/update", "content": "Dated event"}]})}]})
        return SimpleNamespace(call_tool=call_tool), {"server": {"name": "frozen-test-server"}, "tools": [{"name": "tavily_search", "inputSchema": {"properties": {"time_range": {}}}}]}
    monkeypatch.setattr(gateway, "_session", session)
    for _ in range(4):
        result = await gateway.fetch("tavily_search", SEARCH, request={}, agent="Current Developments", emit=lambda e: None, refresh=True)
        assert result.get("snapshot_id")
    assert len(calls) == 4 and ledger.snapshot()["estimated_credits"] == 8
    frozen = LiveGateway(mode="frozen", path=gateway.path)
    snapshot = frozen.inspect(result["snapshot_id"])
    file = gateway.path / (result["snapshot_id"] + ".json")
    snapshot["payload"]["content"][0]["text"] = "tampered"
    file.write_text(json.dumps(snapshot))
    with pytest.raises(ValueError, match="checksum"):
        frozen.inspect(result["snapshot_id"])
