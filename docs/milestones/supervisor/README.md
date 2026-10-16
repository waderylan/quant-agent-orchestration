# M9 — Supervisor cooperation

Owner: Rylan Wade. The [milestone index](../README.md) owns status.

The LangGraph supervisor plans requested outputs and executes only their required workers. Single filing, exact-figure, quote, and risk-change requests take short paths. Financial arithmetic orders Data before Quant; supported annual component gaps use one filing-extraction handoff. Mixed requests can run Data → Quant → Risk Summary → Filings Research → Buy-Side Analyst. Narrative specialists preserve checked figures; each receives its assigned output rather than responsibility for the entire request.

## State and transitions

`TaskState` records requested outputs, required workers, ordered `Task` dependencies and reasons, completed outputs, worker outcomes, `EvidenceRef` records, missing inputs, follow-up/tool/step counts, and terminal state. Each evidence record retains one owner, source ID, exact value/unit, fiscal dates, accounting basis, calculation lineage, inspection URL, bundle identity, and a stable provenance/value digest. Full source objects remain in the request registry; narrative handoffs carry bounded excerpts and exact metadata. New workers start above all existing S/F/C IDs.

Each worker returns to the supervisor. The supervisor validates evidence transactionally before publishing it; changed values/bases or reused IDs fail the handoff. Copies prevent a worker from mutating prior evidence. A failed later worker leaves earlier verified findings available. Scope errors terminate before generation. Unsupported or missing inputs stay explicit; a missing structured observation may trigger one supported filing follow-up. There is no cross-turn memory or scope expansion.

Limits are seven worker steps, one evidence follow-up, 64 executed model tool calls per request, and 210 seconds per worker including acquisition. Each specialist retains its smaller local budget and generation deadline. Cancellation propagates to the owned CLI/graph work. Outcomes distinguish completed, partial, needs clarification, coverage gap, and the existing failed/unverified contracts. A partial result retains cited findings and names unresolved outputs; no failed handoff becomes completed evidence.

## Verification

[M9 acceptance](evidence/M9_ACCEPTANCE_2026-10-16.json) separates actual subscription direct/graph/API paths, native and Docker Chromium, concurrent HTTP turns, and synthetic transition/failure tests. The five-specialist Qualcomm question compares reported revenue and margins, explains management drivers and original risk changes, then gives a conditional valuation assessment with explicit missing market bases. S/F/C browser links open exact sources and checked lineage. Market limitations yield a partial result while financial and filing work remains usable.

Short Data-only, Buy-Side-only quote, and Data → Risk paths complete. Native and Docker browsers expose all five workers, open S/F/C evidence, and cancel a separate turn with controls restored. Concurrent AMD/QCOM HTTP turns keep separate source registries. Fixture tests cover deadline, missing structured source, bounded follow-up, unsupported year, source-less clarification, conflicting and mutating worker evidence, cancellation, and existing Research/Data/Quant regressions. The first real five-worker run exposed an ID collision; the registry rejected it, and the corrected handoff passes the affected path. Formal trajectory scoring remains M12.

```powershell
uv run --locked pytest -q
uv run --locked python scripts/demo_supervisor.py --url http://127.0.0.1:8080
uv run --locked python scripts/verify_cooperation_edges.py --url http://127.0.0.1:8080
uv run --locked python scripts/demo_supervisor.py --browser-only --url http://127.0.0.1:8084 --output artifacts/m9-docker-browser.json
```

The [first independent engineering review](evidence/review-round-1/README.md) retains 48 sealed questions, worktree isolation and actual delegation evidence, application outcomes, exact source inspections, calculation replays and substantive fixes. The reviewer receives answers only after question sealing. Review cases and criteria remain unchanged. These checks are distinct from formal RAGAS evaluation and use the same shared live-provider budgets.
