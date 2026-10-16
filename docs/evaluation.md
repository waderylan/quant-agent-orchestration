# Evaluation

Formal RAGAS, agent trajectory, provider, and Cloud Run reports are pending. The checks below are exploratory acceptance evidence; their dated JSON retains exact cases, sources, and timing. [Milestones](milestones/README.md) link the individual records.

| Area | Measured evidence |
| --- | --- |
| Source preparation | 46 verified selected bodies/extractions; source and hash checks in [M2](milestones/source-preparation/README.md) |
| Filings Research | 19 focused tests; four company turns, one direct worker, browser/source checks, and failure probes in [M3](milestones/filings-research/README.md) |
| Local container | 22 focused tests; cited SSE, browser, auth isolation, cancellation, and model failure in [M4](milestones/local-container/README.md) |
| Financial Data | 31 focused tests; 32 annual references, four direct workers, browser and Docker checks in [M5](milestones/financial-data/README.md) |
| Quant and PM workflows | Latest 118 tests; 30 chats: 24 complete, four partial, one clarification, one coverage gap; 215 source checks, 85 calculations, 17 replayed bundles, eight browser checks, six Linux fixtures in [M6](milestones/quant/README.md) |
| M7–M9 engineering review | 192 regression tests; [first 48 sealed cases](milestones/supervisor/evidence/review-round-1/README.md): 416 source inspections, 136 replayed calculations, 44 passes and four unverified setup/basis conditions; [second 24 new cases](milestones/supervisor/evidence/review-round-2/README.md): 190 source inspections, 73 replayed calculations and 24 reviewer passes |

The PM questions and original exploratory responses are in [research](research/pm-exploration/README.md). Their labels reflect reviewed outcomes on that set, not accuracy on unseen questions. Native subscription, direct-worker, fixture, browser, Docker, and future deployed-provider results are distinct.

M12 defines a fixed, source-checked question set and reports required RAGAS faithfulness, answer relevance, context precision, and context recall. It also checks actual agent handoffs, citation support, calculation definitions, period alignment, missing evidence, and latency. Model judge compatibility, calibration, sample size, held-out cases, and thresholds are decided from observed behavior. M13 measures serving-provider cost/quality/routing and Cloud Run cold/warm, SSE, and concurrency behavior with the deployed configuration. Current local timings do not establish those results.
