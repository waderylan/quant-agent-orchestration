# Evaluation

Static Filings Research has measured RAGAS results dated 2026-10-22. This report separates direct native worker runs, hosted worker runs, deterministic/container checks and earlier full-application evidence. Cloud Run cold/warm results remain pending.

## Static RAGAS results

The four required metrics use the actual `ragas.metrics.collections` implementations in **RAGAS 0.4.3**. Values below are unweighted means of per-question scores. All 96 metric values across 24 captured question-runs are available; none is replaced with zero for failure. There are **12 unique answerable questions**, with the eight development questions generated twice and the four held-out questions generated once per profile.

| Cohort | n per metric | Faithfulness | Answer relevance | Context precision | Context recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development baseline | 8 | 0.9792 | 0.8070 | 0.6654 | 0.9583 |
| Development refined | 8 | 0.9821 | 0.7969 | 0.7430 | 1.0000 |
| Native held-out | 4 | 1.0000 | 0.8060 | 0.8169 | 0.9375 |
| Hosted held-out | 4 | 1.0000 | 0.8353 | 0.8025 | 1.0000 |

The [full report](milestones/experience-evaluation/evidence/RAGAS_2026-10-22.json) records unrounded values, each answer, source identities, every structured judgment, model versions, runtime hashes, valid/missing counts, dispersion and timings. The [CSV](milestones/experience-evaluation/evidence/SCORES_2026-10-22.csv) gives all 24 rows at full numeric precision. Values printed as 1.0000 can be slightly below one because context precision uses RAGAS' denominator epsilon.

Development context precision rises **0.0777** (7.77 percentage points), with six cases improving, one unchanged and one declining. Recall rises **0.0417**, from one improved case and seven unchanged. Relevance falls **0.0101**. Faithfulness rises only **0.0030**; the changed decomposition of a procedural sentence explains that difference, so it is not evidence of improved financial accuracy. One stochastic before/after pair per question does not identify a causal effect.

| Development case | Faithfulness, before → after | Relevance | Precision | Recall |
| --- | ---: | ---: | ---: | ---: |
| ragas_dev_01 | 1.0000 → 1.0000 | 0.8161 → 0.7842 | 0.5516 → 0.6429 | 1.0000 → 1.0000 |
| ragas_dev_02 | 1.0000 → 1.0000 | 0.8267 → 0.8366 | 0.2283 → 0.3894 | 1.0000 → 1.0000 |
| ragas_dev_03 | 1.0000 → 1.0000 | 0.6921 → 0.7084 | 1.0000 → 1.0000 | 1.0000 → 1.0000 |
| ragas_dev_04 | 1.0000 → 1.0000 | 0.8564 → 0.8564 | 0.9889 → 0.9403 | 0.6667 → 1.0000 |
| ragas_dev_05 | 0.8333 → 0.8571 | 0.7305 → 0.7267 | 0.3076 → 0.4125 | 1.0000 → 1.0000 |
| ragas_dev_06 | 1.0000 → 1.0000 | 0.8734 → 0.8441 | 0.6152 → 0.8529 | 1.0000 → 1.0000 |
| ragas_dev_07 | 1.0000 → 1.0000 | 0.7745 → 0.7154 | 0.7762 → 0.8298 | 1.0000 → 1.0000 |
| ragas_dev_08 | 1.0000 → 1.0000 | 0.8864 → 0.9037 | 0.8552 → 0.8767 | 1.0000 → 1.0000 |

Case questions, source excerpts and atomic reference facts are in the [development fixture](../tests/fixtures/ragas_development.json). Cases cover AMD's amendment, NVIDIA annual margins, Intel's Altera accounting, Qualcomm deferred taxes, AMD Q2 margins, NVIDIA Q2 Blackwell timing, cross-company manufacturing and QTL recognition/growth.

| Held-out case | Faithfulness, Codex / Hosted | Relevance | Precision | Recall |
| --- | ---: | ---: | ---: | ---: |
| ragas_holdout_01 | 1.0000 / 1.0000 | 0.8292 / 0.8869 | 1.0000 / 1.0000 | 1.0000 / 1.0000 |
| ragas_holdout_02 | 1.0000 / 1.0000 | 0.7080 / 0.7583 | 0.7261 / 0.7155 | 1.0000 / 1.0000 |
| ragas_holdout_03 | 1.0000 / 1.0000 | 0.8941 / 0.8755 | 0.5414 / 0.4943 | 0.7500 / 1.0000 |
| ragas_holdout_04 | 1.0000 / 1.0000 | 0.7927 / 0.8205 | 1.0000 / 1.0000 | 1.0000 / 1.0000 |

