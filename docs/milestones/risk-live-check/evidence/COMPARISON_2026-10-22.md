# Tavily sharing comparison — 2026-10-22

Owner: Rylan Wade. This is local engineering evidence for M12, separate from formal RAGAS and Cloud Run evaluation.

## Decision supported by the evidence

Keep both capabilities available for selection. Risk Summary adds useful, specific follow-up to a disclosure comparison; Filings Research checks whether an official source updates a particular filed statement. These are different user needs. Current Developments remains the broader news/reaction specialist in either configuration.

Risk provides the more automatic demonstration: every registered finding receives a search without requiring a separate news request. Research earns its place through source authority and narrow verification, including single-year questions that do not need a risk comparison. Keeping Research adds no search to an ordinary request that does not ask for an official update.

The evidence supports useful Risk supplementation. It does **not** establish that searching every registered wording change improves overall answer quality. Several checks return overlapping or weakly useful context. Both capabilities remain implemented; Rylan Wade makes the final selection.

## Method and boundaries

- An independent agent, initially given project coverage rather than implementation, authors six questions and source/usefulness rubrics. Dataset preflight corrects its year-field name and an unsupported three-year selection before any successful acquisition. The final six questions remain unchanged during the comparison.
- Each question runs once with `RISK_LIVE_CHECK=off` (Research baseline) and once with `on` (both additional uses). Current Developments and the existing Research capability remain enabled in both. There is no Risk-only control.
- All six baseline captures precede all six Risk-enabled captures. Generation uses local Codex `gpt-6.1-sol`; retrieval uses actual Tavily Remote MCP. The runtime source hashes remain unchanged throughout these twelve captures. Source and dataset hashes are retained in the JSON evidence.
- A separate agent reviews every requested output and material claim against actual returned text. Four dimensions score 0–2: coverage, synthesis, provenance and honest limits. A useful partial answer can pass; a terminal `completed` label does not establish substantive completeness. The reviewer can see tool identities and is independent, not blinded to configuration.
- All 181 displayed-source inspections return HTTP 200. All 27 reviewed W-text hashes match. These checks establish provenance, not the truth of every external report.
- Results are one stochastic pair per question. They are neither general accuracy estimates nor causal latency/quality effects. Model planning, selected S passages and broader Current searches can differ between variants.

## Measured results

| Measure | Research baseline | Both uses |
| --- | ---: | ---: |
| Captured requests | 6 | 6 |
| Independently useful | 5/6 | 6/6 |
| Critical workflow failures | 1 | 0 |
| Total rubric points | 41/48 | 41/48 |
| Completed / partial / clarification | 2 / 3 / 1 | 2 / 4 / 0 |
| Total Tavily tool invocations | 14 | 23 |
| Estimated uncached credits | 28 | 46 |
| Median total seconds | 78.747 | 93.970 |
| Mean total seconds | 128.144 | 133.717 |
| Median first answer-token seconds | 56.264 | 65.078 |
| Total latency range, seconds | 52.745–249.357 | 46.047–270.296 |

The 18-credit batch difference is not simply the cost of Risk. Risk itself accounts for 11 searches and 22 estimated credits; Current calls change from 12 to nine, and Research calls from two to three. Estimates assign two credits to each uncached attempted tool, including failed attempts; they are not verified account billing. The final comparison uses request traces, not shared-ledger deltas that were contaminated by concurrent development runs.

Risk registers 16 findings in the enabled batch. Five checks are suppressed by the explicit no-web control; all 11 enabled registered findings receive a search. Searches trigger in three of six requests. The AMD risk question instead encounters a planner failure and falls back to Research, so its zero Risk calls are not a legitimate no-web suppression or evidence of Risk effectiveness.

First-answer-token time measures answer prose, not early routing/activity events. These are local application times, including orchestration and transport; there is no Cloud Run cold/warm claim. The differing number of Risk worker invocations also prevents interpreting their pooled medians as a matched marginal cost.

