"""Export compact M12 evidence without copying large filing/tool payloads."""

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.live_mcp import sanitized
from src.source_collection import digest, now, write_json


def distribution(values):
    values = [value for value in values if value is not None]
    return {"n": len(values), "min": min(values), "median": statistics.median(values), "max": max(values)} if values else {"n": 0}


def summarize(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    report = {"checked_at": now(), "capture_sha256": digest(path.read_bytes()), "dataset_sha256": raw["dataset_sha256"], "profile": raw["profile"], "method": raw["method"], "runtime_hashes": raw.get("runtime_hashes"), "runtime_unchanged": raw.get("runtime_unchanged"), "cases": [], "variants": {}}
    for row in raw["cases"]:
        traces = [event["data"] for event in row["trace"] if event["type"] == "trace"]
        calls = row["live_calls"]
        activities, durations = {}, {}
        for event in row["events"]:
            if event["type"] == "activity":
                data = event["data"]
                if data["status"] == "running":
                    activities[data["id"]] = data
                elif data["id"] in activities:
                    start = activities[data["id"]]
                    durations.setdefault(data["agent"], []).append(round((data["elapsed_ms"] - start["elapsed_ms"]) / 1000, 3))
        report["cases"].append({k: row[k] for k in ("id", "variant", "companies", "years", "question", "answer", "terminal", "seconds", "answer_token_ttft_seconds", "estimated_uncached_credits", "inspections")} | {
            "answer_sha256": digest(row["answer"].encode()), "agent_seconds": durations, "live_calls": calls,
            "worker_outcomes": [trace for trace in traces if trace.get("node") == "worker_outcome"],
            "risk_live_checks": [check for trace in traces if trace.get("node") == "risk_live_checks" for check in trace["checks"]],
            "coverage": [trace for trace in traces if trace.get("node") == "answer_coverage"],
            "provider_usage": [trace for trace in traces if trace.get("node") in ("provider_usage", "provider_fallback")],
            "sources": [{k: source.get(k) for k in ("source_id", "agent", "kind", "company", "document_id", "fiscal_year", "filed", "fiscal_start", "fiscal_end", "text_sha256", "chunk_id", "start", "end", "complete_section", "snapshot_id", "date_snapshot_id", "published_date", "date_source", "source_tier", "publisher", "title", "url", "inspection_url")} for source in row["sources"]]})
    for name in dict.fromkeys(row["variant"] for row in report["cases"]):
        rows = [row for row in report["cases"] if row["variant"] == name]
        calls = [call for row in rows for call in row["live_calls"]]
        agents = sorted({call["agent"] for call in calls})
        report["variants"][name] = {
            "n": len(rows), "terminal_counts": {status: sum(row["terminal"]["data"]["status"] == status for row in rows) for status in sorted({row["terminal"]["data"]["status"] for row in rows})},
            "total_seconds": distribution([row["seconds"] for row in rows]), "answer_token_ttft_seconds": distribution([row["answer_token_ttft_seconds"] for row in rows]),
            "estimated_uncached_credits": sum(row["estimated_uncached_credits"] for row in rows),
            "live_calls_by_agent": {agent: {"calls": sum(call["agent"] == agent for call in calls), "uncached_attempts": sum(call["agent"] == agent and not call.get("cache") and call.get("outcome") in ("returned", "provider_error", "transport_failure") for call in calls), "request_trigger_count": sum(any(call["agent"] == agent for call in row["live_calls"]) for row in rows)} for agent in agents},
            "risk_worker_seconds": distribution([duration for row in rows for duration in row["agent_seconds"].get("Risk Summary", [])]),
        }
    return sanitized(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.capture)
    write_json(args.output, result)
    print(json.dumps(result["variants"], indent=2))
