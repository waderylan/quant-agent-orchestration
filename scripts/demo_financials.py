"""Verify source figures and actual direct-worker/application/browser behavior."""

import argparse
import asyncio
import re
import sys
from decimal import Decimal
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn
from src.financial_data import FinancialStore, METRICS
from src.financial_workflow import financial_turn
from src.research_index import ResearchIndex
from src.source_collection import ROOT, now, write_json

# Independently inspected original annual figures from M1, in USD millions.
REFERENCE = {
    ("NVDA", 2025): [130497, 97858, 81453, 64089],
    ("NVDA", 2026): [215938, 153463, 130387, 102718],
    ("AMD", 2024): [25785, 12725, 1900, 3041],
    ("AMD", 2025): [34639, 17152, 3694, 7709],
    ("INTC", 2024): [53101, 17345, -11678, 8288],
    ("INTC", 2025): [52853, 18375, -2214, 9697],
    ("QCOM", 2024): [38962, 21902, 10071, 12202],
    ("QCOM", 2025): [44284, 24546, 12355, 14012],
}


def answer_values_match(answer, values):
    numbers = {
        Decimal(n.replace(",", "")) for n in re.findall(r"-?\d[\d,]*(?:\.\d+)?", answer)
    }
    return all(
        Decimal(value) in numbers
        or "million" in answer.lower()
        and Decimal(value) / 1000000 in numbers
        or "billion" in answer.lower()
        and Decimal(value) / 1000000000 in numbers
        for value in values
    )


def question(company, year):
    return (
        f"Show {company} FY{year} consolidated GAAP revenue, gross profit, operating income, "
        "and operating cash flow. Use exact whole USD integers, original filing sources, and actual fiscal dates."
    )


async def main(args):
    store, index = FinancialStore(), ResearchIndex()
    report = {
        "checked_at": now(),
        "kind": "M5 exploratory correctness; no formal scores",
        "source_checks": [],
        "direct_workers": [],
    }
    for (company, year), expected in REFERENCE.items():
        query = store.query([company], [year])
        values = {r["metric"]: r for r in query["observations"]}
        for metric, millions in zip(METRICS, expected):
            row = values[metric]
            text = index.text(index.documents[row["document_id"]])
            inputs = row["inputs"] or [row]
            samples = []
            for source in inputs:
                needle = f"{abs(source['value']) // 1000000:,}"
                location = text.find(needle)
                samples.append(
                    {
                        "value": source["value"],
                        "found_in_collected_filing": location >= 0,
                        "passage": text[
                            max(0, location - 100) : location + len(needle) + 100
                        ],
                    }
                )
            report["source_checks"].append(
                {
                    "company": company,
                    "year": year,
                    "metric": metric,
                    "value": row["value"],
                    "accession": row["accession"],
                    "snapshot_sha256": row["snapshot_sha256"],
                    "passed": row["value"] == millions * 1000000
                    and all(s["found_in_collected_filing"] for s in samples),
                    "source_samples": samples,
                }
            )
    report["observation_slots"] = len(store.observations)
    report["available"] = sum(
        r["status"] == "available" for r in store.observations.values()
    )
    report["expected_quarter_cash_flow_gaps"] = sum(
        r["metric"] == "operating_cash_flow"
        and r["basis"] == "quarter"
        and r["status"] == "missing"
        for r in store.observations.values()
    )
    for company, year in [
        ("NVDA", 2026),
        ("AMD", 2025),
        ("INTC", 2025),
        ("QCOM", 2025),
    ]:
        events = []
        result = await financial_turn(
            store,
            {
                "question": question(company, year),
                "companies": [company],
                "years": [year],
            },
            events.append,
        )
        expected = [v * 1000000 for v in REFERENCE[company, year]]
        report["direct_workers"].append(
            {
                "company": company,
                "year": year,
                "answer": result["answer"],
                "tool_calls": [e["data"] for e in events if e["type"] == "tool"],
                "passed": not result.get("error")
                and answer_values_match(result["answer"], expected),
            }
        )
        write_json(args.output, report)
        print(
            f"Direct Financial Data {company}: {report['direct_workers'][-1]['passed']}",
            flush=True,
        )
    async with httpx.AsyncClient(base_url=args.url, timeout=240) as client:
        turn = await capture_turn(client, question("AMD", 2025), ["AMD"], [2025])
        inspections = []
        for source in turn["sources"]:
            response = await client.get(source["inspection_url"])
            inspected = response.json()
            inspections.append(
                response.status_code == 200
                and inspected["value"] == source["value"]
                and inspected["accession"] == source["accession"]
            )
        turn["passed"] = (
            turn["terminal"]["data"]["status"] == "completed"
            and bool(inspections)
            and all(inspections)
            and answer_values_match(
                turn["answer"], [v * 1000000 for v in REFERENCE["AMD", 2025]]
            )
        )
        report["application"] = turn
        unsupported = await capture_turn(
            client,
            "Show AMD FY2025 adjusted non-GAAP operating income",
            ["AMD"],
            [2025],
        )
        report["unsupported"] = {
            "answer": unsupported["answer"],
            "passed": any(
                e["type"] == "trace" and e["data"].get("decision") == "Filings Research"
                for e in unsupported["trace"]
            )
            and not any(
                e["type"] == "tool" and e["data"].get("name") == "run_analysis"
                for e in unsupported["trace"]
            ),
        }
        row = turn["sources"][0]
        snapshot = await client.get(
            f"/api/financial/snapshots/{row['snapshot_sha256']}"
        )
        from src.source_collection import digest

        report["snapshot_hash_matches"] = (
            digest(snapshot.content) == row["snapshot_sha256"]
        )
        report["missing_observation_status"] = (
            await client.get("/api/financial/observations/missing")
        ).status_code
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(args.url)
        await page.wait_for_function(
            "document.getElementById('year').options.length > 0"
        )
        await page.locator("#company").select_option("AMD")
        await page.locator("#year").select_option("2025")
        await page.locator("#question").fill(question("AMD", 2025))
        await page.locator("#ask").click()
        await page.wait_for_function(
            "!document.getElementById('ask').disabled", timeout=240000
        )
        await page.locator("#answer a").first.click()
        await page.wait_for_function(
            "document.getElementById('passage').textContent.includes('observation_id')"
        )
        report["browser"] = {
            "status": await page.locator("#status").inner_text(),
            "inspection": await page.locator("#passage").inner_text(),
            "page_errors": errors,
        }
        report["browser"]["passed"] = (
            report["browser"]["status"] == "Complete · source references checked"
            and not errors
        )
        await page.screenshot(
            path=str(ROOT / "artifacts/m5-browser.png"), full_page=True
        )
        await browser.close()
    checks = [r["passed"] for r in report["source_checks"] + report["direct_workers"]]
    report["passed"] = all(
        checks
        + [
            report["application"]["passed"],
            report["unsupported"]["passed"],
            report["browser"]["passed"],
            report["snapshot_hash_matches"],
            report["missing_observation_status"] == 404,
        ]
    )
    write_json(args.output, report)
    print(f"Saved {args.output}; passed={report['passed']}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8085")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/checks/m5-demonstration.json",
    )
    asyncio.run(main(parser.parse_args()))
