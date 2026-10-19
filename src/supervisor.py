"""Bounded task-driven cooperation with typed, immutable evidence handoffs."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
from dataclasses import asdict, replace
from typing import Literal

from langgraph.config import get_stream_writer
from langgraph.graph import START, END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from src.request_routing import plan_request, requested_metrics, risk_comparison_request, price_request, live_intent, live_phrase, filing_clauses, PRICE_GAP
from src.source_collection import digest

Worker = Literal["data", "filing_inputs", "quant", "risk", "research", "current"]
NAMES = {
    "data": "Financial Data",
    "filing_inputs": "Filings Research",
    "quant": "Financial Analysis / Quant",
    "risk": "Risk Summary",
    "research": "Filings Research",
    "current": "Current Developments",
}
MAX_STEPS, MAX_TOOL_CALLS, MAX_FOLLOWUPS = 7, 64, 1
WORKER_TIMEOUT_SECONDS = 210
OUTPUT_OWNERS = {"financial_inputs": "data", "checked_calculations": "quant", "filing_explanation": "research", "risk_changes": "risk", "official_update": "research", "current_developments": "current", "public_reaction": "current"}
OUTPUT_TITLES = {
    "financial_inputs": "Reported figures",
    "filing_financial_inputs": "Filing table inputs",
    "checked_calculations": "Calculations",
    "filing_explanation": "Explanation from filings",
    "filing_evidence_followup": "Filing evidence follow-up",
    "risk_changes": "Risk-factor changes",
    "official_update": "Official update check",
    "current_developments": "Recent developments",
    "public_reaction": "Outside reaction",
    "capabilities": "System capabilities",
    "system_capabilities": "System capabilities",
    "unsupported": "Outside supported scope",
}
SECTION_LABELS = {"quant": "Financial analysis", "research": "From the filings", "current": "Outside research", "risk": "Changes in filing risks"}


def step_ids(plan):
    """Execution increments steps and position together, so position names the call."""
    return {t.worker: f"worker-{i}" for i, t in enumerate(plan, 1)}


def plan_event(task, request_plan, *, reason="", companies=(), years=()):
    """Plain-language request parts, their owners and the dispatch order."""
    outputs = (request_plan or {}).get("outputs") or []
    if outputs:
        rows = [{"id": o["id"], "kind": o["kind"], "description": o["description"], "owner": OUTPUT_OWNERS.get(o["kind"]), "timeframe": o.get("timeframe")} for o in outputs]
    else:
        rows = [{"id": f"O{i}", "kind": t.output, "description": t.reason, "owner": t.worker, "timeframe": None} for i, t in enumerate(task.plan, 1)]
    if not rows and task.requested_outputs == ["system_capabilities"]:
        rows = [{"id": "O1", "kind": "capabilities", "description": "Describe the implemented agents and their roles", "owner": None, "timeframe": None}]
    planned = {t.worker for t in task.plan}
    for row in rows:
        row["title"] = OUTPUT_TITLES.get(row["kind"], row["kind"].replace("_", " ").capitalize())
        row["agent"] = NAMES.get(row["owner"]) if row["owner"] else "Supervisor" if row["kind"] == "capabilities" else None
        row["assigned"] = row["owner"] in planned or row["kind"] == "capabilities"
    steps = []
    for i, t in enumerate(task.plan, 1):
        earlier = step_ids(task.plan[: i - 1])
        steps.append({
            "id": f"worker-{i}", "position": i, "worker": t.worker, "agent": NAMES[t.worker],
            "title": OUTPUT_TITLES.get(t.output, t.output.replace("_", " ").capitalize()), "output": t.output, "reason": t.reason,
            "called_by": "Supervisor", "after": [earlier[w] for w in t.depends_on if w in earlier],
            "serves": [r["id"] for r in rows if r["owner"] == t.worker], "feeds": [],
        })
    for step in steps:
        for prior in step["after"]:
            next(s for s in steps if s["id"] == prior)["feeds"].append(step["id"])
    return {
        "planner": "semantic" if outputs else "rules",
        "route": " → ".join(NAMES[t.worker] for t in task.plan),
        "reason": reason,
        "companies": list(companies),
        "years": list(years),
        "outputs": rows,
        "steps": steps,
    }


def review_context(state):
    """Trusted dates the reviewer needs to judge since-filing and reaction windows."""
    from src.current_developments import anchors, research_windows

    outputs = [o for o in (state.get("request_plan") or {}).get("outputs", []) if o["kind"] in ("current_developments", "public_reaction", "official_update")]
    if not outputs:
        return None
    try:
        return {
            "latest_collected_filings": anchors(state["companies"]),
            "research_windows": {o["id"]: research_windows(state, o) for o in outputs},
        }
    except (ValueError, KeyError):
        return None


def compose(rows):
    return "\n\n".join((r["label"] + ":\n" if r["labeled"] else "") + r["markdown"] for r in rows)


def strip_sections(rows, claims):
    """Remove reviewer claims per section; None means a claim crossed a boundary."""
    from src.request_plan import remove_unsupported

    if not claims:
        return rows
    reviewed = []
    for row in rows:
        found = [c for c in claims if c and c in row["markdown"]]
        reviewed.append({**row, "markdown": remove_unsupported(row["markdown"], claims), "removed": row["removed"] + found})
    kept = [row for row in reviewed if row["markdown"].strip()]
    if any(c and c in compose(kept) for c in claims):
        return None
    return reviewed


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worker: Worker
    output: str
    reason: str
    depends_on: list[Worker] = Field(default_factory=list)


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    owner: Worker
    kind: str
    company: str | None = None
    start: str | int | None = None
    end: str | int | None = None
    fiscal_year: int | None = None
    fiscal_start: str | None = None
    fiscal_end: str | None = None
    value: str | None = None
    unit: str | None = None
    accounting_basis: str | None = None
    period: str | None = None
    basis: str | None = None
    metric: str | None = None
    status: str | None = None
    freshness: str | None = None
    currency: str | None = None
    url: str | None = None
    publisher: str | None = None
    source_tier: str | None = None
    published_date: str | None = None
    as_of: str | None = None
    inspection_url: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    bundle_id: str | None = None
    identity: str


class TaskState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requested_outputs: list[str]
    required_workers: list[Worker]
    plan: list[Task]
    completed_outputs: list[str] = Field(default_factory=list)
    worker_outcomes: dict[str, str] = Field(default_factory=dict)
    registered_evidence: dict[str, EvidenceRef] = Field(default_factory=dict)
    missing_inputs: list[str] = Field(default_factory=list)
    reported_gaps: list[str] = Field(default_factory=list)
    followups: int = 0
    tool_calls: int = 0
    steps: int = 0
    terminal: Literal[
        "running",
        "completed",
        "partial",
        "needs_clarification",
        "coverage_gap",
        "failed",
        "unverified",
    ] = "running"


def filing_tasks(question):
    """Select requested outputs; dependency order never implies all workers run."""

    base = plan_request(question)
    risk = base.worker == "risk" or risk_comparison_request(question)
    financial = bool(requested_metrics(question)) and bool(
        re.search(
            r"\b(revenues?|sales|gross (?:profit|margin)|operating (?:income|margin|cash|performance)|net (?:income|loss|margin)|cash (?:flow|generation|conversion)|earnings)\b",
            question,
            re.I,
        )
    )
    if re.search(r"\b(hypothetical|suppose)\b", question, re.I) and not re.search(r"\bFY\s*20\d\d\b", question, re.I):
        financial = False
    consolidated = not re.search(r"\b(adjusted|non.GAAP|EBITDA)\b", question, re.I) or bool(re.search(r"\b(?:consolidated GAAP|GAAP (?:margins?|result|operating|parent))\b", question, re.I))
    if financial and consolidated:
        financial_plan = plan_request(question, financial_only=True)
        # Primary routing must retain the financial requirements of mixed tasks.
        base = replace(base, **{field: getattr(financial_plan, field) for field in ("revenue_component", "revenue_share", "revenue_components", "revenue_denominator", "required_calculations", "earnings_ranking", "earnings_order", "scenario")})
    numeric = financial and bool(
        re.search(
            r"\b(compar\w*|calculat\w*|grow\w*|grew|chang\w*|margins?|ratio|conversion|percentage|share|chart|plot)\b",
            question,
            re.I,
        )
    )
    if numeric and base.worker == "research":
        numeric = any(requested_metrics(clause) and re.search(r"\b(compar\w*|calculat\w*|grow\w*|grew|chang\w*|margins?|ratio|conversion|percentage|share|chart|plot)\b", clause, re.I) for clause in re.split(r"[.!?;](?:\s|$)", question))
    if (
        numeric
        and re.search(r"\bcompare\b[^.;:]*\brisk", question, re.I)
        and not re.search(
            r"\b(calculate|growth|grew|margins?|ratio|conversion|percentage|share|chart|plot)\b",
            question,
            re.I,
        )
    ):
        numeric = False
    research = base.synthesize or bool(
        re.search(
            r"\b(explain|explanations?|reasons?|drivers?|management|filing explanation|business mix|why|drove)\b",
            question,
            re.I,
        )
    )
    plan = []

    def add(worker, output, reason, depends=()):
        if not any(t.worker == worker for t in plan):
            plan.append(
                Task(
                    worker=worker,
                    output=output,
                    reason=reason,
                    depends_on=list(depends),
                )
            )

    if base.worker in ("data", "analysis_data") or financial and consolidated and (numeric or risk or re.search(r"\b(show|reported|tell me|what was)\b", question, re.I)):
        add(
            "data",
            "financial_inputs",
            "Requested reported figures require original-accession financial evidence",
        )
        if base.revenue_component:
            add(
                "filing_inputs",
                "filing_financial_inputs",
                "The requested annual component is outside the consolidated store",
                ["data"],
            )
        if base.worker == "analysis_data" or base.revenue_component or numeric:
            add(
                "quant",
                "checked_calculations",
                "Requested arithmetic must follow verified financial selection",
                ["data"],
            )
    if risk:
        add(
            "risk",
            "risk_changes",
            "Requested risk changes require complete original before/after sections",
        )
    if (
        research
        and (
            financial
            or bool(
                re.search(
                    r"\b(management(?:'s)? drivers|business mix|filing explanation)\b",
                    question,
                    re.I,
                )
            )
        )
        or financial and not risk and re.search(r"\brisks?\b", question, re.I)
        or base.worker == "research"
        and not risk
        and not plan
    ):
        add(
            "research",
            "filing_explanation",
            "Explain requested disclosure context after checked figures and risk evidence",
            [t.worker for t in plan if t.worker in ("quant", "risk")],
        )
    if not plan:
        add("research", "filing_explanation", base.reason)
    return plan, base


def tasks_for(question, *, intent=None, price_gap=None):
    from src.capabilities import capability_request
    intent = live_intent(question) if intent is None else intent
    price_gap = price_request(question) if price_gap is None else price_gap
    capability = capability_request(question)
    if capability and not capability["question"]:
        return [], plan_request("")
    scoped = filing_clauses(question, developments=intent == "developments") if price_gap or intent == "developments" else question
    if re.search(r"\bcurrent liabilities\b", scoped, re.I):
        tasks, base = [Task(worker="data", output="financial_inputs", reason="Identify the requested structured metric gap")], plan_request(scoped)
    elif scoped:
        tasks, base = filing_tasks(scoped)
    else:
        tasks, base = [], plan_request("")
    if intent == "verify" and not any(t.worker == "research" for t in tasks):
        tasks.append(Task(worker="research", output="filing_explanation", reason="Check a specific filed statement for an official update", depends_on=[t.worker for t in tasks]))
    if intent == "developments":
        tasks.append(Task(worker="current", output="current_developments", reason="Discover dated developments after the collected filings", depends_on=[t.worker for t in tasks]))
    return tasks, base


def evidence_ref(sid, source, owner):
    if not re.fullmatch(r"[SFCW][1-9]\d{0,5}", sid) or source.get("source_id") != sid:
        raise ValueError("Evidence key and typed source identifier differ")
    kind = source.get("kind", "filing_passage")
    # URLs may become frozen bundle URLs; identity is the stable provenance/value,
    # never the incidental route used to inspect the same immutable observation.
    identity = {
        k: source.get(k)
        for k in (
            "observation_id",
            "chunk_id",
            "document_id",
            "snapshot_id",
            "text_sha256",
            "snapshot_sha256",
            "company",
            "fiscal_year",
            "fiscal_start",
            "fiscal_end",
            "start",
            "end",
            "value",
            "unit",
            "metric",
            "status",
            "freshness",
            "period",
            "basis",
            "currency",
            "source_kind",
            "formula",
            "source_ids",
            "accounting_basis",
            "revision_basis",
            "as_of",
            "url",
            "publisher",
            "source_tier",
            "published_date",
        )
    }
    return EvidenceRef(
        source_id=sid,
        owner=owner,
        kind=kind,
        company=source.get("company"),
        start=source.get("start"),
        end=source.get("end"),
        fiscal_year=source.get("fiscal_year"),
        fiscal_start=source.get("fiscal_start"),
        fiscal_end=source.get("fiscal_end"),
        value=str(source["value"]) if source.get("value") is not None else None,
        unit=source.get("unit", source.get("currency")),
        accounting_basis=source.get("accounting_basis"),
        period=source.get("period"),
        basis=source.get("basis"),
        metric=source.get("metric"),
        status=source.get("status"),
        freshness=source.get("freshness"),
        currency=source.get("currency"),
        as_of=source.get("as_of"),
        url=source.get("url"),
        publisher=source.get("publisher"),
        source_tier=source.get("source_tier"),
        published_date=source.get("published_date"),
        inspection_url=source.get("inspection_url"),
        source_ids=source.get("source_ids", []),
        bundle_id=source.get("bundle_id"),
        identity=digest(json.dumps(identity, sort_keys=True).encode()),
    )


def handoff_sources(sources):
    """Keep exact metadata/values; full passage text remains available by inspection."""
    return {
        sid: {**row, "text": row.get("text", "")[:1600]} for sid, row in sources.items()
    }


def cooperative_graph(
    index, *, model_stream, financials=None, gateway=None, worker_overrides=None
):
    from src.research_workflow import State, scope_error, research_turn
    from src.financial_workflow import financial_turn
    from src.quant_workflow import quant_turn, prefetch_for_analysis
    from src.risk_summary import risk_turn
    from src.filing_financials import filing_revenue_turn
    from src.current_developments import current_turn

    class GraphState(State, total=False):
        task: dict
        evidence: dict
        worker_answers: dict
        current: int
        last_failure: str
        capability_answer: str
        request_plan: dict
        coverage_review: dict
        original_question: str

    async def plan(state):
        writer = get_stream_writer()
        writer({"type": "activity", "data": {"id": "plan", "agent": "Supervisor", "status": "running", "task": "Plan"}})
        from src.capabilities import capability_request
        original_question = state["question"]
        capability = capability_request(state["question"])
        mixed_capability = bool(re.search(r"\b(?:and|then|also)\b", original_question, re.I)) and os.getenv("REQUEST_PLANNER", "semantic") == "semantic"
        if capability and not capability["question"] and not mixed_capability:
            task = TaskState(plan=[], requested_outputs=["system_capabilities"], required_workers=[], completed_outputs=["system_capabilities"])
            writer({"type": "trace", "data": {"agent": "Supervisor", "node": "capabilities", "decision": "local_capability_answer", "reason": "Describe implemented behavior without model generation acquisition", "task": task.model_dump()}})
            writer({"type": "plan", "data": plan_event(task, {}, reason="Answered locally from implemented agent descriptions", companies=state["companies"], years=state["years"])})
            writer({"type": "activity", "data": {"id": "plan", "agent": "Supervisor", "status": "completed"}})
            return {"capability_answer": capability["answer"], "task": task.model_dump(), "evidence": {}, "worker_answers": {}, "error": "", "current": 0}
        if capability and capability["question"]:
            state = {**state, "question": capability["question"]}
        from src.request_routing import excluded_companies, mentioned_companies, mentioned_years
        companies = [company for company in state["companies"] if company not in excluded_companies(state["question"])]
        memory_reference = bool(re.search(r"\b(?:from (?:our |the )?(?:previous|prior|last) (?:conversation|chat)|same assumptions as before|as we discussed)\b", state["question"], re.I))
        clarification = memory_reference and (not mentioned_companies(state["question"]) or not mentioned_years(state["question"]) or bool(re.search(r"same assumptions as before", state["question"], re.I)))
        error = scope_error(
            state["question"], companies, state["years"], index.coverage(), check_years=os.getenv("REQUEST_PLANNER", "semantic") != "semantic"
        )
        if clarification:
            error = "Each request is self-contained. Specify the company, fiscal comparison years and any assumptions from the previous conversation; UI defaults cannot recover that context."
        intent, price_gap = live_intent(state["question"]), price_request(state["question"])
        tasks, base = tasks_for(state["question"], intent=intent, price_gap=price_gap)
        semantic, planning_gap = {}, []
        if not error and (tasks or capability) and os.getenv("REQUEST_PLANNER", "semantic") == "semantic":
            from src.request_plan import decompose
            from src.request_routing import NEGATED_LIVE
            try:
                semantic = await decompose({**state, "question": original_question, "companies": companies}, model_stream, writer)
                kinds = {o["kind"] for o in semantic["outputs"]}
                if "capabilities" in kinds and not capability:
                    capability = capability_request("What can this system do?")
                forbidden = bool(re.search(NEGATED_LIVE + r"|\b(?:no (?:web|live|online)(?: research| search)?|only (?:the )?filings|filings only)\b", state["question"], re.I))
                needs_live = bool(kinds & {"current_developments", "public_reaction"})
                intent = "developments" if needs_live else "verify" if "official_update" in kinds else "none"
                if forbidden and intent != "none":
                    intent = "none"
                    planning_gap.append("Outside research is requested but web acquisition is explicitly disabled by the question.")
                tasks, base = tasks_for(state["question"], intent=intent, price_gap=price_gap)
                owners = OUTPUT_OWNERS
                needed = {owners[k] for k in kinds if k in owners}
                if "quant" in needed:
                    needed.add("data")
                    if base.revenue_component:
                        needed.add("filing_inputs")
                tasks = [t for t in tasks if t.worker in needed and (t.worker != "current" or not forbidden)]
                for worker in ("data", "quant", "risk", "research", "current"):
                    if worker in needed and not any(t.worker == worker for t in tasks) and (worker != "current" or not forbidden):
                        tasks.append(Task(worker=worker, output=next(k for k,v in owners.items() if v == worker and k in kinds) if worker != "data" or "financial_inputs" in kinds else "financial_inputs", reason="Requested output identified from the whole question"))
                order = ["data", "filing_inputs", "quant", "risk", "research", "current"]
                tasks.sort(key=lambda t: order.index(t.worker))
                for step in tasks:
                    step.depends_on = [worker for worker in step.depends_on if any(t.worker == worker for t in tasks)]
                planning_gap.extend(o["description"] for o in semantic["outputs"] if o["kind"] == "unsupported" and not price_gap)
                writer({"type": "trace", "data": {"agent": "Supervisor", "node": "request_understanding", "plan": semantic, "reason": "Preserve every requested output independently of worker selection"}})
            except Exception:
                planning_gap.append("The complete request could not be checked; the answer covers the recognized filing tasks only.")
        if not error and os.getenv("REQUEST_PLANNER", "semantic") == "semantic":
            historical = not semantic or any(o["kind"] in ("financial_inputs", "checked_calculations", "filing_explanation", "risk_changes") for o in semantic["outputs"])
            error = scope_error(state["question"], companies, state["years"], index.coverage(), check_years=historical)
        # Preserve the supported annual component boundary.
        period_gap = None
        capability_gaps = list(planning_gap)
        for pattern, message in (
            (r"\b(?:ten.year|10.year|discounted.cash.flow|discount rate|terminal value)\b", "A full DCF requires an unsupported forecast model, discount rate and terminal assumptions; historical cash-flow evidence remains available."),
            (r"\btotal return\b|reinvested dividends", "Historical total return is unavailable: adjusted price history, dividends and reinvestment inputs are not supplied."),
            (r"\b(?:retirement portfolio|place the trades|place trades|my portfolio)\b", "Personal portfolio allocations and trade execution are unsupported; the answer provides company research only."),
        ):
            if re.search(pattern, state["question"], re.I):
                capability_gaps.append(message)
        if price_gap:
            capability_gaps.append(PRICE_GAP)
        if base.revenue_component and re.search(
            r"\bQ[1-4]\b|\b(quarter|ytd)\b", state["question"], re.I
        ):
            quarterly_tasks = [
                Task(
                    worker="research",
                    output="filing_explanation",
                    reason="Component calculations support annual tables only; inspect the requested quarterly disclosure",
                )
            ]
            period_gap = {
                "kind": "unsupported_component_period",
                "message": quarterly_tasks[0].reason,
            }
            if re.search(r"\bannual\b", state["question"], re.I):
                # Preserve explicitly requested supported annual calculations.
                # Research owns the unsupported quarterly disclosure component.
                if not any(t.worker == "research" for t in tasks):
                    quarterly_tasks[0].depends_on = ["quant"]
                    tasks.extend(quarterly_tasks)
            else:
                tasks = quarterly_tasks
        task = TaskState(
            plan=tasks,
            requested_outputs=[o["description"] for o in semantic["outputs"]] if semantic else [t.output for t in tasks],
            required_workers=[t.worker for t in tasks],
            missing_inputs=([period_gap["message"]] if period_gap else []) + capability_gaps,
        )
        writer(
            {
                "type": "trace",
                "data": {
                    "agent": "Supervisor",
                    "node": "task_selection",
                    "live_intent": intent,
                    "matched_phrase": live_phrase(state["question"], intent),
                    "price_gap": price_gap,
                    "decision": "needs_clarification" if clarification else "coverage_gap"
                    if error
                    else " → ".join(NAMES[t.worker] for t in tasks),
                    "reason": base.reason,
                    "companies": companies,
                    "selected_companies": state["companies"],
                    "years": state["years"],
                    "task": task.model_dump(),
                    "limits": {
                        "steps": MAX_STEPS,
                        "followups": MAX_FOLLOWUPS,
                        "model_tool_calls": MAX_TOOL_CALLS,
                        "worker_seconds": WORKER_TIMEOUT_SECONDS,
                    },
                },
            }
        )
        if not error and tasks:
            # The filing router's fallback reason does not describe a web-only route.
            route_reason = "The question asks for outside research only" if all(t.worker == "current" for t in tasks) else base.reason
            writer({"type": "plan", "data": plan_event(task, semantic, reason=route_reason, companies=companies, years=state["years"])})
        if error:
            from src.request_routing import mentioned_companies

            requested = mentioned_companies(state["question"])
            if set(requested) - set(state["companies"]):
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
        writer({"type": "activity", "data": {"id": "plan", "agent": "Supervisor", "status": "partial" if error or planning_gap else "completed"}})
        return {
            **asdict(base),
            "live_intent": intent,
            "request_plan": semantic,
            "question": state["question"],
            "original_question": original_question,
            "capability_answer": capability["answer"] if capability else "",
            "companies": companies,
            "clarification": clarification,
            "error": error,
            "task": task.model_dump(),
            "evidence": {},
            "worker_answers": {},
            "current": 0,
            "needs_evidence": period_gap,
            "partial": bool(period_gap or capability_gaps),
        }

    async def execute(state):
        writer = get_stream_writer()
        task = TaskState.model_validate(state["task"])
        position = state["current"]
        step = task.plan[position]
        task.steps += 1
        evidence, answers = dict(state["evidence"]), dict(state["worker_answers"])
        previous_ids = set(evidence)
        activity_id = f"worker-{task.steps}"
        writer({"type": "activity", "data": {"id": activity_id, "agent": NAMES[step.worker], "status": "running", "task": step.reason}})
        last = position == len(task.plan) - 1
        writer(
            {
                "type": "trace",
                "data": {
                    "agent": "Supervisor",
                    "node": "handoff",
                    "decision": NAMES[step.worker],
                    "reason": step.reason,
                    "depends_on": step.depends_on,
                    "evidence": [
                        r.model_dump() for r in task.registered_evidence.values()
                    ],
                    "step": task.steps,
                },
            }
        )

        class BoundedTools:
            def __init__(self, handler):
                self.handler = handler
                self.max_tool_calls = max(
                    1,
                    min(
                        getattr(handler, "max_tool_calls", 8),
                        MAX_TOOL_CALLS - task.tool_calls,
                    ),
                )

            def __getattr__(self, name):
                return getattr(self.handler, name)

            def __call__(self, name, arguments):
                if task.tool_calls >= MAX_TOOL_CALLS:
                    raise ValueError(
                        "Supervisor total tool budget exhausted; synthesize existing evidence"
                    )
                task.tool_calls += 1
                return self.handler(name, arguments)

        async def bounded_model(prompt, schemas, handler, **kwargs):
            async for event in model_stream(
                prompt, schemas, BoundedTools(handler), **kwargs
            ):
                yield event

        def emit(event):
            # Every step's prose streams as its own tagged draft. The legacy answer
            # stream still carries only the last step.
            if event["type"] in ("token", "draft"):
                writer({"type": "draft", "data": {"step": activity_id, "agent": NAMES[step.worker], "delta": event["data"]}})
                if event["type"] == "draft":
                    return
            elif event["type"] == "answer":
                writer({"type": "draft_replace", "data": {"step": activity_id, "agent": NAMES[step.worker], "markdown": event["data"]}})
            if event["type"] in ("token", "answer", "sources") and not last:
                return
            writer(event)

        failed = None
        result = {}
        try:
            if task.steps > MAX_STEPS or task.tool_calls >= MAX_TOOL_CALLS:
                raise ValueError("Supervisor work budget exhausted")
            local = {
                **state,
                "live_check": state.get("live_intent") != "none" and (state.get("live_intent") == "verify" or any(o["kind"] == "official_update" for o in state.get("request_plan", {}).get("outputs", []))),
                "analysis_sources": handoff_sources(evidence),
                "risk_sources": handoff_sources(state.get("risk_sources", {})),
                "live_offset": max([int(s[1:]) for s in evidence if re.fullmatch(r"W\d+", s)], default=0),
                "source_offset": max(
                    [int(s[1:]) for s in evidence if re.fullmatch(r"S\d+", s)],
                    default=0,
                ),
            }
            local = copy.deepcopy(local)
            if step.worker == "quant":
                local["excluded_financial_inputs"] = [{k: source.get(k) for k in ("source_id", "company", "fiscal_year", "metric", "status")} for source in local.get("financial_sources", {}).values() if source.get("status") != "available"]
                local["financial_sources"] = {sid: source for sid, source in local.get("financial_sources", {}).items() if source.get("status") == "available"}
            local["worker_output"] = step.output
            if (
                step.worker == "research"
                and len(task.plan) > 1
            ):
                clauses = re.split(r"(?<=[.!?;])\s+", state["question"])
                clauses = [filing_clauses(state["question"], developments=True)] if state.get("live_intent") == "developments" else clauses
                narrative = " ".join(c for c in clauses if re.search(r"\b(explain|explanations?|reasons?|why|drivers?|management|relate|implications?|amend\w*)\b|MD&A|10-K/A", c, re.I)) or state["question"]
                local["question"] = (
                    "Provide only the requested filing interpretation: " + narrative
                    + "\nAssigned scope: "
                    + ", ".join(state["companies"])
                    + " in fiscal years "
                    + ", ".join(map(str, state["years"]))
                    + ". Preserve supplied verified figures and calculations with original filing citations and actual fiscal dates. Do not calculate new figures. Assess only the requested explanation; do not demand unrequested metrics, a full causal bridge or a full reconciliation when a qualified explanation of important differences answers the question. Risk-change and live outputs belong to their assigned specialists."
                + (" Include the requested original annual risk context and its relationship to the business mix; do not infer reduced risk from a calculated mix alone." if not any(t.worker == "risk" for t in task.plan) and re.search(r"\brisks?\b", state["question"], re.I) else "")
                + (" Explain the release headline versus consolidated GAAP measures with the release's reconciliation and definitions; do not substitute adjusted earnings for GAAP operating income." if re.search(r"\b(release|headline|adjusted|non.GAAP)\b", state["question"], re.I) else "")
                )
            local["handoff_role_note"] = (
                "Provide only the requested filing drivers and interpretation of supplied checked figures. Preserve F/C values and bases. Risk Summary outputs are composed separately; do not duplicate their briefs or recalculate their figures."
            )
            if step.worker == "current":
                local["handoff_role_note"] = "Answer external-research outputs within research_windows with W citations. Filing explanations, figures, calculations and risk comparisons are already in the answer; relate outside findings to them without repeating them."
            async with asyncio.timeout(WORKER_TIMEOUT_SECONDS):
                if step.worker == "quant" and not local.get("financial_sources"):
                    result = {"answer": "", "partial": True, "coverage_gap": True, "missing_outputs": ["No trusted financial inputs for Quant; unsupported calculations remain missing"], "analysis_sources": {}}
                elif worker_overrides and step.worker in worker_overrides:
                    result = await worker_overrides[step.worker](local, emit)
                elif step.worker == "data":
                    if financials is None:
                        raise ValueError(
                            "Financial data unavailable; collect SEC snapshots"
                        )
                    result = await financial_turn(
                        financials,
                        local,
                        emit,
                        model_stream=bounded_model,
                        emit_answer=last,
                        handoff=any(t.worker in ("quant", "filing_inputs") for t in task.plan[position + 1 :]),
                        prefetch=([{"period": "FY", "basis": "annual", "metrics": ["revenue"]}] if state.get("revenue_component") else prefetch_for_analysis(state["question"]))
                        if any(t.worker == "quant" for t in task.plan)
                        else None,
                    )
                elif step.worker == "filing_inputs":
                    result = await filing_revenue_turn(
                        index, financials, local, emit, model_stream=bounded_model
                    )
                    task.followups += 1
                elif step.worker == "quant":
                    result = await quant_turn(
                        local, emit, model_stream=bounded_model, emit_answer=last
                    )
                elif step.worker == "risk":
                    result = await risk_turn(
                        index, local, emit, model_stream=bounded_model, emit_answer=last
                    )
                elif step.worker == "current":
                    result = await current_turn(local, emit, gateway=gateway, model_stream=bounded_model, emit_answer=last)
                elif step.worker == "research":
                    result = await research_turn(
                        index, local, emit, model_stream=bounded_model, gateway=gateway
                    )
            if result.get("error"):
                raise ValueError(result["error"])
            if not isinstance(result, dict):
                raise ValueError("Worker returned no typed result")
            sources = {
                **result.get("financial_sources", {}),
                **result.get("analysis_sources", {}),
                **result.get("risk_sources", {}),
                **result.get("research_sources", {}),
                **result.get("live_sources", {}),
            }
            pending_refs, pending_sources = {}, {}
            for sid, source in sources.items():
                # Risk tools register navigation candidates too. Pass only citations
                # and classification endpoints to subsequent specialists.
                if step.worker == "risk" and sid not in set(
                    re.findall(r"\[([SFCW]\d+)\]", result.get("answer", ""))
                ) | {
                    c[k]
                    for c in result.get("risk_changes", [])
                    for k in ("before", "after")
                    if c.get(k)
                }:
                    continue
                ref = evidence_ref(sid, source, step.worker)
                previous = task.registered_evidence.get(sid)
                if previous and previous.identity != ref.identity:
                    raise ValueError(
                        "Evidence ID collision or changed value/basis across handoff: "
                        + sid
                    )
                if previous:
                    ref.owner = previous.owner
                pending_refs[sid] = ref
                # Narrative handoffs contain excerpts. Echoing an existing ID
                # cannot replace its complete authoritative registry object.
                pending_sources[sid] = copy.deepcopy(evidence[sid] if previous else source)
            task.registered_evidence.update(pending_refs)
            evidence.update(pending_sources)
            status = (
                "needs_clarification"
                if result.get("clarification")
                else "partial"
                if result.get("partial")
                else "completed"
            )
            task.worker_outcomes[step.worker] = status
            if status == "completed":
                task.completed_outputs.append(step.output)
            task.missing_inputs.extend(result.get("missing_outputs", []))
            task.reported_gaps.extend(result.get("reported_missing_outputs", []))
            if result.get("answer"):
                answers[step.worker] = result["answer"]
            # One supported recovery from structured absence to filing extraction.
            gap = result.get("needs_evidence")
            if (
                gap
                and step.worker == "data"
                and not any(t.worker == "filing_inputs" for t in task.plan)
            ):
                if task.followups < MAX_FOLLOWUPS:
                    target = (
                        "filing_inputs"
                        if gap.get("kind") == "revenue_component"
                        else "research"
                    )
                    if not any(t.worker == target for t in task.plan[position + 1 :]):
                        task.plan.insert(
                            position + 1,
                            Task(
                                worker=target,
                                output="filing_evidence_followup",
                                reason=gap.get(
                                    "message", "Resolve missing structured evidence"
                                ),
                                depends_on=["data"],
                            ),
                        )
                        task.required_workers.insert(position + 1, target)
                        if target == "research":
                            task.followups += 1
                        writer({"type": "plan", "data": plan_event(task, state.get("request_plan"), reason=state.get("reason", ""), companies=state["companies"], years=state["years"])})
            task.missing_inputs = list(dict.fromkeys(task.missing_inputs))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Live transport exceptions are already scrubbed by the gateway.
            # Never allow an arbitrary worker exception to expose runtime credentials.
            from src.live_mcp import sanitized

            failed = f"{NAMES[step.worker]}: " + sanitized(
                str(error)
                or (
                    "A worker timed out before completing. Please retry."
                    if isinstance(error, TimeoutError)
                    else type(error).__name__
                )
            )
            task.worker_outcomes[step.worker] = (
                "unverified"
                if step.worker == "research" and result.get("answer")
                else "failed"
            )
            task.missing_inputs.append(failed)
            writer(
                {
                    "type": "trace",
                    "data": {
                        "agent": "Supervisor",
                        "node": "worker_failure",
                        "decision": "preserve_trusted_evidence"
                        if evidence
                        else "no_verified_output",
                        "worker": step.worker,
                        "reason": failed,
                    },
                }
            )
            # An intermediate unverified answer must never replace trusted results.
            result = {}
        writer(
            {
                "type": "trace",
                "data": {
                    "agent": "Supervisor",
                    "node": "worker_outcome",
                    "worker": step.worker,
                    "outcome": task.worker_outcomes[step.worker],
                    "evidence_count": len(evidence),
                    "tool_calls": task.tool_calls,
                    "missing_inputs": task.missing_inputs,
                },
            }
        )
        added = sorted(set(evidence) - previous_ids, key=lambda s: (s[0], int(s[1:])))
        writer({"type": "draft_final", "data": {"step": activity_id, "agent": NAMES[step.worker], "markdown": result.get("answer", ""), "outcome": task.worker_outcomes[step.worker], "evidence": added}})
        writer({"type": "activity", "data": {"id": activity_id, "agent": NAMES[step.worker], "status": task.worker_outcomes[step.worker], "sources": [evidence[sid] for sid in sorted(set(evidence) - previous_ids)]}})
        # Keep only bounded handoff sources in graph state, full evidence in registry.
        if "risk_sources" in result:
            result["risk_sources"] = {
                sid: source
                for sid, source in result["risk_sources"].items()
                if sid in evidence
            }
        return {
            **result,
            "task": task.model_dump(),
            "evidence": evidence,
            "worker_answers": answers,
            "current": position + 1,
            "partial": bool(state.get("partial"))
            or bool(result.get("partial"))
            or bool(failed),
            "error": "",
            "last_failure": failed.split(": ", 1)[1]
            if failed
            else state.get("last_failure", ""),
        }

    async def finish(state):
        writer = get_stream_writer()
        task = TaskState.model_validate(state["task"])
        answers = state.get("worker_answers", {})
        sections, folded, answer = [], {}, ""
        if state.get("capability_answer") and not task.plan and not task.missing_inputs:
            answer, status = state["capability_answer"], "completed"
        elif state.get("error"):
            answer, status = state["error"], "needs_clarification" if state.get("clarification") else "coverage_gap"
        elif not answers:
            answer = "No verified answer is available. " + "; ".join(
                task.missing_inputs
            )
            status = (
                "unverified"
                if "unverified" in task.worker_outcomes.values()
                else "failed"
                if "failed" in task.worker_outcomes.values()
                else "coverage_gap"
            )
        else:
            # A synthesis can explain calculations, but cannot erase a requested risk
            # or filing output. Preserve specialist evidence when the task is mixed.
            has_conflicts = any(source.get("status") == "conflicting" for source in state.get("evidence", {}).values())
            mixed = "risk" in answers or "current" in answers or has_conflicts
            include = [
                t.worker
                for t in task.plan
                if t.worker in answers
                and (mixed or t.worker == next(reversed(answers)))
            ]
            include = list(dict.fromkeys(include))
            if "quant" in include and "data" in include and not has_conflicts:
                include.remove("data")
                folded["data"] = "Its figures appear with checked calculations in Financial analysis."
            if "quant" in include and "research" in include and task.worker_outcomes.get("quant") == "completed":
                calculations = set(re.findall(r"\[(C\d+)\]", answers["quant"]))
                if calculations and calculations <= set(re.findall(r"\[(C\d+)\]", answers["research"])):
                    include.remove("quant")
                    folded["quant"] = "Its calculations are cited in From the filings."
            ids = step_ids(task.plan)
            sections = [
                {"id": ids[w], "worker": w, "agent": NAMES[w], "label": SECTION_LABELS.get(w, NAMES[w]), "labeled": len(include) > 1, "markdown": answers[w], "removed": []}
                for w in include
            ]
            status = (
                "needs_clarification"
                if "needs_clarification" in task.worker_outcomes.values()
                else "partial"
                if state.get("partial")
                or task.missing_inputs
                or any(v != "completed" for v in task.worker_outcomes.values())
                else "completed"
            )
        if not sections:
            sections = [{"id": "capabilities" if state.get("capability_answer") and not task.plan else "supervisor", "worker": None, "agent": "Supervisor", "label": "System capabilities" if state.get("capability_answer") and not task.plan else "Supervisor", "labeled": False, "markdown": answer, "removed": []}]
        final_agent = next((s["agent"] for s in reversed(sections) if s["worker"]), None)
        for t in task.plan:
            if t.worker in folded or any(s["worker"] == t.worker for s in sections):
                continue
            outcome = task.worker_outcomes.get(t.worker)
            folded[t.worker] = (
                "Not run before the supervisor stopped." if outcome is None
                else f"No verified answer from this agent ({outcome})." if t.worker not in answers
                else f"Its results were handed to {final_agent}, whose answer uses them." if final_agent
                else "Its answer was not used."
            )
        if not task.registered_evidence and status == "partial" and state.get("live_intent", "none") == "none":
            status = "failed" if "failed" in task.worker_outcomes.values() else "coverage_gap"
        review, review_status, fallback = {}, "skipped", False
        if state.get("capability_answer") and (task.plan or task.missing_inputs):
            sections.insert(0, {"id": "capabilities", "worker": None, "agent": "Supervisor", "label": "System capabilities", "labeled": False, "markdown": state["capability_answer"], "removed": []})
        answer = compose(sections)

        def reviewed(rows, claims):
            # Sections are the source of truth; a claim crossing a section
            # boundary falls back to whole-answer removal in one section.
            nonlocal fallback
            from src.request_plan import remove_unsupported

            if not fallback and (result := strip_sections(rows, claims)) is not None:
                return result
            fallback = True
            text = compose([r for r in rows if r["markdown"].strip()])
            found = [c for c in claims if c and c in text]
            return [{"id": "answer", "worker": None, "agent": "Supervisor", "label": "Answer", "labeled": False, "markdown": remove_unsupported(text, claims) if claims else text, "removed": [c for r in rows for c in r["removed"]] + found}]

        if state.get("request_plan") and (answers or state.get("capability_answer")) and not state.get("error"):
            from src.request_plan import coverage
            context = review_context(state)
            writer({"type": "activity", "data": {"id": "review", "agent": "Answer Reviewer", "status": "running", "task": "Check answer"}})
            review_status = "failed"
            try:
                review = await coverage(state.get("original_question", state["question"]), state["request_plan"]["outputs"], answer, state.get("evidence", {}), model_stream, writer, context)
                sections = reviewed(sections, review["unsupported_claims"])
                answer = compose([s for s in sections if s["markdown"].strip()])
                if review["unsupported_claims"]:
                    removed = review["unsupported_claims"]
                    review = await coverage(state.get("original_question", state["question"]), state["request_plan"]["outputs"], answer, state.get("evidence", {}), model_stream, writer, context)
                    # One bounded repair pass. If a second check finds more unsupported
                    # claims, remove them and retain the partial outcome.
                    sections = reviewed(sections, review["unsupported_claims"])
                    answer = compose([s for s in sections if s["markdown"].strip()])
                    review["removed_claims"] = removed + review["unsupported_claims"]
                if not review["missing"]:
                    task.missing_inputs = [gap for gap in task.missing_inputs if gap not in task.reported_gaps]
                    if status == "partial" and not task.missing_inputs and not any(v in ("failed", "unverified", "needs_clarification") for v in task.worker_outcomes.values()):
                        status = "completed"
                task.missing_inputs.extend(review["missing"])
                writer({"type": "trace", "data": {"agent": "Supervisor", "node": "answer_coverage", **review}})
                review_status = "partial" if review["missing"] else "completed"
            except Exception:
                task.missing_inputs.append("Full-question coverage review is unavailable.")
            task.missing_inputs = list(dict.fromkeys(task.missing_inputs))
            if task.missing_inputs and status == "completed":
                status = "partial"
            writer({"type": "activity", "data": {"id": "review", "agent": "Answer Reviewer", "status": review_status}})
        for row in sections:
            if row["worker"] and not row["markdown"].strip():
                folded[row["worker"]] = "Removed by the Answer Reviewer: no supported sentence remained."
        sections = [s for s in sections if s["markdown"].strip()]
        task.terminal = status
        suffix = ""
        if task.missing_inputs and status in ("partial", "coverage_gap", "needs_clarification"):
            suffix = "\n\nUnresolved outputs:\n" + "\n".join("- " + gap for gap in task.missing_inputs[:12])
        evidence = state.get("evidence", {})
        cited = set(re.findall(r"\[([SFCW]\d+)\]", compose(sections) + suffix))
        invalid = cited - evidence.keys()
        if invalid:
            status = task.terminal = "partial" if evidence else "failed"
            task.missing_inputs.append(
                "Unregistered source references excluded: " + ", ".join(sorted(invalid))
            )
            for sid in invalid:
                suffix = suffix.replace("[" + sid + "]", "[unverified source]")
                for row in sections:
                    row["markdown"] = row["markdown"].replace("[" + sid + "]", "[unverified source]")
        answer = compose(sections) + suffix
        outputs = (state.get("request_plan") or {}).get("outputs") or []
        gaps = []
        for gap in dict.fromkeys(task.missing_inputs):
            match = re.match(r"([RO]\d+):\s*", gap)
            owner = next((o for o in outputs if (match and o["id"] == match[1]) or gap.startswith(o["description"] + ":")), None)
            text = gap[match.end():] if match else gap[len(owner["description"]) + 1:].strip() if owner else gap
            gaps.append({"output": owner["id"] if owner else match[1] if match else None, "text": text, "source": "Answer Reviewer" if gap in review.get("missing", []) else "Agent" if gap in task.reported_gaps else "Supervisor"})
        final_ids = step_ids(task.plan)
        writer({"type": "answer_sections", "data": {
            "sections": [{k: s[k] for k in ("id", "worker", "agent", "label", "labeled", "markdown", "removed")} for s in sections],
            "folded": [{"id": f"worker-{i}", "worker": t.worker, "agent": NAMES[t.worker], "reason": folded[t.worker]} for i, t in enumerate(task.plan, 1) if t.worker in folded and final_ids[t.worker] == f"worker-{i}"],
            "review": {"status": review_status, "results": review.get("results", []), "removed_claims": review.get("removed_claims", review.get("unsupported_claims", []))},
            "gaps": gaps,
            "fallback": fallback,
        }})
        writer({"type": "answer", "data": answer})
        if cited & evidence.keys():
            writer(
                {
                    "type": "sources",
                    "data": [
                        evidence[sid]
                        for sid in sorted(
                            cited & evidence.keys(), key=lambda s: (s[0], int(s[1:]))
                        )
                    ],
                }
            )
        writer(
            {
                "type": "trace",
                "data": {
                    "agent": "Supervisor",
                    "node": "termination",
                    "reason": "Implemented capabilities described locally" if state.get("capability_answer") and not task.plan else "All requested outputs have verified worker outcomes"
                    if status == "completed"
                    else "Preserve verified findings and expose missing or unresolved outputs",
                    "task": task.model_dump(),
                },
            }
        )
        if status == "failed" and state.get("last_failure"):
            writer({"type": "error", "data": state["last_failure"]})
        writer(
            {
                "type": "complete",
                "data": {
                    "status": status,
                    "verified_citations": bool(cited & evidence.keys()) and not invalid,
                    **({"coverage_checked": True} if review else {}),
                    **(
                        {"missing_outputs": task.missing_inputs}
                        if task.missing_inputs and status != "failed"
                        else {}
                    ),
                },
            }
        )
        return {"answer": answer, "task": task.model_dump(), "coverage_review": review}

    workflow = StateGraph(GraphState)
    workflow.add_node("supervisor", plan)
    workflow.add_node("worker", execute)
    workflow.add_node("finish", finish)
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor", lambda s: "finish" if s.get("error") or not s["task"]["plan"] else "worker"
    )
    workflow.add_conditional_edges(
        "worker",
        lambda s: "worker"
        if s["current"] < len(s["task"]["plan"]) and s["task"]["steps"] < MAX_STEPS
        else "finish",
    )
    workflow.add_edge("finish", END)
    return workflow.compile()
