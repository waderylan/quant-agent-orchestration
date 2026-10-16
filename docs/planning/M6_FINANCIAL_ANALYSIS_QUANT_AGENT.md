# M6 — Financial Analysis / Quant agent

- [Capability routing](CAPABILITY_ROUTING_AND_REVENUE_SHARES.md) specifies checked annual revenue shares, parent-earnings ranking, and filing-input handoff. [Aligned coverage](ALIGNED_FISCAL_COVERAGE.md) defines current company/year coverage. Dated M6 evidence retains its recorded sample and configuration.

- Owner: Rylan Wade.
- Status: implemented and verified locally; final Docker acceptance is recorded in the linked evidence.
- Scope: source-linked consolidated GAAP revenue/cash-flow growth, gross and operating margins, margin changes in percentage points, and compatible quarter-only derivations within the selected four-company corpus.
- Verified generation runtime: host Codex CLI 0.162.1, `gpt-6.1-sol`, subscription profile. Native, direct-role, and Docker-to-host routes remain distinct evidence paths.
- Components: `src/quant_runner.py`, `src/quant_analysis.py`, `src/quant_workflow.py`, `src/analysis_artifacts.py`, `prompts/quant.md`, and `scripts/quant.py`.

## Agent cooperation and generation

- The visible supervisor selects Research for narrative/disclosure investigations, Data for structured figures, and Data → Quant for numerical requests. Quarter-only Q2–Q4 cash-flow requests select the numerical path; explicit YTD requests retain the Data path.
- Financial Data uses its own prompt and query/inspection tools to establish source inputs. The graph passes registered observations to Quant and suppresses the intermediate Data answer from final-answer tokens. Actual assignments, tools, evidence, and the handoff remain inspectable.
- Quant has a distinct prompt and two tools: `run_analysis` and `inspect_calculation`. It generates an arithmetic Python program, executes it through the bounded interpreter, inspects its results, and streams a cited answer.
- A direct Quant CLI run supplies source-checked observations without invoking the supervisor/Data model/browser. Direct-role evidence is separate from actual graph/application/browser evidence.
- The graph has three implemented specialists: Filings Research, Financial Data, and Quant. Risk Summary and the full task-driven cooperation/follow-up/recovery design remain M7/M8 work. This increment supplies a focused Data-to-Quant dependency path.

## Execution contract

| Boundary | Enforced behavior |
| --- | --- |
| Language | Simple assignments, numbers/strings, lists/dictionaries, registered `values['F1']`, and `+ - * /`. A custom AST interpreter evaluates the subset without `eval` or `exec`. |
| Generated capabilities | No imports, calls, attributes, functions, loops, comprehensions, mutation of inputs, filesystem, shell, or network operations. No model-selected libraries. |
| Program size | 12,000 characters, 40 assignments, 1,000 AST nodes, 2,000 evaluated expression steps, nesting depth 40. |
| Numerical bounds | Decimal precision 28; finite inputs/literals/intermediates bounded to magnitude 10^18. Division by zero fails explicitly. |
| Input/output | At most 256 KiB input, 64 result rows, 1–2 declared inputs per result, and eight metric groups per chart. Result metadata must remain scalar/bounded before serialization. |
| Process | Separate Python interpreter with `-I -S -B`, temporary working directory, and a minimal environment excluding provider credentials and bridge configuration. |
| Deadline | Three seconds per execution; timeout kills/reaps the child. HTTP request ownership can also terminate an active execution child on disconnect. |
| Linux limits | Two CPU seconds, 256 MiB address space, and no regular-file output. Windows uses the deadline and language/size/operation limits; it does not claim an OS memory sandbox. |
| Attempts | At most three execution attempts; one successful analysis bundle per Quant turn. The existing eight-tool/180-second model-phase limit remains. |

- This is an intentionally restricted analysis language, not an arbitrary-Python execution service. Application-controlled Matplotlib 3.11.2 produces charts after validation; generated programs cannot import it or select plotting/file operations.
- `run_analysis` executes real generated code with runtime values. Metadata cannot supply a precomputed constant in place of source arithmetic: every numeric expression carries the exact F-source IDs it used, including through intermediate variables.

## Independent financial validation

- The application recomputes each declared result independently from its registered inputs. Declared lineage must equal executed lineage; a coincidentally correct value from different inputs is rejected.
- `value` preserves an input; `growth` uses new/old − 1; `margin` uses gross profit or operating income divided by matching revenue; `difference` preserves compatible units; `quarter` subtracts adjacent cumulative amounts.
- Monetary results require exact agreement. Percent/percentage-point results use absolute tolerance 10^-8. Full Decimal values remain in the ledger/CSV; display formatting is separate.
- Calculations require matching company, accounting/revision basis, metrics/units where appropriate, and correct interval ordering. Margins require identical numerator/denominator intervals and positive revenue. Growth requires a positive baseline and comparable non-overlapping durations.
- Known conflicting comparative revisions through the calculation's latest input filing date prevent calculation. The selected policy remains original-report values, not automatic latest-restatement substitution.
- Margin changes are percentage points. Negative operating margins remain valid. Missing values remain missing; no zero fill, denominator replacement, period relabeling, or silent annualization occurs.
- Q2 cash flow = six-month YTD − Q1 YTD; Q3 = nine-month YTD − six-month YTD; Q4 = annual − nine-month YTD. Inputs must share fiscal year/start, metric/unit, revision basis, and adjacent report periods. A six-month difference cannot be labeled a quarter.
- Q4 margins require separately derived quarter-only numerator and revenue, then division. Annual margins and YTD margins cannot be subtracted to construct Q4 margin.
- Qualcomm's 53-week FY2024 qualification propagates to affected comparisons. Cross-company arithmetic is rejected; separate company values can be presented with their actual fiscal dates.

