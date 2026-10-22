# M13 — Experience and evaluation

Owner: Rylan Wade. The [milestone index](../README.md) owns order and status. This increment implements and measures static Filings Research RAGAS; broader experience and agent evaluation remain.

## Implemented contract

- Fixed source-reviewed development, held-out and nonmetric control fixtures live under [tests/fixtures](../../../tests/fixtures/README.md). Questions cover reported disclosures, periods, amendment scope, conditional events and cross-company interpretation. References and exact immutable spans remain outside answer generation.
- [evaluate_ragas.py](../../../scripts/evaluate_ragas.py) captures the real Research worker and runs the four pinned RAGAS collection metrics using local Codex judging and ONNX embeddings. Missing or invalid metrics remain unavailable rather than becoming zero. Explicit reference errata preserve original datasets/captures.
- [report_ragas.py](../../../scripts/report_ragas.py) exports full-precision per-question scores, timings, usage, source identities and structured judge responses. [verify_ragas_report.py](../../../scripts/verify_ragas_report.py) replays arithmetic without model calls. Recorded metric inputs retain every model-visible context, including uncited retrievals and inspected metadata.
- Explicit annual/interim/quarter scope filters improve retrieval before semantic ranking. Mixed-form requests and original/amended versions remain available; empty scope filters cannot fall back to the whole index. Company/year context remains visible to direct hosted routing.
- [Evaluation](../../evaluation.md) owns measured values, paired changes, calibration, independent source/claim reviews, hosted costs, methodological corrections and remaining limits. [Dated evidence](evidence/RAGAS_2026-10-22.json) preserves the original cohort identities and source/code hashes.

## Verification and reproduction

Use the [root README](../../../README.md#static-filing-ragas) for setup and commands. The [acceptance record](evidence/ACCEPTANCE_2026-10-22.json) identifies regression and documentation checks. The [container record](evidence/CONTAINER_2026-10-22.json) separates Linux real retrieval/fixture generation and capability SSE from native/hosted model scores.

The fixed question set is now published. Further tuning on its held-out cases requires fresh held-out questions. Hosted semantic defects remain visible even where model-judged faithfulness reaches its ceiling.

## Remaining M13 work

- Broader whole-supervisor evaluation of checked arithmetic, agent handoffs, shared live MCP, prompt injection and failure recovery.
- Additional browser completion-state, narrow-layout, source/download and cancellation acceptance over the final integrated release.
- Integration of the selected M12 Tavily configuration; this branch starts from remote main independently of that local implementation.
- M14 owns Cloud Run cold/warm, deployment concurrency, serving-provider release checks and operating cost. PROCESS_LOG.md remains Rylan Wade's personal reflection template.
