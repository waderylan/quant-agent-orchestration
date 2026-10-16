# Evaluation

- Status: formal evaluations are **unstarted**. M3–M6 correctness, direct-role, native application/browser, and local Docker checks are separate evidence.
- Source feasibility and preparation are verified for NVIDIA, AMD, Intel, and Qualcomm. [M1 evidence](planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md) records aligned financial inputs; [M2 evidence](planning/M2_SOURCE_COLLECTION_AND_PREPARATION.md) records 41/41 bodies/extractions, section/table checks, and no collection gaps.
- Source availability checks are basic correctness evidence; they are not RAGAS scores, agent evaluations, provider comparisons, or deployed acceptance results.
- Original-document collection and readable preparation are implemented. M3 implements RAG and a local filings-research workflow. Structured observations, Financial Data, and bounded independently checked Quant analysis are implemented. Formal evaluation follows working demonstrations and Rylan Wade's feedback.

## Evaluation scope

- Supported task families, independently checked reference cases, dataset size/splits, calibration rubric, and formal thresholds remain undecided.
- Exploratory questions in the M1 document are demonstration ideas, not a fixed benchmark.
- Current company/year scope is FY2024–FY2025 for all four companies and retained NVIDIA FY2026. Financial cases must retain actual fiscal dates, units, accession/version, GAAP definitions, and required derivations. [Aligned coverage](planning/ALIGNED_FISCAL_COVERAGE.md) records current source checks.
- Qualcomm's 53-week FY2024 and derived gross profit, AMD's amended explanation, YTD cash-flow differences, and unavailable evidence are relevant correctness cases.

## Required RAGAS report

- Required metrics: faithfulness, answer relevance, context precision, and context recall.
- Fixed question set, source-checked references, executable evaluator, compatible client configuration, exact framework versions, and measured results are pending.
- Formal generation/judges use subscription-backed adapters with verified evaluator compatibility during development; the M3 application uses direct Codex. Client compatibility and judge calibration require verification.
- Separate paid judges and actual runtime-provider measurements belong to final integration.

## Financial correctness and agent behavior

- Independently checked calculations must validate input periods, units, definitions, formulas, revision basis, and table/chart consistency.
- Risk comparisons require reviewed before/after passages and classification of added, removed, changed, or relocated language.
- Agent checks must inspect delegation, evidence handoff, shared MCP calls, follow-up limits, failures, and unsupported conclusions.
- Individual-role Codex tests, fixture-based graph tests, direct Codex application/browser runs, and final provider/deployment tests are separate evidence categories.
- M3 focused correctness checks cover scope, provenance, graph streaming, and failure handling. Exploratory model-backed results are recorded in the M3 demonstration evidence; no formal scores exist.
- M3 actual evidence: [demonstration](research/M3_DEMONSTRATION_RESULTS.json), [browser](research/M3_BROWSER_RESULTS.json), [HTTP](research/M3_HTTP_RESULTS.json), [model failure](research/M3_MODEL_FAILURE_RESULTS.json), and [cancellation](research/M3_CANCELLATION_RESULTS.json). Results are 19 passing correctness tests, 4/4 company application turns, three honest coverage gaps, one direct worker run, and one Chromium citation/trace demonstration. These are exploratory acceptance checks, not a fixed benchmark or formal agent evaluation.

## Latency

- M3 demonstration reports contain local total latency and answer-token time-to-first-token observations. They are single-run exploratory samples, not a latency benchmark. Per-stage timing and broader latency acceptance remain pending.
- Cloud Run cold/warm behavior and concurrency checks are pending.
- Source-download timings or progress events do not establish application answer-token latency.

## Cost per query and provider comparison

- Runtime token use, bills, cost estimates, latency, and quality comparisons are unavailable.
- Nebius Token Factory is selected; NVIDIA-hosted NIM remains tentative. Exact models, access, pricing, routing thresholds, and budgets require verification.
- Local subscription observations must remain separate from serving-provider measurements.
- Cost estimates require dated prices and actual token counts or billing evidence.

