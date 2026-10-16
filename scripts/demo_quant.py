"""Actual Quant worker, Data-to-Quant application, browser, and failure demonstrations."""

import argparse
import asyncio
import copy
import csv
import io
import sys
from decimal import Decimal
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_financials import REFERENCE
from scripts.demo_support import capture_turn
from src.analysis_artifacts import ArtifactStore
from src.financial_data import FinancialStore, METRICS
from src.financial_workflow import FinancialTools
from src.quant_analysis import run_isolated
from src.quant_workflow import direct_inputs, quant_turn, QuantTools
from src.source_collection import ROOT, digest, now, write_json


def reference_value(source):
    if (
        source["company"] == "AMD"
        and source["fiscal_year"] == 2025
        and source["basis"] == "ytd"
        and source["metric"] == "operating_cash_flow"
    ):
        # Original Q1/Q2/Q3 statements: net operating cash flow, USD millions.
        return Decimal({"Q1": 939, "Q2": 2950, "Q3": 5109}[source["period"]]) * 1000000
    return (
        Decimal(
            REFERENCE[source["company"], source["fiscal_year"]][
                METRICS.index(source["metric"])
            ]
        )
        * 1000000
    )


def verify_bundle(bundle):
    expected = {
        sid: reference_value(source)
        for sid, source in bundle["sources"].items()
        if source["basis"] == "annual" or source["metric"] == "operating_cash_flow"
    }
    checks = []
    for row in bundle["calculations"]:
        values = [expected[s] for s in row["inputs"]]
        kind = row["calculation_kind"]
        if kind == "value":
            value = values[0]
        elif kind == "growth":
            value = (values[0] / values[1] - 1) * 100
        elif kind == "margin":
            value = values[0] / values[1] * 100
        else:
            value = values[0] - values[1]
        expected[row["source_id"]] = value
        checks.append(abs(value - Decimal(row["value"])) <= Decimal("1e-8"))
    return bool(checks) and all(checks)


def annual_question(company, years):
    return (
        f"Calculate {company} FY{years[0]} versus FY{years[1]} revenue growth, gross and operating margins "
        "for both years, each margin change in percentage points, and operating cash-flow growth. "
        "State actual dates and comparison qualifications; provide a table/chart."
    )


def failure_checks(store, artifacts):
    state = {
        "question": "Calculate AMD revenue, gross profit, operating income and operating cash flow growth",
        "companies": ["AMD"],
        "years": [2024, 2025],
    }
    base = direct_inputs(store, state)
    code = "results=[{'label':'Growth','kind':'growth','inputs':['F5','F1'],'value':(values['F5']/values['F1']-1)*100}]"
    other = FinancialTools(store, ["NVDA"], [2025])(
        "query_financials", {"metrics": ["revenue"]}
    )["sources"][0]
    cross = {**base, "F1": other}
    zero = copy.deepcopy(base)
    zero["F1"]["value"] = 0
    cases = [
        ("cross-company comparison", cross, code, "actual source observations"),
        (
            "zero denominator",
            zero,
            code,
            "explicit synthetic failure fixture; not company evidence",
        ),
        ("missing input", base, code.replace("F1", "F999"), "unregistered identifier"),
        ("prohibited execution", base, "import os", "prohibited generated syntax"),
        (
            "incorrect arithmetic",
            base,
            code.replace("-1", "+1"),
            "deliberately wrong formula",
        ),
    ]
    checks = []
    for name, sources, program, kind in cases:
        tools = QuantTools(sources, artifacts)
        try:
            tools("run_analysis", {"code": program})
        except ValueError as error:
            checks.append(
                {
                    "case": name,
                    "evidence_kind": kind,
                    "error": str(error),
                    "passed": tools.bundle is None,
                }
            )
        else:
            checks.append({"case": name, "passed": False})
    try:
        run_isolated(code, base, timeout=0.001)
    except ValueError as error:
        checks.append(
            {
                "case": "child deadline",
                "error": str(error),
                "passed": "timed out" in str(error),
            }
        )
    else:
        checks.append({"case": "child deadline", "passed": False})
    return checks


