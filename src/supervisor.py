"""Bounded task-driven cooperation with typed, immutable evidence handoffs."""

from __future__ import annotations

import asyncio
import copy
import json
import re
from dataclasses import asdict
from typing import Literal

from langgraph.config import get_stream_writer
from langgraph.graph import START, END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from src.request_routing import plan_request, requested_metrics
from src.source_collection import digest

Worker = Literal["data", "filing_inputs", "quant", "risk", "research", "buy"]
NAMES = {
    "data": "Financial Data",
    "filing_inputs": "Filings Research",
    "quant": "Financial Analysis / Quant",
    "risk": "Risk Summary",
    "research": "Filings Research",
    "buy": "Buy-Side Analyst",
}
MAX_STEPS, MAX_TOOL_CALLS, MAX_FOLLOWUPS = 7, 64, 1


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


def tasks_for(question):
    """Select requested outputs; dependency order never implies all workers run."""
    from src.buy_side import market_request

    base = plan_request(question)
    risk = base.worker == "risk" or bool(
        re.search(r"\brisk(?:s| factors)?\b", question, re.I)
        and re.search(
            r"\b(chang\w*|compar\w*|add\w*|remov\w*|relocat\w*|mov\w*|reword\w*)\b",
            question,
            re.I,
        )
    )
    market = market_request(question)
    financial = bool(requested_metrics(question)) and bool(
        re.search(
            r"\b(revenues?|gross (?:profit|margin)|operating (?:income|margin|cash)|net income|net loss|cash (?:flow|generation|conversion))\b",
            question,
            re.I,
        )
    )
    numeric = financial and bool(
        re.search(
            r"\b(compar\w*|calculat\w*|growth|grew|margins?|ratio|conversion|percentage|share|chart|plot)\b",
            question,
            re.I,
        )
    )
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
            r"\b(explain|drivers?|management|filing explanation|business mix|why|drove)\b",
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

    if base.worker in ("data", "analysis_data") or financial and (risk or market):
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
        or base.worker == "research"
        and not risk
        and not market
    ):
        add(
            "research",
            "filing_explanation",
            "Explain requested disclosure context after checked figures and risk evidence",
            [t.worker for t in plan if t.worker in ("quant", "risk")],
        )
    if market:
        add(
            "buy",
            "valuation_brief"
            if re.search(r"valu|premium|P/E|multiples?|upside|scenario", question, re.I)
            else "market_snapshot",
            "Requested market/valuation output needs dated market evidence and existing checked handoffs",
            [t.worker for t in plan if t.worker in ("quant", "risk", "research")],
        )
    if not plan:
        add("research", "filing_explanation", base.reason)
    return plan, base


