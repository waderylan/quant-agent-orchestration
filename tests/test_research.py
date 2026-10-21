"""Protect provenance, scope isolation, and streamed-answer failure handling."""

import json
import asyncio
import socket

import chromadb
import pytest
from chromadb.config import Settings
from tokenizers import Tokenizer, models, pre_tokenizers

from src.research_index import CONFIG, ResearchIndex, chunks
from src.research_workflow import ResearchTools, events
from src.source_collection import digest


def test_chunks_keep_unicode_offsets_and_page_section_boundaries():
    tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    text = "révenue " * 310 + "risk " * 290
    split = len("révenue " * 310)
    document = {
        "document_id": "amd-original",
        "company": "AMD",
        "fiscal_year": 2025,
        "kind": "filing",
        "form": "10-K",
        "period_end": "2025-12-27",
        "version": "original",
        "canonical_url": "https://www.sec.gov/example",
        "extraction": {
            "text_sha256": digest(text.encode()),
            "pages": [
                {"page": 1, "start": 0, "end": split},
                {"page": 2, "start": split, "end": len(text)},
            ],
            "sections": {
                "mda": {"start": 0, "end": split},
                "risk_factors": {"start": split, "end": len(text)},
                "unavailable": {"status": "not_present"},
            },
        },
    }
    rows = list(chunks(text, document, tokenizer))
    assert {m["section"] for _, _, m in rows} == {"mda", "risk_factors"}
    for _, passage, metadata in rows:
        assert passage == text[metadata["start"] : metadata["end"]]
        assert not metadata["start"] < split < metadata["end"]
        assert len(tokenizer.encode(passage).ids) <= CONFIG["tokens"]
    assert (
        rows[1][2]["start"] < rows[0][2]["end"]
    )  # Overlap preserves sentence context.


@pytest.fixture
def small_index(tmp_path):
    index = ResearchIndex.__new__(ResearchIndex)
    index.path = tmp_path / "index"
    index.corpus = tmp_path / "corpus"
    index.corpus.mkdir()
    index.fingerprint = "verified-snapshot"
    index.client = chromadb.PersistentClient(
        path=str(index.path), settings=Settings(anonymized_telemetry=False)
    )
    collection = index.client.create_collection("fixture", embedding_function=None)
    rows = [
        ("original", "AMD", 2025, "original"),
        ("amendment", "AMD", 2025, "amendment"),
        ("other-company", "NVDA", 2025, "original"),
        ("other-year", "AMD", 2024, "original"),
    ]
    index.documents = {}
    for cid, company, year, version in rows:
        text = f"{company} {year} {version} revenue evidence"
        (index.corpus / f"{cid}.txt").write_text(text, encoding="utf-8")
        sha = digest(text.encode())
        index.documents[cid] = {
            "document_id": cid,
            "company": company,
            "fiscal_year": year,
            "body": {"retrieval_url": "https://example.com"},
            "extraction": {"text_path": f"{cid}.txt", "text_sha256": sha},
        }
        collection.add(
            ids=[cid],
            embeddings=[[1.0, 0.0, 0.0]],
            documents=[text],
            metadatas=[
                {
                    "document_id": cid,
                    "company": company,
                    "fiscal_year": year,
                    "version": version,
                    "start": 0,
                    "end": len(text),
                    "section": "mda",
                    "page": 0,
                    "text_sha256": sha,
                }
            ],
        )
    index.embedding = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    (index.path / "active.json").write_text(
        json.dumps({"fingerprint": index.fingerprint, "collection": "fixture"})
    )
    return index


@pytest.mark.asyncio
async def test_research_can_inspect_registered_risk_handoff_without_retrieving_a_new_identity(small_index):
    from src.research_workflow import research_turn
    handed = {"source_id": "S1", "kind": "filing_passage", "text": "Verified prior risk wording"}
    async def model(prompt, schema, handler, **kwargs):
        assert "Only the filing interpretation" in prompt and "Recent outside developments" not in prompt
        assert handler("inspect_source", {"source_id": "S1"})["source"] == handed
        with pytest.raises(KeyError):
            handler("inspect_source", {"source_id": "S99"})
        handler("report_outcome", {"status": "complete", "missing": []})
        yield {"type": "token", "data": "Prior risk wording [S1]."}
    result = await research_turn(small_index, {"question": "Explain AMD filing context", "companies": ["AMD"],
        "years": [2025], "analysis_sources": {"S1": handed}, "source_offset": 1,
        "request_plan": {"outputs": [{"kind": "filing_explanation", "description": "Only the filing interpretation"},
                                      {"kind": "current_developments", "description": "Recent outside developments"}]}}, lambda event: None, model_stream=model)
    assert result["citation_verified"] and result["research_sources"]["S1"] == handed


