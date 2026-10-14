# Public-Company Research Assistant

- Owner: Rylan Wade.
- Status: **M1 scope and source feasibility complete**. Application implementation and M2 are unstarted.
- Initial company set: NVIDIA (NVDA), AMD (AMD), Intel (INTC), and Qualcomm (QCOM).
- Company coverage starts with these four and is planned to expand. Approximately 20 companies is the expansion target, subject to source coverage, working demonstrations, and feedback.
- Selected years: NVIDIA FY2025–2026; AMD, Intel, and Qualcomm FY2024–2025. Fiscal dates differ and must remain visible in comparisons.
- Collection target: **41 documents** — 32 annual/quarterly reports, eight Q4/full-year earnings releases, and AMD's FY2025 amendment. Full corpus collection and ingestion are pending.
- Initial metrics: consolidated US GAAP revenue growth, gross margin, operating margin, and operating cash flow.

Company research requires matching financial periods, checking metric definitions, and inspecting the passages behind management's explanations. The selected design uses a LangGraph supervisor with four specialists: Filings Research, Financial Data, Financial Analysis / Quant, and Risk Summary. The application, RAG pipeline, shared MCP tool, SSE frontend, and deployment are not implemented.

## Verified source feasibility

- SEC submissions and Company Facts return the expected companies and aligned USD inputs for all 32 original reports.
- Official AMD/Intel filing bodies and all eight earnings releases have verified local download paths. NVIDIA/Qualcomm body access is verified for samples; complete collection remains pending.
- Direct local SEC Archives probes returned HTTP 403. Official IR mirrors/CDNs provide alternate source paths.
- Qualcomm gross profit requires revenue minus cost of revenue. Its FY2024 contains 53 weeks versus 52 in FY2025.
- AMD's FY2025 amendment corrects an MD&A explanation; retain it alongside the original annual report.
- Source links, all 33 filing identities, annual figures, and a runnable Python availability check are in [M1 scope and source feasibility](docs/planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md).

## Development and testing

- Application development and acceptance use local Codex/Claude Code subscriptions. Individual-agent tests bypass Kessel; model-backed application runs use the local Kessel gateway.
- Nebius Token Factory is selected for deployment generation; NVIDIA-hosted NIM is tentative. Exact model IDs, access, budgets, and routing thresholds are unverified.
- Runtime-provider generation calls and separate paid judges are deferred to final integration. Cloud Run deployment follows local acceptance.
- Formal evaluations are unstarted and follow working research/financial-analysis demonstrations.
- Application startup, container, and deployment commands are unavailable because the application is unimplemented. The M1 Python source-check recipe is runnable independently.

## Documentation

| Document | Current role |
| --- | --- |
| [Project spec](docs/planning/PROJECT_SPEC.md) | Selected scope, architecture direction, development constraints, and open decisions. |
| [M1 feasibility](docs/planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md) | Dated source evidence, financial inputs, access limitations, and filing inventory. |
| [Architecture](docs/architecture.md) | Selected design and component implementation status. |
| [Evaluation](docs/evaluation.md) | Evaluation status and required reporting areas; no runtime scores or performance results. |
| [Company product description](docs/ideas/public-company-research-assistant.md) | Selected product, audience, and capability boundaries. |
| [Process log](PROCESS_LOG.md) | Template awaiting Rylan Wade's personal reflection. |
| [Assignment](docs/assignment/Assignment_2_Description.md) | Governing requirements and grading contract. |

- Law and ski documents in docs/ideas/ are unselected alternatives.
- docs/cost_analysis.md, docs/frontend_vibecode_prompt.md, and docs/alternative_*.md are instructor reference guidance. Their example models, routes, files, and configurations do not describe an implemented HW2 application.
- CLAUDE.md imports the canonical AGENTS.md instructions.