## Paired findings

| Case | Baseline / both score | Useful incremental information and limits |
| --- | --- | --- |
| NVIDIA no-web risk continuity | 8 / 8 | Both produce useful S-grounded comparisons; no web calls occur. Different prose is not a Risk web benefit. |
| AMD manufacturing/export risk | 8 / 7 | The enabled run falls back to Research-only after planning failure. Its net-charge detail comes from S passages, not W acquisition. This pair does not exercise the treatment. |
| AMD official amendment check | 7 / 7 | Both preserve the historical correction and make one official-check search, but results concern other issuers. Neither establishes a subsequent official update. |
| Qualcomm customer/modem update | 5 / 7 | Baseline unnecessarily asks which outlook is meant and performs no search. Both adds attributed Apple deployment and Samsung sampling reports, then performs the official search. Official revision remains unverified. Routing and synthesis differences prevent attributing the whole gain to Risk alone. |
| NVIDIA full workflow | 6 / 6 | Risk adds March approval/order reporting and June licensing-guidance context. Research supplies a useful official quarterly update in both. They overlap on one document identity; exact publication dating remains missing. Both variants omit requested net income. |
| Intel full workflow | 7 / 6 | Risk adds a report on continued 14A development and customer discussions. Construction/financing context overlaps Current. Six Risk searches produce only two surviving contextual claims. The enabled answer loses a driver limitation during repair and overstates completion. |

Research's narrow official-update capability is useful even when no positive update is established, provided the answer distinguishes an unsuccessful search from confirmation that nothing changed. A failed check must not be disguised as a provider failure when no call occurred.

Risk's strongest contribution is a dated connection between a known exposure and subsequent evidence. It should distinguish realization, continued exposure, mitigation and future plans. It cannot use a later publication date to relabel an earlier event as post-filing, or use W evidence to change the original S-cited classification.

## Improvements made during evaluation

1. **Preserve evidence for review.** Initial complete risk citations were truncated to their first 12,000 characters, causing supported late-section findings to be removed. Review now receives complete risk-section text and filing/fiscal metadata. Subject-filtered alignment navigation supplies focused exact paragraph IDs without treating similarity as classification.
2. **Acquire dated, focused context.** Initial general-topic Risk searches frequently returned undated snippets. Short per-risk news queries supply usable publication metadata on the development cases. Explicit official SEC-filing title dates also retain their provenance; URL dates and ordinary headline event dates remain insufficient.
3. **Preserve honest search outcomes.** Application-supplied acquisition records let review distinguish no dated evidence, skipped checks and unavailable acquisition. A bounded no-finding statement does not require inventing a W citation or imply proof of absence.
4. **Resolve ownership contradictions.** Research prompts and handoffs formerly told the worker to leave live outputs elsewhere, even though no other worker owned its official check. Prompts and hosted assigned-output instructions now give it that responsibility in the same invocation.
5. **Avoid unnecessary overlap.** Focused materialization questions stay with Risk when automatic checks are enabled. Broad news/reactions remain separate outputs; the disabled comparison profile preserves explicitly requested materialization through Current.
6. **Expose the integration.** Agent details show `tavily-mcp · tavily_search` for each caller. The new risk example preserves selected companies/years. Chromium replay of the captured full workflow verifies all three callers and S/F/C/W inspection with no page errors.
7. **Separate filing and period dates.** A later hosted check uses Qualcomm's fiscal year-end as a filing date despite the correct acquisition window. The final implementation supplies `filed` and `fiscal_end` explicitly in risk context/check results. Targeted post-comparison native and hosted validation is recorded separately; it does not replace the twelve original captures.
8. **Tighten interpretation checks.** Independent hosted audits identify a pre-existing exposure described as new, an analyst forecast attributed to management, unsupported Apple-specific causality for an aggregate revenue decline, and concentration trends inferred from unlike cohorts. Risk and review prompts now require checking the complete older subject inventory, preserving forecast speakers, comparing matching cohorts and verifying direct same-period causal support. These rules reduce particular failures; prompt changes alone do not establish universal enforcement.