def test_retrieval_filters_and_tools_cannot_cross_company_year_or_version(small_index):
    found = small_index.search("revenue", ["AMD"], [2025], version="amendment")
    assert [p["chunk_id"] for p in found] == ["amendment"]
    tools = ResearchTools(small_index, ["AMD"], [2025])
    with pytest.raises(ValueError, match="scope"):
        tools("search_sources", {"query": "revenue", "company": "NVDA"})
    with pytest.raises(ValueError, match="scope"):
        tools("search_sources", {"query": "revenue", "year": 2024})
    with pytest.raises(KeyError):
        tools("inspect_source", {"source_id": "S99"})
    with pytest.raises(ValueError, match="JSON object"):
        tools("search_sources", [])


def test_source_inspection_detects_corrupt_text_and_stale_index(small_index):
    assert small_index.inspect("original")["text"] == small_index.text(
        small_index.documents["original"]
    )
    (small_index.corpus / "original.txt").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        small_index.inspect("original")
    small_index.fingerprint = "different-corpus"
    with pytest.raises(ValueError, match="changed"):
        small_index.search("revenue", ["AMD"], [2025])


def test_comparison_search_balances_scope_and_reports_empty_cells(small_index):
    tools = ResearchTools(small_index, ["AMD", "NVDA"], [2024, 2025])
    result = tools("search_sources", {"query": "revenue"})
    assert {(s["company"], s["fiscal_year"]) for s in result["sources"]} == {
        ("AMD", 2024),
        ("AMD", 2025),
        ("NVDA", 2025),
    }
    assert {
        (c["company"], c["fiscal_year"]): c["passages"]
        for c in result["retrieval_coverage"]
    } == {
        ("AMD", 2024): 1,
        ("AMD", 2025): 2,
        ("NVDA", 2024): 0,
        ("NVDA", 2025): 1,
    }
    assert tools.max_tool_calls == 12
    assert ResearchTools(small_index, ["AMD"], [2025]).max_tool_calls == 8
    assert (
        ResearchTools(
            small_index, ["AMD", "NVDA", "INTC", "QCOM"], [2024, 2025]
        ).max_tool_calls
        == 24
    )


@pytest.mark.asyncio
async def test_research_keeps_cited_findings_and_marks_budget_limited_answer_partial(
    small_index,
):
    async def limited(prompt, tools, handler):
        handler("report_outcome", {"status": "complete", "missing": []})
        yield {"type": "trace", "data": {"decision": "synthesize_existing_evidence"}}
        yield {"type": "token", "data": "Revenue evidence [S1]."}

    result = [
        e
        async for e in events(
            small_index, "Revenue drivers", ["AMD"], [2025], model_stream=limited
        )
    ]
    assert result[-1]["data"] == {"status": "partial", "verified_citations": True}
    answer = "".join(e["data"] for e in result if e["type"] == "token")
    assert "Revenue evidence [S1]" in answer and "may be incomplete" in answer
    assert any(e["type"] == "sources" for e in result)


@pytest.mark.asyncio
async def test_unsupported_scope_returns_gap_without_model_call(small_index):
    async def forbidden(*args):
        pytest.fail("Unsupported scope must not invoke a model")
        yield

    for question, companies, years in [
        ("Apple revenue", ["AAPL"], [2025]),
        ("AMD FY2027 revenue", ["AMD"], [2027]),
        ("NVIDIA revenue", ["AMD"], [2025]),
    ]:
        result = [
            e
            async for e in events(
                small_index, question, companies, years, model_stream=forbidden
            )
        ]
        assert result[-1]["data"]["status"] == "coverage_gap"


