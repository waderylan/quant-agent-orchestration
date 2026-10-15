# Public-Company Research Assistant

- Owner: Rylan Wade.
- Status: **M1–M6 implemented and verified; local Docker acceptance passes**. M2 and M3 are accepted.
- Initial company set: NVIDIA (NVDA), AMD (AMD), Intel (INTC), and Qualcomm (QCOM).
- Company coverage starts with these four and is planned to expand. Approximately 20 companies is the expansion target, subject to source coverage, working demonstrations, and feedback.
- Selected years: NVIDIA FY2025–2026; AMD, Intel, and Qualcomm FY2024–2025. Fiscal dates differ and must remain visible in comparisons.
- Verified corpus: **41/41 documents** — 32 annual/quarterly reports, eight Q4/full-year earnings releases, and AMD's FY2025 amendment. No collection gaps. The local Chroma index contains 10,681 chunks.
- Available structured figures: consolidated US GAAP revenue, gross profit, operating income/loss, and operating cash flow, with exact fiscal intervals and original accession provenance. Quant computes checked growth/margins, percentage-point changes, and compatible quarter-only amounts, with CSV/PNG/code/ledger exports.

Company research requires matching financial periods, checking metric definitions, and inspecting the passages behind management's explanations. The selected design uses a LangGraph supervisor with four specialists: Filings Research, Financial Data, Financial Analysis / Quant, and Risk Summary. M3 implements Filings Research, a minimal supervisor, local semantic RAG, exact source inspection, and browser answer-token streaming. Financial Data, bounded Quant execution, Data-to-Quant cooperation, and local Docker are implemented and verified. Risk Summary, full task-driven cooperation, live/shared MCP, multi-provider routing, and deployment remain unimplemented.

## Run local research

```powershell
uv sync --locked
codex login
uv run --locked python scripts/collect_sources.py collect
uv run --locked python scripts/research.py ingest
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8080
```

- Install Codex CLI and authenticate with `codex login`; local generation uses its subscription. Open `http://127.0.0.1:8080` and ask a question with explicit company/fiscal-year selection.
- Inspect live answer tokens, routing/tool traces, and clickable citations. The source panel highlights exact passages and links to canonical filings, official mirrors, and collected originals.
- Local embeddings use CPU ONNX MiniLM; first ingestion downloads its pinned model. Chroma and corpus data are gitignored reproducible artifacts. No paid generation APIs are called by this local profile.
- Unsupported companies/years and explicit current requests receive coverage explanations. Each question is self-contained. Structured figure requests use Financial Data; numerical requests use Data then Quant; disclosure explanations use Filings Research. Live research and conversation memory are unavailable.

```powershell
uv run --locked python scripts/research.py status
uv run --locked python scripts/research.py search "Client unit shipments average selling price" --company AMD --year 2025 --section mda --version amendment
uv run --locked python scripts/research.py inspect CHUNK_ID
uv run --locked python scripts/research.py agent "What does AMD's amended FY2025 MD&A correct?" --company AMD --year 2025
uv run --locked python scripts/demo_research.py
uv run --locked playwright install chromium
uv run --locked python scripts/demo_browser.py
uv run --locked pytest -q
```