The [published held-out fixture](../tests/fixtures/ragas_heldout.json) covers AMD acquisition/disposition timing, Intel's conditional 14A plan, NVIDIA/Qualcomm customer definitions and NVIDIA segment reporting. It was withheld from implementation decisions until all four native captures completed. These questions are now public regression cases; future tuning on them needs a new held-out set.

## Dataset and run boundaries

- An independent coding agent authors eight development questions, four sealed held-out questions and two separate controls. References contain 44 atomic facts across the 12 metric questions, backed by 24 exact spans from 12 immutable documents. Full-document and excerpt hashes plus Unicode character offsets are checked against the prepared corpus. The actual retriever still searches the 46-document, 11,764-chunk corpus within selected scope. [Dataset audit](milestones/experience-evaluation/evidence/DATASET_AUDIT_2026-10-22.json).
- Baseline product code is remote `main` at `aec3b3c`. The RAGAS work starts on a separate `eval/ragas` branch; M12's automatic Risk web integration is excluded. Development feedback changes general source scoping, not ticker-specific answers. The final product/prompt hashes stay unchanged through native and hosted held-out captures and match the [freeze record](milestones/experience-evaluation/evidence/FREEZE_2026-10-22.json).
- Each run invokes the real `research_turn` worker: initial Chroma retrieval, LCEL augmentation, model-driven search/inspection, completion reporting and citation verification. This is not the whole supervisor/browser workflow. Selected company/year and question enter generation; reference answers, expected facts and reference passages do not. No live-check state is supplied, no web tool is exposed and no Tavily calls occur.
- Contexts include **all** unique model-visible chunks, including uncited results, in first-seen adaptive retrieval order. Inspection widens that chunk's context without adding a duplicate rank. Actual observed metadata, including filing form/version and period end, accompanies text. Post-generation citation checks do not add model-visible evidence. Precision therefore measures the adaptive accumulated ordering, not one fixed top-k query.
- Development and native held-out generation use the local Codex subscription, `gpt-6.1-sol`. Judge generation uses the same model family through a custom `InstructorBaseRagasLLM` adapter. This creates possible self-judging bias. The independent reviewer is another coding agent, not a human adjudicator, and can see the run type. No statistical population-accuracy or blinded human-study claim is made.
- Embeddings use the pinned CPU ONNX `all-MiniLM-L6-v2`, 384 dimensions, with model artifact hash in the report. Python is 3.13.12; RAGAS 0.4.3, Chroma 1.5.9, ONNX Runtime 1.31.0, LangChain Core 1.6.10 and Pydantic 2.14.1 are recorded. `langchain-community==0.4.1` is pinned for evaluation because 0.4.2 removes a module imported by this RAGAS release. RAGAS stays in the development dependency group.

## Metric definitions and calibration

- **Faithfulness:** supported generated statements divided by all generated statements. The unmodified RAGAS judge first decomposes the answer, then checks those statements against contexts. [RAGAS faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/).
- **Answer relevance:** mean cosine similarity between the original question and three independently generated questions inferred from the answer. Pinned collection behavior returns zero when all generated responses are noncommittal. It does not establish factual correctness. [RAGAS response relevancy](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/).
- **Context precision:** average precision of reference-relevant chunks in their observed order, using RAGAS' binary verdicts and epsilon. It is not simply the fraction of relevant chunks. [RAGAS context precision](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/).
- **Context recall:** reference statements supported by retrieved contexts divided by all decomposed reference statements. It measures retrieved support, not whether the answer actually states every required fact. [RAGAS context recall](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/).

[Calibration](milestones/experience-evaluation/evidence/CALIBRATION_2026-10-22.json) uses a separate synthetic company example. The supported answer scores faithfulness/precision/recall 1; a numerically contradicted answer scores faithfulness 0 while relevance remains 0.9566. An irrelevant answer has relevance 0.1659. With reference support removed, precision/recall are 0 even though answer relevance stays 0.9571. These controls validate basic directionality, not domain-wide judge accuracy. Their four rows are excluded from corpus metric averages.

Each relevancy draw has a separate cache sample index. Cache identity includes model, schema, prompt, transport hash and draw index. Identical previously judged inputs can replay; different inputs are not substituted. The selected scoring runs record 393 judge invocations: 240 new calls and 153 cache hits. Those counts exclude other calibration/preliminary work and are not session token totals. No paid judge or embedding fallback exists.