## Artifacts and source inspection

- Only independently verified results publish. A content-addressed bundle contains the generated program, registered observations, exact calculations/formulas, flattened source lineage, chart-series values/scales, and hashes for exported files.
- Exports: `table.csv`, `chart.png`, `analysis.py`, and `bundle.json`. Matplotlib groups charts by metric/unit; USD plots explicitly use millions. Display labels are generated from validated company/period/metric metadata.
- The browser displays a result table, PNG chart, download links, `[C1]` calculation citations, and `[F1]` figure citations. Calculation inspection opens both formulas and their input evidence, including nested derived calculations.
- Saved calculation inspection uses its own frozen observations and hash-checked archived SEC snapshot links. Refreshing the active financial store cannot silently replace a saved ledger's inputs.
- `ArtifactStore` validates bundle identity and exported-file hashes on read. Unknown identifiers/filenames and modified ledgers/files fail explicitly. A bundle manifest publishes after all exports are written.
- `QUANT_ARTIFACT_DIR` defaults to ignored `artifacts/quant/`. These are local artifacts, not a promise of durable Cloud Run storage or conversation memory. Replaying uses the ledger's recorded inputs; source refresh and source verification remain separate concerns.

## Reproduce

```powershell
uv sync --locked
uv run --locked python scripts/financials.py collect
uv run --locked python scripts/quant.py agent "Calculate AMD FY2024 versus FY2025 revenue growth, gross and operating margins, margin changes in percentage points, and operating cash-flow growth, with dates and a table/chart." --company AMD --year 2024 2025
uv run --locked python scripts/quant.py inspect BUNDLE_ID
uv run --locked python scripts/quant.py replay BUNDLE_ID
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8086
```

- The direct worker prints actual tools, evidence, answer tokens, and artifact identity. `inspect` opens the ledger; `replay` re-executes the saved program and compares the independently validated ledger.
- In the browser, select AMD/FY2024/FY2025 and request the same analysis. Open a C citation, follow an input to its source snapshot, and download the CSV/PNG/code/ledger.
- For Q4, select AMD/FY2025 and ask: “Calculate Q4-only operating cash flow from compatible cumulative inputs, with exact USD and actual dates.” The expected source-backed result is USD 2,600,000,000 for September 28–December 27, 2025.

With the server running:

```powershell
uv run --locked pytest -q
uv run --locked python scripts/demo_quant.py
uv run --locked python scripts/demo_financial_edges.py --url http://127.0.0.1:8086
uv run --locked python scripts/demo_container.py --image hw2-research:m6 --analysis --output docs/research/M6_CONTAINER_RESULTS.json --browser-output docs/research/M6_CONTAINER_APPLICATION_RESULTS.json
uv run --locked python scripts/verify_quant_container.py
```

- `demo_quant.py --application-only --url URL --output PATH` checks actual application/browser behavior without repeating direct-role generation. Its deterministic failure probes execute locally and are labeled separately from provider/application results.
- All runtime dependencies are exactly pinned in `pyproject.toml`, `uv.lock`, and the exported `requirements.txt`. The container uses those same requirements.

## Verified evidence and limits

- [Native demonstration](../research/M6_DEMONSTRATION_RESULTS.json): four real direct annual Quant runs, checked against independently inspected M1 references; AMD Q2/Q3/Q4 cash-flow runs checked against the original 939/2,950/5,109/7,709 million cumulative values; actual Data → Quant streaming; calculation/input/snapshot inspection; file hashes; CSV/ledger consistency; Chromium table/chart/download behavior.
- Actual AMD quarter-only results: Q2 USD 2,011,000,000; Q3 USD 2,159,000,000; Q4 USD 2,600,000,000. Direct tests are not counted as browser/graph tests.
- Failure evidence includes actual cross-company source incompatibility, deliberately synthetic zero denominators, missing identifiers, prohibited execution, deliberately incorrect arithmetic, and an actual child deadline. Rejected attempts publish no successful bundle. Synthetic failure inputs are explicitly labeled and are not company evidence.
- All 61 focused tests pass, including interpreter/resource escape attempts, executed-lineage checks, independent arithmetic, unit/period/revision incompatibility, negative margins, quarter adjacency/Q4 margin lineage, 53-week context, ledger/export integrity, frozen inputs, graph handoff, and suppression of invalid upstream inputs. These are correctness tests, not formal model-judged scores.
- [Container evidence](../research/M6_CONTAINER_RESULTS.json) and [container application/browser evidence](../research/M6_CONTAINER_APPLICATION_RESULTS.json) cover the Linux image, its actual interpreter/plotting/export path, host authentication isolation, cited research/Data output, model rejection, and process-tree cleanup. Local resource/timing observations do not establish Cloud Run behavior or provider pricing.
- [Linux interpreter fixtures](../research/M6_LINUX_EXECUTION_RESULTS.json) separately verify arithmetic/lineage output and rejection of imports, loops, zero denominators, missing inputs, and oversized numeric values in the actual image. These six fixtures use no provider, application mount, or real company observations.
- Final-answer citation identity and verified tables do not prove every natural-language claim. Formal held-out datasets, RAGAS/trajectory evaluation, model-judge calibration, deployment-provider comparisons, and Cloud Run remain pending. The formal-evaluation checkpoint requires Rylan Wade's feedback on the working research/numerical workflow.
