"""Reproduce reported queries through actual workers, checked artifacts, and Chromium."""

import argparse
import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn
from src.source_collection import now, write_json

COMPARISON = "Show qualcomm FY2024 and FY2025 consolidated GAAP revenue, gross profit, operating income, and operating cash flow with exact USD values and sources. then compare the two years numbers"
AUTOMOTIVE = "How much of qualcomm's revenue in fy2025 was from automotive?"
EARNINGS = (
    "which company had the largest earnings growth from 24 to 25? what is the number"
)


async def checked_turn(client, question, companies, years):
    turn = await capture_turn(client, question, companies, years)
    assert turn["terminal"]["data"]["status"] == "completed", turn
    source = next((s for s in turn["sources"] if s.get("kind") == "calculation"), None)
    bundle = None
    if source:
        identity = source["bundle_id"]
        response = await client.get(f"/api/analysis/{identity}/files/bundle.json")
        response.raise_for_status()
        bundle = response.json()
        for name in ("table.csv", "chart.png", "analysis.py"):
            response = await client.get(f"/api/analysis/{identity}/files/{name}")
            response.raise_for_status()
            from src.source_collection import digest

            assert digest(response.content) == bundle["files"][name]
        for sid in bundle["sources"]:
            response = await client.get(f"/api/analysis/{identity}/observations/{sid}")
            response.raise_for_status()
        turn["bundle_id"] = identity
        turn["calculations"] = bundle["calculations"]
        turn["assessment"] = bundle.get("assessment")
    print(question, turn["seconds"], "seconds", flush=True)
    return turn, bundle


async def data_cases(client):
    records = []
    turn = await capture_turn(client, COMPARISON, ["AMD"], [2024, 2025])
    assert turn["terminal"]["data"]["status"] == "coverage_gap"
    assert (
        "Selected companies: AMD" in turn["answer"]
        and "Qualcomm (QCOM)" in turn["answer"]
    )
    records.append(turn)
    turn, bundle = await checked_turn(client, COMPARISON, ["QCOM"], [2024, 2025])
    assert len(bundle["calculations"]) >= 4
    assert any(
        "53 weeks" in w for s in bundle["sources"].values() for w in s["warnings"]
    )
    records.append(turn)
    turn, _ = await checked_turn(
        client,
        "Show NVIDIA FY2024 GAAP net income with exact USD and source",
        ["NVDA"],
        [2024],
    )
    assert any(
        s.get("metric") == "net_income" and s["value"] == 29_760_000_000
        for s in turn["sources"]
    )
    records.append(turn)
    turn, bundle = await checked_turn(
        client, EARNINGS, ["NVDA", "AMD", "INTC", "QCOM"], [2024, 2025]
    )
    assessment = bundle["assessment"]
    assert assessment["winners"][0]["company"] == "AMD"
    assert abs(
        Decimal(assessment["winners"][0]["value"])
        - (Decimal(4335) / Decimal(1641) - 1) * 100
    ) < Decimal("1e-8")
    assert assessment["excluded"][0]["company"] == "INTC"
    assert {r["company"] for r in assessment["ranking"]} == {"AMD", "NVDA", "QCOM"}
    assert "AMD" in turn["answer"] and ("net income" in turn["answer"].lower())
    records.append(turn)
    return records


async def filing_cases(client):
    records = []
    for question, year, component, value, total, share in [
        (AUTOMOTIVE, 2025, "automotive", 3957, 44284, True),
        (
            "What percentage of Qualcomm FY2024 revenue came from automotive?",
            2024,
            "automotive",
            2910,
            38962,
            True,
        ),
        (
            "What share of Qualcomm FY2025 total revenue was IoT?",
            2025,
            "iot",
            6617,
            44284,
            True,
        ),
        (
            "Show Qualcomm FY2025 handsets revenue with its source",
            2025,
            "handsets",
            27793,
            44284,
            False,
        ),
    ]:
        turn, bundle = await checked_turn(client, question, ["QCOM"], [year])
        component_source = next(
            s for s in bundle["sources"].values() if s.get("component") == component
        )
        assert component_source["value"] == value * 1_000_000
        assert component_source["filing_evidence"]["scale"] == 1_000_000
        if share:
            result = next(
                r for r in bundle["calculations"] if r["calculation_kind"] == "share"
            )
            assert abs(
                Decimal(result["value"]) - Decimal(value) / Decimal(total) * 100
            ) < Decimal("1e-8")
        assert any(
            e["type"] == "tool" and e["data"]["name"] == "extract_revenue_component"
            for e in turn["trace"]
        )
        records.append(turn)
    return records