async def main(args):
    store, artifacts = FinancialStore(), ArtifactStore()
    report = {
        "checked_at": now(),
        "kind": "M6 exploratory acceptance; no formal scores",
        "direct_workers": [],
        "quarter_workers": [],
    }
    report["execution_scope"] = (
        "application/browser only"
        if args.application_only
        else "direct roles plus application/browser"
    )
    cases = (
        []
        if args.application_only
        else [
            ("NVDA", [2025, 2026]),
            ("AMD", [2024, 2025]),
            ("INTC", [2024, 2025]),
            ("QCOM", [2024, 2025]),
        ]
    )
    for company, years in cases:
        state = {
            "question": annual_question(company, years),
            "companies": [company],
            "years": years,
        }
        state["financial_sources"] = direct_inputs(store, state)
        events = []
        result = await quant_turn(state, events.append, artifacts=artifacts)
        bundle = (
            artifacts.load(result["bundle_id"]) if result.get("bundle_id") else None
        )
        metrics = {r["metric"] for r in bundle["calculations"]} if bundle else set()
        required = {
            "revenue_growth",
            "gross_margin",
            "operating_margin",
            "gross_margin_change",
            "operating_margin_change",
            "operating_cash_flow_growth",
        }
        check = {
            "company": company,
            "years": years,
            "question": state["question"],
            "answer": result["answer"],
            "bundle_id": result.get("bundle_id"),
            "code": bundle["code"] if bundle else None,
            "calculations": bundle["calculations"] if bundle else [],
            "tool_calls": [e["data"]["name"] for e in events if e["type"] == "tool"],
            "passed": bool(bundle)
            and not result.get("error")
            and required <= metrics
            and verify_bundle(bundle),
        }
        if company == "QCOM":
            check["passed"] &= "53" in result["answer"] and any(
                r["warnings"] for r in bundle["calculations"]
            )
        report["direct_workers"].append(check)
        write_json(args.output, report)
        print(f"Direct Quant {company}: {check['passed']}", flush=True)
    for quarter in () if args.application_only else (2, 3, 4):
        state = {
            "question": f"Calculate AMD FY2025 Q{quarter}-only operating cash flow from compatible cumulative inputs, with actual dates and a table/chart.",
            "companies": ["AMD"],
            "years": [2025],
        }
        state["financial_sources"] = direct_inputs(store, state)
        events = []
        result = await quant_turn(state, events.append, artifacts=artifacts)
        bundle = (
            artifacts.load(result["bundle_id"]) if result.get("bundle_id") else None
        )
        expected = Decimal({2: 2011, 3: 2159, 4: 2600}[quarter]) * 1000000
        matching = (
            [
                r
                for r in bundle["calculations"]
                if r["metric"] == "operating_cash_flow"
                and r["period"] == f"Q{quarter}"
                and r["calculation_kind"] == "quarter"
            ]
            if bundle
            else []
        )
        report["quarter_workers"].append(
            {
                "quarter": quarter,
                "answer": result["answer"],
                "bundle_id": result.get("bundle_id"),
                "calculations": bundle["calculations"] if bundle else [],
                "code": bundle["code"] if bundle else None,
                "passed": len(matching) == 1
                and Decimal(matching[0]["value"]) == expected
                and verify_bundle(bundle),
            }
        )
        write_json(args.output, report)
        print(
            f"Direct Quant AMD Q{quarter}: {report['quarter_workers'][-1]['passed']}",
            flush=True,
        )
    report["failures"] = failure_checks(store, artifacts)
    async with httpx.AsyncClient(base_url=args.url, timeout=420) as client:
        turn = await capture_turn(
            client, annual_question("AMD", [2024, 2025]), ["AMD"], [2024, 2025]
        )
        calcs = [s for s in turn["sources"] if s.get("kind") == "calculation"]
        identity = calcs[0]["bundle_id"] if calcs else None
        bundle_response = await client.get(
            f"/api/analysis/{identity}/files/bundle.json"
        )
        bundle = bundle_response.json() if bundle_response.status_code == 200 else None
        turn["verified_against_independent_references"] = bool(
            bundle
        ) and verify_bundle(bundle)
        turn["file_checks"] = []
        if bundle:
            for name, expected_hash in bundle["files"].items():
                response = await client.get(f"/api/analysis/{identity}/files/{name}")
                turn["file_checks"].append(
                    {
                        "name": name,
                        "passed": response.status_code == 200
                        and digest(response.content) == expected_hash,
                    }
                )
            csv_response = await client.get(f"/api/analysis/{identity}/files/table.csv")
            table = list(csv.DictReader(io.StringIO(csv_response.text)))
            turn["table_matches_ledger"] = [r["value"] for r in table] == [
                r["value"] for r in bundle["calculations"]
            ]
            inspected = (await client.get(calcs[0]["inspection_url"])).json()
            first_input = inspected["input_sources"][0]
            first_input = (await client.get(first_input["inspection_url"])).json()
            turn["input_inspection"] = first_input
            if first_input["kind"] == "financial_observation":
                snapshot = await client.get(first_input["snapshot_url"])
                turn["frozen_snapshot_hash_matches"] = (
                    digest(snapshot.content) == first_input["snapshot_sha256"]
                )
        roles = [e["data"].get("agent") for e in turn["trace"] if e["type"] == "trace"]
        turn["passed"] = (
            turn["terminal"]["data"]["status"] == "completed"
            and bool(calcs)
            and turn["verified_against_independent_references"]
            and all(c["passed"] for c in turn.get("file_checks", []))
            and turn.get("table_matches_ledger")
            and "Financial Data" in roles
            and "Financial Analysis / Quant" in roles
        )
        report["application"] = turn
        quarter_turn = await capture_turn(
            client,
            "Calculate AMD FY2025 Q4-only operating cash flow using compatible cumulative inputs, with exact USD, fiscal dates, and a table/chart.",
            ["AMD"],
            [2025],
        )
        quarter_calculations = [
            s
            for s in quarter_turn["sources"]
            if s.get("kind") == "calculation"
            and s.get("metric") == "operating_cash_flow"
            and s.get("period") == "Q4"
        ]
        quarter_turn["passed"] = (
            quarter_turn["terminal"]["data"]["status"] == "completed"
            and len(quarter_calculations) == 1
            and Decimal(quarter_calculations[0]["value"]) == 2600000000
            and quarter_calculations[0]["start"] == "2025-09-28"
        )
        report["quarter_application"] = quarter_turn
        report["unknown_artifact_status"] = (
            await client.get("/api/analysis/not-a-bundle/files/table.csv")
        ).status_code
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 960})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(args.url)
        await page.wait_for_function(
            "document.getElementById('year').options.length > 0"
        )
        await page.locator("#company").select_option("AMD")
        await page.locator("#year").select_option(["2024", "2025"])
        await page.locator("#question").fill(annual_question("AMD", [2024, 2025]))
        await page.locator("#ask").click()
        await page.wait_for_function(
            "!document.getElementById('ask').disabled", timeout=420000
        )
        status = await page.locator("#status").inner_text()
        await page.locator("#artifacts table").wait_for()
        await page.locator("#artifacts table a").first.click()
        await page.wait_for_function(
            "document.getElementById('passage').textContent.includes('formula')"
        )
        await page.get_by_role(
            "button", name="Inspect input", exact=False
        ).first.click()
        await page.wait_for_function(
            "document.getElementById('passage').textContent.includes('observation_id')"
        )
        chart_loaded = await page.locator("#artifacts img").evaluate(
            "img => img.complete && img.naturalWidth > 0"
        )
        report["browser"] = {
            "status": status,
            "table_rows": await page.locator("#artifacts table tr").count() - 1,
            "chart_loaded": chart_loaded,
            "downloads": await page.locator("#artifacts nav a").count(),
            "input_inspection": await page.locator("#passage").inner_text(),
            "page_errors": errors,
            "passed": status == "Complete · citations verified"
            and chart_loaded
            and not errors,
        }
        screenshot = ROOT / "artifacts" / (args.output.stem.lower() + ".png")
        await page.screenshot(path=str(screenshot), full_page=True)
        report["browser"]["screenshot"] = str(screenshot.relative_to(ROOT))
        await browser.close()
    report["passed"] = all(
        r["passed"]
        for key in ("direct_workers", "quarter_workers", "failures")
        for r in report[key]
    )
    report["passed"] &= (
        report["application"]["passed"]
        and report["quarter_application"]["passed"]
        and report["browser"]["passed"]
        and report["unknown_artifact_status"] == 404
    )
    write_json(args.output, report)
    print(f"Saved {args.output}; passed={report['passed']}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8086")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/research/M6_DEMONSTRATION_RESULTS.json",
    )
    parser.add_argument("--application-only", action="store_true")
    asyncio.run(main(parser.parse_args()))
