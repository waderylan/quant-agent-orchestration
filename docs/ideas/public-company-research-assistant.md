# Public-Company Research Assistant

Product name: TBD  
Owner: Rylan Wade  
Status: selected project; original product exploration. Current scope and decisions are in the [project spec](../planning/PROJECT_SPEC.md); implementation is not yet authorized.  
Deadline planning assumption: October 29, 2026, as supplied by Rylan Wade.

## Product concept

A research assistant for understanding public companies through their disclosures, financial results, and current developments. Users ask questions in plain English and receive explanations, comparisons, and charts with inspectable evidence.

The central question is: **what changed, does the financial evidence support the explanation, and where is the uncertainty?** The assistant connects what a company reported, what its numbers establish, and what has happened since. Specialized agents investigate those questions rather than merely summarizing documents independently.

The product is a research tool. It does not execute trades, provide personalized buy/sell recommendations, or promise stock-price predictions. It can examine a user's investment hypothesis by identifying supporting evidence, contrary evidence, and assumptions that remain unproven.

## Problem and audience

Company research requires navigating long filings, locating relevant passages, aligning financial periods, and checking whether recent developments affect earlier statements. Comparing several companies adds inconsistent terminology, different fiscal calendars, and potentially different accounting measures.

The target users are self-directed investors researching a company, existing shareholders tracking developments, and finance students or junior analysts preparing comparisons. They need an answer they can inspect and challenge, including an explanation of the calculations and evidence behind it.

Filings provide substantial disclosed information, but they are not a complete account of everything that matters to a business. The product must distinguish management's statements from independently established facts and its own analysis.

## Main experience

1. **Ask:** identify one or more supported companies, a question, and a reporting period where relevant.
2. **Investigate:** the supervisor selects the needed agents. They retrieve documents, obtain financial figures, perform analysis, and request additional evidence when needed.
3. **Receive:** get a streamed answer with a concise conclusion, a table or chart when useful, and material qualifications.
4. **Inspect:** open the exact source passage or underlying financial observation, including its reporting period and filing. Inspect the inputs and method behind a calculated value.
5. **Challenge:** ask whether another period, peer, risk disclosure, or current development changes the interpretation. The agents revisit the evidence and update the conclusion where warranted.

The initial interface is a research conversation with linked sources, readable tables/charts, and an expandable record of agent activity and provider choices. It does not need brokerage integration or a full financial-terminal interface.

## Representative questions

- "What risks were added, removed, or materially changed between these two annual reports?"
- "Compare gross margins for NVIDIA, AMD, and Intel over eight quarters, and explain any comparability limitations."
- "Revenue increased, but did operating cash flow and margins improve as well?"
- "Does management's explanation of this quarter's results match the reported segment data?"
- "I think this company benefits from a particular trend. What supports that thesis, and what evidence challenges it?"
- "What recent developments relate to risks the company previously disclosed?"

These are examples of question types, not claims about current company results. Coverage must extend to unfamiliar reasonable questions within the supported company set rather than memorized answers to these prompts.

## Specialized agents and supervisor

| Role | Responsibility | Decisions it must make | Distinct capabilities |
| --- | --- | --- | --- |
| Filings Research | Interpret disclosures and investigate relevant current developments. | Identify the right company, document, period, and passage; distinguish management claims from supporting evidence; retrieve additional context; assess whether current news actually relates to the question. | Search indexed filings, inspect source sections, and use live retrieval for company announcements and relevant reporting. |
| Financial Data | Establish the numerical evidence. | Select the correct metric, units, fiscal period, and filing version; identify missing values or reporting-definition changes; reject unsupported comparisons. | Query structured financial observations and filing metadata, with links to their original sources. A separate quote tool is optional once its provider is selected. |
| Quant | Produce reproducible calculations and analysis artifacts. | Choose appropriate comparisons and formulas; test whether the inputs are comparable; identify assumptions; explain what a chart or calculation can establish. | Write and run bounded analysis code over supplied data, validate outputs, and produce tables/charts with their input lineage and method. |
| Risk Summary | Investigate changes in disclosed risks and produce a risk-change brief. | Distinguish genuinely new or changed language from moved sections and boilerplate; preserve context; assess what the text supports and label judgments about significance. | Compare versioned risk sections, inspect aligned before/after passages, and construct a cited change brief. |
| Supervisor | Coordinate the investigation. | Decide which agents are needed, direct bounded follow-up, handle failures, and identify outstanding evidence needs. | Delegate tasks and track completion and unresolved questions. |

