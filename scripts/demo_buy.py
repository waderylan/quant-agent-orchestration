"""Actual Buy-Side generation, graph/API, MCP, browser and artifact acceptance."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urljoin

import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn
from src.buy_side import buy_turn
from src.market_mcp import MarketGateway
from src.quant_valuation import replay
from src.analysis_artifacts import ArtifactStore
from src.source_collection import ROOT, now, write_json


SCENARIO = "For Qualcomm, assume EPS of $10 and P/E of 18x. Show the conditional 12-month implied value and upside/downside against the dated quote. Give the strongest counterargument and name unverified inputs."


async def browser_check(url):
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
        await page.locator("#year").select_option("2025")
        await page.locator("#question").fill(SCENARIO)
        await page.locator("#ask").click()
        await page.wait_for_function(
            "!document.getElementById('ask').disabled", timeout=300000
        )
        status, answer = (
            await page.locator("#status").inner_text(),
            await page.locator("#answer").inner_text(),
        )
        await page.locator("summary").click()
        trace = await page.locator("#trace").inner_text()
        c = page.locator("#artifacts a").filter(has_text="[C").first
        calculations = await page.locator(
            "#artifacts table tbody tr, #artifacts table tr"
        ).count()
        links = await page.locator("#answer a").count()
        inspection = ""
        if links:
            await page.locator("#answer a").first.click()
            await page.wait_for_timeout(300)
            inspection = await page.locator("#passage").inner_text()
        image = await page.locator("#artifacts img").count()
        checks = []
        for anchor in await page.locator("#artifacts nav a").all():
            checks.append(
                (
                    await page.request.get(
                        urljoin(url, await anchor.get_attribute("href"))
                    )
                ).status
                == 200
            )
        await browser.close()
        return {
            "status": status,
            "answer": answer,
            "trace": trace,
            "citations": links,
            "inspection_characters": len(inspection),
            "chart": bool(image),
            "artifact_downloads": checks,
            "page_errors": errors,
            "passed": bool(links and inspection and image and checks)
            and all(checks)
            and not errors
            and "Buy-Side Analyst" in trace
            and "Financial Analysis / Quant" in trace,
        }


async def main(args):
    load_dotenv(ROOT / ".env")
    report = {"checked_at": now(), "kind": args.kind, "url": args.url}
    if args.direct:
        events = []
        result = await buy_turn(
            {"question": SCENARIO, "companies": ["QCOM"], "years": [2025]},
            events.append,
            gateway=MarketGateway(mode="live"),
        )
        report["direct"] = {
            "answer": result["answer"],
            "partial": result["partial"],
            "missing": result["missing_outputs"],
            "bundles": result["valuation_bundles"],
            "trace": [e for e in events if e["type"] in ("trace", "tool", "error")],
        }
        report["replay"] = [
            replay(ArtifactStore().load(b)) for b in result["valuation_bundles"]
        ]
        write_json(args.output, report)
    if not args.browser_only:
        async with httpx.AsyncClient(base_url=args.url, timeout=400) as client:
            report["api"] = []
            for companies, question in [
                (
                    ["NVDA", "AMD", "INTC", "QCOM"],
                    "Give a dated quote snapshot for NVDA, AMD, INTC, QCOM. Show currency, price time, session, feed, delay, and freshness.",
                ),
                (
                    ["NVDA", "AMD", "INTC", "QCOM"],
                    "Compare NVDA, AMD, INTC, QCOM trailing and next-fiscal-year P/E, explain valuation premiums, give supporting evidence and the strongest counterargument. Do not substitute unqualified estimates or historical annual earnings for TTM.",
                ),
            ]:
                result = await capture_turn(client, question, companies, [2025])
                checks = []
                for source in result["sources"]:
                    if source.get("inspection_url"):
                        checks.append(
                            (await client.get(source["inspection_url"])).status_code
                            == 200
                        )
                result["inspection_checks"] = checks
                report["api"].append(result)
                write_json(args.output, report)
    report["browser"] = await browser_check(args.url)
    write_json(args.output, report)
    print(f"Saved {args.output}; browser={report['browser']['passed']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--browser-only", action="store_true")
    parser.add_argument(
        "--kind",
        default="real MCP acquisition/cache and actual local subscription generation",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/m8-native.json"
    )
    asyncio.run(main(parser.parse_args()))