async def browser_case(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        await page.wait_for_function(
            "document.querySelector('#year').options.length > 0"
        )
        await page.select_option("#company", ["NVDA", "AMD", "INTC", "QCOM"])
        assert await page.locator("#year").evaluate(
            "e=>Array.from(e.options,o=>o.value)"
        ) == ["2024", "2025"]
        await page.select_option("#company", ["AMD"])
        await page.select_option("#year", ["2024", "2025"])
        await page.fill("#question", COMPARISON)
        await page.click("#ask")
        await page.get_by_role("button", name="Select Qualcomm", exact=True).wait_for()
        await page.get_by_role("button", name="Select Qualcomm", exact=True).click()
        assert await page.locator("#year").evaluate(
            "e=>Array.from(e.selectedOptions,o=>o.value)"
        ) == ["2024", "2025"]
        assert await page.locator("#company").evaluate(
            "e=>Array.from(e.selectedOptions,o=>o.value)"
        ) == ["QCOM"]
        await page.select_option("#year", ["2025"])
        await page.fill("#question", AUTOMOTIVE)
        await page.click("#ask")
        await page.wait_for_function(
            "document.querySelector('#status').textContent.startsWith('Complete')",
            timeout=240000,
        )
        assert "8.9355" in await page.locator("#artifacts").inner_text()
        await page.locator("#artifacts img").wait_for()
        await page.wait_for_function(
            "document.querySelector('#artifacts img').naturalWidth > 0"
        )
        await (
            page.locator("#artifacts tr")
            .filter(has_text="automotive revenue share")
            .locator("a")
            .click()
        )
        await page.get_by_role("button", name="Inspect input [F2]", exact=True).click()
        await page.wait_for_function(
            "document.querySelector('#passage').textContent.includes('QCT revenue streams')"
        )
        assert "3,957" in await page.locator("#passage").inner_text()
        await page.screenshot(
            path="artifacts/capability-fixes-browser.png", full_page=True
        )
        result = {
            "common_year_selection": True,
            "company_correction_preserves_years": True,
            "automotive_share": True,
            "chart_loaded": True,
            "frozen_filing_input_inspected": True,
            "status": await page.locator("#status").inner_text(),
        }
        await page.select_option("#company", ["NVDA", "AMD", "INTC", "QCOM"])
        await page.select_option("#year", ["2024", "2025"])
        await page.fill("#question", EARNINGS)
        await page.click("#ask")
        await page.wait_for_function(
            "document.querySelector('#status').textContent.startsWith('Complete')",
            timeout=240000,
        )
        assert "AMD" in await page.locator("#answer").inner_text()
        assert "164.1682" in await page.locator("#artifacts").inner_text()
        result["all_company_earnings_ranking"] = True
        await browser.close()
        return result


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8086")
    parser.add_argument(
        "--phase", choices=["data", "filings", "browser", "all"], default="all"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/checks/capability-fixes.json"),
    )
    args = parser.parse_args()
    report = {
        "recorded_at": now(),
        "url": args.url,
        "phase": args.phase,
        "provider": "Local Codex subscription; not deployment-provider or formal evaluation evidence",
    }
    async with httpx.AsyncClient(base_url=args.url, timeout=240) as client:
        if args.phase in ("data", "all"):
            report["data_cases"] = await data_cases(client)
        if args.phase in ("filings", "all"):
            report["filing_cases"] = await filing_cases(client)
    if args.phase in ("browser", "all"):
        report["browser"] = await browser_case(args.url)
    report["status"] = "passed"
    write_json(args.output, report)
    print(json.dumps({"status": "passed", "output": str(args.output)}))


if __name__ == "__main__":
    asyncio.run(main())
