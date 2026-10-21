# Public-Company Research Assistant

Owner: Rylan Wade. The [assignment](reference/assignment/Assignment_2_Description.md) governs deliverables.

The assistant answers what changed in a company's filings, whether the numbers support the explanation, and what remains uncertain. Answers show dates, source passages, exact financial observations, and checked calculations. The initial audience is finance students, junior analysts, and self-directed investors.

The selected companies are NVIDIA (NVDA), AMD, Intel (INTC), and Qualcomm (QCOM). The [inventory](../data/source_inventory.json) contains 46 verified documents: nine 10-Ks, 27 Q1–Q3 10-Qs, nine Q4/full-year releases, and AMD's FY2025 10-K/A. An official mirror and its SEC original share one document identity. The index contains 11,764 chunks. These are historical windows, not a latest-report claim.

| Company | Fiscal year | Actual start → end |
| --- | --- | --- |
| NVIDIA | 2024 | 2023-01-30 → 2024-01-28 |
| NVIDIA | 2025 | 2024-01-29 → 2025-01-26 |
| NVIDIA | 2026 | 2025-01-27 → 2026-01-25 |
| AMD, Intel | 2024 | 2023-12-31 → 2024-12-28 |
| AMD, Intel | 2025 | 2024-12-29 → 2025-12-27 |
| Qualcomm | 2024 | 2023-09-25 → 2024-09-29 (53 weeks) |
| Qualcomm | 2025 | 2024-09-30 → 2025-09-28 (52 weeks) |

Fiscal labels do not imply matching calendar periods. Comparisons display the actual dates. Qualcomm's reported gross profit is derived from revenue minus cost of revenue. AMD's amendment corrects FY2025 MD&A language and stays separate from the original filing.

The application has a LangGraph supervisor and five specialists: Filings Research, Financial Data, Financial Analysis / Quant, Risk Summary, and Current Developments. [Milestones](milestones/README.md) give the authoritative implementation state. Additional companies and reporting formats require source checks and feedback.

The assistant handles self-contained requests. It does not retain a conversation across turns, trade, or recommend a personal portfolio. Current Developments uses Tavily Remote MCP for recent events and identifiable outside reactions, with a separate research window for each requested output. Fiscal-year controls select historical filings and numbers. Filings Research shares search for an official update when a request verifies a filed statement. Explicit no-web instructions prevent acquisition. The supervisor preserves requested outputs independently of worker selection, and a separate reviewer checks the original question and cited answer before completion. Unsupported claim spans are removed and the repaired answer receives one bounded recheck; remaining evidence gaps stay explicit. Market prices and valuation are outside scope. Implemented system and agent capabilities are explained locally. [Architecture](architecture.md) defines evidence, timeframe and completion rules.

Local development uses Python 3.13 and uv. The default Codex profile supplies subscription generation; the explicit API profile routes planning and evidence-heavy synthesis to Nebius DeepSeek and narrow lookups to NVIDIA through hosted endpoints. [Provider routing](milestones/provider-routing/README.md) defines model identities, inspectable rules and account limits. The local Codex login stays on the host and is not a deployed credential. Cloud Run deployment and formal evaluation remain pending.

The final assignment needs the runnable service, provider routing, live/shared MCP, formal RAGAS reporting, deployed checks, and Rylan Wade's own 200–300-word [process log](../PROCESS_LOG.md). [Evaluation](evaluation.md) records what has actually been measured.
