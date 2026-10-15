# M5 — Financial Data agent

- Owner: Rylan Wade.
- Status: implemented and verified locally. Financial Data is a distinct specialist with its own prompt, structured-query tools, direct Codex entry point, and graph node.
- Scope: the 32 original reports for NVIDIA FY2025–2026 and AMD/Intel/Qualcomm FY2024–2025. Earnings releases and AMD's MD&A amendment do not supply replacement financial statements.

## Observations and selection policy

- `src/financial_data.py` collects four SEC Company Facts snapshots using the existing identified, sequential, bounded-retry collector. The [SEC API contract](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) describes entity-wide standard-taxonomy observations; the implementation selects explicit company fiscal intervals instead of calendar frames.
- Snapshots are content-addressed and retain URL, retrieval time, hash, and company identity. A complete four-company preparation publishes atomically; refresh preserves raw versions and run manifests. Chat requests read local data and make no SEC downloads.
- Every selected value matches the original accession, filing form/date, actual start/end interval, and USD unit. Fiscal `fy`/`fp` labels in repeated comparative facts do not define the observation interval. Identical duplicates collapse; conflicting original values remain unresolved.
- Revision basis is **as originally reported**, not latest restated. Later conflicting comparative values retain their own accession/date/value and cannot replace the original silently. A future revision-selection policy requires explicit implementation and review.
- Core metrics: consolidated US GAAP revenue, gross profit, operating income/loss, and operating cash flow. Values retain integer USD precision, including losses and zero. Missing values carry a status and no numeric value.
- Qualcomm gross profit retains the revenue and cost-of-revenue observations and subtraction formula. Its FY2024 53-week qualification remains attached. Optional cost-of-revenue observations support input inspection; the unconfigured Intel tag remains a visible gap rather than an inferred zero.
- Periods: annual FY, Q1–Q3 quarter-only, and Q1–Q3 YTD. Quarter starts follow the preceding filing's actual period end. Annual/YTD/quarter observations remain separate even when Q1 intervals coincide.
- Prepared inventory: **280 slots, 250 available**. The four core metrics have 208 available slots. Sixteen Q2/Q3 quarter-only cash-flow slots are missing because filings report cumulative cash flow; compatible differences belong to Quant. Fourteen optional Intel cost-of-revenue slots are also missing. All 128 core annual/YTD slots across the 32 reports are available.
- Runtime loading rechecks inventory identity, snapshot hashes/company identity, and equality of prepared observations with reconstruction from the snapshots. Run one collector per output directory. CLI refresh/repreparation requires an application restart; no automatic freshness service is claimed.

## Worker, graph, and inspection

- `prompts/financial_data.md` supplies the role. `query_financials` returns scoped figures and gaps; `inspect_observation` exposes registered evidence. Company/year filters cannot exceed the request scope. The worker cannot call research or execution tools.
- Initial query filters identify explicitly named Q1–Q4 and quarter/YTD intent; the model can refine supported filters. Entirely missing scoped results return a coverage gap before generation. Q4-only figures need Quant derivation.
- The minimal supervisor uses a visible provisional routing rule: structured figure requests select Financial Data; explanatory/disclosure questions select Filings Research. Full task-driven multi-worker cooperation remains M8 work.
- Codex generation traces identify Financial Data separately. A completed generated answer requires actual tool use and registered `[F1]` citations. These checks establish evidence identity, not comprehensive claim-level faithfulness.
- The browser links financial citations to observation metadata, exact USD figures, dates, tags, original accessions, revision evidence, derivation inputs, collected originals, and the hash-checked collected SEC snapshot. No financial tables are scraped or generated during a chat request.
- HTTP: `/api/financial/observations/{id}` and `/api/financial/snapshots/{sha256}`. Unknown identifiers return 404. Snapshot delivery rechecks its content hash.

## Reproduce

```powershell
uv sync --locked
uv run --locked python scripts/financials.py collect
uv run --locked python scripts/financials.py status
uv run --locked python scripts/financials.py query --company QCOM --year 2024 2025
uv run --locked python scripts/financials.py query --company AMD --year 2025 --period Q2 --basis ytd
uv run --locked python scripts/financials.py agent "Show AMD FY2025 consolidated GAAP revenue and operating cash flow with exact USD figures, dates, and sources." --company AMD --year 2025
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8085
```

With the server running:

```powershell
uv run --locked pytest -q
uv run --locked python scripts/demo_financials.py
uv run --locked python scripts/demo_financial_edges.py
uv run --locked python scripts/demo_container.py --image hw2-research:m5 --output docs/research/M5_CONTAINER_RESULTS.json --browser-output docs/research/M5_CONTAINER_BROWSER_RESULTS.json
```

- Refresh with `financials.py collect --refresh`; cached collection rechecks existing hashes and prepares offline from the saved snapshots. `inspect OBSERVATION_ID` opens provenance in the terminal. `--data PATH` selects a separate local store.
- `FINANCIAL_DATA_DIR` selects the application store. `data/financials/` is ignored; the Docker acceptance script mounts it read-only when present. Source code, prompts, CLI, focused checks, and compact evidence remain tracked.

## Verification and limits

- [Demonstration](../research/M5_DEMONSTRATION_RESULTS.json): 32 annual values match independently inspected M1 figures and values in collected filings; Qualcomm derived gross profit checks both original inputs. Direct Codex Financial Data runs for all four companies, sourced application output, financial citation inspection, unsupported adjusted metrics, snapshot hashes, and Chromium interaction pass.
- [Edge checks](../research/M5_EDGE_RESULTS.json) exercise honest missing quarter-only cash flow and concurrent requests with separate company/period scopes. [Docker checks](../research/M5_CONTAINER_RESULTS.json) exercise the expanded image and source-linked financial output through host subscription generation.
- All 31 focused tests pass. Financial tests protect accession/date/unit selection, duplicate/conflicting facts, fiscal interval distinctions, separate amendments, derived inputs, losses/zero/missingness, 53-week context, evidence tampering, scope isolation, unsupported bases, citation identity, and abstention before generation.
- This is a deliberate four-company mapping, not a universal XBRL resolver. Segment, adjusted/non-GAAP, net-income/EPS, foreign-form, arbitrary taxonomy, and latest-restatement selection are unsupported by the structured worker.
- [M6](M6_FINANCIAL_ANALYSIS_QUANT_AGENT.md) implements growth/margins, generated analysis code, source-linked tables/charts, and compatible quarter-only cash-flow derivation. The Data worker retains explicit raw quarter-only gaps and leaves derivation to Quant. Full supervisor cooperation, live/shared MCP, provider routing, formal evaluation, and Cloud Run remain separate milestones.
