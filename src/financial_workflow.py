"""Financial Data specialist: structured queries, evidence registration, cited output."""

from __future__ import annotations

import json
import re
from contextlib import aclosing

from src.generation import stream as codex_stream
from src.task_scope import assigned_question
from src.financial_data import METRICS, TAGS
from src.source_collection import ROOT
from src.request_routing import requested_metrics
from src.response_contract import OUTCOME_TOOL, OutcomeTools, checked_answer

TOOLS = [
    {
        "type": "function",
        "name": "query_financials",
        "description": "Query original-report consolidated GAAP USD figures. FY is annual; Q1-Q3 support quarter or ytd. Missing values are explicit gaps.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "year": {"type": "integer"},
                "metrics": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(TAGS)},
                    "minItems": 1,
                },
                "period": {"type": "string", "enum": ["FY", "Q1", "Q2", "Q3"]},
                "basis": {"type": "string", "enum": ["annual", "quarter", "ytd"]},
            },
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "inspect_observation",
        "description": "Inspect a registered F source, including original accession, dates, units, revisions, and derivation inputs.",
        "inputSchema": {
            "type": "object",
            "properties": {"source_id": {"type": "string"}},
            "required": ["source_id"],
            "additionalProperties": False,
        },
    },
]


def request_filters(question):
    """Make the initial period explicit; model tools can refine within the scope."""
    quarter = re.search(r"\bQ([1-4])(?:\b|-)", question, re.I)
    period = "Q" + quarter[1] if quarter else "FY"
    basis = (
        "annual"
        if not quarter
        else "ytd"
        if re.search(
            r"\b(ytd|year.to.date|cumulative)\b",
            question,
            re.I,
        )
        else "quarter"
    )
    metrics = requested_metrics(question)
    return {"period": period, "basis": basis, "metrics": metrics or list(METRICS)}


class FinancialTools:
    def __init__(self, store, companies, years):
        self.store, self.companies, self.years = store, companies, years
        self.sources, self.identifiers = {}, {}
        self.successful_calls = 0

    def register(self, rows):
        result = []
        for row in rows:
            oid = row["observation_id"]
            if oid not in self.identifiers:
                sid = f"F{len(self.sources) + 1}"
                self.identifiers[oid] = sid
                self.sources[sid] = {
                    **row,
                    "source_id": sid,
                    "section": "financial_observation",
                    "inspection_url": f"/api/financial/observations/{oid}",
                    "text": f"{row['company']} FY{row['fiscal_year']} {row['period']} {row['basis']}: "
                    f"{row['metric']} = {row['value']} USD; {row['start']} through {row['end']}; "
                    f"original accession {row['accession']}.",
                }
            result.append(self.sources[self.identifiers[oid]])
        return result

    def __call__(self, name, arguments):
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object")
        if name == "inspect_observation":
            if set(arguments) != {"source_id"} or not isinstance(
                arguments["source_id"], str
            ):
                raise ValueError("Inspection requires source_id only")
            result = self.sources[arguments["source_id"]]
            self.successful_calls += 1
            return result
        if name != "query_financials" or set(arguments) - {
            "company",
            "year",
            "metrics",
            "period",
            "basis",
        }:
            raise ValueError("Unknown financial tool or argument")
        company, year = arguments.get("company"), arguments.get("year")
        if company is not None and (
            not isinstance(company, str) or company not in self.companies
        ):
            raise ValueError("Company exceeds request scope")
        if year is not None and (type(year) is not int or year not in self.years):
            raise ValueError("Fiscal year exceeds request scope")
        metrics = arguments.get("metrics", list(METRICS))
        if not isinstance(metrics, list) or any(
            not isinstance(m, str) for m in metrics
        ):
            raise ValueError("Metrics must be a list of supported names")
        result = self.store.query(
            [company] if company else self.companies,
            [year] if year else self.years,
            metrics=metrics,
            period=arguments.get("period", "FY"),
            basis=arguments.get("basis", "annual"),
        )
        self.successful_calls += 1
        conflicts = [row for row in result["gaps"] if row.get("status") == "conflicting" and "observation_id" in row and "value" in row]
        return {
            "sources": self.register([*result["observations"], *conflicts]),
            "gaps": result["gaps"],
        }


