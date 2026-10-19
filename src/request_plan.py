"""Bounded semantic request decomposition and an independent answer coverage check."""

import json
import re
from contextlib import aclosing
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, StrictBool
from typing import Literal

from src.source_collection import ROOT


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["financial_inputs", "checked_calculations", "filing_explanation", "risk_changes", "current_developments", "public_reaction", "official_update", "capabilities", "unsupported"]
    description: str = Field(min_length=1, max_length=350)
    timeframe: Literal["recent", "since_filing", "reaction", "specified"] | None = None
    year: int | None = Field(default=None, ge=2020, le=2100)
    start_date: str | None = None
    end_date: str | None = None


class RequestPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outputs: list[Output] = Field(min_length=1, max_length=8)
    timeframe: Literal["recent", "since_filing", "reaction", "specified"]
    start_date: str | None
    end_date: str | None


class OutputReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    addressed: StrictBool
    citations: list[str]
    missing: str


class AnswerReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[OutputReview]
    missing_requests: list[str]
    unsupported_claims: list[str]


async def structured(prompt, name, schema, model_stream, emit, *, agent):
    class Handler:
        max_tool_calls = 1
        value = None

        def __call__(self, tool, args):
            if tool != name or self.value is not None:
                raise ValueError("Submit the structured result exactly once")
            self.value = args
            return {"accepted": True}

    handler = Handler()
    tool = {"type": "function", "name": name, "description": "Submit the requested structured result once; no final prose.", "inputSchema": schema}
    async with aclosing(model_stream(prompt, [tool], handler, agent=agent, timeout=65, reason="Understand every requested output and check original-request coverage")) as events:
        async for event in events:
            if event["type"] == "trace":
                emit(event)
    if not isinstance(handler.value, dict):
        raise ValueError("Structured request result missing")
    return handler.value


async def decompose(state, model_stream, emit):
    prompt = (ROOT / "prompts/request_plan.md").read_text(encoding="utf-8")
    value = await structured(prompt + "\nRequest: " + json.dumps({**{k: state[k] for k in ("question", "companies", "years")}, "today": datetime.now(timezone.utc).date().isoformat()}), "submit_plan", RequestPlan.model_json_schema(), model_stream, emit, agent="Request Planner")
    plan = RequestPlan.model_validate(value).model_dump()
    for scope in [plan, *plan["outputs"]]:
        for key in ("start_date", "end_date"):
            if scope.get(key):
                datetime.strptime(scope[key], "%Y-%m-%d")
        if scope.get("start_date") and scope.get("end_date") and scope["start_date"] > scope["end_date"]:
            raise ValueError("Research dates are reversed")
    for number, output in enumerate(plan["outputs"], 1):
        output["id"] = f"R{number}"
    return plan