@pytest.mark.asyncio
async def test_streamed_answer_exposes_evidence_and_rejects_fabricated_citations(
    small_index,
):
    async def valid(prompt, tools, handler):
        source = handler("inspect_source", {"source_id": "S1"})
        assert source["text"] in prompt
        yield {"type": "token", "data": "Revenue evidence [S1]."}

    result = [
        e
        async for e in events(
            small_index, "Revenue drivers", ["AMD"], [2025], model_stream=valid
        )
    ]
    assert result[-1]["data"]["verified_citations"]
    sources = next(e["data"] for e in result if e["type"] == "sources")
    assert [s["source_id"] for s in sources] == ["S1"]

    async def invalid(*args):
        yield {"type": "token", "data": "Invented evidence [S99]."}

    result = [
        e
        async for e in events(
            small_index, "Revenue", ["AMD"], [2025], model_stream=invalid
        )
    ]
    assert result[-1]["data"]["status"] == "unverified"
    assert not any(e["type"] == "sources" for e in result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,message",
    [
        (RuntimeError("Codex unavailable"), "Codex unavailable"),
        (TimeoutError(), "A worker timed out before completing. Please retry."),
    ],
)
async def test_model_failure_has_terminal_failure_event(small_index, failure, message):
    async def failed(*args):
        raise failure
        yield

    result = [
        e
        async for e in events(
            small_index, "Revenue", ["AMD"], [2025], model_stream=failed
        )
    ]
    assert result[-2] == {"type": "error", "data": message}
    assert result[-1]["data"] == {"status": "failed", "verified_citations": False}


@pytest.mark.asyncio
async def test_asgi_send_failure_closes_generator_suspended_at_yield():
    from main import ClosingStreamingResponse
    from starlette.requests import ClientDisconnect

    closed = asyncio.Event()

    async def body():
        try:
            yield "model event"
            await asyncio.Event().wait()
        finally:
            closed.set()

    async def disconnected_send(message):
        if message["type"] == "http.response.body":
            raise OSError("client disconnected after a streamed event")

    async def receive():
        await asyncio.Event().wait()

    with pytest.raises(ClientDisconnect):
        await ClosingStreamingResponse(body())(
            {"type": "http", "asgi": {"spec_version": "2.4"}},
            receive,
            disconnected_send,
        )
    assert closed.is_set()


@pytest.mark.asyncio
async def test_pure_clarification_does_not_require_filing_citations(small_index):
    async def clarification(prompt, schema, handler):
        handler(
            "report_outcome",
            {"status": "clarification", "missing": ["Which company and metric?"]},
        )
        yield {"type": "token", "data": "Which company and metric do you mean?"}

    result = [
        e
        async for e in events(
            small_index,
            "What about the other one?",
            ["AMD"],
            [2025],
            model_stream=clarification,
        )
    ]
    assert result[-1]["data"] == {
        "status": "needs_clarification",
        "verified_citations": False,
        "missing_outputs": ["Which company and metric?"],
    }
    assert not any(e["type"] == "error" for e in result)


@pytest.mark.asyncio
async def test_http_disconnect_closes_running_graph_worker(small_index, monkeypatch):
    """Use a real ASGI connection: fixture transports cannot reproduce this cancellation."""
    import httpx
    import uvicorn
    import main

    closed = asyncio.Event()

    async def blocked_model(*args):
        try:
            yield {"type": "trace", "data": {"provider": "fixture"}}
            await asyncio.Event().wait()
        finally:
            closed.set()

    monkeypatch.setattr(main, "ResearchIndex", lambda *args: small_index)
    monkeypatch.setattr(
        main,
        "events",
        lambda *args, **kwargs: events(*args, model_stream=blocked_model),
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        address = listener.getsockname()
        server = uvicorn.Server(uvicorn.Config(main.app, log_level="error"))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(5):
                while not server.started:
                    await asyncio.sleep(0.01)
            async with httpx.AsyncClient(timeout=5) as client:
                async with client.stream(
                    "POST",
                    f"http://{address[0]}:{address[1]}/api/chat",
                    json={
                        "question": "Revenue drivers",
                        "companies": ["AMD"],
                        "years": [2025],
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if '"provider": "fixture"' in line:
                            break
                await asyncio.wait_for(closed.wait(), timeout=2)
        finally:
            server.should_exit = True
            await asyncio.wait_for(serving, timeout=5)
