# M12 — Risk Summary live check: implement and compare

Owner: Rylan Wade. The [milestone index](../README.md) owns status and order. Both additional Tavily uses remain available until Rylan Wade selects Research, Risk Summary, or both.

The [dated comparison](evidence/COMPARISON_2026-10-22.md) explains user value, paired outcomes, overhead, refinements and limits. [Application evidence](evidence/APPLICATION_2026-10-22.json) and [independent review](evidence/REVIEW_2026-10-22.json) retain the original twelve frozen captures. [Hosted checks](evidence/HOSTED_2026-10-22.json), [browser replay](evidence/BROWSER_2026-10-22.json), [development review](evidence/DEVELOPMENT_2026-10-22.json) and [post-comparison date validation](evidence/DATE_VALIDATION_2026-10-22.json) remain distinct.

## Outcome

Risk Summary automatically checks every registered risk finding for post-filing context through the same Tavily Remote MCP `tavily_search` tool as Current Developments and Filings Research. This includes added, changed, removed, relocated and unchanged wording. Stable disclosure can describe an exposure that later occurs. A risk request needs no separate live-news clause to trigger the check. No-web/filings-only requests suppress it.

## Dependencies

- M13's formal RAGAS set evaluates filing retrieval with web disabled and does not depend on which additional Tavily use is selected. This milestone compares the two live uses only.
- M7 risk classifications, M10 shared Tavily gateway and ledger, and M11 routing.
- Local Codex supplies development generation; real Tavily still consumes account credits. Hosted compatibility checks are separate evidence.

## Scope

- `record_risk_change` validates the original S-cited classification first, then performs one advanced news search per distinct finding. Distinct subject rationales sharing complete-section endpoints each receive a check; exact duplicate registration cannot retry it. Existing worker/tool/time limits bound the brief; there is no spend stop.
- The model supplies a short subject/event query. The application supplies the company and the interval from the newer source's actual filing date plus one day through today. Fiscal year-end and unrelated latest inventory dates do not replace the filing date.
- Separate W evidence retains publication basis, publisher, tier, snapshot and hash. Only dated in-window candidates enter the risk follow-up. Publication after filing does not prove the event occurred after filing; reported events, ongoing exposure, mitigation and realized consequences remain distinct. W never changes the filed classification.
- Empty/undated results produce an honest bounded no-finding statement. Acquisition failures preserve filing comparisons and retain an explicit live gap. Neither implies the risk did not occur.
- The shared gateway, credential, ledger, scrubber, source inspector and `live_mcp` trace serve all three callers. Agent activity details display the actual server/tool. The browser's “Compare risk changes” example preserves company/year selections.
- `RISK_LIVE_CHECK=on` is the default; `off` supplies the matched Research baseline. Planning preserves an explicitly requested materialization check through Current Developments when the automatic Risk check is off. Broad news/reactions remain separate outputs in either configuration.

## Comparison and handoff

- Matched cases cover risk comparisons, specific official updates and full five-agent workflows. An independent subagent authors sealed cases and reviews the resulting answers against actual returned evidence after capture.
- Capture records actual answers, trace-attributed calls, source inspections, runtime hashes, total/first-answer-token time and estimated credits. A two-credit-per-uncached-tool estimate is not an account bill. Shared ledger deltas can include concurrent runs; request traces own attribution.
- Research tests whether an official source updates a particular filed statement. Risk Summary connects each registered disclosure comparison to later dated events or continuing exposure. The comparison judges useful incremental information rather than rewarding call counts.
- Rylan Wade selects which uses to keep after reviewing the comparison. No caller is removed in this milestone.

```powershell
uv run --locked pytest -q
uv run --locked python scripts/compare_risk_live.py --variant research=http://127.0.0.1:8093 --variant both=http://127.0.0.1:8092 --output artifacts/m12/comparison.json
```

Start the two server processes with `RISK_LIVE_CHECK=off` on port 8093 and `on` on port 8092; both use `LIVE_MODE=live`. `--dataset` selects a fixed case file; `--profile api` runs hosted compatibility checks. The [root README](../../../README.md) owns setup.

## Acceptance checks

1. Frozen and development runs expose `node=live_mcp`, `agent=Risk Summary`, `server=tavily-mcp`, `tool=tavily_search`.
2. Controlled worker tests preserve identical filing classifications and S registries with checks on, off or failing. Real model runs can choose different findings; that is distinct from classification mutation by acquisition.
3. Tests cover every classification, no-web variants, exact duplicate suppression, distinct subjects, post-filing date/tier filtering, invalid registration/query rejection, failures and multi-issuer W identity. Browser regressions expose the shared tool under each agent.
4. Development captures and final comparison evidence distinguish local subscription generation, actual MCP, replay, browser and hosted-provider checks. They are not formal RAGAS or Cloud Run measurements.

## Refinements from development evaluation

- Complete risk sections no longer lose late-section evidence in Answer Reviewer truncation; fiscal and filing dates accompany them. Subject-filtered alignment navigation provides focused exact spans without treating similarity as classification.
- News-topic discovery supplies dated reporting more reliably on the development risks than general-topic discovery. Official SEC-filing titles with explicit publication labels also retain their date basis; ordinary headline/URL dates remain insufficient.
- Application acquisition outcomes allow the reviewer to preserve honest no-finding/unavailable statements without treating them as proof of absence.
- Research prompts, handoff notes and hosted role instructions agree that the enabled official-update check belongs to the same Research invocation. It is not delegated to a nonexistent second worker.
- Narrow risk-materialization questions avoid duplicate broad research; independently requested news still runs through Current Developments.
- Hosted validation exposes fiscal-end/filing-date confusion. Explicit `filed` and `fiscal_end` metadata now enter the model context and each check result, alongside a prompt rule separating them. The original matched comparison predates this correction; fresh native/hosted validation is separate evidence.
- Independent semantic audits also test old-warning continuity, forecast attribution, causal support and matching concentration cohorts. Refined prompts require these checks; dated audits preserve remaining failures separately from transport success and the original comparison scores.
