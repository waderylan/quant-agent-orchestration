"""Real five-specialist cooperation, short paths, browser links, and cancellation."""

import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import urljoin

import httpx
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn, wait_ready
from src.source_collection import ROOT, now, write_json

FULL = "For Qualcomm FY2024-FY2025, compare revenue, gross and operating margins, explain management's drivers and risk changes, and give a conditional valuation view with the strongest counterargument. State actual dates, preserve checked figures, and tell me which valuation inputs are missing."


async def browser_check(url):
    async with httpx.AsyncClient(base_url=url, timeout=30) as ready_client:
        await wait_ready(ready_client)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(url)
        await page.wait_for_function(
            "document.getElementById('year').options.length > 0"
        )
        await page.locator("#company").select_option("QCOM")
        await page.locator("#year").select_option(["2024", "2025"])
        await page.locator("#question").fill(FULL)
        await page.locator("#ask").click()
        await page.wait_for_function(
            "!document.getElementById('ask').disabled", timeout=600000
        )
        answer, status = (
            await page.locator("#answer").inner_text(),
            await page.locator("#status").inner_text(),
        )
        await page.locator("summary").click()
        trace = await page.locator("#trace").inner_text()
        inspections = []
        for prefix in ("S", "F", "C"):
            link = page.locator("#answer a").filter(has_text="[" + prefix).first
            if await link.count():
                href = await link.get_attribute("href")
                response = await page.request.get(urljoin(url, href))
                await link.click()
                await page.wait_for_timeout(200)
                inspections.append(
                    {
                        "kind": prefix,
                        "status": response.status,
                        "viewer_characters": len(
                            await page.locator("#passage").inner_text()
                        ),
                    }
                )
        all_workers = all(
            name in trace
            for name in (
                "Financial Data",
                "Financial Analysis / Quant",
                "Risk Summary",
                "Filings Research",
                "Buy-Side Analyst",
            )
        )
        # Cancel a separate actual turn after generation starts, then ensure controls reset.
        await page.locator("#question").fill(
            "Explain Qualcomm FY2025 business strategy in detail."
        )
        await page.locator("#ask").click()
        await page.wait_for_function(
            "document.getElementById('trace').textContent.includes('Codex subscription')",
            timeout=30000,
        )
        await page.locator("#stop").click()
        await page.wait_for_function(
            "!document.getElementById('ask').disabled", timeout=15000
        )
        cancelled = "stopp" in (await page.locator("#status").inner_text()).lower()
        await browser.close()
        return {
            "status": status,
            "answer": answer,
            "trace": trace,
            "inspections": inspections,
            "five_workers": all_workers,
            "cancelled_controls_reset": cancelled,
            "page_errors": errors,
            "passed": all_workers
            and {i["kind"] for i in inspections} == {"S", "F", "C"}
            and all(
                i["status"] == 200 and i["viewer_characters"] > 0 for i in inspections
            )
            and not errors
            and cancelled,
        }


async def main(args):
    report = {"checked_at": now(), "kind": args.kind, "url": args.url, "api": []}
    if not args.browser_only:
        async with httpx.AsyncClient(base_url=args.url, timeout=600) as client:
            await wait_ready(client)
            cases = [
                (["QCOM"], [2024, 2025], FULL),
                (["AMD"], [2025], "Show AMD FY2025 GAAP revenue with fiscal dates."),
                (
                    ["QCOM"],
                    [2025],
                    "Give a dated Qualcomm stock price quote with market session and freshness.",
                ),
                (
                    ["QCOM"],
                    [2024, 2025],
                    "Compare Qualcomm FY2024-FY2025 risk changes with financial context: show revenue and operating cash flow.",
                ),
            ]
            for companies, years, question in cases:
                result = await capture_turn(client, question, companies, years)
                result["inspection_checks"] = [
                    (await client.get(s["inspection_url"])).status_code == 200
                    for s in result["sources"]
                    if s.get("inspection_url")
                ]
                report["api"].append(result)
                write_json(args.output, report)
                print(
                    [
                        e["data"].get("decision")
                        for e in result["trace"]
                        if e["type"] == "trace"
                        and e["data"].get("node") == "task_selection"
                    ],
                    result["terminal"],
                    flush=True,
                )
    report["browser"] = await browser_check(args.url)
    write_json(args.output, report)
    print("Browser:", report["browser"]["passed"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8082")
    parser.add_argument(
        "--kind",
        default="Actual subscription five-worker application; market cache/live provenance retained",
    )
    parser.add_argument("--browser-only", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/m9-native.json"
    )
    asyncio.run(main(parser.parse_args()))
