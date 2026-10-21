"""Explicit task context and deterministic cost/capability routing."""
from dataclasses import asdict, dataclass
from src import provider_models
from src.generation_context import RoutingContext
POLICY = "m11-v1"


@dataclass(frozen=True)
class Route:
    provider: str
    model: str
    publisher: str
    rule: str
    reason: str
    context_limit: int

    def trace(self):
        return {**asdict(self), "policy": POLICY}


def route(context: RoutingContext, *, agent: str, input_bound: int) -> Route:
    complex_task = (context.companies > 1 or context.years > 1 or
                    context.source_conflict or context.output in ("risk_changes", "filing_explanation", "checked_calculations", "current_developments", "public_reaction", "official_update") or
                    len(context.evidence_kinds) > 1 or input_bound > 64000)
    if context.phase == "planner" or agent == "Request Planner":
        return Route("nvidia", provider_models.NVIDIA_LIGHTNING, "NVIDIA", "structured_plan",
                     "Bounded request decomposition on the smaller free model", 262144)
    if complex_task:
        return Route("nebius", provider_models.NEBIUS_QWEN, "Qwen", "complex_evidence",
                     "Comparison, source conflict, risk alignment, mixed evidence, or large context", 262144)
    if agent == "Answer Reviewer" or context.phase == "reviewer":
        return fallback("Independent review of the original request and cited evidence")
    if agent == "Financial Data" or context.output in ("financial_inputs", "narrow_lookup"):
        return fallback("Source-linked financial answers need the larger free model for citation compliance")
    return fallback("Grounded specialist synthesis and tool orchestration on the free model")


def fallback(reason: str) -> Route:
    return Route("nvidia", provider_models.NVIDIA_SUPER, "NVIDIA", "grounded_synthesis", reason, 1048576)
