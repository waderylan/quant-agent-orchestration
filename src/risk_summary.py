"""Complete original risk inventories, exact spans, and bounded comparison tools.

Alignment is evidence navigation, not a semantic classifier. Only exact normalized
matches establish unchanged wording. Unmatched spans remain candidates until read
against both complete inventories; quarterly omissions never establish removals.
"""

from __future__ import annotations

import json
import re
from contextlib import aclosing
from difflib import SequenceMatcher
from datetime import date
from typing import TypedDict, Literal

from src.codex_model import stream as codex_stream
from src.response_contract import OUTCOME_TOOL, OutcomeTools, checked_answer
from src.source_collection import ROOT, digest


class RiskChange(TypedDict):
    classification: Literal["added", "removed", "changed", "relocated", "unchanged"]
    before: str | None
    after: str | None
    rationale: str


def normalize(text: str) -> str:
    # Ignore extraction page furniture and whitespace, never wording or numbers.
    text = re.sub(r"(?m)^\s*(?:\[PDF page \d+\]|Table of Contents|\d+)\s*$", "", text)
    return " ".join(text.split())


def section(index, document_id: str) -> dict:
    index.collection()  # Fail stale index manifests even though this path reads originals.
    doc = index.documents[document_id]
    bounds = doc["extraction"].get("sections", {}).get("risk_factors", {})
    text = index.text(doc)  # Hash check before trusting offsets or an absence.
    start, end = bounds.get("start"), bounds.get("end")
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        raise ValueError("Insufficient evidence: complete risk section unavailable")
    return {
        **{k: doc.get(k) for k in ("document_id", "company", "fiscal_year", "fiscal_start", "fiscal_end", "period_end", "form", "accession", "version", "canonical_url")},
        "section": "risk_factors", "start": start, "end": end,
        "text_sha256": doc["extraction"]["text_sha256"],
        "text": text[start:end], "original_url": f"/api/originals/{document_id}",
        "retrieval_url": doc["body"]["retrieval_url"],
        "complete_section": True,
        "omission_proves_removal": doc.get("form") == "10-K" and doc.get("version") == "original",
    }


def inspect_span(index, document_id: str, start: int, end: int) -> dict:
    full = section(index, document_id)
    if not full["start"] <= start < end <= full["end"]:
        raise ValueError("Risk span outside complete section")
    text = index.text(index.documents[document_id])
    return {**full, "start": start, "end": end, "text": text[start:end],
            "context_start": max(full["start"], start - 300),
            "context": text[max(full["start"], start - 300):min(full["end"], end + 300)],
            "complete_section": start == full["start"] and end == full["end"]}


def paragraphs(full: dict) -> list[dict]:
    # Prepared HTML has one line per block; PDF prose wraps within blank-line blocks.
    separator = r"\n\s*\n" if "[PDF page " in full["text"] else r"\n"
    result, left = [], 0
    for match in [*re.finditer(separator, full["text"]), None]:
        right = match.start() if match else len(full["text"])
        raw = full["text"][left:right]
        if len(normalize(raw)) >= 80:
            result.append({"start": full["start"] + left, "end": full["start"] + right, "text": raw})
        left = match.end() if match else right
    return result


def align(before: list[dict], after: list[dict]) -> list[dict]:
    """Global exact matches first; subject candidates never prove addition/removal."""
    old, new = [normalize(p["text"]) for p in before], [normalize(p["text"]) for p in after]
    old_tokens, new_tokens = [s.split() for s in old], [s.split() for s in new]
    old_sets, new_sets = list(map(set, old_tokens)), list(map(set, new_tokens))
    used, pairs = set(), []
    pending = []
    for i, text in enumerate(old):
        matches = [j for j, other in enumerate(new) if j not in used and text == other]
        if matches:
            j = min(matches, key=lambda j: abs(j / max(1, len(new)) - i / max(1, len(old))))
            used.add(j)
            pairs.append({"before_index": i, "after_index": j, "alignment": "exact", "similarity": 1.0})
        else:
            pending.append(i)
    for i in pending:
        # Token overlap only prunes candidates; character ratio ranks wording similarity.
        words = old_sets[i]
        candidates = [(len(words & new_sets[j]) / max(1, len(words | new_sets[j])), j) for j in range(len(new)) if j not in used]
        scores = [(SequenceMatcher(None, old_tokens[i], new_tokens[j], autojunk=False).ratio(), j) for _, j in sorted(candidates, reverse=True)[:6]]
        score, j = max(scores, default=(0, -1))
        if score >= .55:
            used.add(j)
            pairs.append({"before_index": i, "after_index": j, "alignment": "wording_candidate", "similarity": round(score, 4)})
        else:
            pairs.append({"before_index": i, "after_index": None, "alignment": "unresolved_before"})
    pairs.extend({"before_index": None, "after_index": j, "alignment": "unresolved_after"} for j in range(len(new)) if j not in used)
    return pairs


