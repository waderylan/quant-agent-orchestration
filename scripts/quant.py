"""Run Quant independently, inspect an analysis ledger, or replay its generated code."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.analysis_artifacts import ArtifactStore
from src.financial_data import FINANCIALS, FinancialStore
from src.quant_analysis import run_isolated, validate_results
from src.quant_workflow import direct_inputs, quant_turn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=FINANCIALS)
    parser.add_argument("--artifacts", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    agent = sub.add_parser("agent")
    agent.add_argument("question")
    agent.add_argument("--company", nargs="+", required=True)
    agent.add_argument("--year", nargs="+", type=int, required=True)
    for name in ("inspect", "replay"):
        command = sub.add_parser(name)
        command.add_argument("bundle_id")
    args = parser.parse_args()
    artifacts = ArtifactStore(args.artifacts)
    if args.command == "agent":
        state = {
            "question": args.question,
            "companies": args.company,
            "years": args.year,
        }
        state["financial_sources"] = direct_inputs(
            FinancialStore(args.data.resolve()), state
        )
        result = asyncio.run(
            quant_turn(
                state, lambda e: print(json.dumps(e), flush=True), artifacts=artifacts
            )
        )
        if result.get("error"):
            raise SystemExit(result["error"])
    else:
        bundle = artifacts.load(args.bundle_id)
        if args.command == "replay":
            actual = validate_results(
                run_isolated(bundle["code"], bundle["sources"]), bundle["sources"]
            )
            if actual != bundle["calculations"]:
                raise SystemExit(
                    "Replayed calculations differ from the recorded ledger"
                )
            result = {
                "bundle_id": args.bundle_id,
                "replayed_calculations": len(actual),
                "passed": True,
            }
        else:
            result = bundle
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
