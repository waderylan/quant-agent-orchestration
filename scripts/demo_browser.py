"""Exercise the actual browser SSE consumer and citation viewer with Chromium."""

import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.source_collection import ROOT, now, write_json


async def main(args):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 960})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(args.url)
        await page.wait_for_function(
            "document.getElementById('year').options.length > 0"
        )
        await page.get_by_role("button", name="Research", exact=True).click()
        await page.wait_for_function(
            "!document.getElementById('ask').disabled", timeout=240000
        )
        status = await page.locator("#status").inner_text()
        answer = await page.locator("#answer").inner_text()
        citation_count = await page.locator("#answer a").count()
        if citation_count:
            await page.locator("#answer a").first.click()
            await page.locator("#passage mark").wait_for()
        exact_passage = (
            await page.locator("#passage mark").inner_text() if citation_count else ""
        )
        source_label = await page.locator("#source-label").inner_text()
        await page.locator("summary").click()
        trace = await page.locator("#trace").inner_text()
        screenshot = ROOT / "artifacts/m3-browser.png"
        screenshot.parent.mkdir(exist_ok=True)
        await page.screenshot(path=str(screenshot), full_page=True)
        result = {
            "checked_at": now(),
            "browser": browser.version,
            "url": args.url,
            "status": status,
            "answer": answer,
            "citation_links": citation_count,
            "inspected_passage": exact_passage,
            "source_label": source_label,
            "page_errors": errors,
            "routing_and_tools_visible": "Codex subscription" in trace
            and "search_sources" in trace,
            "screenshot": "artifacts/m3-browser.png",
        }
        result["passed"] = (
            status == "Complete · source references checked"
            and bool(exact_passage)
            and not errors
            and result["routing_and_tools_visible"]
        )
        write_json(args.output, result)
        print(f"Saved {args.output}; passed={result['passed']}")
        await browser.close()
        if not result["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/checks/m3-browser.json"
    )
    asyncio.run(main(parser.parse_args()))
