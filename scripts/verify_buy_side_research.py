"""Selected-company HTTP/SSE review with actual generation and no live market calls.

Model turn starts and tool-result continuations share a persistent 49-unit ceiling.
Recorded MCP responses and synthetic failures exercise production application paths.
This is exploratory engineering evidence, not a formal quality score.
"""

import argparse
import asyncio
from contextlib import aclosing
import json
from pathlib import Path
import socket
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import uvicorn
from fastapi import Request

from scripts.demo_support import capture_turn, wait_ready
from scripts.review_application import app, FrozenFaultGateway, DENIED_LIVE_ATTEMPTS
from main import turn_services, TurnServices
from src.codex_model import stream
from src.analysis_artifacts import ArtifactStore
from src.market_mcp import UsageLedger, sanitized
from src.quant_valuation import replay
from src.source_collection import ROOT, digest, now, write_json


async def main(args):
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    if args.ids:
        cases = [case for case in cases if case["id"] in args.ids]
    report = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {
        "started_at": now(), "kind": "Actual local subscription generation through production HTTP/SSE; recorded MCP replay and labeled synthetic faults; no live market acquisition",
        "budget": {"limit": 49, "model_turns": 0, "tool_continuations": 0, "live_market_calls": 0}, "results": [],
    }
    budget = report["budget"]
    ledger_before = UsageLedger().snapshot()["calls"]
    report["cases_sha256"] = digest(args.cases.read_bytes())
    implementation = {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in [ROOT / "src/buy_side.py", ROOT / "src/supervisor.py", ROOT / "src/capabilities.py", ROOT / "prompts/buy_side.md", ROOT / "web/index.html"]}
    report.setdefault("implementation_revisions", []).append({"at": now(), "code_sha256": implementation})

    def reserve(kind):
        used = sum(budget[key] for key in ("model_turns", "tool_continuations", "live_market_calls"))
        if used >= budget["limit"]:
            raise RuntimeError("Review call budget exhausted; no additional generation")
        budget[kind] += 1
        write_json(args.output, sanitized(report))

    async def budgeted_stream(prompt, schemas, handler, **kwargs):
        reserve("model_turns")
        async with aclosing(stream(prompt, schemas, handler, **kwargs)) as generated:
            async for event in generated:
                if event["type"] == "tool" or event["type"] == "trace" and event["data"].get("decision") in ("report_completion", "synthesize_existing_evidence"):
                    reserve("tool_continuations")
                yield event

    gateways = {}

    async def services(request: Request):
        case_id = request.headers.get("X-Buy-Case")
        case = next(case for case in cases if case["id"] == case_id)
        gateway = FrozenFaultGateway(case.get("condition", "normal"))
        gateways[case_id] = []
        original_fetch = gateway.fetch

        async def tracked_fetch(provider, tool, arguments, **kwargs):
            gateways[case_id].append({"provider": provider, "tool": tool, "arguments": arguments})
            return await original_fetch(provider, tool, arguments, **kwargs)

        gateway.fetch = tracked_fetch
        return TurnServices(gateway=gateway, model_stream=budgeted_stream)

    app.dependency_overrides[turn_services] = services
    listener = socket.socket()
    listener.bind(("127.0.0.1", args.port))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=300) as client:
            await wait_ready(client)
            for case in cases:
                if any(row["case"]["id"] == case["id"] for row in report["results"]):
                    continue
                print("START", case["id"], flush=True)
                result = await capture_turn(client, case["question"], case["companies"], case["years"], headers={"X-Buy-Case": case["id"]})
                checks, bundles = [], {}
                for source in result["sources"]:
                    if source.get("inspection_url"):
                        response = await client.get(source["inspection_url"])
                        checks.append({"source_id": source["source_id"], "status": response.status_code})
                    if source.get("bundle_id"):
                        bundles[source["bundle_id"]] = True
                for identity in bundles:
                    bundle = ArtifactStore().load(identity)
                    replay_result = replay(bundle)
                    downloads = []
                    for filename in ("table.csv", "chart.png", "analysis.py", "bundle.json"):
                        response = await client.get(f"/api/analysis/{identity}/files/{filename}")
                        downloads.append({"file": filename, "status": response.status_code, "bytes": len(response.content)})
                    bundles[identity] = {"replay": replay_result, "calculations": bundle["calculations"], "downloads": downloads}
                row = {"case": case, "result": result, "code_sha256": implementation, "acquisitions": gateways.get(case["id"], []), "source_checks": checks, "bundles": bundles, "manual_semantic_review_required": True}
                report["results"].append(row)
                write_json(args.output, sanitized(report))
                print("DONE", case["id"], result["terminal"], "budget", budget, flush=True)
    finally:
        server.should_exit = True
        await task
        report["finished_at"] = now()
        report["denied_live_attempts"] = len(DENIED_LIVE_ATTEMPTS)
        report["ledger_unchanged"] = ledger_before == UsageLedger().snapshot()["calls"]
        write_json(args.output, sanitized(report))
    assert report["denied_live_attempts"] == 0, "Review attempted live market acquisition"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "tests/fixtures/buy_side_review.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/buy-side-research-review.json")
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--port", type=int, default=0)
    asyncio.run(main(parser.parse_args()))
