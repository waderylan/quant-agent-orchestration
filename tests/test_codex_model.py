"""Exercise the real JSON-RPC loop with deterministic app-server messages."""

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio

from src import codex_model


@pytest_asyncio.fixture
async def rpc(monkeypatch):
    reader = asyncio.StreamReader()
    sent, executed, closed = [], [], []

    def feed(message):
        reader.feed_data((json.dumps(message) + "\n").encode())

    class Writer:
        def write(self, data):
            message = json.loads(data)
            sent.append(message)
            method = message.get("method")
            if method in ("initialize", "thread/start", "turn/start"):
                feed(
                    {
                        "id": message["id"],
                        "result": {"thread": {"id": "test"}, "model": "fixture"},
                    }
                )
            if method == "turn/start":
                for number in range(self.calls):
                    feed(
                        {
                            "id": 100 + number,
                            "method": "item/tool/call",
                            "params": {
                                "tool": "search_sources",
                                "arguments": {"query": str(number)},
                            },
                        }
                    )
                feed(
                    {
                        "method": "item/agentMessage/delta",
                        "params": {
                            "itemId": "answer",
                            "delta": "Supported findings [S1].",
                        },
                    }
                )
                feed(
                    {
                        "method": "turn/completed",
                        "params": {"turn": {"status": "completed"}},
                    }
                )

        async def drain(self):
            pass

    writer = Writer()

    @asynccontextmanager
    async def connection():
        try:
            yield reader, writer
        finally:
            closed.append(True)

    monkeypatch.setattr(codex_model, "connection", connection)

    def handler(name, arguments):
        executed.append(arguments)
        return {"sources": []}

    return writer, handler, sent, executed, closed


@pytest.mark.asyncio
async def test_budget_exhaustion_returns_findings_without_executing_extra_tools(rpc):
    writer, handler, sent, executed, closed = rpc
    writer.calls = 10
    events = [event async for event in codex_model.stream("question", [], handler)]
    assert len(executed) == 8
    replies = [m["result"] for m in sent if m.get("id", 0) >= 100]
    assert len(replies) == 10 and not replies[-1]["success"]
    assert "budget_exhausted" in replies[-1]["contentItems"][0]["text"]
    assert any(
        e["type"] == "trace"
        and e["data"].get("decision") == "synthesize_existing_evidence"
        for e in events
    )
    assert events[-1] == {"type": "token", "data": "Supported findings [S1]."}
    assert closed == [True]


@pytest.mark.asyncio
async def test_scope_budget_allows_additional_calls_and_exposes_remaining_work(rpc):
    writer, handler, sent, executed, closed = rpc
    handler.max_tool_calls = 12
    writer.calls = 9
    events = [event async for event in codex_model.stream("question", [], handler)]
    assert len(executed) == 9
    replies = [m["result"] for m in sent if m.get("id", 0) >= 100]
    assert (
        json.loads(replies[-1]["contentItems"][0]["text"])["tool_budget"]["remaining"]
        == 3
    )
    assert not any(
        e["type"] == "trace"
        and e["data"].get("decision") == "synthesize_existing_evidence"
        for e in events
    )
    assert closed == [True]


@pytest.mark.asyncio
async def test_repeated_calls_after_budget_remain_bounded_and_close_transport(rpc):
    writer, handler, _, executed, closed = rpc
    writer.calls = 11
    with pytest.raises(RuntimeError, match="ignored the tool limit"):
        _ = [event async for event in codex_model.stream("question", [], handler)]
    assert len(executed) == 8 and closed == [True]
