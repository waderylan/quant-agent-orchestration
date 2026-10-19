# M6 — Financial Analysis / Quant

Owner: Rylan Wade.

Financial Data supplies scoped observations; Quant writes bounded arithmetic, executes it in an isolated child, and publishes results only after an independent financial and lineage check. Supported work includes growth, margins, percentage-point changes, compatible quarter-only differences, parent-attributable earnings rankings, Qualcomm annual revenue shares, cash conversion, and user-specified component/FX scenarios. A numerical question that also asks why passes checked values to Filings Research for a final cited explanation.

Programs allow arithmetic and assignments, with no imports, calls, loops, file access, or network. Limits include 12,000 source characters, 40 assignments, 1,000 AST nodes, 2,000 steps, depth 40, 28-digit Decimal arithmetic, magnitude below 10^18, and a three-second wall deadline. Linux also caps CPU, address space, and file output; Windows has no OS memory sandbox. USD checks are exact; percentage, percentage-point and EUR checks allow 10^-8 tolerance. The validator checks actual executed input lineage as well as period, company, units, accounting basis, and revision. Each accepted bundle freezes inputs and includes CSV, PNG, code, and a hashed ledger; replay needs no model.

Parent-attributable GAAP net income defines “earnings” for ranking. Percentage growth requires a positive base; dollar change still shows losses. A doubled revenue component holds other revenue unchanged. QCT share uses a QCT denominator; consolidated share uses consolidated revenue. Q2/Q3/Q4 cash-flow differences use adjacent compatible cumulative intervals. An explicit USD-per-EUR rate controls conversion. Missing or conflicting inputs produce a visible partial result, and ambiguity requests clarification.

## Handoffs and artifacts

- Financial Data registers source observations before Quant executes. A calculation records the exact `F` inputs actually read, its formula, assumptions, period, unit, and `C` citation. A source-correct value with false declared lineage is rejected.
- For Qualcomm annual automotive, handsets, IoT, and QCT questions, a bounded Filings Research extraction can supply original table values in USD millions. It checks table identity, row, annual column, passage overlap, and hash before Quant calculates a share. Unsupported segment/geographic substitution remains a gap.
- The browser opens a `C` calculation, its `F` source inputs, original/snapshot evidence, and the CSV/PNG/code/ledger bundle. Hashes guard saved files; `quant.py replay` re-executes frozen inputs without a model. Local bundles do not promise durable Cloud Run storage.
- A final explanation can use Research after Quant, but the checked numeric result and missing-output list remain authoritative. The outcome state distinguishes complete, partial, clarification, coverage gap, unverified, and failed.

```powershell
uv run --locked python scripts/quant.py agent "Calculate AMD FY2024 versus FY2025 revenue growth, gross and operating margins, and operating cash-flow growth with dates and a table." --company AMD --year 2024 2025
uv run --locked python scripts/quant.py replay BUNDLE_ID
uv run --locked python scripts/demo_quant.py
```

Verified milestone commit: `b62f69b`; aligned coverage/routing: `4976789`; PM workflow fixes: `b09e760`. The latest PM retest records 118 passing tests; 30 chats with 24 complete, four partial, one clarification, one coverage gap; 215 source checks, 85 calculation checks, 17 replayable bundles, eight browser checks, and six Linux fixture checks. These are exploratory results, not formal benchmark scores. [Native demonstration](evidence/M6_DEMONSTRATION_RESULTS.json), [container](evidence/M6_CONTAINER_RESULTS.json), [container application](evidence/M6_CONTAINER_APPLICATION_RESULTS.json), [Linux interpreter](evidence/M6_LINUX_EXECUTION_RESULTS.json), [aligned financial coverage](evidence/ALIGNED_FINANCIAL_COVERAGE_RESULTS.json), [capability checks](evidence/CAPABILITY_DATA_RESULTS.json), [filing inputs](evidence/CAPABILITY_FILING_RESULTS.json), [PM retest](evidence/PM_FIXES_RETEST_RESULTS.json), [PM audit](evidence/PM_FIXES_RETEST_AUDIT.json), [replay](evidence/PM_FIXES_REPLAY_RESULTS.json), and [container browser](evidence/PM_FIXES_CONTAINER_BROWSER_RESULTS.json) retain the details. All JSON files in this milestone's [evidence folder](evidence/) remain available.

Valuation is unsupported. Formal model-judged performance is M12 work.
