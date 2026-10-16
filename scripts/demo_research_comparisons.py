"""Capture ordinary multi-company filing questions through the local application."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn

QUESTIONS = [
    "what were comon factors driving revenue growth for all companies",
    "Which revenue growth drivers were shared by NVIDIA, AMD, Intel and Qualcomm in FY2025, and which were company-specific? Check whether each company actually grew.",
    "Compare the demand headwinds described by AMD and Intel in FY2024 and FY2025. Cite the filings and distinguish annual from quarterly evidence.",
]


async def browser_case(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(url)
            await page.wait_for_function(
                "document.querySelector('#year').options.length > 0"
            )
            await page.select_option("#company", ["NVDA", "AMD", "INTC", "QCOM"])
            await page.select_option("#year", ["2024", "2025"])
            await page.fill("#question", QUESTIONS[0])
            await page.click("#ask")
            await page.wait_for_function(
                "document.querySelector('#ask').disabled === false", timeout=240000
            )
            status = await page.locator("#status").inner_text()
            answer = await page.locator("#answer").inner_text()
            assert status.startswith("Complete"), status
            assert all(
                name in answer for name in ("NVIDIA", "AMD", "Intel", "Qualcomm")
            ), answer
            assert "declin" in answer.lower() or "decreas" in answer.lower(), answer
            citation = page.locator("#sources button").first
            await citation.click()
            await page.wait_for_function(
                "document.querySelector('#passage').textContent.length > 100"
            )
            await page.screenshot(
                path="artifacts/research-comparison-browser.png", full_page=True
            )
            return {
                "status": status,
                "answer": answer,
                "source_inspection": True,
                "screenshot": "artifacts/research-comparison-browser.png",
            }
        finally:
            await browser.close()


async def run(args):
    results = []
    if args.browser:
        result = await browser_case(args.url)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(result), flush=True)
        return
    async with httpx.AsyncClient(base_url=args.url, timeout=300) as client:
        for number, question in enumerate(QUESTIONS[: args.count]):
            companies = (
                ["AMD", "INTC"] if number == 2 else ["NVDA", "AMD", "INTC", "QCOM"]
            )
            years = [2025] if number == 1 else [2024, 2025]
            result = await capture_turn(client, question, companies, years)
            results.append(result)
            print(
                json.dumps(
                    {
                        k: result[k]
                        for k in ("question", "answer", "terminal", "seconds", "trace")
                    }
                ),
                flush=True,
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8086")
    parser.add_argument("--count", type=int, choices=[1, 2, 3], default=3)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
