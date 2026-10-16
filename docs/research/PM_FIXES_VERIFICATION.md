# PM workflow verification — October 15, 2026

- Owner: Rylan Wade.
- Scope: fixes and checked arithmetic extensions for the 26-question [PM exploration](PM_EXPLORATION_2026-10-15.md) and four wording controls. This is local development verification, not a held-out benchmark, exhaustive semantic evaluation, or deployment acceptance.
- Runtime: native FastAPI/LangGraph, local Codex subscription, `gpt-6.1-sol`; two concurrent chats. Corpus: 46 documents and 11,764 chunks. The [final report](PM_FIXES_RETEST_RESULTS.json) records exact runtime file hashes because generation ran against uncommitted fixes on baseline revision `ec0a44e9a9da9f923cbd5e749707d720c1f33993`.
- Implemented contracts and reproduction commands: [PM workflow correctness](../planning/PM_WORKFLOW_CORRECTNESS.md).

## Observed results

- All 30 questions were rerun through the actual application: 24 completed, four partial, one clarification, and one live-data coverage gap. No transport errors, failed/unverified outcomes, unknown final citation IDs, or model timeouts occurred in this final run.
- The four partial answers identify specific evidence gaps: NVIDIA customer-level incremental growth attribution, authentication of the supplied Qualcomm quote, missing Broadcom coverage, and unavailable exact calendar-year boundaries. They preserve available sourced findings. Clarification asks for the absent company/metric referent. Live valuation remains unsupported.
- [Independent audit](PM_FIXES_RETEST_AUDIT.json): 215 exposed source inspections match; 85 calculations in 17 bundles recompute correctly; downloadable code/CSV/PNG hashes match. Zero mismatches. [Replay](PM_FIXES_REPLAY_RESULTS.json) executes all 17 saved programs against frozen inputs and approved assumptions and reproduces all 85 ledger rows.
- Automated suite: `uv run --locked pytest -q` — 118 passed in 64.73 seconds during concurrent local verification. Ruff F checks, `git diff --check`, and `uv lock --check` pass. No dependencies changed.
- [Docker acceptance](PM_FIXES_CONTAINER_RESULTS.json): actual Research and Data turns, non-root identity, custom PORT, absent CLI/auth stores inside the image, unavailable-model errors, and disconnect cleanup pass. Fresh startup was 4.988 seconds; cleanup took 0.652 seconds. Resource observations are a post-Research/Data snapshot, not peak analysis memory.
- [Chromium](PM_FIXES_CONTAINER_BROWSER_RESULTS.json): eight actual chats pass for ratios, mixed quarter/YTD explanation, hypothetical component revenue, assumed FX, fabricated citation refusal, visible partial outputs, excluded-company scope, and citation-free clarification. Calculation ledgers, input inspection, assumption metadata, charts, and downloads are checked where applicable.
- [Linux interpreter fixtures](PM_FIXES_LINUX_RESULTS.json): six checks pass, independently of provider/application generation: valid arithmetic and rejection of imports, loops, zero denominators, missing identifiers, and oversized numbers.
- Final native latency across all 30 chats: median 38.978 seconds, maximum 118.773 seconds. Additional Data/Quant/Research phases increase latency for mixed requests; this is a correctness tradeoff, not evidence of cloud or paid-provider performance. The baseline primary-only sample has a different case denominator and is not a controlled latency benchmark.

## Question-by-question review

- Exact questions, original answers, and final answers are preserved in the linked baseline/control reports and final report. Each result below was reviewed for the requested outcome and material numerical/source distinctions. Source identity auditing is separate from narrative review.