## Deployment and failure handling

- Public Cloud Run deployment, cold-start behavior, SSE, routing, citations, shared MCP use, and partial-failure acceptance are pending.
- Initial requests are self-contained. Instance-replacement persistence checks apply if a durable memory claim is introduced.
- Submission readiness requires measured evaluation reporting and Rylan Wade's completed personal process log.

## Local container correctness

- M4 Docker startup, custom PORT, non-root identity, credential isolation, actual cited SSE, source inspection, Chromium interaction, unavailable-model transport, and disconnect cleanup pass. Real-socket authentication/child cleanup and HTTP error fixtures remain distinct checks.
- [Container evidence](research/M4_CONTAINER_RESULTS.json) contains actual local startup, TTFT, completion, image, and resource observations; [browser evidence](research/M4_BROWSER_RESULTS.json) records Chromium checks. These are exploratory local acceptance evidence, not formal scores or cloud performance.

## Financial Data correctness

- [M5 demonstration](research/M5_DEMONSTRATION_RESULTS.json) records 32 source/reference checks, four independent Data worker runs, actual application output, financial Chromium inspection, collected snapshot hashes, and unsupported adjusted metrics. [Edge evidence](research/M5_EDGE_RESULTS.json) records quarter/YTD/missing-data behavior and concurrent scope isolation.
- [M5 Docker](research/M5_CONTAINER_RESULTS.json) verifies financial output with a read-only observation mount while preserving research streaming, credential isolation, model failure, and process-tree cleanup. These checks are exploratory acceptance evidence, not RAGAS scores, financial-analysis scores, or deployment-provider measurements.

## Financial Analysis / Quant correctness

- [M6 native evidence](research/M6_DEMONSTRATION_RESULTS.json) records four actual direct annual Quant runs checked against independent source references; AMD Q2/Q3/Q4 cash-flow derivations; actual Data-to-Quant application and Chromium behavior; table/ledger/file/snapshot checks; and explicitly labeled rejection/deadline probes.
- [M6 Docker evidence](research/M6_CONTAINER_RESULTS.json) and [container application/browser evidence](research/M6_CONTAINER_APPLICATION_RESULTS.json) verify the Linux interpreter/plotting/export path, ordinary research/Data behavior, non-root/authentication isolation, model errors, cancellation, and resource observations.
- The 61-case focused suite protects provenance, extraction, research, transport cleanup, Data selection, bounded generated execution, independent arithmetic/lineage, revision/period/unit errors, negative margins, quarterly derivations, artifact integrity, and handoff failures. These are correctness checks, not formal model-judged scores.
- Final-answer claim-level correctness, held-out generalization, required RAGAS metrics, broader trajectory checks, judge calibration, comparative provider measurements, and Cloud Run retesting remain pending. Select the formal-evaluation checkpoint from Rylan Wade's feedback on the working research/numerical workflow.

## Ordinary-query regression checks

- [PM workflow correctness](planning/PM_WORKFLOW_CORRECTNESS.md) links 26 exploratory PM questions, four matched wording controls, the application retest, independent source/arithmetic/artifact audit, browser/container checks, and Linux execution fixtures. These are development regressions with actual outputs; no held-out model-quality score or judge-based evaluation is claimed.

- [Capability routing](planning/CAPABILITY_ROUTING_AND_REVENUE_SHARES.md) specifies the reported automotive question, company-scope mismatch, two-year consolidated comparison, and cross-company earnings ranking. Actual worker/application/browser evidence is separate from deterministic contract fixtures and formal evaluation.
- The numerical reference for Qualcomm FY2025 automotive revenue is USD 3.957 billion divided by USD 44.284 billion consolidated revenue, approximately 8.9355%. FY2024 automotive is USD 2.910 billion; annual table year columns, units, and original accessions must agree with each source.
- Parent-earnings ranking includes every selected company/year, independently checked positive-baseline growth, loss-baseline exclusions, actual fiscal dates, and the 53/52-week qualification. A source-reference status is not a claim-level model-quality score.