class RiskTools:
    max_tool_calls = 16

    def __init__(self, index, companies, years, *, source_offset=0):
        self.index, self.companies, self.years = index, companies, years
        self.sources, self.sections, self.comparisons, self.changes = {}, {}, {}, []
        self.offset = source_offset

    def register(self, full, span=None):
        row = {**full, **(span or {})}
        existing = next((sid for sid, s in self.sources.items() if (s["document_id"], s["start"], s["end"]) == (row["document_id"], row["start"], row["end"])), None)
        sid = existing or f"S{self.offset + len(self.sources) + 1}"
        self.sources[sid] = {**row, "source_id": sid, "inspection_url": f"/api/risks/{row['document_id']}?start={row['start']}&end={row['end']}", "chunk_id": digest(f"risk:{row['document_id']}:{row['text_sha256']}:{row['start']}:{row['end']}".encode())}
        return sid

    def prepare(self):
        gaps = []
        for company in self.companies:
            for year in sorted(self.years):
                docs = [d for d in self.index.documents.values() if d.get("company") == company and d.get("fiscal_year") == year and d.get("form") == "10-K" and d.get("version") == "original"]
                if len(docs) != 1:
                    gaps.append(f"{company} FY{year}: unique complete original annual risks unavailable")
                    continue
                try:
                    full = section(self.index, docs[0]["document_id"])
                except (ValueError, KeyError, FileNotFoundError) as error:
                    gaps.append(f"{company} FY{year}: {error}")
                    continue
                self.sections[company, year] = (full, self.register(full), paragraphs(full))
            for a, b in zip(sorted(self.years), sorted(self.years)[1:]):
                if (company, a) not in self.sections or (company, b) not in self.sections:
                    continue
                before, bsid, bp = self.sections[company, a]
                after, asid, ap = self.sections[company, b]
                pairs = align(bp, ap)
                for pair in pairs:
                    pair["before"] = self.register(before, bp[pair["before_index"]]) if pair["before_index"] is not None else None
                    pair["after"] = self.register(after, ap[pair["after_index"]]) if pair["after_index"] is not None else None
                self.comparisons[f"{company}:{a}:{b}"] = {"company": company, "before_section": bsid, "after_section": asid, "pairs": pairs}
        return gaps

    def __call__(self, name, args):
        if name == "inspect_risk":
            s = self.sources[args["source_id"]]
            return {"source_id": s["source_id"], **inspect_span(self.index, s["document_id"], s["start"], s["end"])}
        if name == "risk_pairs":
            pairs = self.comparisons[args["comparison"]]["pairs"]
            offset = args.get("offset", 0)
            if type(offset) is not int or not 0 <= offset <= len(pairs):
                raise ValueError("Invalid comparison offset")
            return {"pairs": [{**p, "before_text": self.sources[p["before"]]["text"] if p["before"] else None, "after_text": self.sources[p["after"]]["text"] if p["after"] else None} for p in pairs[offset:offset + 12]], "total": len(pairs), "next_offset": offset + 12 if offset + 12 < len(pairs) else None}
        if name == "record_risk_change":
            change: RiskChange = args
            if set(args) != {"classification", "before", "after", "rationale"} or args["classification"] not in ("added", "removed", "changed", "relocated", "unchanged"):
                raise ValueError("Invalid risk classification")
            old, new = (self.sources.get(args[k]) for k in ("before", "after"))
            if not old or not new or old["company"] != new["company"] or old["fiscal_year"] >= new["fiscal_year"]:
                raise ValueError("Classification needs ordered same-company before and after evidence; use complete section for an absence")
            kind = args["classification"]
            if kind in ("added", "removed"):
                absent, present = (old, new) if kind == "added" else (new, old)
                if not absent["complete_section"] or not absent["omission_proves_removal"]:
                    raise ValueError("Absence requires a complete original annual section, never a quarterly omission")
                if normalize(present["text"]) in normalize(absent["text"]):
                    raise ValueError("Language exists in comparison section; cannot label absent")
            if kind in ("unchanged", "relocated") and normalize(old["text"]) != normalize(new["text"]):
                raise ValueError("Unchanged/relocated requires matching wording; rephrasing is changed")
            if not isinstance(args["rationale"], str) or not 20 <= len(args["rationale"]) <= 1200:
                raise ValueError("Supply a concrete wording/subject rationale")
            self.changes.append(change)
            return {"recorded": change, "qualification": "Language classification; absence of an exact phrase does not prove a new economic exposure"}
        raise ValueError("Unknown Risk Summary tool")


def tool(name, description, properties, required):
    return {"type": "function", "name": name, "description": description, "inputSchema": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}


TOOLS = [
    tool("inspect_risk", "Read exact risk span or COMPLETE section; full sections establish the comparison universe.", {"source_id": {"type": "string"}}, ["source_id"]),
    tool("risk_pairs", "Page subject/wording candidates from exhaustive section alignment. Unmatched does not mean added/removed.", {"comparison": {"type": "string"}, "offset": {"type": "integer"}}, ["comparison"]),
    tool("record_risk_change", "Record an inspected material classification with both citations. Added/removed uses complete absent-side section. Rephrasing is changed, not new exposure.", {"classification": {"type": "string", "enum": ["added", "removed", "changed", "relocated", "unchanged"]}, "before": {"type": "string"}, "after": {"type": "string"}, "rationale": {"type": "string"}}, ["classification", "before", "after", "rationale"]),
]


