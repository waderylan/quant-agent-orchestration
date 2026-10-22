"""Inspect captured real M12 SSE in Chromium without repeating generation or acquisition."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.source_collection import now, write_json


async def verify(args):
    data = json.loads(args.capture.read_text(encoding="utf-8"))
    row = next(row for row in data["cases"] if row["id"] == args.case and row["variant"] == args.variant)
    frames = "".join("event: " + event["type"] + "\ndata: " + json.dumps(event["data"]) + "\n\n" for event in row["events"])
    errors, shared, inspections = [], [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(args.url)
        await page.wait_for_function("document.getElementById('year').options.length > 0")
        await page.locator("#company").select_option(row["companies"])
        await page.locator("#year").select_option(list(map(str, row["years"])))
        await page.get_by_role("button", name="Compare risk changes", exact=True).click()
        assert await page.locator("#company").evaluate("e=>Array.from(e.selectedOptions,o=>o.value)") == row["companies"]
        assert await page.locator("#year").evaluate("e=>Array.from(e.selectedOptions,o=>Number(o.value))") == row["years"]
        await page.route("**/api/chat", lambda route: route.fulfill(content_type="text/event-stream", body=frames))
        await page.locator("#question").fill(row["question"])
        await page.locator("#ask").click()
        await page.wait_for_function("!document.getElementById('ask').disabled", timeout=30000)
        for agent in dict.fromkeys(call["agent"] for call in row["live_calls"]):
            call = page.locator(".agent-call").filter(has=page.locator(".agent-name", has_text=agent)).first
            await call.click()
            detail = await page.locator("#agent-details").inner_text()
            assert "tavily-mcp · tavily_search" in detail, agent
            shared.append(agent)
        for prefix in ("S", "F", "C", "W"):
            link = page.locator("#answer a").filter(has_text="[" + prefix).first
            if not await link.count():
                continue
            sid = (await link.inner_text()).strip("[]")
            source = next(source for source in row["sources"] if source["source_id"] == sid)
            async with page.expect_response(lambda response: response.url.endswith(source["inspection_url"])) as response_info:
                await link.click()
            await (await response_info.value).body()
            await page.wait_for_timeout(100)
            text = await page.locator("#passage").inner_text()
            inspections.append({"prefix": prefix, "characters": len(text), "label": await page.locator("#source-label").inner_text()})
            if prefix == "W":
                await page.wait_for_function("url => Array.from(document.querySelectorAll('#source-label a')).some(a=>a.getAttribute('href')===url)", arg=source["url"])
                external = page.locator("#source-label a").first
                assert await external.get_attribute("rel") == "noopener noreferrer"
        await page.get_by_text("Routing and tool trace", exact=True).click()
        assert "live_mcp" in await page.locator("#trace").inner_text()
        assert not errors
        await page.screenshot(path=str(args.output.with_suffix(".png")), full_page=True)
        status = await page.locator("#status").inner_text()
        await browser.close()
    report = {"checked_at": now(), "method": "Chromium replay of captured real application SSE; source inspection uses the running native API. No new generation or Tavily calls.", "case": row["id"], "variant": row["variant"], "source_capture": str(args.capture), "shared_tool_agents": shared, "inspections": inspections, "status": status, "page_errors": errors, "example_preserves_scope": True, "passed": True}
    write_json(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--variant", default="both")
    parser.add_argument("--url", default="http://127.0.0.1:8092")
    parser.add_argument("--output", type=Path, default=Path("artifacts/m12/browser.json"))
    asyncio.run(verify(parser.parse_args()))
