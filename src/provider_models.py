"""Pinned identifiers and verified limits for the two serving endpoints."""
from dataclasses import dataclass
from decimal import Decimal

NVIDIA_SUPER = "nvidia/nemotron-3.5-super-vl-120b-a12b"
NEBIUS_DEEPSEEK = "deepseek-ai/DeepSeek-V4-Flash-0731"


@dataclass(frozen=True)
class Limits:
    context: int
    planner_output: int
    output: int
    input_price: Decimal = Decimal(0)
    output_price: Decimal = Decimal(0)


LIMITS = {
    NVIDIA_SUPER: Limits(1048576, 2048, 4096),
    # Hidden reasoning tokens count toward completion limits and output cost; generous
    # headroom prevents truncated reasoning (finish_reason=length) on large contexts.
    NEBIUS_DEEPSEEK: Limits(1024000, 16384, 32768, Decimal("0.00000014"), Decimal("0.00000028")),
}
