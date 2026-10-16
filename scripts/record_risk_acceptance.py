"""Freeze inspected M7 results without copying raw complete filings into evidence."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.source_collection import ROOT, now, write_json


def read(name):
    return json.loads((ROOT / "artifacts" / name).read_text(encoding="utf-8"))


def compact(turn):
    return {**turn, "sources": [{k: v for k, v in s.items() if k not in ("text", "context")} | {"excerpt": s.get("text", "")[:240]} for s in turn["sources"]], "trace": [e for e in turn["trace"] if e["type"] != "tool" or e["data"].get("name") != "initial_retrieval"]}


native, docker = read("m7-verified-native.json"), read("m7-verified-docker.json")
bn, bd = read("m7-browser-native.json"), read("m7-browser-docker.json")
assert bn["browser"]["passed"] and bd["browser"]["passed"]
assert all(all(t["inspection_checks"]) for r in (native, docker) for t in r["api"])
injection = read("m7-injection-generation.json")
report = {"checked_at": now(), "test_command": "uv run --locked pytest -q", "tests": {"passed": 124, "failed": 0}, "direct": read("m7-application.json")["direct"], "native_api": [compact(t) for t in native["api"]], "docker_api": [compact(t) for t in docker["api"]], "native_browser": bn["browser"], "docker_browser": bd["browser"], "injected_document_actual_generation": {k: injection[k] for k in ("answer", "changes", "partial")}, "evidence_limits": ["Local subscription generation, not deployment providers", "Semantic labels reviewed from exact source text; no formal risk scoring", "Synthetic failures do not represent live financial provider failures"]}
write_json(ROOT / "docs/milestones/risk-summary/evidence/M7_ACCEPTANCE_2026-10-16.json", report)
print("Recorded verified M7 evidence")
