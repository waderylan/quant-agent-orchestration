# PM agent exploratory brief — October 15, 2026

- Owner: Rylan Wade.
- Runtime tested: `ec0a44e9a9da9f923cbd5e749707d720c1f33993`, native FastAPI/LangGraph at `http://127.0.0.1:8086`, local Codex subscription with `gpt-6.1-sol`. Corpus/index: 46 documents, 11,764 chunks; the run report preserves the active fingerprint.
- Scope: 26 original PM, arithmetic, ambiguity, and pressure-test chats; four matched wording controls. Each chat is self-contained. Two requests run concurrently; latency includes that local concurrency. Application code, prompts, corpus, and configuration are unchanged during this exploration.
- Evidence: [questions](PM_EXPLORATION_2026-10-15_CASES.json), [actual responses/traces](PM_EXPLORATION_2026-10-15_RESULTS.json), [control questions](PM_EXPLORATION_2026-10-15_CONTROLS.json), [control responses](PM_EXPLORATION_2026-10-15_CONTROL_RESULTS.json), [manual review](PM_EXPLORATION_2026-10-15_REVIEW.json), [reference inputs/arithmetic](PM_EXPLORATION_2026-10-15_REFERENCES.json), [source/artifact/calculation audit](PM_EXPLORATION_2026-10-15_AUDIT.json). Full SSE evidence is retained under each report's ignored `raw_events_path`.

## Assessment

- The eight initial PM synthesis questions all produce useful sourced answers: operating leverage, Qualcomm earnings quality, Intel turnaround, AMD pricing, NVIDIA customer concentration, Qualcomm diversification, portfolio overlap, and company-specific bear cases. Source-linked interpretation is a useful capability.
- Across 26 primary chats: 16 useful answers, four correctly handled unavailable/ambiguous requests, three incomplete numerical tasks, and three workflow failures. All four matched wording controls produce useful answers. These are explicit manual usefulness categories, not formal model-judge scores or a population reliability estimate.
- The application reports 21 `completed`, three `coverage_gap`, two `unverified`, zero `partial`, and zero `failed` primary chats. Those labels disagree with practical completeness: several completed answers explicitly lack the requested outputs. No primary or control chat times out or crashes.
- Primary end-to-end latency has a 24.368-second median, a 55.548-second maximum, and a 0.012-second minimum from immediate scope rejection. These are native subscription observations, not cloud or deployment-provider measurements.

## What works

| Cases | Observed behavior |
| --- | --- |
| P01, P03 | Distinguishes operating improvement from loss-base recovery, accounting effects, expense reductions, and supply constraints. |
| P02, P26 | Identifies Qualcomm's $5.7B noncash deferred-tax valuation allowance, contrasts earnings with cash/operating performance, and understands PM shorthand. |
| P04 | Uses AMD's amendment: Client unit shipments +15%, ASP +31%; does not mistake higher realized ASP for proven like-for-like pricing power. |
| P05 | Separates NVIDIA direct and indirect customers, overlapping exposures, revenue concentration, and contribution to growth. |
| P07, P08 | Produces specific portfolio overlaps and differentiated bear cases; does not invent measured correlations or valuations. |
| P09, P10 | Correctly changes the winner when the question changes from percentage earnings growth (AMD, +164.17%) to dollar improvement (NVIDIA, +$43.120B); includes Intel in dollar changes. |
| P12 | Derives AMD Q4 net income correctly: $4.335B annual minus $2.824B nine-month = $1.511B. Data obtains the additional inputs dynamically. |
| P15, P16 | Challenges the false universal-growth premise and does not authenticate a fabricated Qualcomm management quote. |
| P18, P21–P23 | Handles unavailable Broadcom coverage, fiscal/calendar mismatch, an ambiguous follow-up, and unavailable current valuation without inventing missing facts. |

## Failures and controls