Four specialized workers are proposed; the supervisor does not count toward the assignment minimum. Their prompts and tool access must make their roles behaviorally distinct.

Risk Summary earns its separate role through document-comparison tools and a defined change artifact. If it only repeats the Filings Research agent's summary, it should be folded into that role rather than presented as an additional capability. The remaining Research, Data, and Code roles still meet the three-worker floor if implemented substantively.

## What reasoning should look like

For an earnings question, Filings Research might retrieve management's explanation that a segment drove growth. Financial Data then obtains the matching segment and consolidated figures. Quant checks the contribution, margins, and period alignment. If the evidence supports only part of management's explanation, the answer should say which part is established and what remains unexplained.

For a risk-change question, Risk Summary compares the relevant versions. An apparently new heading might turn out to contain language moved from another section. A genuinely changed passage might qualify an existing risk rather than introduce a new one. The brief must cite both versions and explain the classification.

The strongest demonstration shows a preliminary interpretation changing after another agent supplies contrary evidence. The activity trace should expose source-backed decision summaries, tool calls, and follow-up requests. It should not imply that a long sequence of agents is itself evidence of good reasoning.

## Evidence contract

- Verifiable factual claims link to the passage, financial observation, or current source that supports them.
- Calculated results identify their source inputs, periods, units, formula, and relevant assumptions.
- Management statements, externally reported developments, and the assistant's inferences remain distinguishable.
- Conflicting sources are retained with their dates and context rather than silently reconciled into a false certainty.
- Missing or incompatible data produces a qualified answer or an explicit gap.
- A citation must support the claim; attaching a real document is insufficient by itself.

Interpretations are reasoned conclusions grounded in evidence, not direct quotations. The assistant must make that distinction clear without presenting all analysis as independently established fact.

## Document corpus and current sources

The proposed starting sector is semiconductors, with approximately 20 supported companies and 2–3 years of filings. This is a coverage target, not a completed collection. The selected company list and filing types must be defined before implementation.

The core corpus includes annual and quarterly reports, relevant current reports, earnings releases, and source documents supporting financial comparisons. Company-provided earnings materials and transcripts can be included where accessible and permitted; universal transcript coverage is not assumed.

