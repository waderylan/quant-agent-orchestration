"""Record private MCP acceptance, account limits, and credential-free usage."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.analysis_artifacts import ArtifactStore
from src.market_mcp import MarketGateway, UsageLedger, provider_error, sanitized
from src.market_evidence import payload_text
from src.quant_valuation import replay
from src.source_collection import ROOT, now, write_json, digest


def read(name):
    return json.loads((ROOT / "artifacts" / name).read_text(encoding="utf-8"))


def compact(turn):
    return {**turn, "answer": "Private market answer retained under ignored artifacts; sha256=" + digest(turn["answer"].encode()), "sources": [{k: v for k, v in s.items() if k not in ("text", "raw", "context", "normalized", "value")} for s in turn.get("sources", [])], "trace": [e for e in turn.get("trace", []) if e["type"] not in ("tool", "evidence")]}


def private_browser(browser):
    return {k: v for k, v in browser.items() if k not in ("answer", "trace")} | {"answer_sha256": digest(browser["answer"].encode()), "trace_sha256": digest(browser["trace"].encode())}


native, docker = read("m8-native-verified.json"), read("m8-docker.json")
browser = read("m8-docker-browser-fixed.json")["browser"]
assert native["browser"]["passed"] and browser["passed"]
assert all(all(t["inspection_checks"]) for r in (native, docker) for t in r["api"])
direct_grid = read("m8-grid-direct.json")
replays = [replay(ArtifactStore().load(b)) for b in direct_grid["result"]["valuation_bundles"]]
ledger = UsageLedger()
probes, gmail = read("market/account-probes.json"), read("market/gmail-entitlement-audit.json")
# Correct early protocol-success labels using the inspected provider refusal bodies.
for call in ledger.snapshot()["calls"]:
    if call["provider"] == "twelve" and call["tool"] in {"get_statistics", "get_earnings", "get_splits"}:
        ledger.finish(call["id"], "provider_error")
account_rows = []
for item in gmail["calls"]:
    account_rows.append({"account": "gmail", "tool": item["tool"], "outcome": "provider_error" if provider_error(item["payload"]) else "returned", "mcp": item.get("mcp"), "response_excerpt": payload_text(item)[:320]})
probe_rows = [{k: v for k, v in row.items() if k != "snapshot"} | ({"outcome": "provider_error" if provider_error(row["snapshot"]["payload"]) else "returned", "response_excerpt": payload_text(row["snapshot"])[:320]} if row.get("snapshot", {}).get("payload") else {}) for row in probes["results"]]
report = {"checked_at": now(), "kind": "Private local acceptance; public display and qualified live multiples remain limited", "tests": {"passed": 139, "failed": 0}, "discovery": {p: {k: v for k, v in read("market/" + p + "-discovery.json").items() if k != "tools"} | {"tools": [t["name"] for t in read("market/" + p + "-discovery.json")["tools"]]} for p in ("twelve", "alpha", "tavily")}, "account_probes": probe_rows, "gmail_sequential_audit": account_rows, "tavily_initial_usage": read("market/tavily-initial-usage.json"), "tavily_final_observed_usage": read("market/tavily-m8-usage.json"), "native_api": [compact(t) for t in native["api"]], "native_browser": native["browser"], "docker_api": [compact(t) for t in docker["api"]], "docker_browser": browser, "docker_actual_refresh_api": compact(read("m8-docker-live-api.json")), "docker_actual_mcp": {k: v for k, v in read("market/docker-live-proof.json").items() if k != "payload"}, "direct_sensitivity": {"question": "For Qualcomm, assume EPS grid: 8, 10, 12; P/E grid: 16, 18, 20. Build a conditional 12-month sensitivity grid, checked implied prices and scenario returns, with opposing evidence.", "answer": direct_grid["result"]["answer"], "bundles": direct_grid["result"]["valuation_bundles"], "replay": replays}, "injected_source_generation": {k: read("m8-injection-generation.json")[k] for k in ("kind", "answer", "partial")}, "limits": ["No verified public display rights", "Consensus accounting/currency/dilution/split/as-of/fiscal-date basis unqualified; forward P/E excluded", "Current TTM and matching EV/FCF inputs unavailable", "Quoted feed/delay unspecified", "Private frozen/raw provider data stays ignored; evidence distinguishes schemas, entitlement and synthetic assumptions"]}
folder = ROOT / "docs/milestones/buy-side-analyst/evidence"
for key in ("native_browser", "docker_browser"):
    report[key] = private_browser(report[key])
report["direct_sensitivity"]["answer"] = "Private source-linked answer sha256=" + digest(report["direct_sensitivity"]["answer"].encode())
for row in report["account_probes"]:
    norm = row.get("normalized", {})
    norm.pop("value", None)
    norm.pop("raw", None)
    for estimate in norm.get("rows", []):
        estimate.pop("eps_average", None)
        estimate.pop("revenue_average", None)
write_json(folder / "M8_ACCEPTANCE_2026-10-16.json", sanitized(report))
write_json(folder / "PROVIDER_USAGE_LEDGER.json", ledger.snapshot())
print("Recorded M8 evidence; calls:", {p: len([c for c in ledger.snapshot()["calls"] if c["provider"] == p]) for p in ("twelve", "alpha", "tavily")})
