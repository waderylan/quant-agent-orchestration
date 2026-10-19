"""Exercise real Current Developments, POST/SSE, and native Chromium source inspection."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_support import capture_turn, wait_ready
from src.current_developments import current_turn
from src.live_mcp import LiveGateway, UsageLedger, sanitized
from src.source_collection import ROOT, now, write_json

CASES = {
    "nvda": ("What has happened at NVIDIA since its latest filing? Cite dated sources.", ["NVDA"], [2026], ["current"]),
    "verify": ("Is the export-control risk in AMD's FY2025 10-K still current? Check for an official update.", ["AMD"], [2025], ["research"]),
    "mixed": ("Explain Qualcomm's FY2025 revenue change and what has happened since the filing.", ["QCOM"], [2024, 2025], ["data", "quant", "research", "current"]),
    "price": ("What is NVIDIA's stock price and P/E?", ["NVDA"], [2026], []),
    "historical": ("As of FY2024, what did Intel say about its foundry strategy? Use only the filings.", ["INTC"], [2024], ["research"]),
}


def inspect_turn(turn, name):
    expected = CASES[name][3]
    selection = next(e["data"] for e in turn["trace"] if e["type"] == "trace" and e["data"].get("node") == "task_selection")
    assert selection["task"]["required_workers"] == expected, selection
    live = [e["data"] for e in turn["trace"] if e["type"] == "trace" and e["data"].get("node") == "live_mcp"]
    if name in ("price", "historical"):
        assert not live
    elif name == "verify":
        assert len(live) == 1 and live[0]["tool"] == "tavily_search" and live[0]["agent"] == "Filings Research"
        assert "[S" in turn["answer"] and "[W" in turn["answer"]
    else:
        assert {e["tool"] for e in live} == {"tavily_search", "tavily_extract"}, live
        assert "[W" in turn["answer"]
    assert turn["terminal"]["data"]["status"] in (("coverage_gap",) if name == "price" else ("completed", "partial")), turn["terminal"]
    return {"passed": True, "workers": expected, "live_events": live}


def parse_browser(text, question):
    events = []
    for frame in text.split("\n\n"):
        lines = frame.splitlines()
        kind = next((l[7:] for l in lines if l.startswith("event: ")), None)
        body = next((l[6:] for l in lines if l.startswith("data: ")), None)
        if kind and body:
            events.append({"type": kind, "data": json.loads(body)})
    return {"question": question, "answer": next(e["data"] for e in reversed(events) if e["type"] == "answer"), "sources": next((e["data"] for e in reversed(events) if e["type"] == "sources"), []), "terminal": events[-1], "trace": [e for e in events if e["type"] in ("trace", "tool", "error")]}


async def browser_checks(url, output):
    checks, turns, errors = [], {}, []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(url)
        await page.wait_for_function("document.getElementById('year').options.length > 0")
        assert not await page.get_by_role("button", name="Stock prices", exact=True).count()
        for name in ("nvda", "verify", "mixed"):
            question, companies, years, _ = CASES[name]
            await page.locator("#company").select_option(companies)
            await page.locator("#year").select_option(list(map(str, years)))
            if name != "mixed":
                await page.get_by_role("button", name="Current developments" if name == "nvda" else "Check an official update", exact=True).click()
                assert await page.locator("#company").evaluate("e=>Array.from(e.selectedOptions,o=>o.value)") == companies
                question = await page.locator("#question").input_value()
            else:
                question = "Calculate Qualcomm FY2024 to FY2025 revenue growth with actual dates."
                await page.locator("#question").fill(question)
            async with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/api/chat"), timeout=600000) as response_info:
                await page.locator("#ask").click()
            response = await response_info.value
            turn = parse_browser(await response.text(), question)
            await page.wait_for_function("!document.getElementById('ask').disabled", timeout=600000)
            if name == "mixed":
                selection = next(e["data"] for e in turn["trace"] if e["type"] == "trace" and e["data"].get("node") == "task_selection")
                assert selection["task"]["required_workers"] == ["data", "quant"]
                turn["checks"] = {"passed": True, "workers": ["data", "quant"]}
            else:
                turn["checks"] = inspect_turn(turn, name)
            turns[name] = turn
            for prefix in (("W",) if name == "nvda" else ("S",) if name == "verify" else ("C",)):
                link = page.locator("#answer a").filter(has_text="[" + prefix).first
                assert await link.count(), (name, prefix, turn["answer"])
                await link.click()
                await page.wait_for_timeout(150)
                label = await page.locator("#source-label").inner_text()
                excerpt = await page.locator("#passage").inner_text()
                assert excerpt
                check = {"kind": prefix, "label": label, "excerpt_characters": len(excerpt), "passed": True}
                if prefix == "W":
                    external = page.locator("#source-label a")
                    assert await external.get_attribute("rel") == "noopener noreferrer"
                    assert await external.get_attribute("target") == "_blank"
                    check["external_url"] = await external.get_attribute("href")
                checks.append(check)
            write_json(output, sanitized({"browser": {"same_session_inspections": checks, "turns": turns, "page_errors": errors}}))
            print("Browser", name, turn["terminal"]["data"]["status"], flush=True)
        await page.screenshot(path=str(ROOT / "artifacts/m10-browser.png"), full_page=True)
        assert not errors
        await browser.close()
    return {"passed": True, "same_session_inspections": checks, "page_errors": errors, "turns": turns}


async def main(args):
    load_dotenv()
    before = UsageLedger().snapshot()
    report = {"checked_at": now(), "kind": "Real Tavily Remote MCP and local Codex subscription", "ledger_before": before}
    if args.direct:
        emitted = []
        question, companies, years, _ = CASES["nvda"]
        result = await current_turn({"question": question, "companies": companies, "years": years, "live_intent": "developments"}, emitted.append, gateway=LiveGateway())
        report["direct"] = {**result, "trace": [e for e in emitted if e["type"] in ("trace", "tool", "error")]}
        assert result["live_sources"] and "[W" in result["answer"]
        assert {s["tool"] for s in result["live_sources"].values()} == {"tavily_search", "tavily_extract"}
        print(json.dumps({"answer": result["answer"], "registered_sources": [{k:s.get(k) for k in ("source_id", "company", "publisher", "published_date", "source_tier", "freshness", "inspection_url")} for s in result["live_sources"].values()]}), flush=True)
    elif args.browser:
        report["browser"] = await browser_checks(args.url, args.output)
    else:
        report["application"] = {}
        async with httpx.AsyncClient(base_url=args.url, timeout=600) as client:
            await wait_ready(client)
            for name in CASES if args.case == "all" else [args.case]:
                question, companies, years, _ = CASES[name]
                if args.refresh:
                    question += " Refresh live sources."
                turn = await capture_turn(client, question, companies, years)
                turn["checks"] = inspect_turn(turn, name)
                inspections = []
                for s in turn["sources"]:
                    if s.get("inspection_url"):
                        response = await client.get(s["inspection_url"])
                        inspections.append({"source_id": s["source_id"], "status": response.status_code})
                        assert response.status_code == 200
                turn["inspections"] = inspections
                report["application"][name] = turn
                write_json(args.output, sanitized(report))
                print(name, turn["terminal"]["data"]["status"], flush=True)
    report["ledger_after"] = UsageLedger().snapshot()
    report["reserved_credits"] = report["ledger_after"]["reserved_credits"] - before["reserved_credits"]
    write_json(args.output, sanitized(report))
    print(json.dumps({"output": str(args.output), "reserved_credits": report["reserved_credits"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:8088")
    parser.add_argument("--case", choices=["all", *CASES], default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/m10-native.json")
    asyncio.run(main(parser.parse_args()))
