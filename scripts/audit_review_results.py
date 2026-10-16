"""Merge sealed application runs and independently inspect/replay their evidence.

Private answers remain in artifacts. The public report contains hashes, routing,
terminal outcomes and check results, without redistributing market observations.
"""

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.analysis_artifacts import ArtifactStore
from src.quant_analysis import run_isolated, validate_results
from src.quant_valuation import replay
from src.source_collection import digest, now, write_json
from scripts.demo_support import wait_ready


async def audit(args):
    questions = json.loads(args.questions.read_text(encoding="utf-8-sig"))
    expected = {case["id"]: case for case in questions["cases"]}
    selected, provenance = {}, []
    for spec in args.run:
        url, filename = spec.split("=", 1)
        path = Path(filename)
        report = json.loads(path.read_text(encoding="utf-8"))
        assert report["questions_sha256"] == digest(args.questions.read_bytes())
        assert report["no_live_provider_calls"], "Review must forbid live calls"
        provenance.append({"file": path.name, "sha256": digest(path.read_bytes()), "guards": report["review_service_guards"], "shared_ledger_unchanged": report["shared_ledger_unchanged"]})
        for row in report["results"]:
            assert row["case"] == expected[row["case"]["id"]], "Sealed case changed"
            selected[row["case"]["id"]] = (row, url, path.name)
    assert selected.keys() == expected.keys(), "Every sealed case needs an outcome"
    store, bundles, results = ArtifactStore(), {}, []
    for url in sorted({url for _, url, _ in selected.values()}):
        async with httpx.AsyncClient(base_url=url, timeout=30) as ready:
            await wait_ready(ready)
    async with httpx.AsyncClient(timeout=30) as client:
        for identity, (row, url, filename) in sorted(selected.items()):
            result = row.get("result", {})
            checks = []
            for source in result.get("sources", []):
                endpoint = source.get("inspection_url")
                if not endpoint:
                    continue
                response = await client.get(url + endpoint)
                mismatches = []
                if response.status_code == 200:
                    body = response.json()
                    for field in ("value", "unit", "company", "fiscal_year", "fiscal_start", "fiscal_end", "period", "basis", "currency", "dilution", "split_basis", "as_of", "horizon", "formula", "source_ids", "inputs"):
                        if field in source and field in body and source[field] != body[field]:
                            mismatches.append(field)
                    if source.get("text") and source.get("kind") not in ("market_evidence", "valuation_input", "calculation", "financial_observation") and body.get("text") != source["text"]:
                        mismatches.append("exact_text")
                checks.append({"source_id": source["source_id"], "inspection_url": endpoint, "http_status": response.status_code, "mismatched_fields": mismatches, "passed": response.status_code == 200 and not mismatches})
                bundle_id = source.get("bundle_id")
                if bundle_id and bundle_id not in bundles:
                    bundle = store.load(bundle_id)
                    for name in bundle["files"]:
                        store.file(bundle_id, name)
                    if bundle.get("assessment", {}).get("validator") in ("valuation-v1", "valuation-v2"):
                        verified = replay(bundle)["verified"]
                    else:
                        actual = validate_results(run_isolated(bundle["code"], bundle["sources"]), bundle["sources"], scenario=next((r["scenario"] for r in bundle["calculations"] if r.get("scenario")), None))
                        verified = actual == bundle["calculations"]
                    bundles[bundle_id] = {"passed": verified, "calculations": len(bundle["calculations"]), "validator": bundle.get("assessment", {}).get("validator", "financial")}
            termination = next((e["data"].get("task", {}) for e in reversed(result.get("trace", [])) if e.get("type") == "trace" and isinstance(e.get("data"), dict) and e["data"].get("node") == "termination"), {})
            results.append({"case_id": identity, "run": filename, "applied_condition": row["applied_condition"], "terminal": result.get("terminal"), "error_type": row.get("error_type"), "answer_sha256": digest(result.get("answer", "").encode()), "answer_characters": len(result.get("answer", "")), "seconds": result.get("seconds"), "worker_outcomes": termination.get("worker_outcomes", {}), "structural_checks_passed": row["structural_checks_passed"], "source_checks": checks, "concurrent_companion": result.get("concurrent_companion"), "cancellation": {key: result[key] for key in ("cancelled_after_generation_started", "verified_historical_worker_completed", "late_provider_deliveries") if key in result}, "manual_semantic_review_required": True})
    public = {"checked_at": now(), "questions_sha256": digest(args.questions.read_bytes()), "runs": provenance, "cases": results, "source_inspections": sum(len(r["source_checks"]) for r in results), "source_failures": sum(not c["passed"] for r in results for c in r["source_checks"]), "bundles": bundles, "replayed_calculations": sum(b["calculations"] for b in bundles.values()), "terminal_counts": dict(Counter(r.get("terminal", {}).get("data", {}).get("status", "missing") for r in results)), "semantic_accuracy_claim": False}
    write_json(args.output, public)
    print(json.dumps({key: public[key] for key in ("source_inspections", "source_failures", "replayed_calculations", "terminal_counts")}))
    assert public["source_failures"] == 0 and all(b["passed"] for b in bundles.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questions", type=Path)
    parser.add_argument("--run", action="append", required=True, help="URL=private-report.json, later runs supersede affected cases")
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(audit(parser.parse_args()))
