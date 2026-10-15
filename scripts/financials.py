"""Collect, query, inspect, or independently run the Financial Data worker."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.financial_data import FINANCIALS, METRICS, FinancialStore, collect_financials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=FINANCIALS)
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--refresh", action="store_true")
    sub.add_parser("status")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("observation_id")
    for name in ("query", "agent"):
        query = sub.add_parser(name)
        query.add_argument("--company", nargs="+", required=True)
        query.add_argument("--year", nargs="+", type=int, required=True)
        if name == "query":
            query.add_argument("--metric", nargs="+", default=list(METRICS))
            query.add_argument("--period", default="FY")
            query.add_argument("--basis", default="annual")
        else:
            query.add_argument("question")
    args = parser.parse_args()
    store = FinancialStore(args.data.resolve())
    if args.command == "collect":
        result = collect_financials(args.data.resolve(), refresh=args.refresh)
    elif args.command == "status":
        rows = list(store.observations.values())
        result = {
            "observations": len(rows),
            "available": sum(r["status"] == "available" for r in rows),
        }
    elif args.command == "inspect":
        result = store.inspect(args.observation_id)
    elif args.command == "query":
        result = store.query(
            args.company,
            args.year,
            metrics=args.metric,
            period=args.period,
            basis=args.basis,
        )
    else:
        from src.financial_workflow import financial_turn

        result = asyncio.run(
            financial_turn(
                store,
                {
                    "question": args.question,
                    "companies": args.company,
                    "years": args.year,
                },
                lambda e: print(json.dumps(e), flush=True),
            )
        )
        if result.get("error"):
            raise SystemExit(result["error"])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
