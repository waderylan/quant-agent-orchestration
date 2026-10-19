"""Capture real application answers against a fixed human-question dataset."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn, wait_ready
from src.live_mcp import UsageLedger, sanitized
from src.source_collection import ROOT, now, write_json, digest

DEVELOPMENT = [
    {"id": "broad", "question": "what has happened with qualcomm lately", "companies": ["QCOM"], "years": [2025]},
    {"id": "acquisitions", "question": "What has happened with qualcomm and its acquisitions lately", "companies": ["QCOM"], "years": [2025]},
    {"id": "reaction", "question": "explain qualcomms revenue change from the filinings then research what the public thought of it", "companies": ["QCOM"], "years": [2024, 2025]},
]


async def run(args):
    ledger = UsageLedger()
    budget_path = Path(args.budget)
    if not budget_path.exists():
        initial = ledger.snapshot()
        write_json(budget_path, {"initial_calls": len(initial["calls"]), "initial_reserved": initial["reserved_credits"], "max_tavily_calls": 200})
    baseline = json.loads(budget_path.read_text(encoding="utf-8"))
    cases = json.loads(Path(args.dataset).read_text(encoding="utf-8")) if args.dataset else DEVELOPMENT
    if isinstance(cases, dict):
        cases = cases["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] in args.case]
    record = {"checked_at": now(), "profile": "Actual native application, local Codex generation, real Tavily/cache; not deployment-provider evaluation", "dataset_sha256": digest(json.dumps(cases, sort_keys=True).encode()), "cases": []}
    async with httpx.AsyncClient(base_url=args.url, timeout=600) as client:
        await wait_ready(client)
        semaphore = asyncio.Semaphore(args.concurrency)
        async def capture(case):
            async with semaphore:
                spent = len(ledger.snapshot()["calls"]) - baseline["initial_calls"]
                if spent + 7 * args.concurrency > baseline["max_tavily_calls"]:
                    raise RuntimeError("Authorized 200-call Tavily ceiling would be exceeded")
                turn = await capture_turn(client, case["question"], case["companies"], case["years"])
                record["cases"].append({"id": case["id"], "companies": case["companies"], "years": case["years"], **turn})
                current = ledger.snapshot()
                record["tavily_calls_since_start"] = len(current["calls"]) - baseline["initial_calls"]
                record["credits_reserved_since_start"] = current["reserved_credits"] - baseline["initial_reserved"]
                write_json(Path(args.output), sanitized(record))
                print(json.dumps({"id": case["id"], "status": turn["terminal"]["data"]["status"], "seconds": turn.get("seconds"), "sources": len(turn["sources"]), "calls_used": record["tavily_calls_since_start"]}), flush=True)
        await asyncio.gather(*(capture(case) for case in cases))


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8088")
    parser.add_argument("--dataset")
    parser.add_argument("--budget", default="artifacts/usefulness-budget.json")
    parser.add_argument("--case", action="append")
    parser.add_argument("--concurrency", type=int, choices=(1, 2), default=2)
    parser.add_argument("--output", default="artifacts/usefulness-development.json")
    asyncio.run(run(parser.parse_args()))
