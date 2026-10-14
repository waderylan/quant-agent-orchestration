# Public-Company Research Assistant

- Owner: Rylan Wade.
- Status: **M2 source collection and preparation implemented and verified; accepted**. Application implementation is unstarted.
- Initial company set: NVIDIA (NVDA), AMD (AMD), Intel (INTC), and Qualcomm (QCOM).
- Company coverage starts with these four and is planned to expand. Approximately 20 companies is the expansion target, subject to source coverage, working demonstrations, and feedback.
- Selected years: NVIDIA FY2025–2026; AMD, Intel, and Qualcomm FY2024–2025. Fiscal dates differ and must remain visible in comparisons.
- Verified corpus: **41/41 documents** — 32 annual/quarterly reports, eight Q4/full-year earnings releases, and AMD's FY2025 amendment. No collection gaps. RAG ingestion is unstarted.
- Initial metrics: consolidated US GAAP revenue growth, gross margin, operating margin, and operating cash flow.

Company research requires matching financial periods, checking metric definitions, and inspecting the passages behind management's explanations. The selected design uses a LangGraph supervisor with four specialists: Filings Research, Financial Data, Financial Analysis / Quant, and Risk Summary. The application, RAG pipeline, shared MCP tool, SSE frontend, and deployment are not implemented.

## Verified source feasibility

- SEC submissions and Company Facts return the expected companies and aligned USD inputs for all 32 original reports.
- All selected bodies and readable extractions are verified. Provenance retains SEC identities, official retrieval URLs/times, body hashes, fiscal dates, and separate amendment records.
- Direct local SEC Archives probes returned HTTP 403. Official IR mirrors/CDNs provide alternate source paths.
- Qualcomm gross profit requires revenue minus cost of revenue. Its FY2024 contains 53 weeks versus 52 in FY2025.
- AMD's FY2025 amendment corrects an MD&A explanation; retain it alongside the original annual report.
- [Source inventory](data/source_inventory.json) identifies all 41 targets. [M2 preparation](docs/planning/M2_SOURCE_COLLECTION_AND_PREPARATION.md) documents the CLI and evidence; [M1 feasibility](docs/planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md) documents source selection and financial definitions.

## Source preparation

- **uv is the project standard**, with Python 3.13 and committed `uv.lock`. `requirements.txt` is an exact-pinned export for the assignment.
- Run from the repository root:

```powershell
uv sync --locked
uv run --locked python scripts/collect_sources.py collect
uv run --locked python scripts/collect_sources.py verify
uv run --locked python scripts/demo_sources.py
uv run --locked python -m unittest discover -s tests -v
```

- `collect` resumes intact bodies; `collect --refresh` retrieves sources again and preserves raw versions and run histories. `collect --offline` prepares cached originals without network requests.
- `status` lists every target; `inspect DOCUMENT_ID --section risk_factors` opens readable evidence in the terminal. The demo prints original/extracted paths for each company and AMD's corrected passage.
- `discover` creates a separate inventory for an explicit company/fiscal window; `add-release` adds an official release. Collect future inventories with a separate `--output` directory. Exact examples are in [M2 preparation](docs/planning/M2_SOURCE_COLLECTION_AND_PREPARATION.md#future-data-from-the-cli).
- `data/corpus/` is ignored: it contains original bodies, prepared text, section/table records, SEC metadata snapshots, and run histories. Track code, source inventories, dependency pins, and compact evidence reports. Fresh checkouts reproduce downloads with the collection command.
- HTML tables retain cells and spans; PDF text retains page offsets and fixed-width layout with plain-text fallback. Inspect originals for complex table semantics. The collector handles the declared sources, not arbitrary reporting formats.

## Development and testing

- Application development and acceptance use local Codex/Claude Code subscriptions. Individual-agent tests bypass Kessel; model-backed application runs use the local Kessel gateway.
- Nebius Token Factory is selected for deployment generation; NVIDIA-hosted NIM is tentative. Exact model IDs, access, budgets, and routing thresholds are unverified.
- Runtime-provider generation calls and separate paid judges are deferred to final integration. Cloud Run deployment follows local acceptance.
- Formal evaluations are unstarted and follow working research/financial-analysis demonstrations.
- Application startup, container, and deployment commands are unavailable because the application is unimplemented. Source-preparation commands above are runnable.

## Documentation

| Document | Current role |
| --- | --- |
| [Project spec](docs/planning/PROJECT_SPEC.md) | Selected scope, architecture direction, development constraints, and open decisions. |
| [M1 feasibility](docs/planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md) | Dated source evidence, financial inputs, access limitations, and filing inventory. |
| [M2 preparation](docs/planning/M2_SOURCE_COLLECTION_AND_PREPARATION.md) | Verified corpus, extraction decisions, inspection commands, future collection, and limits. |
| [Architecture](docs/architecture.md) | Selected design and component implementation status. |
| [Evaluation](docs/evaluation.md) | Evaluation status and required reporting areas; no runtime scores or performance results. |
| [Company product description](docs/ideas/public-company-research-assistant.md) | Selected product, audience, and capability boundaries. |
| [Process log](PROCESS_LOG.md) | Template awaiting Rylan Wade's personal reflection. |
| [Assignment](docs/assignment/Assignment_2_Description.md) | Governing requirements and grading contract. |

- Law and ski documents in docs/ideas/ are unselected alternatives.
- docs/cost_analysis.md, docs/frontend_vibecode_prompt.md, and docs/alternative_*.md are instructor reference guidance. Their example models, routes, files, and configurations do not describe an implemented HW2 application.
- CLAUDE.md imports the canonical AGENTS.md instructions.
