"""Single-turn supervisor, scoped research tools, LCEL augmentation and citations."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from contextlib import aclosing
from typing import TypedDict

from langchain_core.runnables import RunnableLambda

from src.generation import stream as codex_stream
from src.task_scope import assigned_question
from src.source_collection import ROOT
from src.filing_scope import filing_scope
from src.response_contract import OUTCOME_TOOL, OutcomeTools, checked_answer
from src.request_routing import (
    COMPANY_ALIASES,
    mentioned_companies,
    mentioned_years,
    plan_request,
    requested_metrics,
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
                "year": {"type": "integer", "description": "One fiscal year. Omit this filter to search all selected years; never pass an array."},
                "quarter": {"type": "integer", "enum": [1, 2, 3, 4], "description": "Fiscal quarter for a 10-Q; Q4 has no separate 10-Q. Omit to inherit an explicit quarter in the question."},
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
    generation_request_id: str
    provider_routes: list[dict]
    request_plan: dict
    live_intent: str
    current_answer: str
    live_sources: dict
    risk_sources: dict
    risk_changes: list[dict]
    risk_live_checks: list[dict]
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
    def __init__(self, index, companies, years, *, source_offset=0, question=""):
        self.index, self.companies, self.years = index, companies, years
        self.source_offset = source_offset
        self.question = question
        self.sources = {}
        self.identifiers = {}
        # Each scope cell can need a search and contextual inspections; keep a hard cap.
        self.max_tool_calls = min(24, max(8, 3 * len(companies) * len(years)))

    def register(self, passages):
        result = []
        for passage in passages:
            cid = passage["chunk_id"]
            if cid not in self.identifiers:
                sid = f"S{self.source_offset + len(self.sources) + 1}"
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
        if set(arguments) - {"query", "company", "year", "quarter", "section", "version", "form"}:
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
        quarter = arguments.get("quarter")
        if quarter is not None and (type(quarter) is not int or quarter not in (1, 2, 3, 4)):
            raise ValueError("Fiscal quarter must be an integer from 1 through 4")
        if quarter is not None and arguments.get("form") not in (None, "10-Q"):
            raise ValueError("Quarter filter requires a 10-Q")
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
                    **filing_scope(self.question, getattr(self.index, "documents", {}), [selected_company], [selected_year],
                                   form=arguments.get("form") or ("10-Q" if quarter else None), quarter=quarter),
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


def scope_error(question, companies, years, coverage, *, check_years=True):
    if not companies or not years:
        return "Select at least one company and fiscal year. Each question is self-contained."
    missing = [(c, y) for c in companies for y in years if y not in coverage.get(c, [])]
    if missing:
        return f"Unsupported coverage: {missing}. Available fiscal years: {coverage}."
    if check_years and mentioned_years(question) - set(years):
        return f"Selected fiscal years: {years}. Your question asks about {sorted(mentioned_years(question))}. Select the requested years; fiscal labels can differ from calendar dates."
    requested = mentioned_companies(question)
    if set(requested) - set(companies):
        selected = ", ".join(COMPANY_ALIASES.get(c, (c,))[0] for c in companies)
        names = ", ".join(f"{COMPANY_ALIASES[c][0]} ({c})" for c in requested)
        return f"Selected companies: {selected}. Your question asks about {names}. Change Companies to match your question; keep the requested fiscal years selected."
    return ""


async def research_turn(index, state, writer, *, model_stream=codex_stream, gateway=None):
    """Run the worker directly or as a graph node with the same prompts and tools."""
    sources = ResearchTools(
        index,
        state["companies"],
        state["years"],
        source_offset=state.get("source_offset", 0),
        question=assigned_question(state, "filing_explanation", "official_update"),
    )
    live = None
    if state.get("live_check") and state.get("live_intent") in ("verify", "developments"):
        from src.current_developments import LiveTools, SEARCH_TOOL
        from src.live_mcp import LiveGateway
        live = LiveTools(state, gateway or LiveGateway(), agent="Filings Research")

    class ResearchHandler:
        max_tool_calls = sources.max_tool_calls

        # Hosted role instructions include all outputs owned by this invocation.
        assigned_outputs = ("filing_explanation", "official_update") if live else ("filing_explanation",)

        def __getattr__(self, name):
            return getattr(sources, name)

        def __call__(self, name, arguments):
            if name == "inspect_source" and set(arguments) == {"source_id"} and arguments["source_id"] in analysis_sources:
                return {"source": analysis_sources[arguments["source_id"]],
                        "use": "Verified handoff evidence; preserve its identity and assigned specialist scope"}
            return live(name, arguments) if live and name == "search_web" else sources(name, arguments)

    outcome = OutcomeTools(ResearchHandler())
    analysis_sources = state.get("analysis_sources", {})

    # Retrieve separately for each company/year so one filing cannot monopolize comparisons.
    def retrieve(request):
        passages = [
                p
                for c in request["companies"]
                for y in request["years"]
                for p in index.search(request["question"], [c], [y], k=4,
                                      **filing_scope(request["question"], getattr(index, "documents", {}), [c], [y]))
            ]
        if request.get("worker_output") == "filing_explanation" and analysis_sources:
            # Fixed, scoped supplemental searches keep a mixed request from
            # losing an issuer's cash-flow drivers or a release reconciliation.
            queries = []
            if "operating_cash_flow" in requested_metrics(request["question"]):
                queries.append(("operating activities cash flow changes working capital income taxes accounts receivable payables", "10-K", "mda"))
            if re.search(r"\b(release|headline|adjusted|non.GAAP)\b", request["question"], re.I):
                queries.append(("GAAP non-GAAP adjusted earnings reconciliation exclusions operating income", "Earnings release", None))
            if re.search(r"\brisks?\b", request["question"], re.I):
                queries.append(("customer concentration revenue business mix risks", "10-K", "risk_factors"))
            for company in request["companies"]:
                for year in request["years"]:
                    for query, form, section in queries:
                        passages.extend(index.search(query, [company], [year], form=form, section=section, k=2))
        if re.search(r"\bamend\w*\b|10-K/A", request["question"], re.I):
            for company in request["companies"]:
                for year in request["years"]:
                    for query, form, version, section in (
                        ("Client processors unit shipments average selling price", "10-K", "original", "mda"),
                        ("Client processors unit shipments average selling price", "10-K/A", "amendment", "mda"),
                        ("explanatory note amendment purpose correction", "10-K/A", "amendment", None),
                    ):
                        passages.extend(index.search(query, [company], [year], form=form, version=version, section=section, k=2))
        return sources.register(passages)

    def augment(passages):
        return (
            (ROOT / "prompts/filings_research.md").read_text(encoding="utf-8")
            + "\nRequest scope: "
            + json.dumps(
                {"companies": state["companies"], "fiscal_years": state["years"]}
            )
            + "\nQuestion: "
            + assigned_question(state, "filing_explanation", "official_update")
            + (
                "\nSupervisor role boundary: " + state["handoff_role_note"]
                if state.get("handoff_role_note")
                else ""
            )
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
    writer({"type": "tool", "data": {"name": "initial_retrieval", "arguments": {k: state[k] for k in ("question", "companies", "years")}}})
    prompt = await pipeline.ainvoke({**state, "question": assigned_question(state, "filing_explanation", "official_update")})
    if live:
        prompt += "\nLive verification: Use at most one search_web call with topic=general to check whether an official company or SEC source updates the specific filed statement. Report the filed statement with its S citation first, then the update or absence of a found official update with a W citation. Only official-tier W sources establish an update; if results are third-party only, say no official update found. W never replaces S for filed content. Do not list developments or calculate. Omit market prices, multiples and analyst estimates even if returned."
    writer({"type": "evidence", "data": {"sources": list(sources.sources.values())}})
    if not sources.sources and not analysis_sources:
        return {"answer": "No verified filing evidence is available for the selected request.", "partial": True, "coverage_gap": True, "missing_outputs": ["Original filing retrieval returned no passages; no reported values or risk conclusions are verified."], "research_sources": {}, "citation_verified": False}
    answer = ""
    exhausted = False
    async with aclosing(
        model_stream(prompt, [*TOOLS, *([SEARCH_TOOL] if live else []), OUTCOME_TOOL], outcome)
    ) as model_events:
        async for event in model_events:
            if live:
                live.flush(writer)
            if event["type"] == "token":
                answer += event["data"]
            if (
                event["type"] == "trace"
                and event["data"].get("decision") == "synthesize_existing_evidence"
            ):
                exhausted = True
            writer(event)
    if live:
        live.flush(writer)
    registered = {**sources.sources, **analysis_sources, **(live.sources if live else {})}
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
    live_missing = []
    if live:
        live_missing = [*live.missing]
        if not live.request.get("searches"):
            live_missing.append("Live search unavailable: official update check was not performed")
        if "[unverified source]" in answer:
            live_missing.append("A live citation is unregistered or malformed")
    return {
        "answer": answer,
        "partial": bool(state.get("partial")) or exhausted or bool(outcome.missing) or bool(live_missing),
        "missing_outputs": [*state.get("missing_outputs", []), *outcome.missing, *live_missing],
        "reported_missing_outputs": outcome.missing,
        "clarification": outcome.status == "clarification",
        "citation_verified": bool(cited),
        "research_sources": registered,
    }


def select_worker(question):
    return plan_request(question).worker


def graph(
    index,
    *,
    model_stream=codex_stream,
    financials=None,
    gateway=None,
    worker_overrides=None,
):
    from src.supervisor import cooperative_graph

    return cooperative_graph(
        index,
        model_stream=model_stream,
        financials=financials,
        gateway=gateway,
        worker_overrides=worker_overrides,
    )


async def events(
    index,
    question,
    companies,
    years,
    *,
    model_stream=codex_stream,
    financials=None,
    gateway=None,
    worker_overrides=None,
):
    try:
        async with aclosing(
            graph(
                index,
                model_stream=model_stream,
                financials=financials,
                gateway=gateway,
                worker_overrides=worker_overrides,
            ).astream(
                {"question": question, "companies": companies, "years": years, "generation_request_id": uuid.uuid4().hex},
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
