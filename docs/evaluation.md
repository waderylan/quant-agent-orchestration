# Evaluation

- Status: formal evaluations and application/runtime measurements are **unstarted**.
- Source feasibility and preparation are verified for NVIDIA, AMD, Intel, and Qualcomm. [M1 evidence](planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md) records aligned financial inputs; [M2 evidence](planning/M2_SOURCE_COLLECTION_AND_PREPARATION.md) records 41/41 bodies/extractions, section/table checks, and no collection gaps.
- Source availability checks are basic correctness evidence; they are not RAGAS scores, agent evaluations, provider comparisons, or deployed acceptance results.
- Original-document collection and readable preparation are implemented. RAG ingestion, the application, and research/financial-analysis workflows are unimplemented. Formal evaluation follows working demonstrations and Rylan Wade's feedback.

## Evaluation scope

- Supported task families, independently checked reference cases, dataset size/splits, calibration rubric, and formal thresholds remain undecided.
- Exploratory questions in the M1 document are demonstration ideas, not a fixed benchmark.
- Initial company/year scope is NVIDIA FY2025–2026 and AMD/Intel/Qualcomm FY2024–2025. Financial cases must retain actual fiscal dates, units, accession/version, GAAP definitions, and required derivations.
- Qualcomm's 53-week FY2024 and derived gross profit, AMD's amended explanation, YTD cash-flow differences, and unavailable evidence are relevant correctness cases.

## Required RAGAS report

- Required metrics: faithfulness, answer relevance, context precision, and context recall.
- Fixed question set, source-checked references, executable evaluator, compatible client configuration, exact framework versions, and measured results are pending.
- RAGAS/AgentEvals generation and compatible judges use local subscription-backed Kessel during development. Client compatibility and judge calibration require verification.
- Separate paid judges and actual runtime-provider measurements belong to final integration.

## Financial correctness and agent behavior

- Independently checked calculations must validate input periods, units, definitions, formulas, revision basis, and table/chart consistency.
- Risk comparisons require reviewed before/after passages and classification of added, removed, changed, or relocated language.
- Agent checks must inspect delegation, evidence handoff, shared MCP calls, follow-up limits, failures, and unsupported conclusions.
- Individual-role Codex tests, fixture-based graph tests, Kessel-backed application runs, and final provider/deployment tests are separate evidence categories.
- No application-role or graph evaluation results exist.

## Latency

- Retrieval, LLM, total latency, and answer-token time-to-first-token measurements are pending.
- Cloud Run cold/warm behavior and concurrency checks are pending.
- Source-download timings or progress events do not establish application answer-token latency.

## Cost per query and provider comparison

- Runtime token use, bills, cost estimates, latency, and quality comparisons are unavailable.
- Nebius Token Factory is selected; NVIDIA-hosted NIM remains tentative. Exact models, access, pricing, routing thresholds, and budgets require verification.
- Local subscription/Kessel observations must remain separate from serving-provider measurements.
- Cost estimates require dated prices and actual token counts or billing evidence.

## Deployment and failure handling

- Public Cloud Run deployment, cold-start behavior, SSE, routing, citations, shared MCP use, and partial-failure acceptance are pending.
- Initial requests are self-contained. Instance-replacement persistence checks apply if a durable memory claim is introduced.
- Submission readiness requires measured evaluation reporting and Rylan Wade's completed personal process log.