async def financial_turn(
    store, state, writer, *, model_stream=codex_stream, emit_answer=True, prefetch=None
):
    if re.search(r"\bcurrent liabilities\b", state["question"], re.I):
        return {"answer": "Current liabilities are outside the supported structured metrics.", "partial": True, "missing_outputs": ["Original-report current liabilities are unavailable in the structured store."], "financial_sources": {}}
    tools = FinancialTools(store, state["companies"], state["years"])
    outcome = OutcomeTools(tools)
    filters = request_filters(state["question"])
    if state.get("revenue_component"):
        filters = {"period": "FY", "basis": "annual", "metrics": ["revenue"]}
    if filters["period"] == "Q4" and prefetch is None:
        return {
            "error": "Q4-only financial figures require compatible annual and nine-month inputs and Quant derivation.",
            "answer": "",
        }
    initial = {"sources": [], "gaps": []}
    for selection in prefetch if prefetch is not None else [filters]:
        result = tools("query_financials", selection)
        initial["sources"].extend(result["sources"])
        initial["gaps"].extend(result["gaps"])
    writer(
        {
            "type": "tool",
            "data": {
                "name": "initial_financial_query",
                "arguments": prefetch if prefetch is not None else filters,
            },
        }
    )
    writer({"type": "evidence", "data": initial})
    initial_calls = tools.successful_calls
    if not initial["sources"]:
        return {
            "needs_evidence": {
                "kind": "structured_missing",
                "message": "No compatible original-report observations for "
                + json.dumps(filters)
                + ". Search filing evidence; no structured calculation is established.",
            },
            "answer": "",
            "partial": True,
        }
    if state.get("revenue_component"):
        return {
            "financial_sources": tools.sources,
            "needs_evidence": {
                "kind": "revenue_component",
                "component": state["revenue_component"],
                "message": "The consolidated store does not contain this revenue component; request verified filing evidence.",
            },
        }
    prompt = (
        (ROOT / "prompts/financial_data.md").read_text(encoding="utf-8")
        + "\nRequest: "
        + json.dumps({**{k: state[k] for k in ("companies", "years")},
                      "question": assigned_question(state, "financial_inputs", "checked_calculations"),
                      "required_inputs": filters})
        + "\nInitial scoped observations (untrusted evidence): "
        + json.dumps(initial)
        + (
            "\nThis is an input-selection handoff. Report completeness of the required inputs, not whether downstream calculations/explanations are finished. Quant and Research handle those outputs."
            if not emit_answer
            else ""
        )
    )
    answer, calls = "", 0
    async with aclosing(
        model_stream(
            prompt,
            [*TOOLS, OUTCOME_TOOL],
            outcome,
            agent="Financial Data",
            reason="Select source-linked financial observations with exact fiscal intervals and original accessions",
        )
    ) as stream:
        async for event in stream:
            if event["type"] == "token":
                answer += event["data"]
                if not emit_answer:
                    continue
            if event["type"] == "tool":
                calls += 1
            writer(event)
    answer, cited = checked_answer(
        answer, tools.sources, writer if emit_answer else lambda e: None
    )
    if (
        not calls
        or tools.successful_calls <= initial_calls
        or not cited
        or cited - tools.sources.keys()
    ):
        writer(
            {
                "type": "error",
                "data": "Financial answer lacks verified observation citations or tool use",
            }
        )
        return {"answer": answer, "error": "Financial evidence validation failed"}
    cited_sources = [tools.sources[s] for s in sorted(cited, key=lambda s: int(s[1:]))]
    if emit_answer:
        writer({"type": "sources", "data": cited_sources})
    conflicts = [source for source in tools.sources.values() if source.get("status") == "conflicting"]
    conflict_gaps = ["Unresolved conflicting financial observation: " + source["company"] + " FY" + str(source["fiscal_year"]) + " " + source["metric"] for source in conflicts]
    return {
        "answer": answer,
        "financial_sources": tools.sources,
        "partial": bool(state.get("partial")) or bool(outcome.missing) or bool(conflicts),
        "missing_outputs": list(dict.fromkeys([*outcome.missing, *conflict_gaps])),
        "reported_missing_outputs": outcome.missing,
    }