## Evaluation corrections and interpretation limits

The [method correction record](milestones/experience-evaluation/evidence/METHOD_CORRECTIONS_2026-10-22.json) and [preserved preliminary evidence](milestones/experience-evaluation/evidence/PRELIMINARY_2026-10-22.json) retain development failures:

1. Initial cache design replayed one answer-relevance question for all three draws. Separate draw identities fix this; a regression checks three actual calls followed by exact three-draw replay. Calibration v2 and final scores use the corrected adapter.
2. Initial metric context export omitted metadata observed by the answering model. A supported fiscal-year-end statement was consequently rejected. The corrected `metadata-v2` protocol includes actual source metadata for every cohort. Preliminary text-only scores are not mixed into the headline table.
3. An independent post-capture source audit finds an overbroad reference clause about NVIDIA's Data Center market. An explicit [reference erratum](../tests/fixtures/ragas_reference_errata.json) narrows it to the accelerated-computing platform and two reportable segments. Original fixture bytes, questions, captures and prior scores remain preserved. Original/corrected reference hashes are recorded; reference-based metrics are rerun. Native case04 numeric scores do not change. Hosted answers are evaluated with the corrected reference.

[Arithmetic replay](milestones/experience-evaluation/evidence/ARITHMETIC_2026-10-22.json) recomputes **all 96 values** from saved structured judgments and local embeddings with zero new model calls, within 1e-6. It retains the three relevance cosine values, binary precision verdicts, recall counts and rejected faithfulness statements.

Faithfulness rejects the development AMD sentence saying no adjusted margin was calculated, because the filing cannot establish what the answer did. The five financial statements in the baseline case pass; the procedural statement gives 5/6 = 0.8333. The refined decomposition gives 6/7 = 0.8571. These raw scores remain unchanged. The metadata correction separately clears the supported AMD fiscal-end rejection in the manufacturing case.

## Independent source review

| Capture | Useful answers | Fully stated reference facts | Supported / unsupported reviewed claims | Verified returned contexts |
| --- | ---: | ---: | ---: | ---: |
| Development baseline | 8/8 | 24/28; four partial details | 90 / 0 | 96/96 |
| Development refined | 8/8 | 28/28 | 93 / 0 | 80/80 |
| Native held-out | 4/4 | 15/16; one partial detail | 54 / 0 | 38/38 |
| Hosted held-out | 4/4 | 15/16; one partial detail | 67 / 2 | 35/35 |

The [baseline](milestones/experience-evaluation/evidence/BASELINE_REVIEW_2026-10-22.json), [refined](milestones/experience-evaluation/evidence/REFINED_REVIEW_2026-10-22.json), [native held-out](milestones/experience-evaluation/evidence/HELDOUT_REVIEW_2026-10-22.json) and [hosted](milestones/experience-evaluation/evidence/HOSTED_REVIEW_2026-10-22.json) reviews retain per-fact judgments and claim rationale. Reviewer segmentation differs from RAGAS statement decomposition; those denominators are not interchangeable. All 249 returned contexts pass source-integrity checks. The two unanswerable/ambiguous controls independently pass honest coverage-gap and clarification behavior and remain outside metric denominators.

The refinement removes 20 explicitly out-of-scope initial sources: **20/46 before versus 0/45 after** across development initial retrievals. Across the six explicitly scoped questions alone, the corresponding counts are 20/38 and 0/37. It adds source-form defaults, fiscal-quarter document filters, safe empty filters and preserved original/amended versions. Mixed-source questions stay broad. Direct worker handlers also retain company/year metadata for hosted routing. No reingestion is needed.

Remaining limits are substantive:

- The held-out annual-segment wording is not recognized by the narrow annual-form parser, so two quarterly sources enter initial retrieval. The native final answer correctly uses annual figures and distinguishes market versus segment breakdowns. This unrecognized phrasing is retained as a held-out limitation, without post-holdout prompt tuning.
- Mixed amendment/interim requests initially prioritize the two annual versions; the worker must explicitly request a 10-Q form for interim context. This combination is not covered by the twelve-question metric suite.
- Native customer-definition coverage leaves one reference detail partial. Native context recall 0.9375 reflects one reference-support gap, despite all generated held-out statements receiving faithfulness 1.
- Hosted customer-definition prose wrongly treats a licensing relationship as excluding chip purchases. Hosted segment prose overstates nesting of the whole Data Center market. Both are useful answers with unsupported interpretations. **RAGAS faithfulness scores all four hosted answers as 1 anyway.** That ceiling is not 100% factual accuracy; independent review catches errors the judge misses.
- Native bounded source/calibration checks pass. Hosted semantic acceptance remains limited by those two material overstatements. No claim is made that the full five-agent application or deployment passes from these direct-worker results.

