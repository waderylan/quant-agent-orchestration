# M5 — Financial Data

Owner: Rylan Wade.

Four content-addressed SEC Company Facts snapshots supply exact original-accession consolidated US GAAP USD observations. Each value keeps its filing, form, version, unit, and actual interval. Annual, quarter-only, and year-to-date values remain distinct; fiscal `fy`/`fp` labels alone do not select an interval. Duplicate facts collapse; conflicting originals remain explicit. Qualcomm gross profit retains revenue and cost inputs.

The worker has scoped `query_financials` and `inspect_observation` tools, direct CLI access, and browser `F` citations to values and hash-checked snapshots. The current store has 378 slots: 346 available, 32 explicit gaps (18 Q2/Q3 quarter-only cash-flow slots and 14 Intel cost-of-revenue slots). Quarter-only cash flow can be calculated by Quant from compatible cumulative inputs.

## Selection and source contract

- Query by company, fiscal year, metric, period, and annual/quarter/YTD basis. Only facts from the selected original report accession and matching USD interval qualify. Later comparative revisions remain inspectable, but do not replace the original-report basis.
- Parent-attributable GAAP net income is queryable for earnings comparisons; it is distinct from generic `ProfitLoss`. Losses and zeros remain values. An absent figure is a named gap, never zero-filled.
- The four core metrics are revenue, gross profit, operating income/loss, and operating cash flow. Optional cost-of-revenue and parent-income inputs support derivations and earnings. The mapping is scoped to these companies and known tags, not arbitrary taxonomies or adjusted metrics.
- Prepared data publishes as a complete local snapshot. Runtime loading rechecks inventory, source hashes, and reconstructed observations. Chat requests do not download SEC data; explicit refresh needs an application restart.

```powershell
uv run --locked python scripts/financials.py collect
uv run --locked python scripts/financials.py query --company AMD --year 2025 --period Q2 --basis ytd
uv run --locked python scripts/financials.py agent "Show AMD FY2025 consolidated GAAP revenue and operating cash flow with exact USD figures and sources." --company AMD --year 2025
uv run --locked python scripts/demo_financials.py
```

`financials.py collect --refresh` explicitly updates snapshots. Verified milestone commit: `a81dcfb`. The milestone run has 31 passing tests, 32 checked annual references, four direct workers, application/browser checks, and Docker checks. [Demonstration](evidence/M5_DEMONSTRATION_RESULTS.json), [edge cases](evidence/M5_EDGE_RESULTS.json), [container](evidence/M5_CONTAINER_RESULTS.json), and [container browser](evidence/M5_CONTAINER_BROWSER_RESULTS.json) retain the results.

When adding a metric or fiscal window, check the original accession, exact interval, units, derived inputs, revision conflicts, citation inspection, and one honest missing case. Keep quarterly and cumulative cash flow separate.
