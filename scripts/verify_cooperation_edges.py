"""Actual concurrent API turns plus controlled failures through the same ASGI app."""

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn
from src.source_collection import ROOT, write_json, now


async def main(args):
    async with httpx.AsyncClient(base_url=args.url, timeout=600) as client:
        requests = [
            ("AMD", "Show AMD FY2025 GAAP revenue with actual dates."),
            ("QCOM", "Show Qualcomm FY2025 GAAP revenue with actual dates."),
        ]
        results = await asyncio.gather(
            *(capture_turn(client, q, [c], [2025]) for c, q in requests)
        )
        checks = []
        for (company, _), result in zip(requests, results):
            checks.append(
                result["terminal"]["data"]["status"] == "completed"
                and {s["company"] for s in result["sources"]} == {company}
            )
        assert all(checks)
        report = {
            "checked_at": now(),
            "kind": "Actual concurrent self-contained API turns with subscription Data workers",
            "turns": results,
            "company_isolation": checks,
        }
        write_json(args.output, report)
        print("Concurrent request isolation:", checks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8082")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/m9-concurrency.json"
    )
    asyncio.run(main(parser.parse_args()))