## Latency, providers and cost

| Cohort | Median retrieval s | Median model wait s | Median answer TTFT s | Median total s | Total range s |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 1.1135 | 16.7070 | 12.9540 | 18.2895 | 14.6900–24.9360 |
| refined | 2.6200 | 17.0590 | 13.9635 | 20.1540 | 16.1550–37.8580 |
| heldout | 3.8305 | 17.5905 | 14.7785 | 20.5715 | 20.1570–22.0200 |
| hosted_heldout | 2.4690 | 17.5775 | 17.8630 | 20.1415 | 12.9520–102.8030 |

The CSV includes every per-query measurement. Retrieval time includes local embedding, Chroma search and source inspections, including citation verification. Model wait subtracts measured dynamic-tool handler time from the model stream; it includes local transport/startup and scheduling, not isolated GPU computation. TTFT measures first answer prose. Model-stream time including tools and other timing fields remain in input artifacts. These are descriptive local timings: native generation uses concurrency two, hosted capture one; some runs overlap judges/tests. They do not establish an intrinsic latency gain/loss or Cloud Run cold/warm behavior. With n=4 or n=8, nearest-rank p95 equals the observed maximum; no population confidence interval is claimed.

Hosted generation routes to NVIDIA `nvidia/nemotron-3.5-super-vl-120b-a12b` and Nebius `deepseek-ai/DeepSeek-V4-Flash-0731`. Two requests recover from NVIDIA HTTP500/read-timeout failures through Nebius; both still complete. NVIDIA is attempted in three requests and returns usage-bearing rounds in two; Nebius returns usage-bearing rounds in three. Route attempts overlap on both recovery cases. This is a paired Codex-versus-routed-profile check, not an isolated comparison of two providers on equivalent tasks.

| Serving provider | Usage-bearing rounds | Prompt tokens | Completion tokens | Configured-price estimate USD |
| --- | ---: | ---: | ---: | ---: |
| NVIDIA | 8 | 56,113 | 643 | 0.00000000 |
| Nebius | 7 | 51,174 | 3,953 | 0.00827120 |
| Total | 15 | 107,287 | 4,596 | 0.00827120 |

The four hosted question-runs average **$0.00206780** in reported token-based estimates. All 15 usage-bearing rounds expose counts; failed attempts may lack usage and are not assumed to have verified zero billing. Prices are the versioned routing configuration, and these numbers are not an account invoice. Local Codex generation/judging and ONNX embeddings consume no direct provider-key API calls; subscription fees and unexposed token usage are excluded. Zero Tavily calls occur in this static evaluation. No Cloud Run operating cost is measured. [M11](milestones/provider-routing/README.md) owns the earlier controlled serving-model comparison and routing evidence.

## Reproduction and verification

