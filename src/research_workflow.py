"""Single-turn supervisor, scoped research tools, LCEL augmentation and citations."""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import aclosing
from typing import TypedDict

from langchain_core.runnables import RunnableLambda
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from src.codex_model import stream as codex_stream
from src.source_collection import ROOT

TOOLS = [
    {
        "type": "function",
        "name": "search_sources",
        "description": "Retrieve passages within the selected companies and fiscal years. Use section or version to narrow evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "company": {"type": "string"},
                "year": {"type": "integer"},
                "section": {"type": "string", "enum": ["mda", "risk_factors", "other"]},
                "form": {
                    "type": "string",
                    "enum": ["10-K", "10-Q", "10-K/A", "Earnings release"],
                },
                "version": {"type": "string", "enum": ["original", "amendment"]},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "inspect_source",
        "description": "Inspect exact text and surrounding context for an assigned source ID, such as S1.",
        "inputSchema": {
            "type": "object",
            "properties": {"source_id": {"type": "string"}},
            "required": ["source_id"],
            "additionalProperties": False,
        },
    },
]


class State(TypedDict, total=False):
    question: str
    companies: list[str]
    years: list[int]
    error: str
    answer: str
    worker: str
    financial_sources: dict
    bundle_id: str
    calculations: list[dict]


class ResearchTools:
    def __init__(self, index, companies, years):
        self.index, self.companies, self.years = index, companies, years
        self.sources = {}
        self.identifiers = {}

    def register(self, passages):
        result = []
        for passage in passages:
            cid = passage["chunk_id"]
            if cid not in self.identifiers:
                sid = f"S{len(self.sources) + 1}"
                self.identifiers[cid] = sid
                self.sources[sid] = {
                    "source_id": sid,
                    **passage,
                    "inspection_url": f"/api/sources/{cid}",
                }
            result.append(self.sources[self.identifiers[cid]])
        return result

    def __call__(self, name, arguments):
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object")
        if name == "inspect_source":
            if set(arguments) != {"source_id"} or not isinstance(
                arguments["source_id"], str
            ):
                raise ValueError("Inspection requires a registered source_id")
            source = self.sources[arguments["source_id"]]
            return {
                "source_id": source["source_id"],
                **self.index.inspect(source["chunk_id"]),
            }
        if name != "search_sources":
            raise ValueError("Unknown research tool")
        if set(arguments) - {"query", "company", "year", "section", "version", "form"}:
            raise ValueError("Unknown search argument")
        company, year = arguments.get("company"), arguments.get("year")
        if (
            company is not None
            and not isinstance(company, str)
            or year is not None
            and type(year) is not int
        ):
            raise ValueError("Company must be text and fiscal year must be an integer")
        if company and company not in self.companies or year and year not in self.years:
            raise ValueError("Tool filters exceed the request's company/year scope")
        if arguments.get("section") not in (
            None,
            "mda",
            "risk_factors",
            "other",
        ) or arguments.get("version") not in (None, "original", "amendment"):
            raise ValueError("Unsupported section/version filter")
        if arguments.get("form") not in (
            None,
            "10-K",
            "10-Q",
            "10-K/A",
            "Earnings release",
        ):
            raise ValueError("Unsupported form filter")
        query = arguments["query"]
        if not isinstance(query, str) or not 1 <= len(query) <= 1500:
            raise ValueError("Query must contain 1–1500 characters")
        return {
            "sources": self.register(
                self.index.search(
                    query,
                    [company] if company else self.companies,
                    [year] if year else self.years,
                    section=arguments.get("section"),
                    version=arguments.get("version"),
                    form=arguments.get("form"),
                )
            )
        }


