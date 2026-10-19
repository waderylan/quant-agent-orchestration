# M10 — Current Developments

Owner: Rylan Wade. The [milestone index](../README.md) owns status and order.

Current Developments researches dated external events and identifiable outside reactions for selected companies. Filings Research shares Tavily search for an official update to a specific filed statement. The application has five specialists. Prices, multiples and analyst forecasts are outside scope; Quant valuation is unsupported.

## Verified behavior

- Semantic request decomposition preserves distinct requested outputs before choosing workers. Casual requests for public reaction receive outside research alongside filing explanations and calculations. A separate answer reviewer checks the original question, including clauses omitted by the plan, against the answer and cited excerpts. Unsupported sentences are removed, followed by one bounded recheck. Final remaining gaps determine completeness; successful review can clear model uncertainty but cannot erase structural evidence gaps or worker failures.
- External research runs after any Data, Quant, Risk or Research tasks. Official-update requests grant Research its general-topic search alongside Current Developments when both are needed. Explicit no-web wording prohibits acquisition. Capability outputs use local implemented descriptions without an external worker. Price-only requests have no worker; mixed supported clauses retain the scope gap. Company coverage remains enforced; fiscal controls select historical evidence independently of recent web research.
- Current Developments owns W evidence and external findings. Research owns filed S explanations, Data reported F figures, Quant C calculations and Risk Summary filing comparisons. Answers lead with findings and supported significance, attribute outside views, and mention material limitations once. General updates do not require unrequested official confirmation.
- Per-output timeframe, reaction year and dates take precedence over compatible plan-wide fallbacks. Recent questions use a 90-day window; stated calendar periods are normalized using today's date. Since-filing questions use the maximum inventory `source_date`; historical reactions use the selected annual filing/release window. Calendar-year web research is independent of fiscal controls, while requested release years must match selected corpus years. Missing requested findings remain named gaps. [Architecture](../../architecture.md) owns exact windows and completion checks.
- W records preserve immutable snapshot observations, publication-date provenance and canonical URL identity across search/extraction. Extracted article bodies take precedence over shorter search text; `date_snapshot_id` retains the date's source snapshot. Page publication labels/datelines can establish dates; incidental event dates and URL paths cannot. Navigation/image data is cleaned before truncation. Issuer-authored wire releases need explicit attribution. The browser shows the requested-output checklist and readable source labels; `/api/live/{snapshot_id}` returns scrubbed, checksum-checked MCP evidence.

## MCP contract and limits

`tavily_search` is the shared Remote MCP tool on `tavily-mcp` 4.1.0 over Streamable HTTP. Runtime query-parameter authentication stays outside stored data, trace and image. Both workers emit `live_mcp` trace events with agent, server, tool, arguments, result count, snapshot, cache and outcome. Research reports filed content with S citations before an official W update. Third-party results do not establish an official update. [Architecture](../../architecture.md) owns the complete sharing rationale and contracts.

