# Evaluation

- Status: formal evaluations are **unstarted**. M3 correctness and exploratory application/browser checks are separate evidence.
- Source feasibility and preparation are verified for NVIDIA, AMD, Intel, and Qualcomm. [M1 evidence](planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md) records aligned financial inputs; [M2 evidence](planning/M2_SOURCE_COLLECTION_AND_PREPARATION.md) records 41/41 bodies/extractions, section/table checks, and no collection gaps.
- Source availability checks are basic correctness evidence; they are not RAGAS scores, agent evaluations, provider comparisons, or deployed acceptance results.
- Original-document collection and readable preparation are implemented. M3 implements RAG and a local filings-research workflow. Financial analysis is unimplemented. Formal evaluation follows working demonstrations and Rylan Wade's feedback.

## Evaluation scope

- Supported task families, independently checked reference cases, dataset size/splits, calibration rubric, and formal thresholds remain undecided.
- Exploratory questions in the M1 document are demonstration ideas, not a fixed benchmark.
- Initial company/year scope is NVIDIA FY2025–2026 and AMD/Intel/Qualcomm FY2024–2025. Financial cases must retain actual fiscal dates, units, accession/version, GAAP definitions, and required derivations.
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
