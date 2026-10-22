"""Capture matched M12 application cases; generation defaults to local Codex."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn, wait_ready
from src.live_mcp import sanitized, UsageLedger
from src.source_collection import ROOT, digest, now, write_json
from main import Question


DEVELOPMENT = [
    {"id": "risk-amd", "question": "What changed in AMD's export-control risks between FY2024 and FY2025? Give me the important differences and whether those risks actually showed up after the filing.", "companies": ["AMD"], "years": [2024, 2025]},
    {"id": "risk-qcom", "question": "Did Qualcomm's customer-concentration risk change from FY2024 to FY2025, or is it mostly the same warning? Give me a concise risk brief.", "companies": ["QCOM"], "years": [2024, 2025]},
    {"id": "official-amd", "question": "Is the export-control risk in AMD's FY2025 10-K still current? Check for an official update and explain what it changes about the filing's warning.", "companies": ["AMD"], "years": [2025]},
    {"id": "full-amd", "question": "For AMD compare FY2024 and FY2025 revenue and operating income, calculate revenue growth and operating margins, explain the filing drivers, compare the main export-control risk changes, and tell me what has happened since the newer filing. Keep it useful and concise.", "companies": ["AMD"], "years": [2024, 2025]},
]


def runtime_hashes():
    paths = [ROOT / "main.py", *sorted((ROOT / "src").glob("*.py")), *sorted((ROOT / "prompts").glob("*.md")), *sorted((ROOT / "web").glob("*.*"))]
    return {str(path.relative_to(ROOT)).replace("\\", "/"): digest(path.read_bytes()) for path in paths if path.is_file()}


async def capture(args):
    cases = json.loads(Path(args.dataset).read_text(encoding="utf-8")) if args.dataset else DEVELOPMENT
    cases = cases["cases"] if isinstance(cases, dict) else cases
    if args.case:
        cases = [row for row in cases if row["id"] in args.case]
    if not cases:
        raise ValueError("No matching evaluation cases; check --case identifiers")
    for case in cases:
        try:
            Question.model_validate({k: case[k] for k in ("question", "companies", "years")})
        except (KeyError, ValueError):
            raise ValueError(f"Case {case.get('id')} does not satisfy the chat request schema") from None
    output = Path(args.output)
    frozen_runtime = runtime_hashes()
    report = {"checked_at": now(), "profile": args.profile, "method": "Matched native FastAPI/SSE cases; actual generation and Tavily/cache, not formal RAGAS or Cloud Run", "dataset_sha256": digest(json.dumps(cases, sort_keys=True).encode()), "cases": []}
    report["runtime_hashes"] = frozen_runtime
    if args.resume and output.exists():
        report = json.loads(output.read_text(encoding="utf-8"))
        if report["dataset_sha256"] != digest(json.dumps(cases, sort_keys=True).encode()) or report["profile"] != args.profile:
            raise ValueError("Resume dataset/profile differs from its recorded capture")
    completed = {(row["variant"], row["id"]) for row in report["cases"]}
    for variant in args.variant:
        name, url = variant.split("=", 1)
        async with httpx.AsyncClient(base_url=url, timeout=900) as client:
            await wait_ready(client)
            for case in cases:
                if (name, case["id"]) in completed:
                    continue
                ledger_before = UsageLedger().snapshot()
                turn = await capture_turn(client, case["question"], case["companies"], case["years"], generation_profile=args.profile, include_events=True)
                ledger_after = UsageLedger().snapshot()
                calls = [e["data"] for e in turn["trace"] if e["type"] == "trace" and e["data"].get("node") == "live_mcp"]
                inspections = []
                for source in turn["sources"]:
                    if source.get("inspection_url"):
                        response = await client.get(source["inspection_url"])
                        inspections.append({"source_id": source["source_id"], "status": response.status_code})
                row = {"id": case["id"], "variant": name, "companies": case["companies"], "years": case["years"], **turn,
                       "live_calls": calls, "estimated_uncached_credits": 2 * sum(not c.get("cache") and c.get("outcome") in ("returned", "provider_error", "transport_failure") for c in calls),
                       "ledger_credit_delta": ledger_after["estimated_credits"] - ledger_before["estimated_credits"],
                       "ledger_note": "Two credits per uncached attempted tool is an estimate, not an account bill. Per-host delta can include concurrent captures; call traces attribute this request.",
                       "inspections": inspections}
                report["cases"].append(row)
                report["runtime_unchanged"] = runtime_hashes() == frozen_runtime
                write_json(output, sanitized(report))
                print(json.dumps({"variant": name, "id": case["id"], "status": turn["terminal"]["data"].get("status"), "seconds": turn["seconds"], "calls": len(calls), "credits_estimate": row["estimated_uncached_credits"]}), flush=True)
    return report


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", action="append", required=True, help="name=http://127.0.0.1:port; separate processes isolate each comparison setting")
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--case", action="append")
    parser.add_argument("--profile", choices=("codex", "api"), default="codex")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("artifacts/m12/development.json"))
    asyncio.run(capture(parser.parse_args()))