async def risk_turn(index, state, writer, *, model_stream=codex_stream, emit_answer=True):
    tools = RiskTools(index, state["companies"], state["years"], source_offset=state.get("source_offset", 0))
    quarterly = bool(re.search(r"\b(?:Q[1-4]|quarter\w*|10-Q)\b", state["question"], re.I))
    gaps = [] if quarterly else tools.prepare()
    if not quarterly and len(set(state["years"])) < 2:
        gaps.append("Risk change comparison needs two selected fiscal years; one annual inventory cannot establish change")
    if quarterly:
        quarter = re.search(r"\bQ([1-4])\b", state["question"], re.I)
        requested_period = f"Q{quarter[1]}" if quarter else None
        for doc in index.documents.values():
            if doc.get("company") in state["companies"] and doc.get("fiscal_year") in state["years"] and doc.get("form") == "10-Q":
                # Inventory period_end determines temporal ordering. Never use the
                # later full-year filing as information available in an earlier quarter.
                if requested_period:
                    elapsed = (date.fromisoformat(doc["period_end"]) - date.fromisoformat(doc["fiscal_start"])).days + 1
                    if abs(elapsed - int(quarter[1]) * 91) > 20 or int(quarter[1]) == 4:
                        continue
                try:
                    full = section(index, doc["document_id"])
                    tools.register(full)
                    tools.sections[doc["company"], doc["period_end"]] = (full, None, [])
                    prior = index.documents.get(doc.get("prior_annual_document_id"))
                    if not prior:
                        annuals = [d for d in index.documents.values() if d.get("company") == doc["company"] and d.get("form") == "10-K" and d.get("version") == "original" and d["period_end"] < doc["period_end"]]
                        prior = max(annuals, key=lambda d: d["period_end"], default=None)
                    if prior:
                        tools.register(section(index, prior["document_id"]))
                    else:
                        gaps.append(f"{doc['company']} {doc['period_end']}: prior annual risk context unavailable")
                except (ValueError, KeyError) as error:
                    gaps.append(f"{doc['company']} {doc['period_end']}: {error}")
        if not tools.sections:
            gaps.append("Requested quarterly risk section unavailable; Q4 is reported in the annual 10-K")
    if not tools.sections:
        message = "Insufficient evidence: " + "; ".join(gaps)
        if emit_answer:
            writer({"type": "token", "data": message})
        return {"answer": message, "partial": True, "missing_outputs": gaps, "risk_sources": {}, "risk_changes": []}
    overview = [{**{k: s[k] for k in ("source_id", "company", "fiscal_year", "fiscal_start", "fiscal_end", "form", "accession", "start", "end", "complete_section")}, "preview": s["text"][:180]} for s in tools.sources.values() if s["complete_section"]]
    comparisons = [{k: v for k, v in c.items() if k != "pairs"} | {"comparison": key, "pair_count": len(c["pairs"])} for key, c in tools.comparisons.items()]
    full_texts, characters = [], 0
    for s in tools.sources.values():
        if s["complete_section"]:
            if characters + len(s["text"]) <= 600000:
                full_texts.append({"source_id": s["source_id"], "untrusted_complete_original_section": s["text"]})
                characters += len(s["text"])
            else:
                gaps.append(f"{s['company']} FY{s['fiscal_year']} {s['form']}: complete text exceeds bounded context; inspect separately")
    prompt = (ROOT / "prompts/risk_summary.md").read_text(encoding="utf-8") + "\n" + json.dumps({"question": state["question"], "complete_sections": overview, "comparisons": comparisons, "missing": gaps, "quarterly": quarterly, "original_section_texts": full_texts})
    outcome, answer = OutcomeTools(tools), ""
    async with aclosing(model_stream(prompt, [*TOOLS, OUTCOME_TOOL], outcome, agent="Risk Summary", reason="Compare complete original filing risk inventories; preserve exact before/after evidence")) as stream:
        async for event in stream:
            if event["type"] == "token":
                answer += event["data"]
            if emit_answer or event["type"] != "token":
                writer(event)
    answer, cited = checked_answer(answer, tools.sources, writer if emit_answer else lambda e: None)
    if not cited or cited - tools.sources.keys():
        raise ValueError("Risk Summary citation validation failed")
    for sid in cited:
        s = tools.sources[sid]
        if inspect_span(index, s["document_id"], s["start"], s["end"])["text"] != s["text"]:
            raise ValueError("Risk citation changed during generation")
    gaps += outcome.missing
    if tools.comparisons and not tools.changes:
        gaps.append("No material risk classification was registered; comparison remains unverified")
    if emit_answer:
        writer({"type": "sources", "data": [tools.sources[s] for s in sorted(cited, key=lambda s: int(s[1:]))]})
    return {"answer": answer, "risk_answer": answer, "risk_sources": tools.sources, "risk_changes": tools.changes, "partial": bool(gaps), "missing_outputs": gaps, "clarification": outcome.status == "clarification", "citation_verified": True}
