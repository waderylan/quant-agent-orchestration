# M12 — Experience and evaluation

Owner: Rylan Wade. This milestone makes the full browser workflow easy to inspect and produces a reproducible local evaluation report over a fixed, source-reviewed question set. The [milestone index](../README.md) owns status and order.

## Inputs and boundaries

- Start from the five-worker graph, actual MCP paths, two-provider routing, and the existing [PM exploration](../../research/pm-exploration/README.md). Use exploratory failures to design cases, but keep a held-out set separate from cases used to tune prompts or routing.
- The [assignment](../../reference/assignment/Assignment_2_Description.md) requires RAGAS faithfulness, answer relevance, context precision, and context recall. The [evaluation page](../../evaluation.md) is the reporting home. M13 adds deployed cold/warm, cost, and provider results.
- Maintain separate labels for deterministic fixtures, direct worker runs, full local application/browser runs, actual MCP/provider calls, and later Cloud Run runs.

## Work to implement

- Define supported task families and a versioned fixed dataset: filing explanation, cross-company comparison, exact GAAP figures, calculations, risk changes, valuation, current news, missing coverage, ambiguity, and source conflict. Review expected source passages, periods, units, formulas, and acceptable partial outcomes by hand.
- Build a repeatable evaluator command using pinned dependencies and recorded dataset/code/model versions. Verify RAGAS client and judge compatibility before scoring; never label an unavailable metric as zero or silently substitute a paid judge. Calibrate model-judged cases against reviewed good and bad answers.
- Report all four required RAGAS metrics with sample sizes and method. Separately measure claim-level citation support, financial correctness, requested-output completion, agent trajectory/delegation, shared-MCP use, prompt-injection resistance, and failure handling. Allow more than one valid tool path where the outcome is correct.
- Capture retrieval, model, and total wall time plus answer-token time to first token for local runs. Record token counts and dated price estimates for both real serving providers where exposed. Cloud cold-start and actual billing results follow in M13.
- Refine the vanilla browser to make selected scope, worker/provider route and reason, progress, citations, missing outputs, partial/gap/clarification, charts, and downloads understandable. Preserve SSE streaming, Stop/cancellation, safe text rendering, and keyboard/browser usability.

## Acceptance evidence

1. A clean checkout can run the fixed dataset and reproduce the report method. [Evaluation](../../evaluation.md) contains actual values for all four RAGAS metrics, sample sizes, evaluator/model versions, and source references; unresolved judge compatibility blocks that claim.
2. Independently checked numerical cases validate dates, definitions, units, formulas, chart/table values, and bundle replay. Human-reviewed risk/current-source cases inspect both cited text and whether it supports the claim.
3. Browser checks exercise all major completion states, long/multi-worker traces, provider routing, mobile/narrow layout, source/attachment opening, chart downloads, and Stop. Run unfamiliar questions in addition to fixed demonstrations.
4. Report concrete failure counts, latency distributions, cost assumptions, remaining limits, and the chosen release criteria. Run the full local suite and Docker application checks; store dated raw results under `evidence/`.

Choose dataset size, holdout split, judge adapter, and numerical release thresholds after a baseline run and Rylan Wade's feedback. No invented benchmark score or cloud measurement belongs in this milestone.
