"""Reusable ingestion, retrieval, passage inspection and direct-agent CLI."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.research_index import INDEX, ResearchIndex
from src.source_collection import DEFAULT_OUTPUT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Verified M2 corpus directory",
    )
    parser.add_argument(
        "--index", type=Path, default=INDEX, help="Persistent Chroma directory"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest")
    sub.add_parser("status")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("chunk_id")
    for name in ("search", "ask", "agent"):
        query = sub.add_parser(name)
        query.add_argument("question")
        query.add_argument("--company", nargs="+", required=True)
        query.add_argument("--year", nargs="+", type=int, required=True)
        if name == "search":
            query.add_argument("--section", choices=["mda", "risk_factors", "other"])
            query.add_argument("--version", choices=["original", "amendment"])
            query.add_argument(
                "--form", choices=["10-K", "10-Q", "10-K/A", "Earnings release"]
            )
    args = parser.parse_args()
    index = ResearchIndex(args.corpus.resolve(), args.index.resolve())
    if args.command == "ingest":
        result = index.ingest()
    elif args.command == "status":
        result = {"coverage": index.coverage(), "chunks": index.collection().count()}
    elif args.command == "inspect":
        result = index.inspect(args.chunk_id)
    elif args.command == "search":
        result = index.search(
            args.question,
            args.company,
            args.year,
            section=args.section,
            version=args.version,
            form=args.form,
        )
    elif args.command == "agent":
        from src.research_workflow import research_turn, scope_error

        error = scope_error(args.question, args.company, args.year, index.coverage())
        if error:
            raise SystemExit(error)
        result = asyncio.run(
            research_turn(
                index,
                {
                    "question": args.question,
                    "companies": args.company,
                    "years": args.year,
                },
                lambda event: print(json.dumps(event), flush=True),
            )
        )
        print(json.dumps({"worker_result": result}))
        if result.get("error"):
            raise SystemExit(1)
        return
    else:
        from src.research_workflow import events
        from src.financial_data import FinancialStore

        async def ask():
            failed = False
            async for event in events(
                index,
                args.question,
                args.company,
                args.year,
                financials=FinancialStore(),
            ):
                print(json.dumps(event, ensure_ascii=True), flush=True)
                failed |= (
                    event["type"] == "complete"
                    and event["data"]["status"] != "completed"
                )
            return failed

        if asyncio.run(ask()):
            raise SystemExit(1)
        return
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
