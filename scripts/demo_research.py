"""M3 exploratory demonstration with real corpus/model calls, not a benchmark."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn
from src.research_index import ResearchIndex
from src.research_workflow import research_turn
from src.source_collection import ROOT, now, write_json

QUESTIONS = [
    ("NVDA", 2026, "What drove NVIDIA's full-year revenue growth in FY2026?"),
    (
        "AMD",
        2025,
        "What does AMD's amended FY2025 MD&A say about Client unit shipments and average selling prices, compared with the original?",
    ),
    (
        "INTC",
        2025,
        "What does Intel's FY2025 annual report disclose about its manufacturing process risks?",
    ),
    ("QCOM", 2025, "What drove Qualcomm QCT revenue growth in FY2025?"),
]


async def application_turn(client, company, year, question):
    turn = await capture_turn(client, question, [company], [year], include_events=True)
    inspections = []
    for source in turn["sources"]:
        if not source.get("source_id", "").startswith("S") or not {"text", "document_id", "chunk_id"} <= source.keys():
            continue
        inspected = (await client.get(source["inspection_url"])).json()
        exact = inspected.get("text") == source["text"]
        scoped = source["company"] == company and source["fiscal_year"] == year
        inspections.append(
            {
                "source_id": source["source_id"],
                "document_id": source["document_id"],
                "chunk_id": source["chunk_id"],
                "exact_passage": exact,
                "correct_scope": scoped,
            }
        )
    final = turn["terminal"] or {}
    passed = (
        final.get("type") == "complete"
        and final.get("data", {}).get("status") == "completed"
        and bool(inspections)
        and all(i["exact_passage"] and i["correct_scope"] for i in inspections)
    )
    return {
        "question": question,
        "company": company,
        "fiscal_year": year,
        "passed": passed,
        "seconds": turn["seconds"],
        "answer_token_ttft_seconds": turn["answer_token_ttft_seconds"],
        "answer": turn["answer"],
        "inspections": inspections,
        "events": turn["events"],
    }


async def main(args):
    index = ResearchIndex()
    report = {
        "checked_at": now(),
        "kind": "exploratory demonstration; no formal scores",
        "index": json.loads((index.path / "active.json").read_text(encoding="utf-8")),
        "retrieval": [],
        "application": [],
        "coverage_gaps": [],
    }
    for company, year, question in QUESTIONS:
        hits = index.search(question, [company], [year])
        passed = bool(hits) and all(
            p["company"] == company
            and p["fiscal_year"] == year
            and index.inspect(p["chunk_id"])["text"] == p["text"]
            for p in hits
        )
        report["retrieval"].append(
            {
                "company": company,
                "year": year,
                "passed": passed,
                "documents": sorted({p["document_id"] for p in hits}),
            }
        )
        print(f"retrieval {company} FY{year}: {passed}", flush=True)
    missing_risks = index.search(
        "risk factors", ["AMD"], [2025], section="risk_factors", version="amendment"
    )
    report["amendment_has_no_replacement_risks"] = not missing_risks
    if not args.retrieval_only:
        async with httpx.AsyncClient(base_url=args.url, timeout=240) as client:
            for company, year, question in QUESTIONS:
                result = await application_turn(client, company, year, question)
                report["application"].append(result)
                print(
                    f"application {company}: {result['passed']} ({result['seconds']}s)",
                    flush=True,
                )
                write_json(args.output, report)
            for company, year, question in [
                ("AAPL", 2025, "Apple revenue drivers"),
                ("AMD", 2027, "AMD FY2027 revenue drivers"),
            ]:
                result = await application_turn(client, company, year, question)
                report["coverage_gaps"].append(
                    {
                        "question": question,
                        "answer": result["answer"],
                        "passed": result["events"][-1]["data"]["status"]
                        == "coverage_gap"
                        and not any(e["type"] == "tool" for e in result["events"]),
                    }
                )
        role_events = []
        company, year, question = QUESTIONS[1]
        result = await research_turn(
            index,
            {"question": question, "companies": [company], "years": [year]},
            role_events.append,
        )
        report["direct_role"] = {
            "question": question,
            "result": result,
            "events": role_events,
            "passed": bool(result.get("answer")) and not result.get("error"),
        }
    checks = [
        r["passed"]
        for name in ("retrieval", "application", "coverage_gaps")
        for r in report[name]
    ]
    checks += [report["amendment_has_no_replacement_risks"]]
    if "direct_role" in report:
        checks += [report["direct_role"]["passed"]]
    report["passed"] = all(checks)
    write_json(args.output, report)
    print(f"Saved {args.output}; passed={report['passed']}", flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/checks/m3-demonstration.json",
    )
    asyncio.run(main(parser.parse_args()))
