# M5 — Financial Data

Four content-addressed SEC Company Facts snapshots supply exact original-accession consolidated US GAAP USD observations. Each value keeps its filing, form, version, unit, and actual interval. Annual, quarter-only, and year-to-date values remain distinct; fiscal `fy`/`fp` labels alone do not select an interval. Duplicate facts collapse; conflicting originals remain explicit. Qualcomm gross profit retains revenue and cost inputs.

The worker has scoped `query_financials` and `inspect_observation` tools, direct CLI access, and browser `F` citations to values and hash-checked snapshots. The current store has 378 slots: 346 available, 32 explicit gaps (18 Q2/Q3 quarter-only cash-flow slots and 14 Intel cost-of-revenue slots). Quarter-only cash flow can be calculated by Quant from compatible cumulative inputs.

```powershell
uv run --locked python scripts/financials.py collect
uv run --locked python scripts/financials.py query --company AMD --year 2025 --period Q2 --basis ytd
uv run --locked python scripts/financials.py agent "Show AMD FY2025 consolidated GAAP revenue and operating cash flow with exact USD figures and sources." --company AMD --year 2025
uv run --locked python scripts/demo_financials.py
```

`financials.py collect --refresh` explicitly updates snapshots. Verified milestone commit: `a81dcfb`. The milestone run has 31 passing tests, 32 checked annual references, four direct workers, application/browser checks, and Docker checks. [Demonstration](evidence/M5_DEMONSTRATION_RESULTS.json), [edge cases](evidence/M5_EDGE_RESULTS.json), [container](evidence/M5_CONTAINER_RESULTS.json), and [container browser](evidence/M5_CONTAINER_BROWSER_RESULTS.json) retain the results.
