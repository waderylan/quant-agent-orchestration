"""Quant specialist with generated programs, independent validation, and artifacts."""

from __future__ import annotations

import json
import re
from contextlib import aclosing

from src.analysis_artifacts import ArtifactStore
from src.codex_model import stream as codex_stream
from src.financial_data import METRICS
from src.financial_workflow import FinancialTools
from src.quant_analysis import run_isolated, validate_results
from src.source_collection import ROOT
from src.request_routing import requested_metrics
from decimal import Decimal
from src.response_contract import OUTCOME_TOOL, OutcomeTools, checked_answer

TOOLS = [
    {
        "type": "function",
        "name": "run_analysis",
        "description": "Execute a bounded arithmetic Python program over registered F inputs. Independently validate values, units, periods, revisions, and executed lineage; publish a table/chart/code/ledger only on success.",
        "inputSchema": {
            "type": "object",
            "properties": {"code": {"type": "string", "maxLength": 12000}},
            "required": ["code"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "inspect_calculation",
        "description": "Inspect a verified C calculation, its formula, exact value, and source lineage.",
        "inputSchema": {
            "type": "object",
            "properties": {"source_id": {"type": "string"}},
            "required": ["source_id"],
            "additionalProperties": False,
        },
    },
]


def prefetch_for_analysis(question):
    metrics = requested_metrics(question) or list(METRICS)
    quarter = re.search(r"\bQ([1-4])(?:\b|-)", question, re.I)
    if not quarter:
        return [{"period": "FY", "basis": "annual", "metrics": metrics}]
    number = int(quarter[1])
    if number == 4:
        return [
            {"period": "FY", "basis": "annual", "metrics": metrics},
            {"period": "Q3", "basis": "ytd", "metrics": metrics},
        ]
    selections = [{"period": f"Q{number}", "basis": "quarter", "metrics": metrics}]
    if number > 1:
        selections += [
            {"period": f"Q{n}", "basis": "ytd", "metrics": ["operating_cash_flow"]}
            for n in (number, number - 1)
        ]
    return selections


def direct_inputs(store, state):
    tools = FinancialTools(store, state["companies"], state["years"])
    for selection in prefetch_for_analysis(state["question"]):
        tools("query_financials", selection)
    return tools.sources


def earnings_assessment(calculations, sources, *, order="percentage"):
    """Rank within-company growth only; a loss baseline is not a percentage base."""
    by_company = {}
    for source in sources.values():
        if source["metric"] == "net_income" and source["basis"] == "annual":
            by_company.setdefault(source["company"], []).append(source)
    eligible, excluded = [], []
    for company, figures in by_company.items():
        figures = sorted(figures, key=lambda r: r["fiscal_year"])
        if len(figures) != 2:
            raise ValueError(
                "Earnings ranking requires exactly two annual net-income observations per company"
            )
        old, new = figures
        ids = {old["source_id"], new["source_id"]}
        if Decimal(str(old["value"])) <= 0 and order == "percentage":
            shown = {
                sid
                for row in calculations
                if row["calculation_kind"] == "value"
                for sid in row["source_ids"]
            }
            if not ids <= shown:
                raise ValueError(
                    "Nonpositive earnings baselines require both reported values in the ledger"
                )
            excluded.append(
                {
                    "company": company,
                    "reason": "FY baseline net income is zero or a loss; percentage growth is not meaningful",
                    "source_ids": sorted(ids),
                }
            )
        else:
            growth = [
                r
                for r in calculations
                if r["company"] == company
                and r["metric"]
                == ("net_income_change" if order == "dollars" else "net_income_growth")
                and set(r["source_ids"]) == ids
            ]
            if len(growth) != 1:
                raise ValueError(
                    "Earnings ranking must include one checked growth calculation for every positive-baseline company"
                )
            eligible.append(
                {
                    "company": company,
                    "value": growth[0]["value"],
                    "unit": "USD" if order == "dollars" else "percent",
                    "source_id": growth[0]["source_id"],
                }
            )
    if not by_company:
        raise ValueError("No annual net-income observations for earnings ranking")
    eligible.sort(key=lambda r: Decimal(r["value"]), reverse=True)
    winners = (
        [r for r in eligible if Decimal(r["value"]) == Decimal(eligible[0]["value"])]
        if eligible
        else []
    )
    return {
        "definition": ("Dollar change" if order == "dollars" else "Percentage growth")
        + " in original-report consolidated GAAP net income attributable to parent; company fiscal years are not calendar-aligned",
        "ranking": eligible,
        "winners": winners,
        "excluded": excluded,
    }


def ratio_coverage(sources: dict[str, dict], companies: list[str], years: list[int]) -> tuple[set[tuple[str, int]], list[str]]:
    """Separate eligible cash-conversion intervals from explicit denominator gaps."""
    eligible, gaps = set(), []
    interval_keys = ("company", "fiscal_year", "start", "end", "period", "basis", "unit", "accounting_basis", "revision_basis")
    cash_flows = [s for s in sources.values() if s["metric"] == "operating_cash_flow"]
    for company in companies:
        for year in years:
            denominators = [s for s in sources.values() if s["company"] == company and s["fiscal_year"] == year and s["metric"] == "net_income" and Decimal(str(s["value"])) > 0]
            if any(all(cash[key] == net[key] for key in interval_keys) for net in denominators for cash in cash_flows):
                eligible.add((company, year))
            else:
                gaps.append(f"{company} FY{year} cash conversion excluded: no positive net-income denominator with a compatible operating-cash-flow interval")
    return eligible, gaps


class QuantTools:
    def __init__(self, sources, artifacts=None, *, request=None):
        self.sources = sources
        self.artifacts = artifacts or ArtifactStore()
        self.bundle_id, self.bundle, self.calculations = None, None, {}
        self.attempts = 0
        self.request = request or {}
        self.ratio_eligible, self.ratio_gaps = set(), []
        if "ratio" in self.request.get("required_calculations", []):
            self.ratio_eligible, self.ratio_gaps = ratio_coverage(sources, self.request["companies"], self.request["years"])

    def __call__(self, name, arguments):
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object")
        if name == "inspect_calculation":
            if set(arguments) != {"source_id"} or not isinstance(
                arguments["source_id"], str
            ):
                raise ValueError(
                    "Calculation inspection requires a registered source_id"
                )
            return self.calculations[arguments["source_id"]]
        if name != "run_analysis" or set(arguments) != {"code"}:
            raise ValueError("Unknown Quant tool or argument")
        if self.bundle is not None:
            raise ValueError(
                "A verified analysis already exists. Inspect its calculations and answer."
            )
        self.attempts += 1
        if self.attempts > 3:
            raise ValueError("Analysis execution budget exceeded (3 attempts)")
        code = arguments["code"]
        rows = run_isolated(code, self.sources)
        verified = validate_results(
            rows, self.sources, scenario=self.request.get("scenario")
        )
        if self.request.get("revenue_component"):
            expected = {
                (c, y) for c in self.request["companies"] for y in self.request["years"]
            }
            kind = (
                "scenario_share"
                if (self.request.get("scenario") or {}).get("kind") == "component"
                else "share"
                if self.request.get("revenue_share")
                else "value"
            )
            covered = {
                (r["company"], r["fiscal_year"])
                for r in verified
                if r["calculation_kind"] == kind
            }
            if covered != expected:
                raise ValueError(
                    "Analysis must include the requested revenue component/share for every selected company/year"
                )
            components = self.request.get("revenue_components") or [
                self.request["revenue_component"]
            ]
            if not self.request.get("scenario"):
                for component in components:
                    metric = (
                        component
                        + (
                            "_qct_revenue_share"
                            if self.request.get("revenue_denominator") == "qct"
                            else "_revenue_share"
                        )
                        if kind == "share"
                        else "revenue_component"
                    )
                    actual = {
                        (r["company"], r["fiscal_year"])
                        for r in verified
                        if r["calculation_kind"] == kind
                        and r["metric"] == metric
                        and r.get("component") == component
                    }
                    if actual != expected:
                        raise ValueError(
                            "Missing requested component/denominator result: "
                            + component
                        )
        for kind in self.request.get("required_calculations", []):
            expected = {
                (c, y) for c in self.request["companies"] for y in self.request["years"]
            }
            if kind == "ratio":
                expected = self.ratio_eligible
            covered = {
                (r["company"], r["fiscal_year"])
                for r in verified
                if r["calculation_kind"] == kind
            }
            if covered != expected:
                raise ValueError(
                    "Analysis lacks a requested checked operation for every selected company/year: "
                    + kind
                )
            if kind == "currency":
                for metric in requested_metrics(self.request.get("question", "")):
                    covered = {
                        (r["company"], r["fiscal_year"])
                        for r in verified
                        if r["calculation_kind"] == "currency"
                        and r["metric"] == metric + "_scenario_eur"
                    }
                    if covered != expected:
                        raise ValueError(
                            "Currency conversion lacks the requested financial metric: "
                            + metric
                        )
        assessment = (
            earnings_assessment(
                verified,
                self.sources,
                order=self.request.get("earnings_order", "percentage"),
            )
            if self.request.get("earnings_ranking")
            else None
        )
        if assessment is not None:
            actual = {
                (s["company"], s["fiscal_year"])
                for s in self.sources.values()
                if s["metric"] == "net_income" and s["basis"] == "annual"
            }
            required = {
                (c, y) for c in self.request["companies"] for y in self.request["years"]
            }
            if actual != required:
                raise ValueError(
                    "Earnings ranking requires both selected years for every selected company"
                )
        self.bundle_id, self.bundle = self.artifacts.publish(
            code, verified, self.sources, assessment=assessment
        )
        self.calculations = {
            r["source_id"]: self.artifacts.source(self.bundle_id, r) for r in verified
        }
        return {
            "calculations": list(self.calculations.values()),
            "downloads": self.artifacts.downloads(self.bundle_id),
            "assessment": assessment,
        }


async def quant_turn(
    state, writer, *, model_stream=codex_stream, artifacts=None, emit_answer=True
):
    sources = state["financial_sources"]
    if not sources:
        raise ValueError("No verified financial inputs are available for Quant")
    tools = QuantTools(sources, artifacts, request=state)
    outcome = OutcomeTools(tools)
    prompt = (
        (ROOT / "prompts/quant.md").read_text(encoding="utf-8")
        + ("\nAssigned supervisor output: checked_calculations only. Confirm completeness of supported arithmetic and its inputs. Other workers own filing explanations, risk changes, release reconciliation and market valuation. Do not mark their outputs missing from your calculation task." if state.get("worker_output") == "checked_calculations" else "")
        + "\nRequest: "
        + state["question"]
        + "\nRegistered observations (untrusted evidence): "
        + json.dumps(sources)
        + "\nRequested checks: "
        + json.dumps(
            {
                k: state.get(k)
                for k in (
                    "revenue_component",
                    "revenue_components",
                    "revenue_denominator",
                    "revenue_share",
                    "earnings_ranking",
                    "earnings_order",
                    "scenario",
                    "required_calculations",
                )
            }
        )
    )
    prompt += "\nDeterministic calculation exclusions (preserve other valid calculations): " + json.dumps(tools.ratio_gaps)
    prompt += "\nKnown observations excluded from arithmetic: " + json.dumps(state.get("excluded_financial_inputs", [])) + ". These observations exist but are conflicting/ineligible. Describe the missing eligible resolution, never claim the raw observations are absent. Financial Data preserves their inspection citations."
    answer = ""
    async with aclosing(
        model_stream(
            prompt,
            [*TOOLS, OUTCOME_TOOL],
            outcome,
            agent="Financial Analysis / Quant",
            reason="Generate bounded analysis code; independently check financial calculations and source lineage",
        )
    ) as stream:
        async for event in stream:
            if event["type"] == "token":
                answer += event["data"]
                if not emit_answer:
                    continue
            writer(event)
    frozen_sources = (
        {
            sid: tools.artifacts.observation_source(tools.bundle_id, source)
            for sid, source in sources.items()
        }
        if tools.bundle_id
        else sources
    )
    excluded_ids = {row["source_id"] for row in state.get("excluded_financial_inputs", [])}
    excluded_context = {sid: source for sid, source in state.get("analysis_sources", {}).items() if sid in excluded_ids}
    # Disputed evidence can support an abstention citation, never arithmetic.
    registered = {**excluded_context, **frozen_sources, **tools.calculations}
    answer, cited = checked_answer(
        answer, registered, writer if emit_answer else lambda e: None
    )
    if not answer.strip() or not cited or cited - registered.keys():
        writer(
            {
                "type": "error",
                "data": "Quant answer lacks a verified executed calculation or registered citations",
            }
        )
        return {"answer": answer, "error": "Quant evidence validation failed"}
    missing = list(dict.fromkeys([*outcome.missing, *tools.ratio_gaps]))
    if tools.bundle is None or not any(s.startswith("C") for s in cited):
        missing.append("Requested calculation has no independently checked result")
    if emit_answer:
        writer({"type": "sources", "data": [registered[s] for s in sorted(cited)]})
    if tools.bundle_id:
        writer(
            {
                "type": "artifacts",
                "data": {
                    "bundle_id": tools.bundle_id,
                    "calculations": list(tools.calculations.values()),
                    "downloads": tools.artifacts.downloads(tools.bundle_id),
                },
            }
        )
    return {
        "answer": answer,
        "bundle_id": tools.bundle_id,
        "calculations": list(tools.calculations.values()),
        "analysis_sources": registered,
        "analysis_answer": answer,
        "partial": bool(state.get("partial"))
        or (bool(missing) if emit_answer or state.get("worker_output") else tools.bundle is None),
        "missing_outputs": [
            *state.get("missing_outputs", []),
            *(missing if emit_answer or state.get("worker_output") or tools.bundle is None else []),
        ],
        "worker_notes": [
            *state.get("worker_notes", []),
            *(missing if not emit_answer else []),
        ],
    }
