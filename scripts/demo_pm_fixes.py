"""Exercise corrected PM workflows, source inspection and partial status in Chromium."""

import argparse
import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]


async def main(args):
    cases = {
        case["id"]: case
        for case in json.loads(
            (ROOT / "tests/fixtures/pm/questions.json").read_text(
                encoding="utf-8"
            )
        )
    }
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(args.url)
            await page.wait_for_function(
                "document.querySelector('#year').options.length > 0"
            )
            for identity in ["P11", "P13", "P24", "P25", "P17", "P18", "P19", "P22"]:
                case = cases[identity]
                await page.select_option("#company", case["companies"])
                await page.select_option("#year", [str(year) for year in case["years"]])
                await page.fill("#question", case["question"])
                await page.click("#ask")
                await page.wait_for_function(
                    "!document.querySelector('#ask').disabled", timeout=300000
                )
                status, answer = (
                    await page.locator("#status").inner_text(),
                    await page.locator("#answer").inner_text(),
                )
                assert status.startswith(
                    "Clarification"
                    if identity == "P22"
                    else "Partial"
                    if identity == "P18"
                    else "Complete"
                ), (identity, status, answer)
                assert (
                    await page.locator("#sources button").count() > 0
                    or identity == "P22"
                )
                if identity == "P13":
                    assert any(
                        value in answer
                        for value in ("2,011,000,000", "2.011 billion", "2.011B")
                    )
                    assert any(
                        value in answer
                        for value in (
                            "2,950,000,000",
                            "2.950 billion",
                            "2.95 billion",
                            "2.950B",
                        )
                    )
                elif identity == "P24":
                    assert (
                        "hypothetical" in answer.lower() or "scenario" in answer.lower()
                    )
                elif identity == "P25":
                    assert "31.49" in answer and ("EUR" in answer or "€" in answer)
                elif identity == "P17":
                    assert "[S999]" not in answer and any(
                        value in answer for value in ("34.6", "34,639")
                    )
                elif identity == "P18":
                    assert (
                        "Still needed:"
                        in await page.locator("#scope-help").inner_text()
                    )
                    assert "Broadcom" in answer
                elif identity == "P19":
                    assert "AMD" in answer and "Intel" in answer
                    assert await page.locator("#company").evaluate(
                        "e=>Array.from(e.selectedOptions,o=>o.value)"
                    ) == ["AMD", "INTC"]
                if identity not in ("P17", "P18", "P22"):
                    await page.wait_for_function(
                        "document.querySelector('#artifacts img')?.naturalWidth > 0"
                    )
                    ledger_url = (
                        await page.locator("#artifacts a")
                        .filter(has_text="Calculation ledger")
                        .get_attribute("href")
                    )
                    response = await page.request.get(args.url + ledger_url)
                    assert response.ok
                    ledger = await response.json()
                    calculations = ledger["calculations"]
                    if identity == "P11":
                        ratios = [
                            Decimal(row["value"])
                            for row in calculations
                            if row["calculation_kind"] == "ratio"
                        ]
                        assert any(
                            abs(value - Decimal(3041) / Decimal(1641)) < Decimal("1e-8")
                            for value in ratios
                        )
                        assert any(
                            abs(value - Decimal(7709) / Decimal(4335)) < Decimal("1e-8")
                            for value in ratios
                        )
                    elif identity == "P24":
                        assert any(
                            row["metric"] == "scenario_total_revenue"
                            and Decimal(row["value"]) == 48241000000
                            for row in calculations
                        )
                        assert any(
                            row["calculation_kind"] == "scenario_share"
                            and abs(
                                Decimal(row["value"])
                                - Decimal(7914) / Decimal(48241) * 100
                            )
                            < Decimal("1e-8")
                            for row in calculations
                        )
                    elif identity == "P25":
                        assert any(
                            row["unit"] == "EUR"
                            and Decimal(row["value"]) == 31490000000
                            for row in calculations
                        )
                    await (
                        page.locator("#sources button")
                        .filter(has_text="[C1]")
                        .first.click()
                    )
                    await page.wait_for_function(
                        "document.querySelector('#passage').textContent.includes('input_sources')"
                    )
                    if identity in ("P24", "P25"):
                        assert (
                            '"origin": "user"'
                            in await page.locator("#passage").inner_text()
                        )
                elif identity != "P22":
                    await page.locator("#sources button").first.click()
                    await page.wait_for_function(
                        "document.querySelector('#passage').textContent.length > 100"
                    )
                await page.screenshot(
                    path=str(ROOT / f"artifacts/pm-browser-{identity}.png"),
                    full_page=True,
                )
                result = {
                    "id": identity,
                    "question": case["question"],
                    "status": status,
                    "answer": answer,
                    "source_inspection": True,
                }
                results.append(result)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps(
                        {"url": args.url, "cases": results},
                        indent=2,
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                print(json.dumps({"id": identity, "status": status}), flush=True)
        finally:
            await browser.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8086")
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