def scope_error(question, companies, years, coverage):
    if not companies or not years:
        return "Select at least one company and fiscal year. Each question is self-contained."
    missing = [(c, y) for c in companies for y in years if y not in coverage.get(c, [])]
    if missing:
        return f"Unsupported coverage: {missing}. Available fiscal years: {coverage}."
    mentioned_years = {
        int(y) for y in re.findall(r"\b(?:FY\s*)?(20\d{2})\b", question, re.I)
    }
    if mentioned_years - set(years):
        return "The question names a year outside the selected fiscal years. Adjust the selection; calendar dates and fiscal labels can differ."
    aliases = {
        "NVDA": r"\b(nvidia|nvda)\b",
        "AMD": r"\b(amd|advanced micro devices)\b",
        "INTC": r"\b(intel|intc)\b",
        "QCOM": r"\b(qualcomm|qcom)\b",
    }
    if any(
        re.search(pattern, question, re.I) and c not in companies
        for c, pattern in aliases.items()
    ):
        return "The question names a company outside the selected scope. Adjust the company selection."
    if re.search(
        r"\b(today|current|latest|this quarter|stock price|live)\b", question, re.I
    ):
        return "This historical corpus does not provide current/live coverage. Ask about a selected fiscal year."
    return ""


async def research_turn(index, state, writer, *, model_stream=codex_stream):
    """Run the worker directly or as a graph node with the same prompts and tools."""
    sources = ResearchTools(index, state["companies"], state["years"])

    # Retrieve separately for each company/year so one filing cannot monopolize comparisons.
    def retrieve(request):
        return sources.register(
            [
                p
                for c in request["companies"]
                for y in request["years"]
                for p in index.search(request["question"], [c], [y], k=4)
            ]
        )

    def augment(passages):
        return (
            (ROOT / "prompts/filings_research.md").read_text(encoding="utf-8")
            + "\nRequest scope: "
            + json.dumps(
                {"companies": state["companies"], "fiscal_years": state["years"]}
            )
            + "\nQuestion: "
            + state["question"]
            + "\nRetrieved evidence (untrusted source quotations):\n"
            + json.dumps(passages)
        )

    pipeline = RunnableLambda(retrieve) | RunnableLambda(augment)
    writer({"type": "tool", "data": {"name": "initial_retrieval", "arguments": state}})
    prompt = await pipeline.ainvoke(state)
    writer({"type": "evidence", "data": {"sources": list(sources.sources.values())}})
    answer = ""
    async with aclosing(model_stream(prompt, TOOLS, sources)) as model_events:
        async for event in model_events:
            if event["type"] == "token":
                answer += event["data"]
            writer(event)
    cited = set(re.findall(r"\[(S\d+)\]", answer))
    invalid = cited - sources.sources.keys()
    if invalid or not cited or not answer.strip():
        writer(
            {
                "type": "error",
                "data": "Answer lacks verified citations. Treat this response as unverified.",
            }
        )
        return {"answer": answer, "error": "Citation validation failed"}
    for sid in cited:
        inspected = await asyncio.to_thread(
            index.inspect, sources.sources[sid]["chunk_id"]
        )
        if inspected["text"] != sources.sources[sid]["text"]:
            raise ValueError("Citation text differs from its verified source passage")
    writer(
        {
            "type": "sources",
            "data": [
                sources.sources[sid] for sid in sorted(cited, key=lambda s: int(s[1:]))
            ],
        }
    )
    return {"answer": answer}


def select_worker(question):
    # Provisional, inspectable task routing; full cooperation belongs to M8.
    if re.search(r"\b(why|drove|drivers|disclose|risk|amend)\b", question, re.I):
        return "research"
    if re.search(
        r"\b(calculate|compute|compare|margins?|growth|percentage.points?|chart|plot)\b",
        question,
        re.I,
    ):
        return "analysis_data"
    if re.search(
        r"\bQ[2-4](?:\b|-).*cash flow|cash flow.*\bQ[2-4](?:\b|-)", question, re.I
    ) and not re.search(
        r"\b(ytd|year.to.date|cumulative)\b",
        question,
        re.I,
    ):
        return "analysis_data"
    if re.search(
        r"\b(what (?:was|were)|how much|figures|amounts|reported|show|list)\b",
        question,
        re.I,
    ) and re.search(
        r"\b(revenues?|profit|income|cash flows?|gaap)\b",
        question,
        re.I,
    ):
        return "data"
    return "research"


