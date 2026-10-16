# Capability routing, filing revenue shares, and earnings comparisons

- [PM workflow contracts](PM_WORKFLOW_CORRECTNESS.md) specify multi-component/QCT arithmetic, numerical-plus-explanation routing, dollar versus percentage ordering, explicit scenarios/FX, citation normalization, and partial/clarification results.

- Owner: Rylan Wade.
- Implemented scope: capability-constrained request planning, a bounded Data → Research → Quant handoff for supported annual revenue components, explicit missing-input follow-up, selected-company correction, and source-checked earnings ranking.
- [Aligned coverage](ALIGNED_FISCAL_COVERAGE.md) defines the company/fiscal windows and verified original-source net-income values. Fiscal labels identify company years; they do not align reporting dates across companies.
- This workflow does not implement M7 Risk Summary or M8's general task planner, arbitrary multi-worker investigation, or recovery loop. Live research, shared MCP, deployment-provider routing, formal evaluation, and cloud deployment remain pending.

## Request routing and evidence gaps

- `src/request_routing.py` describes supported metric aliases and request plans. Ordinary consolidated figures use Financial Data; supported arithmetic uses Data then Quant. Filing-only business, geography, adjusted-metric, and narrative requests use Research instead of treating a recognized word such as revenue as proof that the entire request fits the structured schema.
- These are inspectable deterministic capability rules, not a model-based intent planner. Unknown wording can still need refinement; tested cases and remaining limits are explicit.
- Earnings/net income selects `net_income`, defined as consolidated GAAP income/loss attributable to the parent. EPS, EBITDA, adjusted earnings, and broader `ProfitLoss` are distinct concepts.
- Financial Data returns structured `needs_evidence` when no compatible observation is available or a supported revenue component requires filing evidence. The supervisor makes one bounded Research follow-up. It does not infer absence from a failed structured lookup or retry indefinitely.
- A Research fallback without independently verified numerical inputs remains a partial answer. No successful Quant bundle is produced from guessed values. Citation-reference checks establish registered evidence identity, not complete semantic correctness.

## Annual revenue components

- Supported numerical components: Qualcomm QCT automotive, handsets, and IoT in original annual FY2024/FY2025 10-K revenue-stream tables. This is a revenue disaggregation, not a promise of arbitrary segment metrics or quarterly component analysis.
- Financial Data supplies annual consolidated revenue. Research retrieves scoped original filing passages and calls `extract_revenue_component(source_id)`; the model supplies no value, scale, fiscal column, or metadata.
- `src/filing_financials.py` independently reads the hash-checked prepared original, requires the QCT revenue title, explicit millions scale, unique annual year headers, requested row, matching number of columns, and overlap with the registered source passage. Wrapped PDF titles and scale words retain their original evidence. Repeated quarter headers, ambiguous/duplicate tables, wrong scale, and unrelated passages fail.
- An observation records the original accession, fiscal dates, USD value, component and parent definition, exact table excerpt, original-text hash, source offsets/page, annual column labels, row values, and scale. Numeric amounts are extracted from source; they are not constants in the application.
- The input-acquisition phase ends when every requested company/year/component has an independently verified row, including QCT total when requested. Its unused model summary is not a dependency; closing the stream reaps its owned child before Quant begins. Genuine unfinished model phases retain the 180-second deadline and an explicit timeout/retry message.
- Quant's `share` operation requires the component and requested consolidated or QCT denominator from the same original filing, company, fiscal interval, revision/accounting basis, and USD unit. The denominator must be positive and the component between zero and total. Decimal arithmetic and executed-source lineage are independently recomputed.
- Requests such as “How much of Qualcomm's revenue in FY2025 was from automotive?” return both the amount and percentage. A plain component-amount request can return a checked value without claiming a percentage was requested.
- Saved ledgers freeze filing-table evidence alongside SEC observations. Component citations open the saved observation, its table evidence, and the original retrieved passage; SEC snapshot links apply only to SEC-fact inputs. CSV/PNG/code/ledger exports retain existing hash checks and replay behavior.

## Earnings ranking

