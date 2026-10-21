"""Capture a bounded fixed set through the actual application POST/SSE endpoint."""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn, wait_ready


async def run(args):
    cases = json.loads(args.dataset.read_text(encoding="utf-8"))
    report = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "kind": "Real API-profile application acceptance; engineering checks, not RAGAS",
              "url": args.url, "concurrency": args.concurrency, "cases": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=args.url, timeout=300) as client:
        await wait_ready(client)
        runtime = await client.get("/api/runtime")
        if runtime.status_code != 200 or not any(p["id"] == "api" and p["available"] for p in runtime.json().get("profiles", [])):
            raise RuntimeError("Acceptance requires an application with hosted generation available")
        report["runtime"] = runtime.json()
        limit = asyncio.Semaphore(args.concurrency)
        async def capture(case):
            async with limit:
                await capture_case(case)
        async def capture_case(case):
            result = await capture_turn(client, case["question"], case["companies"], case["years"], include_events=True, generation_profile="api")
            result["id"] = case["id"]
            report["cases"].append(result)
            args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            routes = [e["data"] for e in result["trace"] if e["type"] == "trace" and e["data"].get("node") == "provider_route"]
            print(json.dumps({"id": case["id"], "status": result["terminal"]["data"].get("status"),
                              "seconds": result["seconds"], "routes": sorted({r["provider"]+":"+r["model"] for r in routes})}), flush=True)
        await asyncio.gather(*(capture(case) for case in cases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8146")
    parser.add_argument("--dataset", type=Path, default=Path("tests/fixtures/provider_routes.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/providers/application.json"))
    parser.add_argument("--concurrency", type=int, choices=[1, 2], default=1)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
