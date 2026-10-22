"""Export inspectable per-question RAGAS scores, judgments and descriptive summaries."""

import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.source_collection import digest, now, write_json

METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")


def distribution(values):
    valid = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    if not valid:
        return {"n": 0, "unavailable": len(values)}
    ordered = sorted(valid)
    return {"n": len(valid), "unavailable": len(values) - len(valid),
            "mean": statistics.mean(valid), "median": statistics.median(valid),
            "min": min(valid), "max": max(valid),
            "sample_sd": statistics.stdev(valid) if len(valid) > 1 else None,
            "p95_nearest_rank": ordered[math.ceil(.95 * len(ordered)) - 1]}


def cohort(name, capture_path, score_path, cache):
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    scores = json.loads(score_path.read_text(encoding="utf-8"))
    if scores["capture_sha256"] != digest(capture_path.read_bytes()):
        raise ValueError("Scores do not identify this capture")
    if not scores.get("context_format", "").startswith("metadata-v2"):
        raise ValueError("Submission report requires corrected metadata-v2 context scores")
    by_id = {r["id"]: r for r in scores["cases"]}
    rows = []
    for captured in capture["cases"]:
        score = by_id.get(captured["id"], {})
        traces = [e["data"] for e in captured.get("events", []) if e["type"] == "trace"]
        usage = [t for t in traces if t.get("node") == "provider_usage"]
        routes = [t for t in traces if t.get("node") == "provider_route"]
        row = {"id": captured["id"], "cohort": name, "question": captured.get("question"),
               "answer": captured.get("result", {}).get("answer"), "partial": captured.get("result", {}).get("partial"),
               "capture_error": captured.get("capture_error"), "score_status": score.get("status", "missing"),
               "metrics": score.get("metrics", {}), "timing": captured.get("timing", {}),
               "provider_routes": routes, "provider_usage": usage,
               "token_usage": "reported below" if usage else "not exposed by local subscription transport",
               "api_cost_estimate_usd": str(sum((Decimal(t["cost_usd"]) for t in usage), Decimal(0))) if usage and all(t.get("cost_usd") is not None for t in usage) else None,
               "api_cost_missing_rounds": sum(t.get("cost_usd") is None for t in usage),
               "contexts": [{**{k: c.get(k) for k in ("chunk_id", "source_id", "document_id", "company", "fiscal_year", "form", "version", "period_end", "start", "end", "context_start", "first_seen_rank", "text_sha256")},
                             "model_visible_text_sha256": digest(c["model_visible_text"].encode())} for c in captured.get("contexts", [])]}
        rows.append(row)
    calls = scores.get("judge_calls", [])
    judgments = []
    ranks = Counter()
    for call in calls:
        saved = json.loads((cache / (call["key"] + ".json")).read_text(encoding="utf-8"))
        ranks[call.get("context")] += 1
        judgments.append({**call, "metric_call_rank": ranks[call.get("context")],
                          "prompt_sha256": digest(saved["prompt"].encode()),
                          "response_schema": saved["schema"].get("title"), "response": saved["response"]})
    summary = {"requests": len(rows), "scored_requests": sum(r["score_status"] == "scored" for r in rows),
               "partial": sum(r["partial"] is True for r in rows),
               "capture_errors": sum(bool(r["capture_error"]) for r in rows),
               "metrics": {m: distribution([r["metrics"].get(m, {}).get("value") for r in rows]) for m in METRICS},
               "timing": {m: distribution([r["timing"].get(m) for r in rows]) for m in ("total_seconds", "retrieval_seconds", "model_wait_seconds_excluding_tools", "answer_token_ttft_seconds")},
               "model_visible_contexts": sum(len(r["contexts"]) for r in rows),
               "judge_calls": {"recorded": len(calls), "cache_hits": sum(c["cached"] for c in calls), "new_calls": sum(not c["cached"] for c in calls)},
               "api_cost_estimate_usd": str(sum((Decimal(r["api_cost_estimate_usd"]) for r in rows if r["api_cost_estimate_usd"] is not None), Decimal(0))) if not any(r["api_cost_missing_rounds"] for r in rows) else None,
               "api_cost_missing_rounds": sum(r["api_cost_missing_rounds"] for r in rows),
               "direct_generation_api_calls": sum(len(r["provider_usage"]) for r in rows),
               "serving_models": sorted({(t.get("provider", ""), t.get("model", "")) for r in rows for t in r["provider_routes"]})}
    return {"name": name, "capture_sha256": digest(capture_path.read_bytes()), "scores_sha256": digest(score_path.read_bytes()),
            "dataset_sha256": capture["dataset_sha256"], "capture_runtime_hashes": capture["runtime_hashes"],
            "runtime_unchanged": capture.get("runtime_unchanged"), "evaluator": {k: scores.get(k) for k in ("adapter", "versions", "evaluator_hashes", "context_format", "context_policy", "judge", "embedding", "reference_errata", "reference_errata_sha256")},
            "summary": summary, "cases": rows, "judgments": judgments}


def paired(before, after):
    left, right = ({r["id"]: r for r in c["cases"]} for c in (before, after))
    result = {}
    for metric in METRICS:
        deltas = []
        for identity in sorted(left.keys() & right.keys()):
            a = left[identity]["metrics"].get(metric, {}).get("value")
            b = right[identity]["metrics"].get(metric, {}).get("value")
            if a is not None and b is not None:
                deltas.append({"id": identity, "before": a, "after": b, "delta": b - a})
        result[metric] = {"distribution": distribution([r["delta"] for r in deltas]),
                          "improved": sum(r["delta"] > 1e-8 for r in deltas),
                          "unchanged": sum(abs(r["delta"]) <= 1e-8 for r in deltas),
                          "worse": sum(r["delta"] < -1e-8 for r in deltas), "cases": deltas}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", action="append", required=True, help="name=capture.json,scores.json")
    parser.add_argument("--cache", type=Path, default=Path("artifacts/ragas/judge"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    cohorts = []
    for specification in args.cohort:
        name, paths = specification.split("=", 1)
        capture, scores = paths.split(",", 1)
        cohorts.append(cohort(name, Path(capture), Path(scores), args.cache))
    report = {"checked_at": now(), "aggregation": "Unweighted per-question arithmetic means; valid n and unavailable counts reported. No failed metric becomes zero. p95 uses nearest rank. No population confidence claim.", "cohorts": cohorts}
    if len(cohorts) >= 2:
        report["first_two_cohorts_paired_deltas"] = paired(cohorts[0], cohorts[1])
    write_json(args.output, report)
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["cohort", "id", *METRICS, "score_status", "total_seconds", "retrieval_seconds", "model_wait_seconds_excluding_tools", "answer_token_ttft_seconds", "context_count", "partial", "api_cost_estimate_usd"])
        writer.writeheader()
        for c in cohorts:
            for r in c["cases"]:
                writer.writerow({"cohort": c["name"], "id": r["id"], **{m: r["metrics"].get(m, {}).get("value") for m in METRICS},
                                 **{k: r["timing"].get(k) for k in ("total_seconds", "retrieval_seconds", "model_wait_seconds_excluding_tools", "answer_token_ttft_seconds")}, "context_count": len(r["contexts"]), "partial": r["partial"],
                                 "score_status": r["score_status"], "api_cost_estimate_usd": r["api_cost_estimate_usd"]})
    print(json.dumps({c["name"]: c["summary"] for c in cohorts}, indent=2))