## Final targeted verification

The final implementation passes 330 regression tests in 43.38 seconds. Two fresh local Codex risk questions complete after the date-metadata fix, using five actual Risk searches and ten estimated Tavily credits. They are targeted validation, not another paired quality estimate. The corrected hosted Qualcomm response explicitly distinguishes FY2025's September 28 period-end from its November 5 filing date and starts follow-up on November 6.

Four hosted requests cover Risk, all five workers together, a narrow financial lookup and the corrected date case. They exercise actual Nebius DeepSeek and NVIDIA Super generation. Three finish completed and the full workflow remains partial for omitted requested net income. Recorded token-based generation cost totals **$0.21795298** across these four requests; this is an estimate from reported usage and configured model prices, not verified billing. These requests use 16 estimated Tavily credits. Hosted narrative concerns remain separately audited: successful routing, search and source inspection are not proof of faithful interpretation.

Three subsequent hosted requests validate semantic refinements. Across **all seven hosted requests**, five finish completed and two partial; recorded generation cost is **$0.48995968**, with **36 estimated Tavily credits**. These are repeated development/compatibility checks, not seven independent test questions. The rerun full NVIDIA answer includes requested net income and compares the largest direct customer across matching annual periods, but still lacks filing-driver coverage and retains unverified-source markers. The intermediate Qualcomm rerun still misrepresents an older warning and invents a causal link; those failures remain in [the semantic audit](SEMANTIC_REVIEW_2026-10-22.json).

Two further Codex captures reuse the Qualcomm chronology question after successive prompt revisions, taking 73.187 seconds (partial) and 78.130 seconds (completed), each with two Risk searches and four estimated credits. They are regression checks, not fresh holdout cases. The final hosted Qualcomm check takes 71.874 seconds and makes two Risk searches. The [final audit](FINAL_REVIEW_2026-10-22.json) owns claim-level acceptance; the [original hosted audit](HOSTED_REVIEW_2026-10-22.json) and [fresh date audit](DATE_REVIEW_2026-10-22.json) preserve earlier findings. No later score replaces the original 41/48 paired results.

The final independent audit identifies no material retained error in the native Qualcomm answer and no critical failure in either final targeted answer. The hosted answer fixes the earlier exposure, date, speaker and causality errors, but still calls qualitative impact language “directly quantified,” a moderate wording defect. All 16 final source inspections return 200 and all eight checked W-text hashes match. This focused pass does not clear the earlier full-NVIDIA coverage, dating and malformed-citation limitations.

Tavily skill guidance informs short per-subject queries, advanced discovery, explicit date bounds, source/date post-filtering and independent interpretation checks. The assignment's Remote MCP integration remains in place; unsupported optional SDK fields are not forced into the discovered MCP schema.

## Remaining limits and follow-up

- The comparison has no Risk-only control and does not measure an ordinary-user query distribution. Trigger counts describe these six cases.
- Broad Current coverage can overlap Risk; six searches for six wording findings do not necessarily yield six useful additions.
- Planning failure can prevent Risk selection. One official baseline check asks unnecessary clarification. Fixed per-request search budgets can leave a valid official update undiscovered.
- Full workflows still omit some requested financial outputs, lack some exact publication dates, and can retain citation remnants after repair. Intel's enabled completion label overstates explanation coverage. These are recorded failures/limitations, not erased reruns.
- Hosted transport/tool compatibility is separate from semantic faithfulness. Targeted checks and any remaining hosted interpretation errors belong in their own evidence; they do not establish general provider quality.
- Formal RAGAS evaluates static filing retrieval with web disabled. It can proceed independently on its own branch; these usefulness scores are not RAGAS metrics.

The [milestone record](../README.md) owns current behavior and runnable commands. The dated JSON files retain per-case answers, source identities, trace attribution, score rationale and runtime hashes.