async def coverage(question, outputs, answer, sources, model_stream, emit, context=None):
    cited = set(re.findall(r"\[([SFCW]\d+)\]", answer))
    # Checked calculations retain their original inputs even when only the derived
    # measure belongs in the answer. Make that lineage available to the reviewer.
    pending = list(cited)
    while pending:
        source = sources.get(pending.pop(), {})
        for sid in source.get("source_ids", []):
            if sid in sources and sid not in cited:
                cited.add(sid)
                pending.append(sid)
    excerpts = []
    for sid, source in sources.items():
        if sid not in cited:
            continue
        excerpt = {**{k: source.get(k) for k in ("source_id", "company", "kind", "published_date", "date_source", "date_excerpt", "date_snapshot_id", "source_tier", "title", "value", "unit", "metric", "formula", "source_ids", "fiscal_year",
            # Exact periods, filing identity and basis let the reviewer check stated dates.
            "fiscal_start", "fiscal_end", "start", "end", "period", "basis", "accounting_basis", "revision_basis", "form", "filed", "accession")}, "text": source.get("text", "")[:12000]}
        remaining, observations = 24000, []
        for row in source.get("observations", []):
            if row.get("text") == source.get("text") or not remaining:
                continue
            text = row.get("text", "")[:min(12000, remaining)]
            remaining -= len(text)
            observations.append({**{k: row.get(k) for k in ("snapshot_id", "tool", "published_date", "date_source", "date_excerpt")}, "text": text})
        excerpt["observations"] = observations
        excerpts.append(excerpt)
    from src.capabilities import capability_request
    prompt = (ROOT / "prompts/answer_coverage.md").read_text(encoding="utf-8") + "\n" + json.dumps({"question": question, "required_outputs": outputs, "answer": answer, "implemented_capabilities": capability_request("What can this system do?")["answer"], "untrusted_source_excerpts": excerpts, **({"application_context": context} if context else {})})
    review = AnswerReview.model_validate(await structured(prompt, "submit_coverage", AnswerReview.model_json_schema(), model_stream, emit, agent="Answer Reviewer")).model_dump()
    rows = review.get("results", [])
    if len(rows) != len(outputs) or {r.get("id") for r in rows} != {o["id"] for o in outputs}:
        raise ValueError("Answer review omitted a requested output")
    missing = []
    for output in outputs:
        row = next(r for r in rows if r["id"] == output["id"])
        ids = row.get("citations", [])
        valid = output["kind"] == "capabilities" or bool(ids) and all(s in sources and s in cited for s in ids)
        if output["kind"] in ("current_developments", "public_reaction", "official_update"):
            valid = valid and any(s.startswith("W") for s in ids)
        row["addressed"] = row.get("addressed") is True and valid
        if not row.get("addressed") or not valid:
            missing.append(output["description"] + ": " + (row.get("missing") or "Not supported in the answer"))
    missing.extend(review.get("missing_requests", []))
    unsupported = [claim for claim in review.get("unsupported_claims", []) if claim and claim in answer]
    if unsupported:
        missing.append("Unsupported claims were removed; the cited evidence does not establish them.")
    return {"results": rows, "missing": list(dict.fromkeys(missing)), "unsupported_claims": unsupported}


def remove_unsupported(answer, claims):
    """Remove unsupported sentences without leaving a partial clause behind."""
    for claim in sorted(claims, key=len, reverse=True):
        while claim and claim in answer:
            start = answer.index(claim)
            end = start + len(claim)
            boundaries = [0, len(answer)]
            for match in re.finditer(r"(?<=[.!?])\s+|(?<=\])\s+(?=[A-Z])|\n+", answer):
                if "\n" not in match[0] and re.search(r"\b(?:Inc|Corp|Ltd|Co|Mr|Ms|Dr|U\.S|e\.g|i\.e)\.$", answer[:match.start()], re.I):
                    continue
                boundaries.append(match.end())
            claim_start = start
            start = max(i for i in boundaries if i <= start)
            end = end if claim.endswith((".", "!", "?")) else min(i for i in boundaries if i >= end)
            # Citations after a removed sentence's period belong to that sentence.
            if trailing := re.match(r"(?:[ \t]*\[[SFCW]\d+\])+", answer[end:]):
                end += trailing.end()
            # Keep a list marker when the rest of its line remains.
            line_end = answer.find("\n", end) if "\n" in answer[end:] else len(answer)
            marker = re.match(r"[ \t]*(?:[-*]|\d+\.)[ \t]+", answer[start:claim_start])
            if marker and answer[end:line_end].strip():
                start += marker.end()
                end += len(answer[end:line_end]) - len(answer[end:line_end].lstrip(" \t"))
            answer = answer[:start] + answer[end:]
    answer = re.sub(r"(?m)^\s*[-*]\s*$\n?", "", answer)
    answer = re.sub(r"(?m)^(?:Outside research|From the filings|Financial analysis|Changes in filing risks):\s*(?=\Z|(?:Outside research|From the filings|Financial analysis|Changes in filing risks):)", "", answer)
    return re.sub(r"\n{3,}", "\n\n", answer).strip()