| Case | Actual problem | Matched evidence |
| --- | --- | --- |
| P13 | Asking why quarter and YTD cash flow differ routes the entire request to Research. It misses available exact consolidated values and returns a completed answer describing missing evidence. | C01 removes only the why clause: Data/Quant returns Q2 $2.011B and YTD $2.950B. |
| P19 | “Do not include NVIDIA or Qualcomm” is interpreted as requesting those companies; valid AMD/Intel selection is rejected. | C02 removes only the exclusion sentence; the comparison succeeds. |
| P20 | “Current demand at that fiscal year-end” is rejected as live research despite explicit historical scope. | C03 removes only “current”; historical retrieval succeeds. |
| P17 | A correct refusal repeats `[S999]` to identify it as fake; the citation scanner marks the whole answer unverified. | C04 requests no repetition of the fake ID; the same substantive refusal is verified. |
| P11 | The cash-conversion ratio operation is unsupported. The answer preserves correct input amounts but supplies neither ratio. Citation ranges also fail the individual-calculation-citation check; the useful inputs lose final source cards. | Independent reference ratios: 1.85313833 in FY2024 and 1.77831603 in FY2025, a decline. |
| P24 | Scenario arithmetic is rejected. The answer explicitly states that no verified hypothetical was produced, then shows historical figures; terminal status still says completed. | Independent scenario: total $48.241B, automotive $7.914B, share 16.40513256%. |

## Correct results that still need implementation work

- P06 calculates Qualcomm diversification shares/differences in Research. P14 correctly changes the denominator to QCT revenue: $3.957B / $38.367B, approximately 10.3%. P25 correctly converts AMD's $34.639B to €31.49B using the supplied scenario FX rate. These answers are numerically correct on review, but their derived arithmetic has no checked Quant ledger. A source-reference badge does not establish calculation validation.
- P10's human-facing dollar ranking is correct, but the stored automatic assessment still ranks percentage growth and names AMD. The answer explicitly overrides that assessment. Structured results must represent the requested ordering consistently.
- P13, P18, and P24 illustrate that valid citations and completed generation do not establish that all requested outputs were supplied. The practical outcome and source-validation outcome need separate fields.
- P16 correctly rejects the supplied quotation as unverified but cannot establish its absence across the full filing in the selected Data/Research-input/Quant route. Quote investigation needs search access or an explicit handoff.

## Evidence checks and limits

- All 147 exposed source inspections match the exact passage text or stored observation/calculation value. Filing passages remain inside selected company/year scope.
- Independent Decimal arithmetic reproduces 31 published calculation rows across nine bundles, including a value-only bundle created during the unverified ratio case. Downloaded CSV, PNG, and code hashes match recorded hashes. Generated programs are not executed by this audit.
- Numerical references retain original-accession SEC observation inputs and exact fiscal intervals. Prior independent annual earnings checks are in `ALIGNED_FINANCIAL_COVERAGE_RESULTS.json`; new Decimal references establish the expected ratios and scenarios independently of model-generated programs.
- Manual review inspects substantive claims against cited passages for tax accounting, amended AMD figures, customer concentration, and bear-case disclosures. This is not exhaustive claim-level faithfulness scoring. Source identity checks alone cannot validate interpretation.
- No runtime fixes, new application capabilities, formal RAGAS/AgentEvals, paid providers, Docker acceptance, or deployment are part of this run. The test scripts and records support implementation decisions; M7–M12 remain unstarted.

## Recommended implementation order

1. Correct intent/scope parsing: negation, historical temporal language, and mixed calculation/explanation requests.
2. Track requested outputs explicitly; preserve missing items as partial and expose useful source inputs even when a calculation is unavailable.
3. Pass derived Research arithmetic through checked calculations. Add bounded general ratios, alternative denominators, and scenario assumptions as deliberate capability increments.
4. Distinguish asserted citations from quoted/refuted IDs; support citation ranges or normalize them to individual references.
5. Align structured rankings with the requested ordering; use these cases as development regressions and reserve new questions for future generalization checks.

## Reproduce

```powershell
uv run --locked python scripts/explore_pm_questions.py --output artifacts/pm-exploration-repeat.json
uv run --locked python scripts/explore_pm_questions.py --cases docs/research/PM_EXPLORATION_2026-10-15_CONTROLS.json --output artifacts/pm-controls-repeat.json
uv run --locked python scripts/audit_pm_exploration.py artifacts/pm-exploration-repeat.json artifacts/pm-controls-repeat.json --output artifacts/pm-audit-repeat.json
```

- Default address: `http://127.0.0.1:8086`; `--url` selects another local address. `--ids` selects specific cases; `--concurrency 1` runs sequentially. Repeated generation can differ, so compare actual responses and outcomes rather than assuming this exploratory sample establishes stable rates.
