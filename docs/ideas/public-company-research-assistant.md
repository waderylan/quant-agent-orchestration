# Public-Company Research Assistant

- Owner: Rylan Wade.
- Product name: TBD.
- Status: selected project; M1 scope and source feasibility complete. Application implementation and M2 are unstarted.
- Selected scope and development constraints: [project spec](../planning/PROJECT_SPEC.md).
- Source availability and financial evidence: [M1 feasibility](../planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md).

## Product and audience

The selected product helps users understand what changed in a public company, whether the numbers support management's explanation, and what remains uncertain. Its audience is finance students, junior analysts, and self-directed investors.

Company research requires navigating long disclosures, matching financial periods, checking metric definitions, and deciding whether current developments affect reported conditions. The intended research brief connects disclosures, financial observations, checked calculations, and dated current reporting.

The product is a research tool. Its initial scope excludes trading, personalized buy/sell recommendations, forecasts, market quotes, price-move explanations, valuation, watchlists, and background alerts.

## Selected coverage

| Company | Fiscal years | Fiscal end dates |
| --- | --- | --- |
| NVIDIA (NVDA) | FY2025; FY2026 | 2025-01-26; 2026-01-25 |
| AMD (AMD) | FY2024; FY2025 | 2024-12-28; 2025-12-27 |
| Intel (INTC) | FY2024; FY2025 | 2024-12-28; 2025-12-27 |
| Qualcomm (QCOM) | FY2024; FY2025 | 2024-09-29; 2025-09-28 |

- Company coverage starts with these four and is planned to expand toward approximately 20, subject to source checks, working demonstrations, and feedback.
- Initial collection comprises 32 original 10-K/10-Q reports, eight Q4/full-year earnings releases, and AMD's FY2025 amendment: **41 documents**.
- All four companies use domestic SEC forms. Complete collection and ingestion are pending.
- SEC metadata and matching-duration USD financial inputs are verified for all 32 original reports. AMD/Intel body download paths and all eight earnings releases are verified; NVIDIA/Qualcomm body collection is verified for samples.
- Initial metrics are consolidated US GAAP revenue growth, gross margin, operating margin, and operating cash flow.
- Within-company comparisons take priority. Cross-company comparisons must show fiscal dates and explain timing and business-mix limits.
- Qualcomm gross profit requires revenue minus cost of revenue. Its FY2024 has 53 weeks versus 52 in FY2025.
- AMD's amendment corrects an MD&A explanation and remains separate from the original annual report.
- Additional companies, years, Q1–Q3 releases, transcripts, foreign reporting forms, and segment metrics require separate source checks and useful demonstration feedback.

## Intended user experience

1. Ask a self-contained question about one or more covered companies and identify the period where relevant.
2. Inspect which agents, tools, and providers contribute evidence.
3. Read a streamed brief with a direct conclusion, supporting passages, financial comparisons when useful, relevant risk changes, and unresolved questions.
4. Open the exact passage or observation behind a claim. Inspect the source inputs, fiscal dates, units, and formula behind a calculation.
5. Submit a revised self-contained request to compare another period, peer, or assumption.

The selected frontend design is FastAPI-served vanilla HTML/JS with SSE answer tokens, linked sources, visible provider routing, and inspectable traces. The interface is unimplemented. Initial requests carry no conversation-memory or cross-session persistence promise.

## Application roles

| Role | Selected responsibility | Intended tool access |
| --- | --- | --- |
| Filings Research | Interpret disclosures and investigate relevant current developments. | RAG retrieval, shared source inspection through MCP, Tavily Remote MCP search/extract. |
| Financial Data | Select comparable observations with company, dates, units, definitions, and filing identity. | Structured financial-data and filing-metadata queries. |
| Financial Analysis / Quant | Produce checked calculations and inspectable tables/charts. | Bounded analysis-code execution over supplied observations. Execution limits remain undecided. |
| Risk Summary | Compare versions of risk disclosures and distinguish added, removed, changed, and relocated language. | Risk-section alignment/comparison and the same source-inspection MCP tool used by Filings Research. |
| Supervisor | Coordinate tasks, direct bounded follow-up, handle failures, and synthesize cited evidence. | LangGraph delegation and task-state inspection. |

- The selected design contains four specialized workers and one supervisor. Each worker requires distinct prompts and meaningful tool access.
- Risk Summary requires document comparison; a repeated filings summary does not satisfy that role.
- Generation routing is shared infrastructure. Evaluation runs outside the application and is not an additional agent.
- All application roles and tools are unimplemented.

## Intended investigations

- “Did NVIDIA's revenue growth coincide with better operating margin and operating cash flow across the two covered years?”
- “Why did Qualcomm's gross margin change, and what comparison limits follow from its fiscal calendar?”
- “How does AMD's amended FY2025 explanation differ from the original disclosure?”
- “What changed in Intel's risk disclosures, and which quarterly updates provide context?”

These are exploratory question examples, not a fixed benchmark or implemented answer set. The deployed application must handle unfamiliar reasonable questions within declared coverage.

For financial questions, Filings Research supplies management's explanation, Financial Data supplies compatible observations, and Quant checks calculations. Risk Summary contributes disclosure changes when relevant. Missing or conflicting evidence requires bounded follow-up or a qualified answer.

## Evidence requirements

- Claims cite the exact supporting passage, financial observation, or dated current source.
- Calculations retain inputs, units, fiscal dates, formulas, and revision basis.
- Management statements, outside reporting, and assistant interpretations remain distinguishable.
- Missing observations remain missing; incompatible periods and unresolved revisions cannot support an unqualified calculation.
- Quarterly cash-flow amounts require compatible YTD differences. Margin calculations use corresponding numerators and revenue denominators.
- Annual risks provide the comparison baseline; quarterly disclosures can supply updates or references rather than complete replacement inventories.
- Original filings and amendments remain separately identifiable. Official mirrors preserve SEC accession identity and count as the same document.
- Live-source publication and retrieval dates remain visible. Failed or stale retrieval cannot establish current conditions.

## Development and remaining work

- Development and testing use local Codex/Claude Code subscriptions. Individual-role tests bypass Kessel; full model-backed application runs use the existing local Kessel gateway.
- Nebius Token Factory is selected for deployment generation. NVIDIA-hosted NIM is tentative; exact models, access, pricing, budgets, and routing thresholds remain unverified.
- Runtime-provider generation and separate paid judges belong to final integration. Cloud Run deployment follows local acceptance.
- RAG storage, embeddings, chunking, retrieval settings, observation/revision policy, Quant execution limits, Tavily integration, and frontend interaction details remain unresolved.
- Formal evaluations are unstarted. The evaluation checkpoint follows working research and financial-analysis demonstrations.
- Latency and cost targets require actual measurements; no runtime performance or cost results exist.
- M2 requires an authorized scope and acceptance demonstration. The [project spec](../planning/PROJECT_SPEC.md) lists remaining decisions and submission requirements.