The [root README](../README.md#static-filing-ragas) owns runnable commands. [Recorded inputs](milestones/experience-evaluation/evidence/INPUT_MANIFEST_2026-10-22.json) preserve exact answer strings and model-visible context dictionaries for all four cohorts. They can be rescored without rerunning generation or querying Chroma. The arithmetic replay checks the published scores without a judge call. An actual score-command replay from the published held-out input also reproduces all 16 values using 62 cached judgments and zero Chroma/model calls ([input replay](milestones/experience-evaluation/evidence/INPUT_REPLAY_2026-10-22.json)). New stochastic judge/generation runs need not reproduce identical values.

The [acceptance record](milestones/experience-evaluation/evidence/ACCEPTANCE_2026-10-22.json) contains final regression, link, credential and runtime checks. The [independent report audit](milestones/experience-evaluation/evidence/REPORT_REVIEW_2026-10-22.json) passes 164 consistency checks, including a second recomputation of all 96 values; maximum numeric error is 8.77e-8. The [Linux container check](milestones/experience-evaluation/evidence/CONTAINER_2026-10-22.json) uses actual scoped Chroma retrieval and citation verification with a deterministic model fixture, plus actual FastAPI capability SSE. It is not a hosted model benchmark. Its first ASGI harness omitted application lifespan initialization; initializing lifespan fixes that harness failure, and the repeated check passes.

Broader M13 browser/agent-trajectory/adversarial coverage and M14 Cloud Run evaluation remain outside this completed static-RAG increment. Rylan Wade's personal process log remains a template.

## Earlier engineering evidence

| Area | Measured evidence |
| --- | --- |
| Hosted provider routing | [M11 acceptance](milestones/provider-routing/evidence/ACCEPTANCE_2026-10-20.json) records real NVIDIA/Nebius application calls, Codex/Hosted browser switching, source inspection, controlled worker comparisons and two concurrent Linux requests invoking every specialist. Both full requests remain partial: filing/risk coverage and completion checks retain gaps, and AMD's live acquisition hits the configured Tavily monthly stop. This is not a passing full-workflow quality result. |
| Source preparation | 46 verified selected bodies/extractions; source and hash checks in [M2](milestones/source-preparation/README.md) |
| Filings Research | 19 focused tests; four company turns, one direct worker, browser/source checks, and failure probes in [M3](milestones/filings-research/README.md) |
| Local container | 22 focused tests; cited SSE, browser, auth isolation, cancellation, and model failure in [M4](milestones/local-container/README.md) |
| Financial Data | 31 focused tests; 32 annual references, four direct workers, browser and Docker checks in [M5](milestones/financial-data/README.md) |
| Quant and PM workflows | Latest 118 tests; 30 chats: 24 complete, four partial, one clarification, one coverage gap; 215 source checks, 85 calculations, 17 replayed bundles, eight browser checks, six Linux fixtures in [M6](milestones/quant/README.md) |
| M7–M9 engineering review | 192 regression tests; [first 48 sealed cases](milestones/supervisor/evidence/review-round-1/README.md): 416 source inspections, 136 replayed calculations, 44 passes and four unverified setup/basis conditions; [second 24 new cases](milestones/supervisor/evidence/review-round-2/README.md): 190 source inspections, 73 replayed calculations and 24 reviewer passes |
| Current Developments and shared live MCP | [M10 acceptance](milestones/current-developments/README.md) separates direct-worker, native API, browser, Linux-container, failure-fixture, credit-ledger and image-safety checks. Dated evidence records identify the runtime they measure. |
| Whole-request usefulness | 265 frozen regression tests; [final independent review](milestones/current-developments/evidence/HOLDOUT_FINAL_2026-10-19.json): four fresh casual questions, four useful answers, zero critical failures, mean 7.75/8. [Initial 18 captures](milestones/current-developments/evidence/HOLDOUT_2026-10-19.json) and [iteration 2's six captures](milestones/current-developments/evidence/HOLDOUT_ITERATION2_2026-10-19.json) retain their failures and runtime hashes. |
| Calculation-lineage validation | Two additional [fresh filings-only checks](milestones/current-developments/evidence/HOLDOUT_VALIDATION_2026-10-19.json) complete without web tools on a separately recorded runtime. These verify the lineage fix and remain separate from the four-question usefulness result. |
| Codebase cleanup | 271 frozen regression tests; [C1](milestones/cleanup/README.md) verifies final SSE answer/source capture, partial status, required review checks, sentence repair, native calculations and the Linux container without new Tavily calls. |
| Agent activity UI | 278 regression tests pass on 2026-10-19. [Browser fixtures](../tests/test_agent_activity.py) check repeated calls, timing, shared selection, source inspection, interrupted requests, keyboard focus, and phone layout. [API checks](../tests/test_supervisor_api.py) verify lifecycle timestamps; [review checks](../tests/test_request_plan.py) retain failed review status. A native AMD filings-only browser run completes through Data, Quant and Reviewer with source inspection and Stop verified. The Linux container serves the activity asset and completes a capability request in Chromium. These checks use zero Tavily calls. |

The PM questions and original exploratory responses are in [research](research/pm-exploration/README.md). Their labels reflect reviewed outcomes on that set, not accuracy on unseen questions. Native subscription, direct-worker, fixture, browser, Docker, and future deployed-provider results are distinct.

The final usefulness review uses four independently written questions withheld until one-shot captures complete on a frozen runtime. A separate reviewer checks requested-output coverage, useful synthesis, provenance and honest limits against returned source text. The release gate requires at least 85% useful answers and zero critical failures; this four-case result is a bounded engineering check, not a general accuracy estimate or formal RAGAS score. Median total latency is 91.256 seconds and median answer-token time to first token is 75.828 seconds, including application queue time and concurrent development requests. These are local subscription/Tavily measurements, with no Cloud Run cold-start or generation-provider comparison claim. One minor editorial defect remains in the captured answers.

M14 measures deployed serving-provider routing, Cloud Run cold/warm latency, SSE, concurrency and actual operating costs. Current local timings do not establish those results.