Semantic requests use bounded advanced discovery with explicit research dates, optional domain filters and focused extraction. The gateway discovers the actual tool schema and omits unsupported parameters, including `chunks_per_source`. Research keeps narrow shared-search access; Current Developments also extracts and inspects sources. [Architecture](../../architecture.md#mcp-tool-sharing) owns call/context limits, supported fields, caching, source authority and credit reservations.

The per-host ledger enforces the monthly stop even when account usage is throttled. A verified monthly floor plus local reservations permits acquisition; successful results carry a trace warning without an artificial evidence gap. Without a verified floor, acquisition stops. Real acquisition failures, unsupported citations and missing requested evidence remain partial. Configuration is in [.env.example](../../../.env.example).

`REQUEST_PLANNER=semantic` enables whole-request understanding and independent coverage review by default. `rules` is the frozen regression profile, without model understanding/review. The unchanged [17-row fixture](../../../tests/fixtures/live_routing.json) checks its deterministic worker sequences and price gaps.

## Usefulness evidence

[Usefulness evidence](evidence/USEFULNESS_2026-10-19.json) records the development examples, independently generated human prompts, source checks, request coverage, browser behavior and remaining limits. It distinguishes local subscription generation and actual Tavily acquisition from formal provider/evaluation results.

The [initial review](evidence/HOLDOUT_2026-10-19.json) identifies its captured runtime by hash and reports 18 captures: 17 valid cases, five passes, three passes with limits and nine failures; one invalid evaluator input is excluded. The [six-case iteration 2 review](evidence/HOLDOUT_ITERATION2_2026-10-19.json) preserves its separate runtime and failures. These scores describe their captured versions rather than the current runtime.

The [final four-question review](evidence/HOLDOUT_FINAL_2026-10-19.json) passes its bounded usefulness gate: four useful answers, zero critical failures and mean reviewer score 7.75/8. This small local engineering check does not establish a general accuracy rate. [Evaluation](../../evaluation.md) owns measured timing and method limits.

Two additional [fresh filings-only checks](evidence/HOLDOUT_VALIDATION_2026-10-19.json) complete without web tools on their separately recorded runtime and verify the calculation-lineage fix. These checks remain separate from the four-question review.

## Acceptance — 2026-10-19

The acceptance records below describe version `1df22b7`; the usefulness evidence describes the current request-planning, evidence-processing and answer-coverage behavior.

| Item | Result and evidence |
| --- | --- |
| 1. Regression and phase gates | 209 passed, zero failed; [tests](evidence/TESTS_2026-10-19.json) |
| 2. Direct worker | Real search/extraction and registered W sources; [direct](evidence/DIRECT_2026-10-19.json) |
| 3. Native application | All five required cases match worker plans, citations and terminal contracts; [application](evidence/APPLICATION_2026-10-19.json) |
| 4. Shared tool | Real searches from both agent contexts use the same server/tool; [sharing](evidence/SHARING_2026-10-19.json) |
| 5. Chromium | Both new examples run; W/S/C inspection in one session, safe external link and no stock buttons; [browser](evidence/BROWSER_2026-10-19.json) |
| 6. Linux container | Runtime-only key, real uncached search and extraction on refresh; [container](evidence/DOCKER_2026-10-19.json), [security scan](evidence/SECURITY_2026-10-19.json) |
| 7. Failures | Blank key, 429, timeout and off return partial and preserve earlier Data; [tests](evidence/TESTS_2026-10-19.json) |
| 8. Budget | Atomic reservations, conservative usage floor and monthly stop; [ledger](evidence/BUDGET_2026-10-19.json) |
| 9–10. Docs and removal | Local links, paths, coverage, compile and removal classifications; [checks](evidence/CHECKS_2026-10-19.json), [file manifest](evidence/FILES_2026-10-19.json) |
| 11. Transcript | One local M10 event is finalized after documentation; [acceptance metadata](evidence/ACCEPTANCE_2026-10-19.json) identifies the entry and its final read-only checks. |

```powershell
uv run --locked pytest -q
uv run --locked python scripts/demo_current.py --direct --output artifacts/current-direct.json
uv run --locked python scripts/demo_current.py --url http://127.0.0.1:8088 --output artifacts/current-app.json
uv run --locked python scripts/demo_current.py --browser --url http://127.0.0.1:8088 --output artifacts/current-browser.json
uv run --locked python scripts/start_local_container.py --live-mode live
uv run --locked python scripts/demo_current.py --url http://127.0.0.1:8084 --case nvda --refresh --output artifacts/current-container.json
```

## Evidence limits

Native, direct-worker, fixture, Chromium and Linux-container evidence are distinct; these runs do not establish Cloud Run or serving-provider behavior. Partial results retain supported findings and identify missing requested evidence. Publication metadata, source tier and model coverage review do not prove every narrative claim true. The SQLite monthly floor is per host; M13 decides cross-instance coordination. Coverage is limited to the four selected companies. Raw runs and cached snapshots stay in ignored `artifacts/`; the evidence links retain credential-free summaries.
