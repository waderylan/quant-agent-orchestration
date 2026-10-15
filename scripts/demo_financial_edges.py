"""Actual API checks for quarter/YTD selection, missing inputs, and request isolation."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn
from src.financial_data import FinancialStore
from src.financial_workflow import financial_turn
from src.source_collection import ROOT, now, write_json


async def main(args):
    async with httpx.AsyncClient(base_url=args.url, timeout=240) as client:
        direct_events = []
        missing = await financial_turn(
            FinancialStore(),
            {
                "question": "Show AMD FY2025 Q2-only operating cash flow",
                "companies": ["AMD"],
                "years": [2025],
            },
            direct_events.append,
        )
        missing["execution_scope"] = (
            "direct Financial Data; the application uses Quant for this derivation"
        )
        missing["passed"] = "not zero" in missing.get("error", "") and not any(
            e["type"] == "trace" and e["data"].get("provider") for e in direct_events
        )
        # Run concurrent scopes; request-local F IDs must resolve to their own company.
        questions = [
            (
                "NVDA",
                2026,
                "Show NVIDIA FY2026 Q2-only revenue in exact USD, with actual dates and sources.",
            ),
            (
                "AMD",
                2025,
                "Show AMD FY2025 Q2 year-to-date operating cash flow in exact USD, with actual dates and sources.",
            ),
        ]
        turns = await asyncio.gather(
            *[capture_turn(client, q, [c], [y]) for c, y, q in questions]
        )
        for turn, (company, year, _) in zip(turns, questions):
            expected_basis = "quarter" if company == "NVDA" else "ytd"
            sources = turn["sources"]
            turn["passed"] = (
                turn["terminal"]["data"]["status"] == "completed"
                and bool(sources)
                and all(
                    s["company"] == company
                    and s["fiscal_year"] == year
                    and s["period"] == "Q2"
                    and s["basis"] == expected_basis
                    for s in sources
                )
            )
        report = {
            "checked_at": now(),
            "missing_cash_flow": missing,
            "concurrent_scopes": turns,
        }
        report["passed"] = missing["passed"] and all(t["passed"] for t in turns)
        write_json(args.output, report)
        print(
            json.dumps(
                {
                    "passed": report["passed"],
                    "missing_cash_flow": missing["passed"],
                    "concurrent_scopes": [t["passed"] for t in turns],
                }
            )
        )
        if not report["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8085")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/research/M5_EDGE_RESULTS.json"
    )
    asyncio.run(main(parser.parse_args()))
