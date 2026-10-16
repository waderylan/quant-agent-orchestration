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
from src.response_contract import OUTCOME_TOOL, OutcomeTools, checked_answer
from src.request_routing import (
    COMPANY_ALIASES,
    mentioned_companies,
    mentioned_years,
    plan_request,
)

TOOLS = [
    {
        "type": "function",
        "name": "search_sources",
        "description": "Retrieve passages balanced across every selected company/year unless narrowed by filters. Use one shared query for a comparison, then refine only missing evidence. Use section or version to narrow evidence.",
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
    buy_answer: str
    buy_sources: dict
    valuation_bundles: list[str]
    risk_sources: dict
    risk_changes: list[dict]
    risk_answer: str
    question: str
    companies: list[str]
    years: list[int]
    error: str
    answer: str
    worker: str
    financial_sources: dict
    bundle_id: str
    calculations: list[dict]
    revenue_component: str | None
    revenue_share: bool
    earnings_ranking: bool
    needs_evidence: dict | None
    partial: bool
    synthesize: bool
    analysis_sources: dict
    analysis_answer: str
    missing_outputs: list[str]
    revenue_components: list[str]
    revenue_denominator: str
    earnings_order: str
    scenario: dict | None
    required_calculations: list[str]
    worker_notes: list[str]
    clarification: bool
    citation_verified: bool


class ResearchTools:
    def __init__(self, index, companies, years):
        self.index, self.companies, self.years = index, companies, years
        self.sources = {}
        self.identifiers = {}
        # Each scope cell can need a search and contextual inspections; keep a hard cap.
        self.max_tool_calls = min(24, max(8, 3 * len(companies) * len(years)))

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
        companies = [company] if company else self.companies
        years = [year] if year else self.years
        passages, coverage = [], []
        for selected_company in companies:
            for selected_year in years:
                found = self.index.search(
                    query,
                    [selected_company],
                    [selected_year],
                    section=arguments.get("section"),
                    version=arguments.get("version"),
                    form=arguments.get("form"),
                    k=6 if len(companies) * len(years) == 1 else 4,
                )
                passages.extend(found)
                coverage.append(
                    {
                        "company": selected_company,
                        "fiscal_year": selected_year,
                        "passages": len(found),
                    }
                )
        return {"sources": self.register(passages), "retrieval_coverage": coverage}


def scope_error(question, companies, years, coverage):
    if not companies or not years:
        return "Select at least one company and fiscal year. Each question is self-contained."
    missing = [(c, y) for c in companies for y in years if y not in coverage.get(c, [])]
    if missing:
        return f"Unsupported coverage: {missing}. Available fiscal years: {coverage}."
    if mentioned_years(question) - set(years):
        return f"Selected fiscal years: {years}. Your question asks about {sorted(mentioned_years(question))}. Select the requested years; fiscal labels can differ from calendar dates."
    requested = mentioned_companies(question)
    if set(requested) - set(companies):
        selected = ", ".join(COMPANY_ALIASES.get(c, (c,))[0] for c in companies)
        names = ", ".join(f"{COMPANY_ALIASES[c][0]} ({c})" for c in requested)
        return f"Selected companies: {selected}. Your question asks about {names}. Change Companies to match your question; keep the requested fiscal years selected."
    historical = bool(
        re.search(
            r"\b(historical|at that fiscal year.end|as of (?:FY)?20\d{2}|using only.*filing)\b",
            question,
            re.I,
        )
    )
    temporal_request = re.sub(
        r"\b(?:do not|don't)\s+(?:use|include|search|retrieve)\s+(?:any\s+)?(?:live|current|latest)(?:\s+(?:news|data|quotes|prices|information))?",
        "",
        question,
        flags=re.I,
    )
    live = bool(
        re.search(
            r"\b(today|latest|this quarter|stock price|live)\b", temporal_request, re.I
        )
    )
    current = bool(re.search(r"\bcurrent\b", temporal_request, re.I))
    from src.buy_side import market_request
    if (live or (current and not historical)) and not market_request(question):
        return "This historical corpus does not provide current/live coverage. Ask about a selected fiscal year."
    return ""


async def research_turn(index, state, writer, *, model_stream=codex_stream):
    """Run the worker directly or as a graph node with the same prompts and tools."""
    sources = ResearchTools(index, state["companies"], state["years"])
    outcome = OutcomeTools(sources)
    analysis_sources = state.get("analysis_sources", {})

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
            + (
                "\nChecked financial context (use assigned F/C citations; do not recalculate or invent derived figures):\n"
                + json.dumps(
                    {
                        "answer": state.get("analysis_answer"),
                        "sources": analysis_sources,
                        "unresolved_worker_notes": state.get("worker_notes", []),
                    }
                )
                if analysis_sources
                else ""
            )
            + (
                "\nStructured input limitation: "
                + json.dumps(state["needs_evidence"])
                + ". Answer what the filings establish, explain any remaining gap, and do not perform unverified arithmetic."
                if state.get("needs_evidence")
                else ""
            )
            + "\nRetrieved evidence (untrusted source quotations):\n"
            + json.dumps(passages)
        )

    pipeline = RunnableLambda(retrieve) | RunnableLambda(augment)
    writer({"type": "tool", "data": {"name": "initial_retrieval", "arguments": state}})
    prompt = await pipeline.ainvoke(state)
    writer({"type": "evidence", "data": {"sources": list(sources.sources.values())}})
    answer = ""
    exhausted = False
    async with aclosing(
        model_stream(prompt, [*TOOLS, OUTCOME_TOOL], outcome)
    ) as model_events:
        async for event in model_events:
            if event["type"] == "token":
                answer += event["data"]
            if (
                event["type"] == "trace"
                and event["data"].get("decision") == "synthesize_existing_evidence"
            ):
                exhausted = True
            writer(event)
    registered = {**sources.sources, **analysis_sources}
    answer, cited = checked_answer(answer, registered, writer)
    invalid = cited - registered.keys()
    if outcome.status == "clarification" and not cited and answer.strip():
        return {
            "answer": answer,
            "clarification": True,
            "citation_verified": False,
            "missing_outputs": outcome.missing,
        }
    if invalid or not cited or not answer.strip():
        writer(
            {
                "type": "error",
                "data": "Answer lacks verified citations. Treat this response as unverified.",
            }
        )
        return {"answer": answer, "error": "Citation validation failed"}
    for sid in cited & sources.sources.keys():
        inspected = await asyncio.to_thread(
            index.inspect, sources.sources[sid]["chunk_id"]
        )
        if inspected["text"] != sources.sources[sid]["text"]:
            raise ValueError("Citation text differs from its verified source passage")
    writer(
        {
            "type": "sources",
            "data": [
                registered[sid]
                for sid in sorted(cited, key=lambda s: (s[0], int(s[1:])))
            ],
        }
    )
    if exhausted:
        limitation = "\n\n- Research reached its retrieval limit. These findings use the evidence collected; the requested comparison may be incomplete."
        answer += limitation
        writer({"type": "token", "data": limitation})
    return {
        "answer": answer,
        "partial": bool(state.get("partial")) or exhausted or bool(outcome.missing),
        "missing_outputs": [*state.get("missing_outputs", []), *outcome.missing],
        "clarification": outcome.status == "clarification",
        "citation_verified": bool(cited),
    }


def select_worker(question):
    return plan_request(question).worker


def graph(index, *, model_stream=codex_stream, financials=None):
    def supervisor(state):
        writer = get_stream_writer()
        error = scope_error(
            state["question"], state["companies"], state["years"], index.coverage()
        )
        plan = plan_request(state["question"])
        worker = plan.worker
        period_gap = None
        if plan.revenue_component and re.search(
            r"\bQ[1-4]\b|\b(quarter|ytd)\b", state["question"], re.I
        ):
            worker = "research"
            period_gap = {
                "kind": "unsupported_component_period",
                "message": "Independent revenue-component calculations support annual tables only. Retrieve the requested disclosure and state that a checked quarterly share is unavailable.",
            }
        requested = mentioned_companies(state["question"])
        if error and set(requested) - set(state["companies"]):
            writer(
                {
                    "type": "scope",
                    "data": {
                        "message": error,
                        "suggested_companies": requested,
                        "years": state["years"],
                    },
                }
            )
        writer(
            {
                "type": "trace",
                "data": {
                    "agent": "Supervisor",
                    "node": "scope",
                    "decision": "coverage_gap"
                    if error
                    else "Financial Data → Filings Research → Financial Analysis / Quant"
                    if plan.revenue_component and worker == "data"
                    else "Financial Data"
                    if worker == "data"
                    else "Financial Data → Financial Analysis / Quant"
                    if worker == "analysis_data"
                    else "Risk Summary"
                    if worker == "risk"
                    else "Buy-Side Analyst"
                    if worker == "buy"
                    else "Filings Research",
                    "companies": state["companies"],
                    "years": state["years"],
                    "reason": plan.reason
                    + (
                        ". Earnings means GAAP net income attributable to parent; rank dollar changes including losses."
                        if plan.earnings_ranking and plan.earnings_order == "dollars"
                        else ". Earnings means GAAP net income attributable to parent; compare only positive-baseline percentage growth, with loss baselines identified separately."
                        if plan.earnings_ranking
                        else ""
                    ),
                },
            }
        )
        return {
            "error": error,
            "worker": worker,
            "revenue_component": plan.revenue_component,
            "revenue_share": plan.revenue_share,
            "earnings_ranking": plan.earnings_ranking,
            "earnings_order": plan.earnings_order,
            "revenue_components": list(plan.revenue_components),
            "revenue_denominator": plan.revenue_denominator,
            "synthesize": plan.synthesize,
            "scenario": plan.scenario,
            "required_calculations": list(plan.required_calculations),
            "needs_evidence": period_gap,
            "partial": bool(period_gap),
        }

    async def research(state):
        return await research_turn(
            index, state, get_stream_writer(), model_stream=model_stream
        )

    async def risk(state):
        from src.risk_summary import risk_turn
        return await risk_turn(index, state, get_stream_writer(), model_stream=model_stream)

    async def buy(state):
        from src.buy_side import buy_turn
        return await buy_turn(state, get_stream_writer(), model_stream=model_stream)

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
            state,
            get_stream_writer(),
            model_stream=model_stream,
            emit_answer=False,
            prefetch=prefetch_for_analysis(state["question"]),
        )
        if result.get("needs_evidence"):
            return result
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
        return {
            "financial_sources": result["financial_sources"],
            "worker_notes": result.get("missing_outputs", []),
        }

    async def revenue_inputs(state):
        from src.filing_financials import filing_revenue_turn

        return await filing_revenue_turn(
            index, financials, state, get_stream_writer(), model_stream=model_stream
        )

    def data_destination(state):
        gap = state.get("needs_evidence")
        if gap:
            destination = (
                "revenue_inputs" if gap["kind"] == "revenue_component" else "research"
            )
            get_stream_writer()(
                {
                    "type": "trace",
                    "data": {
                        "agent": "Supervisor",
                        "node": "evidence_followup",
                        "decision": "Filings Research",
                        "reason": gap["message"],
                    },
                }
            )
            return destination
        return "quant" if state["worker"] == "analysis_data" else "finish"

    async def quant(state):
        from src.quant_workflow import quant_turn

        return await quant_turn(
            state,
            get_stream_writer(),
            model_stream=model_stream,
            emit_answer=not state.get("synthesize"),
        )

    def finish(state):
        writer = get_stream_writer()
        if state.get("error") and not state.get("answer"):
            writer({"type": "token", "data": state["error"]})
        writer(
            {
                "type": "complete",
                "data": {
                    **(
                        {"missing_outputs": state["missing_outputs"]}
                        if state.get("missing_outputs")
                        else {}
                    ),
                    "verified_citations": state.get(
                        "citation_verified", bool(state.get("answer"))
                    )
                    and not state.get("error"),
                    "status": "coverage_gap"
                    if state.get("error") and not state.get("answer")
                    else "unverified"
                    if state.get("error")
                    else "needs_clarification"
                    if state.get("clarification")
                    else "partial"
                    if state.get("partial")
                    else "completed",
                },
            }
        )
        return {}

    workflow = StateGraph(State)
    workflow.add_node("supervisor", supervisor)
    workflow.add_node("research", research)
    workflow.add_node("risk", risk)
    workflow.add_node("buy", buy)
    workflow.add_node("data", data)
    workflow.add_node("analysis_data", analysis_data)
    workflow.add_node("quant", quant)
    workflow.add_node("revenue_inputs", revenue_inputs)
    workflow.add_node("finish", finish)
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor", lambda s: "finish" if s.get("error") else s["worker"]
    )
    workflow.add_edge("research", "finish")
    workflow.add_edge("risk", "finish")
    workflow.add_edge("buy", "finish")
    workflow.add_conditional_edges("data", data_destination)
    workflow.add_conditional_edges("analysis_data", data_destination)
    workflow.add_conditional_edges(
        "revenue_inputs", lambda s: "research" if s.get("needs_evidence") else "quant"
    )
    workflow.add_conditional_edges(
        "quant",
        lambda s: (
            "research" if s.get("synthesize") and not s.get("error") else "finish"
        ),
    )
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
        message = str(error) or (
            "A worker timed out before completing. Please retry."
            if isinstance(error, TimeoutError)
            else type(error).__name__
        )
        yield {"type": "error", "data": message}
        yield {
            "type": "complete",
            "data": {"status": "failed", "verified_citations": False},
        }