| Case | Requested outcome | Final reviewed result |
| --- | --- | --- |
| P01 | Operating leverage across all four | Checked growth/margins plus filing explanation; NVIDIA leads eligible percentage growth; Intel loss recovery is separate. |
| P02 | Qualcomm earnings quality | Checked earnings/OCF comparison and ratios; $5.7B deferred-tax charge distinguished from demand and current cash taxes. |
| P03 | Intel turnaround | Demand, cost savings, lower charges, transaction gains, wafer constraints, and foundry losses remain distinct. |
| P04 | AMD pricing versus units | Uses corrected 10-K/A: ASP +31%, units +15%; mix is not proven like-for-like pricing power. |
| P05 | NVIDIA growth/customer dependence | Useful partial: direct/indirect concentration and overlap explained; undisclosed growth attribution is not invented. |
| P06 | Qualcomm diversification | Checked component growth and mix across both years; licensing exposure qualifies the handset concentration interpretation. |
| P07 | Portfolio risk overlap | Specific common demand/customer/foundry/geographic channels; interpretation is separated from disclosure. |
| P08 | Company-specific bear cases | Four concrete filing facts and decision-relevant unanswered questions; no generic valuation claim. |
| P09 | Percentage earnings ranking | AMD +164.1682%; stored assessment also uses percentage order despite requested dollar display. |
| P10 | Dollar earnings ranking | NVIDIA +$43.120B; Intel +$18.489B, AMD +$2.694B, QCOM −$4.601B; stored assessment matches. |
| P11 | Cash conversion | Checked 1.85313833× → 1.77831603×; cash conversion declines despite higher dollar cash flow. |
| P12 | Q4-only net income | Checked AMD $4.335B annual − $2.824B nine-month = $1.511B Q4. |
| P13 | Q2/YTD cash flow and why | Checked $2.011B quarter and $2.950B six months; $939M Q1 explains duration difference. |
| P14 | Automotive/QCT denominator | Checked $3.957B / $38.367B = 10.3135507%; consolidated denominator is not substituted. |
| P15 | False universal AI-growth premise | Checked Intel revenue decline; NVIDIA/AMD AI disclosures do not establish an all-four AI driver. |
| P16 | Authenticate fabricated quote | Useful partial: quote remains unauthenticated after searches; checked 8.94% automotive share contradicts “half.” |
| P17 | Fabricated citation pressure | Correct refusal and actual AMD growth; fake source mention does not invalidate valid evidence. |
| P18 | AMD versus uncovered Broadcom | Useful partial: AMD findings retained; missing Broadcom comparison and winner remain explicit. |
| P19 | Exclude NVIDIA/Qualcomm | AMD/Intel comparison completes in the selected scope; no spurious scope expansion. |
| P20 | Historically current demand | NVIDIA FY2025 year-end disclosure succeeds without claiming current market knowledge. |
| P21 | Exact calendar-year comparison | Useful partial: fiscal windows and reference totals remain explicit; no calendar substitution/proration. |
| P22 | Ambiguous follow-up | Clarification requests company and metric; no invented conversation context or citation requirement. |
| P23 | Current forward P/E | Coverage gap: live prices/forward estimates unavailable. |
| P24 | Automotive doubles scenario | Checked automotive $7.914B, total $48.241B, share 16.40513256%; user assumption retained. |
| P25 | Assumed USD/EUR | Checked $34.639B / 1.10 = EUR31.49B; explicit scenario, not reported EUR. |
| P26 | PM shorthand on QCOM taxes/EPS | Explains tax accounting versus operating improvement and persistent tax economics; concrete management questions. |
| C01 | Q2/YTD without why | Exact quarter and YTD amounts remain correct. |
| C02 | Comparison without exclusions | AMD/Intel values and loss-base treatment remain correct. |
| C03 | Demand without current | Historical disclosure remains correct. |
| C04 | Refusal without fake-ID repetition | Correct evidence-based refusal remains verified. |

## Decisions and verification limits

- Numerical/explanation routing uses inspectable capability rules and one bounded final synthesis, not a general planner. Cash conversion is a specific same-period OCF/positive-net-income ratio. Scenario recognition supports the documented doubling and USD/EUR forms, not arbitrary forecasts, shocks, or currencies.
- Explicit worker completion reporting supplements deterministic required-calculation checks. Narrative completeness still depends partly on the worker's assessment and reviewed evidence. Valid citation identifiers do not establish every claim's faithfulness.
- Model-generated explanations can vary. Regression questions were used during implementation; these results do not establish held-out generalization or formal RAGAS/AgentEvals performance.
- Intermediate verification exposed and corrected stale Quant explanation gaps surviving final Research synthesis, incidental dollar-display language changing stored percentage ordering, and valid clarification being labeled unverified. The final 30-chat run includes these corrections.
- An initial browser check depended on a specific decimal display style; the check now inspects ledger values and user assumptions. Product scenario values were correct. One Linux fixture run during concurrent verification ended with exit 137 for two processes; no cgroup OOM event was recorded in the inspected interval. The cause is not established. A separate six-case rerun passes; the interrupted fixture evidence remains in ignored local artifacts.
- M7–M12, live valuation, expanded company coverage, general risk-version comparison, formal evaluation, and cloud deployment remain unimplemented.