The [SEC's EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) provide company submission history and XBRL financial-statement data without API keys. These feeds support document discovery and structured numerical evidence. They are not a live stock-quote service. Filings may be available as HTML, so the collection should not assume every source is a PDF.

Some issuers use forms such as 20-F and 6-K rather than the domestic 10-K/10-Q reporting pattern. Either support the relevant filing families deliberately or state that the initial company set excludes them. Preserve company identity, accession/document identity, reporting period, filing date, section, and source location; keep amended or restated versions identifiable.

Current research uses newly available filings, official investor-relations announcements, and relevant reporting through Tavily Remote MCP. Record publication and retrieval dates. Market quotes, historical prices, consensus estimates, and broad news feeds require separate provider/access decisions; they are not assumed to be free or included in SEC data.

The product can demonstrate its central value before adding quotes. As one concrete source example, [Microsoft's investor-relations earnings page](https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast) provides earnings material and a transcript link. That illustrates company-hosted availability, not semiconductor-sector coverage already collected.

## Numerical comparisons and price explanations

Financial comparisons must align fiscal periods and metric definitions. Distinguish quarterly values from year-to-date or annual values, GAAP from non-GAAP measures, and reported figures from derived values. A company's fiscal quarter label alone does not establish that it covers the same dates as a peer's quarter.

Quant should execute reproducible, bounded analyses and validate their results. Free-form model arithmetic is not a substitute for a checked calculation. A chart must retain the evidence and method behind its data points.

Explaining a stock-price move is a secondary capability. It requires a verified price source and a dated event timeline. The assistant can report attributed explanations and plausible contributing factors, but timing alone does not establish causation. A previously disclosed risk does not prove that it caused today's move.

## Positioning and scope

Existing research products already combine financial data, company documents, news, and AI comparisons. For example, [Koyfin's Compare Matrix](https://www.koyfin.com/help/release-notes/compare-matrix-beta/) documents natural-language comparisons across company sources with citations. The candidate should not claim this combination is unique or that all general chatbots lack current sources.

The proposed differentiator is the quality of the evidence trail: source passages, inspectable calculations, clear document-change comparisons, and conclusions that expose uncertainty. Whether users prefer that experience needs validation.

The initial version prioritizes company questions, financial comparisons, risk-change briefs, and relevant current research within the supported sector. Trading, automated portfolio decisions, price forecasting, full-terminal coverage, continuous watchlist alerts, and unrestricted analysis-code execution are outside the initial scope.

## Fit with Assignment 2

This is a proposed route to meeting the [assignment specification](../assignment/Assignment_2_Description.md), not evidence of completed implementation.

| Requirement | Proposed fit and evidence |
| --- | --- |
| At least three specialized agents and orchestration | Research, Data, Code, and Summary responsibilities map to Filings Research, Financial Data, Quant, and Risk Summary. Distinct prompts and tools are required. A proposed LangGraph supervisor makes task-driven decisions and handles worker failures. |
| Substantive RAG | Ingest, chunk, embed, and store original company documents in Pinecone or Chroma. Use LangChain LCEL retrieval/augmentation/generation and cite original source chunks in answers. |
| Live knowledge retrieval | Filings Research uses Tavily Remote MCP for current announcements and relevant reporting. A historical filing corpus or numerical SEC API alone is not treated as the required live-knowledge integration. |
| Two different generation providers | Route simpler supported lookups and more demanding interpretation/analysis across at least two providers, with actual use and inspectable cost/capability reasons. Provider/model choices remain open. |
| A2A or shared MCP tools | Expose shared filing/source lookup through MCP. For example, Filings Research retrieves a passage for interpretation while Risk Summary uses the same tool to investigate a proposed change. Demonstrate both agents invoking the same tool in distinct contexts. |
| Streaming frontend | FastAPI serves a vanilla HTML/JS interface with SSE answer tokens, linked evidence, visible provider routing, and inspectable orchestration traces. Phase updates alone do not satisfy token streaming. |
| Cloud Run | Deploy an application that responds to arbitrary reasonable questions within declared coverage, including cold starts and partial failures. Provide external persistence if durable multi-turn state is promised. |
| Evaluation and deliverables | Report fixed-set RAGAS faithfulness, answer relevance, context precision, and context recall; retrieval/LLM/total latency and TTFT; cold/warm behavior; per-query costs; and provider comparisons. Supply the architecture/evaluation reports, README, exact dependency pins, placeholder configuration, source archive, and Rylan Wade's own process log. |

## Success criteria and open decisions

Use reference questions with independently checked source passages and calculations. Evaluate citation support, numeric correctness, period alignment, risk-change classification, appropriate handling of missing evidence, and whether additional evidence changes unsupported conclusions. Include unfamiliar questions and supported companies beyond the examples used in a demonstration.

Sub-two-second warm time-to-first-token, approximately twenty-second completion, and a few cents per question are aspirational targets from the initial concept. They are not measured results or guarantees. Measure actual answer-token latency separately from progress messages and report simple lookups separately from multi-agent comparisons and code analyses.

Before implementation, decide the company list and document depth, treatment of foreign issuers, financial metric definitions, access to current reporting, bounded Quant capabilities, provider pair, and whether quotes are necessary for the first release. Name selection remains open.

The strongest first version gives a user a clear answer to what changed and what the evidence supports, with enough transparency to reproduce the numbers and challenge the interpretation.