- `agent` runs the actual worker without supervisor/browser; `ask` runs the graph in the terminal. `search`/`inspect`/`status` use the local index without generation.
- Refresh sources with `collect --refresh`, re-run `research.py ingest`, and restart the application. Separate future corpora use `research.py --corpus PATH --index PATH ingest`; application settings are in `.env.example`.
- [M3 report](docs/planning/M3_FIRST_RAG_RESEARCH_DEMO.md) records current settings, actual checks, commands, and gaps; [architecture](docs/architecture.md) describes the implementation.

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
uv run --locked pytest -q
```

- `collect` resumes intact bodies; `collect --refresh` retrieves sources again and preserves raw versions and run histories. `collect --offline` prepares cached originals without network requests.
- `status` lists every target; `inspect DOCUMENT_ID --section risk_factors` opens readable evidence in the terminal. The demo prints original/extracted paths for each company and AMD's corrected passage.
- `discover` creates a separate inventory for an explicit company/fiscal window; `add-release` adds an official release. Collect future inventories with a separate `--output` directory. Exact examples are in [M2 preparation](docs/planning/M2_SOURCE_COLLECTION_AND_PREPARATION.md#future-data-from-the-cli).
- `data/corpus/` is ignored: it contains original bodies, prepared text, section/table records, SEC metadata snapshots, and run histories. Track code, source inventories, dependency pins, and compact evidence reports. Fresh checkouts reproduce downloads with the collection command.
- HTML tables retain cells and spans; PDF text retains page offsets and fixed-width layout with plain-text fallback. Inspect originals for complex table semantics. The collector handles the declared sources, not arbitrary reporting formats.

## Development and testing

- Local research generation uses Codex app-server directly with the authenticated Codex CLI and gpt-6.1-sol. No application generation API key is required. Direct worker runs, application/browser demonstrations, fixture checks, and final-provider results remain separate evidence.
- Nebius Token Factory is selected for deployment generation; NVIDIA-hosted NIM is tentative. Exact model IDs, access, budgets, and routing thresholds are unverified.
- Runtime-provider generation calls and separate paid judges are deferred to final integration. Cloud Run deployment follows local acceptance.
- Formal evaluations are unstarted and follow working research/financial-analysis demonstrations.
- Local startup and demonstrations are runnable below. Local Docker commands and evidence are in [M4 acceptance](docs/planning/M4_LOCAL_CONTAINER_ACCEPTANCE.md); cloud deployment remains M12 work.

## Documentation

| Document | Current role |
| --- | --- |
| [Project spec](docs/planning/PROJECT_SPEC.md) | Selected scope, architecture direction, development constraints, and open decisions. |
| [M1 feasibility](docs/planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md) | Dated source evidence, financial inputs, access limitations, and filing inventory. |
| [M2 preparation](docs/planning/M2_SOURCE_COLLECTION_AND_PREPARATION.md) | Verified corpus, extraction decisions, inspection commands, future collection, and limits. |
| [M4 container](docs/planning/M4_LOCAL_CONTAINER_ACCEPTANCE.md) | Verified local Docker, authenticated host generation, isolation, and cancellation. |
| [M6 Quant](docs/planning/M6_FINANCIAL_ANALYSIS_QUANT_AGENT.md) | Bounded generated programs, independent numerical validation, tables/charts, source lineage, and evidence. |
| [M5 financial data](docs/planning/M5_FINANCIAL_DATA_AGENT.md) | Observation selection, original-report policy, Data worker, inspection, and evidence. |
| [M3 research](docs/planning/M3_FIRST_RAG_RESEARCH_DEMO.md) | Local RAG, direct Codex generation, browser/source inspection, and actual verification. |
| [Architecture](docs/architecture.md) | Selected design and component implementation status. |
| [Evaluation](docs/evaluation.md) | Exploratory correctness evidence and required reporting areas; formal scores/provider measurements remain pending. |
| [Company product description](docs/ideas/public-company-research-assistant.md) | Selected product, audience, and capability boundaries. |
| [Process log](PROCESS_LOG.md) | Template awaiting Rylan Wade's personal reflection. |
| [Assignment](docs/assignment/Assignment_2_Description.md) | Governing requirements and grading contract. |

- Law and ski documents in docs/ideas/ are unselected alternatives.
- docs/cost_analysis.md, docs/frontend_vibecode_prompt.md, and docs/alternative_*.md are instructor reference guidance. Their example models, routes, files, and configurations do not describe an implemented HW2 application.
- CLAUDE.md imports the canonical AGENTS.md instructions.

## Run financial data

```powershell
uv run --locked python scripts/financials.py collect
uv run --locked python scripts/financials.py query --company AMD --year 2025 --period Q2 --basis quarter
uv run --locked python scripts/financials.py agent "Show AMD FY2025 consolidated GAAP revenue and operating cash flow with exact USD figures and sources." --company AMD --year 2025
```

- Ask structured figure questions in the same browser. Financial citations open dates, units, accession/revision evidence, collected originals, and the hash-checked SEC snapshot. [M5 details](docs/planning/M5_FINANCIAL_DATA_AGENT.md) include demonstration and refresh commands.

## Run financial analysis

```powershell
uv run --locked python scripts/quant.py agent "Calculate AMD FY2024 versus FY2025 revenue growth, gross and operating margins, and operating cash-flow growth with dates and a table/chart." --company AMD --year 2024 2025
uv run --locked python scripts/quant.py replay BUNDLE_ID
```

- The browser displays independently checked tables/charts and calculation citations. Inspect formulas, source inputs, original filings, and archived SEC snapshots; download CSV, PNG, generated code, and the exact ledger.
- Programs use an import/call/loop-free arithmetic subset with a three-second execution deadline. Figures remain original-report GAAP observations; known revision conflicts and incompatible comparisons fail explicitly. [M6 details](docs/planning/M6_FINANCIAL_ANALYSIS_QUANT_AGENT.md) provide the full contract and native/Docker verification commands.
- M7–M12 and formal evaluation remain pending. The next implementation milestone is Risk Summary; further work requires feedback and authorization.
