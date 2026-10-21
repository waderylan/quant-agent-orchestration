"""Immutable request facts passed explicitly to each generation invocation."""
import uuid
from dataclasses import dataclass, field
from typing import Literal

GenerationProfile = Literal["codex", "api"]


@dataclass(frozen=True)
class RoutingContext:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    activity_id: str = "direct"
    phase: str = "worker"
    companies: int = 1
    years: int = 1
    output: str = ""
    evidence_kinds: tuple[str, ...] = ()
    source_conflict: bool = False

    @classmethod
    def from_state(cls, state, *, activity_id="direct", phase="worker", output=""):
        question = state.get("original_question", state.get("question", "")).lower()
        return cls(request_id=state.get("generation_request_id") or uuid.uuid4().hex,
                   activity_id=activity_id, phase=phase,
                   companies=len(state.get("companies", [])) or 1,
                   years=len(state.get("years", [])) or 1, output=output,
                   evidence_kinds=tuple(sorted({s[0] for s in state.get("evidence", {}) if s})),
                   source_conflict=any(word in question for word in ("amend", "10-k/a", "source conflict")))
