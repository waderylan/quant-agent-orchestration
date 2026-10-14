# Architecture

- Status: **selected design; unimplemented application**. M1 scope and source feasibility is complete; M2 is unstarted.
- Design contract: [project spec](planning/PROJECT_SPEC.md).
- Source evidence: [M1 feasibility](planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md).

## Selected orchestration design

- LangGraph supervisor with four specialists: Filings Research, Financial Data, Financial Analysis / Quant, and Risk Summary.
- Workers return findings through supervisor-managed state. The supervisor selects tasks, requests bounded follow-up, handles partial failures, and synthesizes cited evidence.
- The graph, prompts, tools, API routes, and frontend do not exist yet. The diagram describes the selected design.

~~~mermaid
flowchart TB
    UI["Vanilla HTML/JS: answer tokens, sources, routing, traces"]
    API["FastAPI + SSE"]
    S["LangGraph Supervisor"]
    R["Filings Research"]
    D["Financial Data"]
    Q["Financial Analysis / Quant"]
    K["Risk Summary"]
    MCP["Shared source-lookup MCP"]
    V["Original-document RAG index"]
    DATA["Structured observations + filing metadata"]
    LIVE["Tavily Remote MCP"]
    RUN["Bounded analysis execution"]
    DIFF["Risk-section comparison"]

    UI <--> API
    API <--> S
    S <--> R
    S <--> D
    S <--> Q
    S <--> K
    R <--> MCP
    K <--> MCP
    V --> MCP
    R <--> LIVE
    D <--> DATA
    Q <--> RUN
    K <--> DIFF
~~~

### State contract

- Planned shared state carries the question, selected companies/periods, task status, evidence references, calculations, gaps, routing decisions, and failures.
- Exact field names, types, worker schemas, follow-up limits, and persistence interfaces are unresolved.
- Initial requests are self-contained; no durable conversation-state claim exists.

## Agent responsibilities and tool access

| Agent | Selected responsibility | Intended access | Implementation |
| --- | --- | --- | --- |
| Filings Research | Disclosure interpretation and relevant current research | RAG, shared source inspection, Tavily search/extract | Pending |
| Financial Data | Comparable financial observations and provenance | Structured data and filing metadata | Pending |
| Financial Analysis / Quant | Checked calculations, tables, charts | Bounded code execution over supplied observations | Pending; execution limits undecided |
| Risk Summary | Cited before/after disclosure comparison | Section alignment/comparison; shared source inspection | Pending |
| Supervisor | Task coordination, bounded follow-up, failure handling, synthesis | LangGraph delegation and state inspection | Pending |

## Generation routing

| Profile | Provider direction | Verified integration |
| --- | --- | --- |
| Local development | Codex/Claude Code subscription routes through the existing Kessel gateway | HW2 integration untested |
| Deployment | Nebius Token Factory selected; NVIDIA-hosted NIM tentative | Both untested in HW2 |

- The deployment design requires two distinct serving providers exercised under normal supported workloads, with visible cost/capability reasons.
- Model IDs, routing thresholds, account access, and budgets are unresolved. No worker has a fixed verified provider assignment.
- Record serving provider separately from model publisher and client library.
- Kessel is local infrastructure and remains outside the deployed image. HW2 owns tool validation/execution.
- Runtime-provider integration and measurements belong to final integration, first locally and then on Cloud Run.

## Corpus and financial sources

- Initial companies: NVIDIA, AMD, Intel, Qualcomm. Coverage expansion toward approximately 20 companies is planned after source checks, working demonstrations, and feedback.
- Selected years: NVIDIA FY2025–2026; AMD/Intel/Qualcomm FY2024–2025. Actual fiscal dates are in the [M1 coverage table](planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md#2-company-and-period-coverage).
- Collection target: 32 10-K/10-Q reports, eight Q4/full-year releases, and AMD's FY2025 amendment; **41 documents**.
- SEC submissions provide filing discovery; Company Facts provides structured financial observations. SEC accession remains canonical identity while retrieval URLs identify official mirrors/CDNs.
- Metadata and aligned USD inputs are verified for 32/32 original reports. All AMD/Intel bodies and eight releases have verified download paths. Complete NVIDIA/Qualcomm collection and section extraction are pending.
- Direct local SEC Archives probes return 403. Qualcomm's gross-profit input requires subtraction; its FY2024 has 53 weeks. AMD's corrected MD&A remains linked to its original filing.
- Initial metrics use consolidated US GAAP revenue growth, gross margin, operating margin, and operating cash flow. Observation selection and revision reconciliation are unimplemented.

## RAG pipeline

- Required stages: original-document ingestion, chunking, embeddings, vector storage, top-k retrieval, prompt augmentation, and generation with source-chunk citations.
- Pinecone versus Chroma, local embedding model, chunking rules, retrieval filters/k, and augmentation template remain undecided.
- Full corpus collection, ingestion, vector index, and retrieval are unimplemented.
- Structured financial queries complement original-document RAG; they do not replace it.

## Live knowledge and MCP sharing

- Tavily Remote MCP is the selected live-knowledge path. Public source access and provider documentation are verified; authenticated MCP initialization and tool calls are untested.
- Filings Research and Risk Summary share a source-lookup MCP tool for different evidence tasks.
- The shared tool is unimplemented. Evidence of both workers invoking it remains required; A2A is not the selected integration path.

## Frontend, deployment, and persistence

- Selected interface: FastAPI-served vanilla HTML/JS with SSE answer-token streaming, citations, routing decisions, and orchestration traces.
- Endpoint contracts, source-inspection interaction, SSE handling, and local Docker configuration are unresolved.
- Deployment target: Google Cloud Run after local acceptance. No image, service, public URL, or runtime measurements exist.
- Initial requests are single-turn. Durable conversation persistence is unnecessary for that boundary; any future durability promise requires an external store and instance-replacement verification.
- RAG index storage is a separate decision from conversation persistence.

## Outstanding verification

- Complete original-document collection and check section/table extraction fidelity.
- Implement and verify the graph, role tools, financial calculations, RAG pipeline, shared MCP use, and SSE contract.
- Check local Kessel client compatibility and Docker-to-host access.
- Run formal evaluations after working research/analysis demonstrations.
- Verify final serving providers locally, deploy, and repeat relevant cloud acceptance/evaluation checks.