- “Which company had the largest earnings growth from 24 to 25?” means percentage growth in parent-attributable GAAP net income over the selected company fiscal years. The trace records this interpretation; it is not a calendar-year or EPS comparison.
- Each selected company needs both annual observations. Quant generates within-company arithmetic; the application independently checks every eligible growth row before sorting the results. It records the ranking, tied winners, definition, and exclusions in the hashed bundle assessment.
- A zero/loss baseline is excluded from conventional percentage growth. Both reported values must remain in the ledger. Negative current income with a positive baseline remains valid negative growth. No absolute-loss denominator or zero substitution is permitted.
- Independent original-source references give AMD the largest eligible percentage increase, approximately 164.1682%. NVIDIA has the largest dollar increase, USD 43.120 billion, a different comparison. Intel starts from a FY2024 loss; Qualcomm's parent net income declines. Fiscal dates and Qualcomm's 53/52-week qualification remain visible.

## Scope selection and browser

- Company/year selectors remain authoritative. A question naming Qualcomm while AMD is selected returns both selected and requested company names; it does not silently broaden the request.
- The browser displays the selected companies/years and offers an explicit “Select Qualcomm” correction. The action retains selected years that are supported by the new company. Submission is a separate user action.
- For multiple companies, the fiscal-year selector lists their common supported years. NVIDIA-only selection also offers FY2026; a four-company selection offers FY2024/FY2025. Selecting common labels does not synchronize actual fiscal dates.
- Source status says “source references checked.” Partial answers display an evidence-gap status rather than implying that every requested calculation succeeded.

## Reproduce and inspect

```powershell
uv sync --locked
uv run --locked python scripts/collect_sources.py collect
uv run --locked python scripts/financials.py collect
uv run --locked python scripts/research.py ingest
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8086
uv run --locked pytest -q
uv run --locked python scripts/demo_capability_fixes.py --phase data --output docs/research/CAPABILITY_DATA_RESULTS.json
uv run --locked python scripts/demo_capability_fixes.py --phase filings --output docs/research/CAPABILITY_FILING_RESULTS.json
uv run --locked python scripts/demo_capability_fixes.py --phase browser --output docs/research/CAPABILITY_BROWSER_RESULTS.json
```

- Actual Data/application cases, actual filing/Quant cases, Chromium behavior, deterministic rejection fixtures, and formal model evaluation are separate evidence paths. Evidence files contain actual answers, scoped worker calls, verified calculations, source references, bundle identities, and local timing; they do not establish deployment-provider performance.
- [Data/application evidence](../research/CAPABILITY_DATA_RESULTS.json) records the exact selected-company mismatch, corrected two-year question, NVIDIA FY2024 net income, and the four-company earnings question. [Filing evidence](../research/CAPABILITY_FILING_RESULTS.json) records automotive FY2025/FY2024, IoT share, and handsets amount, checked against independently inspected original table values. [Chromium evidence](../research/CAPABILITY_BROWSER_RESULTS.json) records scope correction, retained/common years, actual automotive analysis, chart loading, frozen input inspection, and four-company earnings ranking.
- Focused tests protect table/column/scale ambiguity, incorrect definitions/denominators, company/period/revision/lineage mismatches, zero/loss baselines, missing structured inputs, presentation units, bounded graph handoffs, and useful timeout messages. They are deterministic correctness checks, not formal model-quality scores; current suite results are recorded in the PM workflow evidence.
- [Docker acceptance](../research/CAPABILITY_CONTAINER_RESULTS.json) and [Docker Chromium evidence](../research/CAPABILITY_CONTAINER_BROWSER_RESULTS.json) verify cited Research/Data output, component extraction and Quant arithmetic, earnings ranking, source inspection, credential isolation, model rejection, and request cleanup. The harness chooses its isolated writable index by corpus fingerprint, so a cached index from another corpus cannot stand in for the current collection. Resource snapshots follow the Research/Data checks and are not peak Quant memory measurements.
- [Quarter/YTD edge evidence](../research/CAPABILITY_FINANCIAL_EDGE_RESULTS.json) verifies explicit missing-input results without Data generation and concurrent request-local period/company isolation. Final-image Linux routing fixtures also verify quarter-only USD presentation and the annual automotive-share plan. Saved native automotive and earnings programs replay successfully against their frozen inputs.
