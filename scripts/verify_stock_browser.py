"""Chromium checks against the local UI, replaying recorded answers without generation."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.async_api import async_playwright
from src.analysis_artifacts import ArtifactStore
from src.source_collection import ROOT, now, write_json


async def main(args):
    recorded = json.loads(args.review.read_text(encoding="utf-8"))
    rows = {row["case"]["id"]: row for row in recorded["results"]}
    report = {"checked_at": now(), "kind": "Actual Chromium UI with recorded SSE answers; real local source/download routes; no generation or live market calls", "checks": []}
    active = None
    requests = []
    errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def replay_response(route):
            requests.append(route.request.post_data_json)
            row = rows[active]
            events = [{"type": "answer", "data": row["result"]["answer"]}]
            for identity, bundle in row["bundles"].items():
                events.append({"type": "artifacts", "data": {"bundle_id": identity, "chart_url": f"/api/analysis/{identity}/files/chart.png", "downloads": ArtifactStore().downloads(identity), "calculations": bundle["calculations"]}})
            events += [{"type": "sources", "data": row["result"]["sources"]}, row["result"]["terminal"]]
            body = "".join(f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n" for event in events)
            await route.fulfill(status=200, content_type="text/event-stream", body=body)

        await page.route("**/api/chat", replay_response)
        await page.goto(args.url)
        await page.wait_for_function("document.getElementById('year').options.length > 0")
        for case_id, button, companies in [
            ("capabilities-system", "System capabilities", ["QCOM"]),
            ("overview-recheck", "Valuation overview", ["NVDA", "AMD", "INTC", "QCOM"]),
            ("changed-selection", "Valuation overview", ["INTC"]),
            ("grid-recheck", None, ["QCOM"]),
        ]:
            active = case_id
            await page.select_option("#company", companies)
            await page.select_option("#year", ["2025"])
            if button:
                await page.get_by_role("button", name=button, exact=True).click()
            else:
                await page.fill("#question", rows[case_id]["case"]["question"])
            await page.click("#ask")
            await page.wait_for_function("!document.getElementById('ask').disabled")
            answer = await page.inner_text("#answer")
            status = await page.inner_text("#status")
            assert requests[-1]["companies"] == companies
            assert requests[-1]["years"] == [2025]
            assert "undefined" not in await page.inner_text("#sources")
            checks = {"case": case_id, "companies_sent": requests[-1]["companies"], "status": status, "table_rows": await page.locator("#answer table tr").count()}
            if case_id == "capabilities-system":
                assert "Buy-Side Analyst" in answer and status == "Complete"
            elif case_id == "overview-recheck":
                assert checks["table_rows"] == 5
                assert all(symbol in answer for symbol in companies)
                await page.locator("#answer table a").first.click()
                await page.wait_for_function("document.getElementById('passage').textContent.length > 30")
                checks["citation_inspection_characters"] = len(await page.inner_text("#passage"))
                await page.screenshot(path=str(ROOT / "artifacts/buy-side-overview.png"), full_page=True)
            elif case_id == "changed-selection":
                assert "INTC" in answer and "NVDA" not in answer and "QCOM" not in answer
            else:
                assert checks["table_rows"] == 4
                image = page.locator("#artifacts img")
                await image.wait_for()
                assert await image.evaluate("image => image.complete && image.naturalWidth > 0")
                downloads = []
                for anchor in await page.locator("#artifacts nav a").all():
                    response = await page.request.get(args.url + await anchor.get_attribute("href"))
                    downloads.append(response.status)
                assert len(downloads) == 4 and all(status == 200 for status in downloads)
                checks["downloads"] = downloads
            checks["passed"] = True
            report["checks"].append(checks)
        # Table cells are untrusted text even when they resemble executable markup.
        await page.evaluate("""() => { document.getElementById('answer').textContent = '| Field | Value |\\n|---|---|\\n| Hostile | <img src=x onerror=window.__injected=1> |'; displaySources([]); }""")
        assert await page.locator("#answer table").count() == 1
        assert await page.locator("#answer img").count() == 0
        assert not await page.evaluate("Boolean(window.__injected)")
        report["untrusted_table_cells_remain_text"] = True
        report["page_errors"] = errors
        assert not errors
        await browser.close()
    write_json(args.output, report)
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8084")
    parser.add_argument("--review", type=Path, default=ROOT / "artifacts/buy-side-research-review.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/buy-side-browser.json")
    asyncio.run(main(parser.parse_args()))
