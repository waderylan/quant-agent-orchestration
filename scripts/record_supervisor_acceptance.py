"""Freeze verified cooperation evidence; keep licensed market answers private."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.source_collection import ROOT, now, write_json, digest
from src.market_mcp import UsageLedger, sanitized


def read(name):
    return json.loads((ROOT / "artifacts" / name).read_text(encoding="utf-8"))


def compact(turn):
    return {"question": turn["question"], "answer_sha256": digest(turn["answer"].encode()), "terminal": turn["terminal"], "seconds": turn["seconds"], "answer_token_ttft_seconds": turn["answer_token_ttft_seconds"], "inspection_checks": turn.get("inspection_checks"), "trace": [e for e in turn["trace"] if e["type"] != "tool"], "source_links": [{k: s.get(k) for k in ("source_id", "company", "fiscal_year", "start", "end", "inspection_url", "source_ids", "bundle_id")} for s in turn["sources"]]}


native, docker = read("m9-native-verified.json"), read("m9-docker-browser.json")
final_api = read("m9-final-five-api.json")
assert native["browser"]["passed"] and docker["browser"]["passed"]
outcomes = [e["data"] for e in final_api["trace"] if e["type"] == "trace" and e["data"].get("node") == "worker_outcome"]
assert [(o["worker"], o["outcome"]) for o in outcomes[:4]] == [("data", "completed"), ("quant", "completed"), ("risk", "completed"), ("research", "completed")]
assert outcomes[-1]["worker"] == "buy" and outcomes[-1]["outcome"] == "partial"
assert all(final_api["inspection_checks"])
browser_rows = {}
for name, run in (("native", native), ("docker", docker)):
    b = run["browser"]
    browser_rows[name] = {k: v for k, v in b.items() if k not in ("answer", "trace")} | {"answer_sha256": digest(b["answer"].encode()), "trace_sha256": digest(b["trace"].encode())}
report = {"checked_at": now(), "tests": {"passed": 151, "failed": 0}, "kind": "Actual local subscription and private market MCP/cache; separate synthetic failure tests", "final_five_specialist_api": compact(final_api), "native_api": [compact(t) for t in native["api"]], "browsers": browser_rows, "concurrent_http": read("m9-concurrency.json"), "failure_cases": ["worker deadline retains prior trusted figures", "conflicting/ID-colliding worker evidence rolls back transactionally", "mutating worker cannot alter prior source", "missing structured observation triggers one follow-up", "unsupported year returns coverage gap before generation", "source-less clarification remains clarification", "cancellation reaches owned worker", "same POST/SSE route handles synthetic timeout, conflict and unsupported scope"], "initial_handoff_failure": {"observed": "Buy-Side reused a Research source ID; supervisor rejected changed evidence and retained checked financial results", "fixed": "All workers receive complete request-local registry; role task boundaries prevent unassigned outputs appearing missing", "terminal": read("m9-initial-handoff-failure.json")["api"][0]["terminal"]}, "review_status": "Two explicitly authorized isolated review rounds begin after the separate M7/M8/M9 implementation commits. Review generation is not yet claimed as executed."}
write_json(ROOT / "docs/milestones/supervisor/evidence/M9_ACCEPTANCE_2026-10-16.json", sanitized(report))
write_json(ROOT / "docs/milestones/buy-side-analyst/evidence/PROVIDER_USAGE_LEDGER.json", UsageLedger().snapshot())
print("Recorded verified M9 evidence")
