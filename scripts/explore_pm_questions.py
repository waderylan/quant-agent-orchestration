"""Record exploratory PM chats and source/artifact checks without changing runtime code."""

from __future__ import annotations

import argparse
import asyncio
import json
import hashlib
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "docs/research/PM_EXPLORATION_2026-10-15_CASES.json"


async def capture(client, case, raw_path):
    started, first_token, kind = time.perf_counter(), None, None
    events, failure = [], None
    try:
        async with client.stream(
            "POST",
            "/api/chat",
            json={key: case[key] for key in ("question", "companies", "years")},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    kind = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
                    if kind == "token" and first_token is None:
                        first_token = time.perf_counter() - started
                    events.append({"type": kind, "data": data})
    except (httpx.HTTPError, ValueError) as error:
        failure = f"{type(error).__name__}: {error}"
    seconds = time.perf_counter() - started
    raw_path.write_text(
        json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    sources = [
        source
        for event in events
        if event["type"] == "sources"
        for source in event["data"]
    ]
    answer = ""
    for event in events:
        if event["type"] == "token":
            answer += event["data"]
        elif event["type"] == "answer":
            answer = event["data"]
    checks, bundles = [], {}
    for source in sources:
        check = {
            "source_id": source["source_id"],
            "kind": source.get("kind", "filing_passage"),
            "inspection_url": source["inspection_url"],
        }
        try:
            response = await client.get(source["inspection_url"])
            response.raise_for_status()
            inspected = response.json()
            if "chunk_id" in source:
                check["exact_text_match"] = inspected["text"] == source["text"]
                check["scope_match"] = (
                    inspected["company"] in case["companies"]
                    and inspected["fiscal_year"] in case["years"]
                )
            elif "value" in source:
                check["exact_value_match"] = str(inspected["value"]) == str(
                    source["value"]
                )
            check["http_status"] = response.status_code
            if source.get("bundle_id") and source["bundle_id"] not in bundles:
                bundle_response = await client.get(
                    f"/api/analysis/{source['bundle_id']}/files/bundle.json"
                )
                bundle_response.raise_for_status()
                bundles[source["bundle_id"]] = bundle_response.json()
        except (httpx.HTTPError, ValueError, KeyError) as error:
            check["error"] = f"{type(error).__name__}: {error}"
        checks.append(check)
    terminal = next(
        (event for event in reversed(events) if event["type"] == "complete"), None
    )
    return {
        **case,
        "answer": answer,
        "terminal": terminal,
        "transport_error": failure,
        "seconds": round(seconds, 3),
        "answer_token_ttft_seconds": round(first_token, 3)
        if first_token is not None
        else None,
        "sources": sources,
        "source_checks": checks,
        "bundles": bundles,
        "unregistered_citations": sorted(
            set(re.findall(r"\[([SFC]\d+)\]", answer))
            - {s["source_id"] for s in sources}
        ),
        "trace": [
            event
            for event in events
            if event["type"] in ("trace", "tool", "error", "scope")
        ],
        "raw_events_path": str(raw_path.relative_to(ROOT)),
    }


async def main(args):
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.ids:
        cases = [case for case in cases if case["id"] in args.ids]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = ROOT / "artifacts/pm-exploration" / run_id
    raw_dir.mkdir(parents=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "code_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "url": args.url,
        "concurrency": args.concurrency,
        "profile": "Actual native FastAPI/LangGraph chats; local Codex subscription. Exploratory review, not formal model-judge evaluation.",
        "runtime_files_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for folder, pattern in (
                (ROOT / "src", "*.py"),
                (ROOT / "prompts", "*.md"),
                (ROOT / "web", "*.html"),
            )
            for path in sorted(folder.glob(pattern))
        },
        "index": json.loads(
            (ROOT / "chroma_index/active.json").read_text(encoding="utf-8")
        ),
        "cases": [],
    }
    semaphore = asyncio.Semaphore(args.concurrency)

    async def run(case, client):
        async with semaphore:
            result = await capture(client, case, raw_dir / f"{case['id']}.json")
            report["cases"].append(result)
            report["cases"].sort(key=lambda item: item["id"])
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {
                        "id": case["id"],
                        "status": result["terminal"],
                        "seconds": result["seconds"],
                        "answer": result["answer"],
                        "errors": [e for e in result["trace"] if e["type"] == "error"],
                    }
                ),
                flush=True,
            )

    async with httpx.AsyncClient(base_url=args.url, timeout=330) as client:
        await asyncio.gather(*(run(case, client) for case in cases))
    print(
        json.dumps(
            {"completed_cases": len(report["cases"]), "output": str(args.output)}
        ),
        flush=True,
    )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8086")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--concurrency", type=int, choices=[1, 2], default=2)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