def graph(index, *, model_stream=codex_stream, financials=None):
    def supervisor(state):
        writer = get_stream_writer()
        error = scope_error(
            state["question"], state["companies"], state["years"], index.coverage()
        )
        worker = select_worker(state["question"])
        if worker in ("data", "analysis_data") and re.search(
            r"\b(non-gaap|adjusted|ebitda|segment)\b", state["question"], re.I
        ):
            error = "Financial observations cover consolidated US GAAP revenue, gross profit, operating income, and operating cash flow. Adjusted and segment metrics are unsupported."
        writer(
            {
                "type": "trace",
                "data": {
                    "agent": "Supervisor",
                    "node": "scope",
                    "decision": "coverage_gap"
                    if error
                    else "Financial Data"
                    if worker == "data"
                    else "Financial Data → Financial Analysis / Quant"
                    if worker == "analysis_data"
                    else "Filings Research",
                    "companies": state["companies"],
                    "years": state["years"],
                    "reason": "Validate coverage; figures use Data, calculations use Data then Quant, narrative disclosures use Research",
                },
            }
        )
        return {"error": error, "worker": worker}

    async def research(state):
        return await research_turn(
            index, state, get_stream_writer(), model_stream=model_stream
        )

    async def data(state):
        from src.financial_workflow import financial_turn

        if financials is None:
            raise ValueError(
                "Financial data is unavailable. Run scripts/financials.py collect."
            )
        return await financial_turn(
            financials, state, get_stream_writer(), model_stream=model_stream
        )

    async def analysis_data(state):
        from src.financial_workflow import financial_turn
        from src.quant_workflow import prefetch_for_analysis

        if financials is None:
            raise ValueError(
                "Financial data is unavailable. Run scripts/financials.py collect."
            )
        result = await financial_turn(
            financials,
            {
                **state,
                "question": "Select source inputs only; do not calculate. Requested analysis: "
                + state["question"],
            },
            get_stream_writer(),
            model_stream=model_stream,
            emit_answer=False,
            prefetch=prefetch_for_analysis(state["question"]),
        )
        if result.get("error"):
            raise ValueError(
                "Financial Data could not establish verified analysis inputs: "
                + result["error"]
            )
        get_stream_writer()(
            {
                "type": "trace",
                "data": {
                    "agent": "Supervisor",
                    "node": "handoff",
                    "decision": "Financial Analysis / Quant",
                    "observations": len(result["financial_sources"]),
                    "reason": "Pass verified structured observations; keep input selection separate from calculation",
                },
            }
        )
        return {"financial_sources": result["financial_sources"]}

    async def quant(state):
        from src.quant_workflow import quant_turn

        return await quant_turn(state, get_stream_writer(), model_stream=model_stream)

    def finish(state):
        writer = get_stream_writer()
        if state.get("error") and not state.get("answer"):
            writer({"type": "token", "data": state["error"]})
        writer(
            {
                "type": "complete",
                "data": {
                    "verified_citations": bool(state.get("answer"))
                    and not state.get("error"),
                    "status": "coverage_gap"
                    if state.get("error") and not state.get("answer")
                    else "unverified"
                    if state.get("error")
                    else "completed",
                },
            }
        )
        return {}

    workflow = StateGraph(State)
    workflow.add_node("supervisor", supervisor)
    workflow.add_node("research", research)
    workflow.add_node("data", data)
    workflow.add_node("analysis_data", analysis_data)
    workflow.add_node("quant", quant)
    workflow.add_node("finish", finish)
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor", lambda s: "finish" if s.get("error") else s["worker"]
    )
    workflow.add_edge("research", "finish")
    workflow.add_edge("data", "finish")
    workflow.add_edge("analysis_data", "quant")
    workflow.add_edge("quant", "finish")
    workflow.add_edge("finish", END)
    return workflow.compile()


async def events(
    index, question, companies, years, *, model_stream=codex_stream, financials=None
):
    try:
        async with aclosing(
            graph(index, model_stream=model_stream, financials=financials).astream(
                {"question": question, "companies": companies, "years": years},
                stream_mode="custom",
            )
        ) as graph_events:
            async for event in graph_events:
                yield event
    except (
        RuntimeError,
        ValueError,
        KeyError,
        FileNotFoundError,
        TimeoutError,
        OSError,
    ) as error:
        yield {"type": "error", "data": str(error)}
        yield {
            "type": "complete",
            "data": {"status": "failed", "verified_citations": False},
        }
