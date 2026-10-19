"""Real filing Risk Summary acceptance via direct worker, HTTP, and Chromium."""

import argparse
import asyncio
import sys
from urllib.parse import urljoin
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn, wait_ready
from src.risk_summary import RiskTools, risk_turn
from src.research_index import ResearchIndex
from src.source_collection import ROOT, now, write_json


async def browser_check(url, question, company, years):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(url)
        await page.wait_for_function("document.getElementById('year').options.length > 0")
        await page.locator("#company").select_option(company)
        await page.locator("#year").select_option([str(y) for y in years])
        await page.locator("#question").fill(question)
        await page.locator("#ask").click()
        await page.wait_for_function("!document.getElementById('ask').disabled", timeout=240000)
        status, answer = await page.locator("#status").inner_text(), await page.locator("#answer").inner_text()
        count = await page.locator("#answer a").count()
        exact, original = "", 0
        if count:
            await page.locator("#answer a").first.click()
            await page.locator("#passage mark").wait_for()
            exact = await page.locator("#passage mark").inner_text()
            href = await page.get_by_role("link", name="Collected original", exact=True).get_attribute("href")
            original = (await page.request.get(urljoin(url, href))).status
        await page.get_by_text("Routing and tool trace", exact=True).click()
        trace = await page.locator("#trace").inner_text()
        await browser.close()
        return {"status": status, "answer": answer, "citations": count, "inspected_characters": len(exact), "original_status": original, "errors": errors, "distinct_worker": "Risk Summary" in trace, "passed": count >= 2 and bool(exact) and original == 200 and not errors and "Risk Summary" in trace}


async def main(args):
    report = {"checked_at": now(), "kind": "real filings and local subscription generation; no market provider calls", "url": args.url}
    if args.browser_only:
        report["browser"] = await browser_check(args.url, "What changed in AMD risk factors from FY2024 to FY2025? Give a concise material-change brief.", "AMD", [2024, 2025])
        write_json(args.output, report)
        print(f"Browser passed={report['browser']['passed']}")
        return
    if args.direct:
        events = []
        result = await risk_turn(ResearchIndex(), {"question": "What changed in AMD risk factors from FY2024 to FY2025? Explain the amendment treatment.", "companies": ["AMD"], "years": [2024, 2025]}, events.append)
        report["direct"] = {"answer": result["answer"], "partial": result["partial"], "changes": result["risk_changes"], "trace": [e for e in events if e["type"] == "trace"]}
        write_json(args.output, report)
    async with httpx.AsyncClient(base_url=args.url, timeout=300) as client:
        await wait_ready(client)
        report["api"] = []
        for company, question, years in [
            ("QCOM", "Did Qualcomm add a customer concentration risk from FY2024 to FY2025, or move/rephrase existing language? Inspect the complete sections and cite before/after.", [2024, 2025]),
            ("AMD", "Did AMD remove its annual risks in the FY2025 Q3 10-Q? Compare with annual context; do not treat quarterly omissions as removed risks.", [2025]),
            ("NVDA", "What changed in NVIDIA risk factors from FY2020 to FY2021?", [2020, 2021]),
        ]:
            result = await capture_turn(client, question, [company], years)
            inspections = []
            for s in result["sources"]:
                response = await client.get(s["inspection_url"])
                inspections.append(response.status_code == 200 and response.json()["text"] == s["text"])
            report["api"].append({**result, "inspection_checks": inspections})
            write_json(args.output, report)
    report["browser"] = await browser_check(args.url, "What changed in AMD risk factors from FY2024 to FY2025? Give a concise material-change brief and amendment qualification.", "AMD", [2024, 2025])
    write_json(args.output, report)
    print(f"Saved {args.output}; browser={report['browser']['passed']}; API statuses={[r['terminal']['data']['status'] for r in report['api']]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--browser-only", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/m7-application.json")
    asyncio.run(main(parser.parse_args()))
