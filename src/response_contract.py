"""Shared citation syntax and explicit worker completion reporting."""

from __future__ import annotations

import re

OUTCOME_TOOL = {
    "type": "function",
    "name": "report_outcome",
    "description": "Before answering, report whether every requested output is established. Valid citations alone do not make an answer complete. List missing outputs or clarification needed; never mark an unavailable calculation or company comparison complete.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["complete", "partial", "clarification"],
            },
            "missing": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
        },
        "required": ["status", "missing"],
        "additionalProperties": False,
    },
}


class OutcomeTools:
    """Keep tool access distinct while sharing the completion contract."""

    def __init__(self, handler):
        self.handler = handler
        self.status = None
        self.missing = ["Worker did not confirm completion of the requested outputs"]

    def __getattr__(self, name):
        return getattr(self.handler, name)

    def __call__(self, name, arguments):
        if name != "report_outcome":
            return self.handler(name, arguments)
        if not isinstance(arguments, dict) or set(arguments) != {"status", "missing"}:
            raise ValueError("Outcome requires status and missing outputs")
        status, missing = arguments["status"], arguments["missing"]
        if (
            status not in ("complete", "partial", "clarification")
            or not isinstance(missing, list)
            or len(missing) > 12
            or any(
                not isinstance(item, str) or not 1 <= len(item) <= 300
                for item in missing
            )
        ):
            raise ValueError("Invalid worker outcome")
        if (status == "complete") != (not missing):
            raise ValueError(
                "Incomplete outcomes require explicit missing outputs; complete outcomes cannot contain gaps"
            )
        self.status, self.missing = status, missing
        return {"status": status, "missing_outputs": missing}


def normalize_citations(answer, registered):
    """Expand bounded citation ranges; unbracket explicitly refuted unknown IDs.

    Positive claims retain unknown references and therefore still fail validation.
    A fake ID mentioned in a refusal is not an assertion that the source exists.
    """

    def expand(match):
        prefix, first, last = match.groups()
        first, last = int(first), int(last)
        if first <= last < first + 64:
            return "".join(f"[{prefix}{number}]" for number in range(first, last + 1))
        return match.group(0)

    answer = re.sub(r"\[([SFC])(\d+)\s*[–—-]\s*\1?(\d+)\]", expand, answer)

    def refuted(match):
        sid = match[1]
        if sid in registered:
            return match[0]
        after = answer[match.end() : match.end() + 100]
        before = answer[max(0, match.start() - 80) : match.start()]
        if re.match(
            r"\s+(?:is|was)\s+not\s+(?:a\s+)?(?:supplied|provided|registered|valid)\s+(?:source|citation|identifier)\b",
            after,
            re.I,
        ) or re.search(
            r"\b(?:fake|fabricated|invalid|unregistered)\s+(?:citation|source|identifier)\s*:?\s*$",
            before,
            re.I,
        ):
            return f"unverified identifier {sid}"
        return match[0]

    return re.sub(r"\[([SFC]\d+)\]", refuted, answer)


def checked_answer(answer, registered, writer):
    normalized = normalize_citations(answer, registered)
    if normalized != answer:
        writer({"type": "answer", "data": normalized})
    cited = set(re.findall(r"\[([SFC]\d+)\]", normalized))
    if re.search(r"\[[SFC]\d+\s*[–—-]", normalized):
        cited.add("invalid_citation_range")
    return normalized, cited
