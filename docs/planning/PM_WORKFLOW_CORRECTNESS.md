# PM workflow correctness

- Owner: Rylan Wade.
- Scope: implemented Financial Data, Quant, and Filings Research workflows. Risk Summary, general task planning, conversation memory, live prices, provider comparisons, and cloud deployment remain separate milestones.

## Request and evidence contracts

- Company exclusions do not expand selected scope. Explicit historical fiscal-year context permits questions about demand that was current at that year-end. Genuine current market requests require unavailable live research.
- Supported numerical questions with an explanation run Data → Quant → Research. Research receives frozen observations and checked calculations, retrieves filing explanations, and publishes the final answer. Intermediate model prose is withheld; checked artifacts remain visible. Intermediate explanation requests become handoff notes; missing required calculations remain explicit gaps.
- Qualcomm annual automotive, handset, and IoT rows are independently extracted from registered original filing tables. Requested rows must each be verified. Shares use the requested consolidated or QCT denominator; QCT revenue is extracted from the same original table.
- Earnings means parent-attributable GAAP net income. Percentage ordering excludes nonpositive baselines; dollar ordering includes loss recovery. Incidental requests to display dollar figures do not change a percentage ranking. Answers and stored assessments use the same ordering.
- Cash conversion is operating cash flow divided by positive parent-attributable net income for the same company, period, and reporting basis. The result is a multiple. Zero/loss denominators and mismatched inputs are rejected.
- Supported hypothetical arithmetic requires an explicit user assumption: one business component doubles with all other revenue unchanged, or one positive `1 EUR = x USD` rate. Component scenarios recompute total revenue as reported total plus incremental component revenue. Assumptions remain labeled as user inputs in calculation inspection and exported ledgers. They do not become reported observations or market forecasts.
- Currency conversion uses the requested supported consolidated metric and divides USD by USD/EUR. Unsupported business/geographic inputs are not replaced with consolidated revenue. No current exchange rate is fetched.
- Quant independently recomputes every published result; verifies lineage, units, periods, component/denominator identity, and authorized assumptions; and checks required calculation coverage. Reported USD arithmetic is exact; percentages, multiples, and EUR conversions use a tolerance of `1e-8`. Bounded execution limits remain defined in [M6](M6_FINANCIAL_ANALYSIS_QUANT_AGENT.md).

## Completion and citations

- Every generated worker reports an explicit outcome through `report_outcome`. Valid source identifiers establish evidence identity, not completeness. Missing completion reports cannot silently produce completed results.
- Final states distinguish `completed`, `partial`, `needs_clarification`, `coverage_gap`, `unverified`, and `failed`. Partial answers retain available evidence and expose `missing_outputs`; the browser displays “Still needed.” A clarification can correctly contain no citations and has `verified_citations: false`.
- Bounded citation ranges expand to individual registered identifiers. An explicitly refuted fabricated identifier becomes plain text. Positive assertions with unknown identifiers still fail verification. SSE `answer` events replace streamed text when normalization changes it; browser and test clients honor the replacement.
- Citation identity, independent arithmetic, and artifact hashes do not establish exhaustive claim-level faithfulness. Narrative conclusions require review against cited passages.

## Verification and reproduction

- [Verification report](../research/PM_FIXES_VERIFICATION.md): 118 automated tests; 30 actual application chats; 215 source inspections; 85 independently checked and replayed calculations across 17 bundles; eight Docker browser flows; six Linux interpreter fixtures. The report records remaining evidence boundaries, latency, and verification interruptions.

- [Exploratory baseline](../research/PM_EXPLORATION_2026-10-15.md) records 26 PM questions and four wording controls at its identified revision. These are development regressions, not held-out evaluation or a reliability estimate.
- [Final application retest](../research/PM_FIXES_RETEST_RESULTS.json) preserves all 30 exact questions, answers, statuses, traces, source inspections, latency, and runtime file hashes. [Independent audit](../research/PM_FIXES_RETEST_AUDIT.json) recomputes arithmetic and checks downloadable artifact hashes.
- [Local Docker acceptance](../research/PM_FIXES_CONTAINER_RESULTS.json), [Chromium checks](../research/PM_FIXES_CONTAINER_BROWSER_RESULTS.json), and [Linux interpreter fixtures](../research/PM_FIXES_LINUX_RESULTS.json) are separate from native evidence. Generation uses the host subscription bridge; credentials remain outside the image.
- `tests/test_pm_workflows.py` protects routing, completion ownership, citation normalization, validation, assumptions, lineage, required outputs, and mixed-worker handoffs. Existing financial, research, and Quant tests protect underlying contracts.

```powershell
uv run --locked pytest -q
uv run --locked python scripts/explore_pm_questions.py --output artifacts/pm-repeat.json
uv run --locked python scripts/explore_pm_questions.py --cases docs/research/PM_EXPLORATION_2026-10-15_CONTROLS.json --output artifacts/pm-controls-repeat.json
uv run --locked python scripts/audit_pm_exploration.py artifacts/pm-repeat.json artifacts/pm-controls-repeat.json --output artifacts/pm-audit.json
uv run --locked python scripts/demo_container.py --image hw2-research:pm-fixes --pm --output artifacts/pm-container.json --browser-output artifacts/pm-browser.json
uv run --locked python scripts/verify_quant_container.py --image hw2-research:pm-fixes --output artifacts/pm-linux.json
uv run --locked python scripts/quant.py replay BUNDLE_ID
```

- Native exploration defaults to `http://127.0.0.1:8086`; `--url` selects another server. Questions are independent and generation varies between runs. Replay uses frozen inputs and user assumptions without model generation.
