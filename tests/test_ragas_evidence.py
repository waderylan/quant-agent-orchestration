"""Protect evaluation evidence boundaries rather than model-score snapshots."""

import pytest
from pydantic import BaseModel

from scripts.evaluate_ragas import formatted_context, verify_references
from scripts.ragas_support import CodexJudge, JUDGMENT_CONTEXT, observed_contexts


def test_contexts_keep_uncited_retrieval_and_actual_inspection_in_first_seen_order():
    first = {"chunk_id": "a", "text": "first", "source_id": "S1"}
    uncited = {"chunk_id": "b", "text": "uncited retrieval", "source_id": "S2"}
    events = [{"type": "evidence", "data": {"sources": [first, uncited]}},
              {"type": "evidence", "data": {**first, "context": "expanded first"}},
              {"type": "evidence", "data": {"sources": [first]}},
              {"type": "sources", "data": [first]}]
    rows = observed_contexts(events)
    assert [(r["chunk_id"], r["model_visible_text"], r["first_seen_rank"]) for r in rows] == [
        ("a", "expanded first", 1), ("b", "uncited retrieval", 2)]


def test_reference_preflight_rejects_wrong_offsets_or_document_hash():
    class Index:
        documents = {"doc": {"extraction": {"text_sha256": "document-hash"}}}

        def text(self, doc):
            return "Verified filing passage."

    ref = {"document_id": "doc", "start": 0, "end": 8, "text": "Verified", "text_sha256": "document-hash"}
    case = {"id": "case", "reference": "Verified", "reference_contexts": [ref]}
    assert verify_references([case], Index()) == 1
    for changed in ({"start": 1}, {"text_sha256": "wrong"}):
        with pytest.raises(ValueError, match="checksum/span"):
            verify_references([{**case, "reference_contexts": [{**ref, **changed}]}], Index())


def test_metric_context_keeps_period_metadata_observed_by_the_answering_worker():
    value = formatted_context({"period_end": "2025-12-27", "form": "10-K", "version": "original",
                               "text": "fragment", "model_visible_text": "actual fragment", "first_seen_rank": 1})
    assert '"period_end": "2025-12-27"' in value
    assert '"form": "10-K"' in value and value.endswith("actual fragment")
    assert "first_seen_rank" not in value


@pytest.mark.asyncio
async def test_strictness_draws_are_independent_and_replay_as_three_cached_draws(tmp_path, monkeypatch):
    class Result(BaseModel):
        question: str

    executions = []

    async def stream(prompt, tools, handler, **kwargs):
        executions.append(prompt)
        handler("submit_metric", {"question": f"draw {len(executions)}"})
        yield {"type": "trace", "data": {"model": "test"}}

    monkeypatch.setattr("scripts.ragas_support.codex_model.stream", stream)
    token = JUDGMENT_CONTEXT.set("case:answer_relevancy")
    try:
        first = CodexJudge(tmp_path)
        values = [(await first.agenerate("same prompt", Result)).question for _ in range(3)]
        replay = CodexJudge(tmp_path)
        cached = [(await replay.agenerate("same prompt", Result)).question for _ in range(3)]
    finally:
        JUDGMENT_CONTEXT.reset(token)
    assert values == cached == ["draw 1", "draw 2", "draw 3"]
    assert len(executions) == 3
    assert all(call["cached"] for call in replay.calls)
