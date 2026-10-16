"""Run sealed independent questions through actual POST/SSE and inspect evidence.

Uses the frozen review application. Live-provider reservations must remain unchanged.
Questions and criteria are preserved verbatim; automated checks are structural, not a
claim that arbitrary financial narrative is correct. Parent review adjudicates flags.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn, wait_ready
from src.market_mcp import UsageLedger
from src.source_collection import ROOT, digest, now, write_json


def condition_name(description):
    text = str(description).lower()
    if text in ("normal", "none", "", "baseline"):
        return "normal"
    if "inject" in text or "malicious" in text or "hostile" in text:
        return "source_prompt_injection"
    if "quota" in text or "429" in text:
        return "quota_error"
    if "timeout" in text or "time out" in text:
        return "worker_timeout_" + next((w for w in ("quant", "risk", "research", "data") if w in text), "buy")
    if "missing" in text and "estimate" in text:
        return "missing_estimates"
    if "negative" in text or "nonpositive" in text or "loss denominator" in text:
        return "negative_denominator"
    if "stale" in text:
        return "stale_quote"
    if "closed" in text:
        return "closed_quote"
    if "future" in text and ("quote" in text or "timestamp" in text):
        return "future_quote"
    if "symbol" in text and ("wrong" in text or "mismatch" in text or "substit" in text):
        return "wrong_quote_symbol"
    if "malformed" in text or "corrupt" in text:
        return "malformed_quote"
    if "contradict" in text or "conflict" in text or "incompatible" in text:
        return "contradictory_sources"
    if "split" in text:
        return "split_mismatch"
    return "normal"


ROUND_ONE_CONDITIONS = {
    "R1-003": "stale_quote", "R1-004": "negative_financials",
    "R1-008": "missing_estimates", "R1-009": "restricted_estimates",
    "R1-010": "relocated_risk", "R1-011": "quota_error",
    "R1-012": "worker_timeout_risk", "R1-014": "cancel_delayed_quote",
    "R1-017": "added_risk", "R1-020": "clarified_risk",
    "R1-019": "quarterly_risk_omission",
    "R1-021": "partial_risk", "R1-023": "q3_ytd_only",
    "R1-024": "conflicting_scale", "R1-025": "filing_injection",
    "R1-027": "parent_income", "R1-030": "mixed_units",
    "R1-029": "quarterly_category_missing",
    "R1-035": "closed_quote", "R1-040": "filing_injection",
    "R1-043": "q2_missing", "R1-047": "all_sources_missing",
}


async def cancelled_turn(client, case, condition):
    observed = []
    before = len((await client.get("/review/late-deliveries")).json())
    historical = False
    async with client.stream("POST", "/api/chat", json={"question": case["question"], "companies": case["companies"], "years": case["years"]}, headers={"X-Review-Condition": condition}) as response:
        response.raise_for_status()
        kind = None
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                kind = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                observed.append({"type": kind, "data": data})
                if kind == "trace" and data.get("node") == "worker_outcome" and data.get("worker") == "quant" and data.get("outcome") in ("completed", "partial") and data.get("evidence_count", 0):
                    historical = True
                if kind == "trace" and data.get("node") == "market_mcp" and historical:
                    break
                if kind == "complete":
                    break
    await asyncio.sleep(6)
    late = (await client.get("/review/late-deliveries")).json()[before:]
    started = historical and bool(late)
    return {"question": case["question"], "answer": "", "sources": [], "trace": observed, "terminal": {"type": "complete", "data": {"status": "cancelled_by_client" if started else "cancellation_condition_not_met"}}, "seconds": None, "cancelled_after_generation_started": started, "verified_historical_worker_completed": historical, "late_provider_deliveries": late}


async def main(args):
    sealed = json.loads(args.questions.read_text(encoding="utf-8-sig"))
    cases = sealed["cases"]
    if args.ids:
        cases = [c for c in cases if c["id"] in args.ids]
    assert len({c["id"] for c in cases}) == len(cases)
    ledger_before = UsageLedger().snapshot()["calls"]
    secrets = [v for k, v in dotenv_values(ROOT / ".env").items() if k.endswith("_API_KEY") and v]
    report = {"started_at": now(), "questions_sha256": digest(args.questions.read_bytes()), "kind": "Sealed independent questions through production POST/SSE, actual subscription generation, frozen market responses; controlled conditions labeled", "question_file": str(args.questions), "results": []}
    gate = asyncio.Semaphore(2)
    async with httpx.AsyncClient(base_url=args.url, timeout=900) as client:
        await wait_ready(client)
        guards = await client.get("/review/guards")
        report["review_service_guards"] = guards.json() if guards.status_code == 200 else {"note": "Initial diagnostic service predates explicit guards; MarketGateway frozen mode"}
        async def run(case):
            async with gate:
                condition = ROUND_ONE_CONDITIONS.get(case["id"], "normal") if case["id"].startswith("R1-") else condition_name(case.get("condition", "normal"))
                try:
                    if "cancel" in str(case.get("condition", "")).lower():
                        result = await cancelled_turn(client, case, condition)
                    elif case["id"] == "R1-013":
                        companion, result = await asyncio.gather(capture_turn(client, "Compare NVIDIA FY2025 and FY2026 annual revenue and risk changes", ["NVDA"], [2025, 2026]), capture_turn(client, case["question"], case["companies"], case["years"], headers={"X-Review-Condition": condition}))
                        returns = sorted([(r["monotonic"], "QCOM") for r in result["worker_return_times"]] + [(r["monotonic"], "NVDA") for r in companion["worker_return_times"]])
                        labels = [label for _, label in returns]
                        result["concurrent_companion"] = {"terminal": companion["terminal"], "source_companies": sorted({s.get("company") for s in companion["sources"] if s.get("company")}), "overlap_seconds": max(0, min(result["request_finished_monotonic"], companion["request_finished_monotonic"]) - max(result["request_started_monotonic"], companion["request_started_monotonic"])), "return_order": labels, "interleaved_returns": any(labels[i] != labels[i + 1] and labels[i] == labels[i + 2] for i in range(len(labels) - 2)), "cross_turn_leakage": any(s.get("company") not in (None, "NVDA") for s in companion["sources"]) or any(s.get("company") not in (None, "QCOM") for s in result["sources"])}
                    else:
                        result = await capture_turn(client, case["question"], case["companies"], case["years"], headers={"X-Review-Condition": condition})
                    checks = []
                    for source in result["sources"]:
                        if not source.get("inspection_url"):
                            continue
                        response = await client.get(source["inspection_url"])
                        checked = response.status_code == 200
                        if checked and source.get("kind") not in ("market_evidence", "valuation_input", "calculation", "financial_observation") and source.get("text"):
                            checked = response.json().get("text") == source["text"]
                        checks.append({"source_id": source["source_id"], "url": source["inspection_url"], "status": response.status_code, "passed": checked})
                    status = result["terminal"]["data"]["status"] if result.get("terminal") else "missing_terminal"
                    acceptable = case.get("acceptable_outcomes", ["completed", "partial", "needs_clarification", "coverage_gap"])
                    passed = status in acceptable and all(c["passed"] for c in checks)
                    if status == "cancelled_by_client":
                        passed = bool(result.get("cancelled_after_generation_started"))
                    encoded = json.dumps(result)
                    leaked = any(secret in encoded for secret in secrets)
                    assert not leaked, "Credential exposure detected; never persist the affected result"
                    result["source_checks"] = checks
                    row = {"case": case, "applied_condition": condition, "result": result, "structural_checks_passed": passed, "manual_semantic_review_required": True}
                except httpx.HTTPStatusError as error:
                    boundary = error.response.status_code == 422
                    row = {"case": case, "applied_condition": condition, "structural_checks_passed": boundary and "needs_clarification" in case.get("acceptable_outcomes", []), "manual_semantic_review_required": True, "result": {"terminal": {"type": "HTTP validation", "data": {"status": "needs_clarification" if boundary else "failed", "http_status": error.response.status_code}}, "answer": "", "sources": [], "validation_errors": error.response.json()}}
                except Exception as error:
                    # Do not persist exception text from arbitrary transports.
                    row = {"case": case, "applied_condition": condition, "structural_checks_passed": False, "error_type": type(error).__name__}
                report["results"].append(row)
                report["results"].sort(key=lambda r: r["case"]["id"])
                write_json(args.output, report)
                print(case["id"], row.get("result", {}).get("terminal", {}).get("data", {}).get("status", row.get("error_type")), row["structural_checks_passed"], flush=True)
        await asyncio.gather(*(run(case) for case in cases))
    ledger_after = UsageLedger().snapshot()["calls"]
    report.update(finished_at=now(), provider_calls_before=len(ledger_before), provider_calls_after=len(ledger_after), shared_ledger_unchanged=ledger_before == ledger_after)
    async with httpx.AsyncClient(base_url=args.url, timeout=30) as client:
        guards = (await client.get("/review/guards")).json()
    report["review_service_guards"] = guards
    report["no_live_provider_calls"] = guards.get("reservation_guard") and guards.get("mcp_connection_guard") and guards.get("denied_live_attempts") == 0
    assert report["no_live_provider_calls"], "Frozen review attempted live provider work"
    write_json(args.output, report)
    print("Finished", len(cases), "cases; frozen provider calls unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questions", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8083")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ids", nargs="+")
    asyncio.run(main(parser.parse_args()))