def evidence_ref(sid, source, owner):
    if not re.fullmatch(r"[SFC][1-9]\d{0,5}", sid) or source.get("source_id") != sid:
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
            "formula",
            "source_ids",
            "accounting_basis",
            "revision_basis",
            "as_of",
            "dilution",
            "split_basis",
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
    from src.buy_side import buy_turn

    class GraphState(State, total=False):
        task: dict
        evidence: dict
        worker_answers: dict
        current: int
        last_failure: str

    def plan(state):
        writer = get_stream_writer()
        error = scope_error(
            state["question"], state["companies"], state["years"], index.coverage()
        )
        tasks, base = tasks_for(state["question"])
        # Preserve the supported annual component boundary.
        period_gap = None
        if base.revenue_component and re.search(
            r"\bQ[1-4]\b|\b(quarter|ytd)\b", state["question"], re.I
        ):
            tasks = [
                Task(
                    worker="research",
                    output="filing_explanation",
                    reason="Component calculations support annual tables only; inspect the requested quarterly disclosure",
                )
            ]
            period_gap = {
                "kind": "unsupported_component_period",
                "message": tasks[0].reason,
            }
        task = TaskState(
            plan=tasks,
            requested_outputs=[t.output for t in tasks],
            required_workers=[t.worker for t in tasks],
            missing_inputs=[period_gap["message"]] if period_gap else [],
        )
        writer(
            {
                "type": "trace",
                "data": {
                    "agent": "Supervisor",
                    "node": "task_selection",
                    "decision": "coverage_gap"
                    if error
                    else " → ".join(NAMES[t.worker] for t in tasks),
                    "reason": base.reason,
                    "companies": state["companies"],
                    "years": state["years"],
                    "task": task.model_dump(),
                    "limits": {
                        "steps": MAX_STEPS,
                        "followups": MAX_FOLLOWUPS,
                        "model_tool_calls": MAX_TOOL_CALLS,
                    },
                },
            }
        )
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
        return {
            **asdict(base),
            "error": error,
            "task": task.model_dump(),
            "evidence": {},
            "worker_answers": {},
            "current": 0,
            "needs_evidence": period_gap,
            "partial": bool(period_gap),
        }

    async def execute(state):
        writer = get_stream_writer()
        task = TaskState.model_validate(state["task"])
        position = state["current"]
        step = task.plan[position]
        task.steps += 1
        evidence, answers = dict(state["evidence"]), dict(state["worker_answers"])
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
            if event["type"] in ("token", "answer", "sources") and not last:
                return
            writer(event)

        failed = None
        result = {}
        try:
            if task.steps > MAX_STEPS or task.tool_calls >= MAX_TOOL_CALLS:
                raise ValueError("Supervisor work budget exhausted")
            if step.worker == "quant" and not state.get("financial_sources"):
                raise ValueError(
                    "No trusted financial inputs for Quant; unsupported inputs remain missing"
                )
            local = {
                **state,
                "analysis_sources": handoff_sources(evidence),
                "risk_sources": handoff_sources(state.get("risk_sources", {})),
                "source_offset": max(
                    [int(s[1:]) for s in evidence if re.fullmatch(r"S\d+", s)],
                    default=0,
                ),
            }
            local = copy.deepcopy(local)
            local["worker_output"] = step.output
            if (
                step.worker == "research"
                and len(task.plan) > 1
                and any(t.worker == "quant" for t in task.plan)
            ):
                local["question"] = (
                    "Explain management's filing-disclosed drivers and business mix for "
                    + ", ".join(requested_metrics(state["question"]))
                    + " for "
                    + ", ".join(state["companies"])
                    + " in fiscal years "
                    + ", ".join(map(str, state["years"]))
                    + ". Interpret the supplied checked figures with original filing citations and actual fiscal dates. Provide this filing explanation only; do not calculate new figures."
                )
            local["handoff_role_note"] = (
                "Provide only the requested filing drivers and interpretation of supplied checked figures. Preserve F/C values and bases. Risk Summary and Buy-Side outputs are composed separately; do not duplicate their briefs or recalculate their figures."
            )
            async with asyncio.timeout(210):
                if worker_overrides and step.worker in worker_overrides:
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
                        prefetch=prefetch_for_analysis(state["question"])
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
                elif step.worker == "research":
                    result = await research_turn(
                        index, local, emit, model_stream=bounded_model
                    )
                else:
                    result = await buy_turn(
                        local,
                        emit,
                        gateway=gateway,
                        model_stream=bounded_model,
                        emit_answer=last,
                    )
            if result.get("error"):
                raise ValueError(result["error"])
            if not isinstance(result, dict):
                raise ValueError("Worker returned no typed result")
            sources = {
                **result.get("financial_sources", {}),
                **result.get("analysis_sources", {}),
                **result.get("risk_sources", {}),
                **result.get("buy_sources", {}),
                **result.get("research_sources", {}),
            }
            pending_refs, pending_sources = {}, {}
            for sid, source in sources.items():
                # Risk tools register navigation candidates too. Pass only citations
                # and classification endpoints to subsequent specialists.
                if step.worker == "risk" and sid not in set(
                    re.findall(r"\[([SFC]\d+)\]", result.get("answer", ""))
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
                pending_sources[sid] = copy.deepcopy(source)
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
            task.missing_inputs = list(dict.fromkeys(task.missing_inputs))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Market transport exceptions are already scrubbed by the gateway.
            # Never allow an arbitrary worker exception to expose runtime credentials.
            from src.market_mcp import sanitized

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

    def finish(state):
        writer = get_stream_writer()
        task = TaskState.model_validate(state["task"])
        answers = state.get("worker_answers", {})
        if state.get("error"):
            answer, status = state["error"], "coverage_gap"
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
            # or valuation output. Preserve specialist evidence when the task is mixed.
            mixed = "risk" in answers or "buy" in answers
            include = [
                t.worker
                for t in task.plan
                if t.worker in answers
                and (mixed or t.worker == next(reversed(answers)))
            ]
            include = list(dict.fromkeys(include))
            if "quant" in include and "data" in include:
                include.remove("data")
            answer = "\n\n".join(
                (NAMES[w] + ":\n" if len(include) > 1 else "") + answers[w]
                for w in include
            )
            status = (
                "needs_clarification"
                if "needs_clarification" in task.worker_outcomes.values()
                else "partial"
                if state.get("partial")
                or task.missing_inputs
                or any(v != "completed" for v in task.worker_outcomes.values())
                else "completed"
            )
        task.terminal = status
        writer({"type": "answer", "data": answer})
        evidence = state.get("evidence", {})
        cited = set(re.findall(r"\[([SFC]\d+)\]", answer))
        invalid = cited - evidence.keys()
        if invalid:
            status = task.terminal = "partial" if evidence else "failed"
            task.missing_inputs.append(
                "Unregistered source references excluded: " + ", ".join(sorted(invalid))
            )
            for sid in invalid:
                answer = answer.replace("[" + sid + "]", "[unverified source]")
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
                    "reason": "All requested outputs have verified worker outcomes"
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
                    **(
                        {"missing_outputs": task.missing_inputs}
                        if task.missing_inputs and status != "failed"
                        else {}
                    ),
                },
            }
        )
        return {"answer": answer, "task": task.model_dump()}

    workflow = StateGraph(GraphState)
    workflow.add_node("supervisor", plan)
    workflow.add_node("worker", execute)
    workflow.add_node("finish", finish)
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor", lambda s: "finish" if s.get("error") else "worker"
    )
    workflow.add_conditional_edges(
        "worker",
        lambda s: "worker"
        if s["current"] < len(s["task"]["plan"]) and s["task"]["steps"] < MAX_STEPS
        else "finish",
    )
    workflow.add_edge("finish", END)
    return workflow.compile()
