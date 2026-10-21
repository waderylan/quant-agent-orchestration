"""Bounded real-worker comparisons with identical inputs and normal spending guards."""
import argparse
import asyncio
import json
import sys
from functools import partial
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import generation, provider_models, provider_policy
from src.financial_data import FinancialStore
from src.financial_workflow import financial_turn
from src.generation_context import RoutingContext
from src.research_index import ResearchIndex
from src.research_workflow import research_turn


async def run(output):
    load_dotenv()
    index, financials = ResearchIndex(), FinancialStore()
    report = {"kind": "Controlled real-worker development comparison, not RAGAS", "cases": []}
    cases = [
        ("financial", "What was AMD's reported FY2025 GAAP revenue? Give the exact value and cite the source. No web.",
         [provider_models.NVIDIA_SUPER, provider_models.NEBIUS_DEEPSEEK], ["AMD"], [2025]),
        ("filing", "What did Intel's FY2024 annual filing say about its foundry strategy? Use only the filings and cite the source.",
         [provider_models.NVIDIA_SUPER, provider_models.NEBIUS_DEEPSEEK], ["INTC"], [2024]),
    ]
    for kind, question, models, companies, years in cases:
        for model in models:
            events = []
            reason = "Same question, sources and tools; selected comparison model"
            selected = (provider_policy.reasoning("controlled_comparison", reason)
                        if model == provider_models.NEBIUS_DEEPSEEK else provider_policy.fallback(reason))
            state = {"question": question, "companies": companies, "years": years}
            model_stream = partial(generation.stream, profile="api", routing_context=RoutingContext(
                companies=len(companies), years=len(years), output="financial_inputs" if kind == "financial" else "filing_explanation"))
            started = asyncio.get_running_loop().time()
            result, error = None, None
            try:
                with patch.object(provider_policy, "route", return_value=selected):
                    result = await financial_turn(financials, state, events.append, model_stream=model_stream) if kind == "financial" else await research_turn(index, state, events.append, model_stream=model_stream)
            except (RuntimeError, ValueError, TimeoutError) as failure:
                error = str(failure)
            row = {"kind": kind, "question": question, "selected_model": model, "result": result,
                   "error": error, "seconds": round(asyncio.get_running_loop().time()-started, 3), "events": events}
            report["cases"].append(row)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"kind": kind, "model": model, "error": error,
                              "worker_error": result.get("error") if result else None, "seconds": row["seconds"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/providers/comparison.json"))
    asyncio.run(run(parser.parse_args().output))
