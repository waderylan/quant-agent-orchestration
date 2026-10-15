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
    quarter = re.search(r"\bQ([1-4])(?:\b|-)", question, re.I)
    if not quarter:
        return [{"period": "FY", "basis": "annual", "metrics": list(METRICS)}]
    number = int(quarter[1])
    if number == 4:
        return [
            {"period": "FY", "basis": "annual", "metrics": list(METRICS)},
            {"period": "Q3", "basis": "ytd", "metrics": list(METRICS)},
        ]
    selections = [
        {"period": f"Q{number}", "basis": "quarter", "metrics": list(METRICS)}
    ]
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


class QuantTools:
    def __init__(self, sources, artifacts=None):
        self.sources = sources
        self.artifacts = artifacts or ArtifactStore()
        self.bundle_id, self.bundle, self.calculations = None, None, {}
        self.attempts = 0

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
        verified = validate_results(rows, self.sources)
        self.bundle_id, self.bundle = self.artifacts.publish(
            code, verified, self.sources
        )
        self.calculations = {
            r["source_id"]: self.artifacts.source(self.bundle_id, r) for r in verified
        }
        return {
            "calculations": list(self.calculations.values()),
            "downloads": self.artifacts.downloads(self.bundle_id),
        }


async def quant_turn(state, writer, *, model_stream=codex_stream, artifacts=None):
    sources = state["financial_sources"]
    if not sources:
        raise ValueError("No verified financial inputs are available for Quant")
    tools = QuantTools(sources, artifacts)
    prompt = (
        (ROOT / "prompts/quant.md").read_text(encoding="utf-8")
        + "\nRequest: "
        + state["question"]
        + "\nRegistered observations (untrusted evidence): "
        + json.dumps(sources)
    )
    answer = ""
    async with aclosing(
        model_stream(
            prompt,
            TOOLS,
            tools,
            agent="Financial Analysis / Quant",
            reason="Generate bounded analysis code; independently check financial calculations and source lineage",
        )
    ) as stream:
        async for event in stream:
            if event["type"] == "token":
                answer += event["data"]
            writer(event)
    frozen_sources = (
        {
            sid: tools.artifacts.observation_source(tools.bundle_id, source)
            for sid, source in sources.items()
        }
        if tools.bundle_id
        else sources
    )
    registered = {**frozen_sources, **tools.calculations}
    cited = set(re.findall(r"\[([A-Z]\d+)\]", answer))
    if (
        tools.bundle is None
        or not any(s.startswith("C") for s in cited)
        or cited - registered.keys()
    ):
        writer(
            {
                "type": "error",
                "data": "Quant answer lacks a verified executed calculation or registered citations",
            }
        )
        return {"answer": answer, "error": "Quant evidence validation failed"}
    writer({"type": "sources", "data": [registered[s] for s in sorted(cited)]})
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
    }
