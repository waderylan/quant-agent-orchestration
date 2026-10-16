# M8 — Buy-Side Analyst

- Owner: Rylan Wade.
- Status: planned; implementation and acceptance are unstarted.
- Position: immediately after M7 Risk Summary and before M9 Full supervisor cooperation. [Project spec](PROJECT_SPEC.md#milestones) governs the sequence.
- Outcome: a sourced public-equity valuation brief with dated multiples, qualified peer comparisons, explicit upside/downside scenarios, supporting and opposing evidence, and visible missing inputs.
- Initial companies: NVDA, AMD, INTC, and QCOM. Current market observations and new financial periods require their own coverage checks; the historical corpus does not establish latest-report coverage.

## Dependencies and increment boundary

- Reuse M5 Financial Data, M6 checked Quant execution/artifacts, M7 Risk Summary evidence, and the existing LangGraph request/evidence path.
- Implement the bounded delegation and evidence handoffs needed for this valuation workflow in M8. General task-driven planning, recovery, and cooperation across all five workers belong to M9.
- Establish the three MCP integrations below during M8. M10 expands current research to the broader Filings Research workflow and implements shared source-lookup MCP use by Filings Research and Risk Summary.
- Local generation and direct-role testing use the subscription profile. Deployment-provider generation, Cloud Run, and final public acceptance belong to M13.

## Selected MCP sources

| Source | Required role | Access and verification |
| --- | --- | --- |
| [Twelve Data official MCP](https://github.com/twelvedata/mcp) | Dated price snapshots and historical prices; reference/corporate-action information where entitled. | Verify actual free-key tools, four-company coverage, currencies, quote timestamps, feed/session/delay, and request limits. Establish adjustment conventions before using historical series. |
| [Alpha Vantage official MCP](https://github.com/alphavantage/alpha_vantage_mcp) | Forward EPS/revenue estimates, company fundamentals, financial statements, and share data needed for supported multiples. | Verify real-key coverage for every company, fiscal horizons, analyst counts/as-of metadata where supplied, GAAP/adjusted definitions, and quota. The IBM demo is source-feasibility evidence, not account entitlement. Educational quota approval remains unverified. |
| [Tavily Remote MCP](https://docs.tavily.com/documentation/mcp) | Retrieve recent earnings announcements, management guidance, company developments, and industry evidence needed to interpret valuation. | Rylan Wade reports existing Tavily student credits. Verify configured access, available balance/limits, and a bounded research allowance during implementation; no numeric or unlimited credit allowance is assumed. Retain publisher, URL, publication/retrieval dates, and exact cited evidence. |

- Prefer the selected providers' official MCP implementations. Verify MCP initialization, tool discovery, actual calls, authentication, and transport in our runtime; an HTTP API wrapped as an ordinary local function is not MCP acceptance.
- Use authenticated Streamable HTTP for Tavily, including the assignment-required key query parameter, with secret-bearing URLs redacted from traces and evidence. Resolve Twelve Data/Alpha Vantage hosted versus self-hosted transport from actual client compatibility and credential isolation.
- Use read-only tool allowlists, scoped symbols, bounded calls/timeouts, request-local evidence, and explicit rate-limit handling. Persist dated snapshots for replay and cache with an explicit freshness policy. Never present a cached value as newly observed.
- Keep credentials in ignored configuration/environment. Confirm intended browser-display and public-coursework usage rights before deployment. No paid data subscription, provider switch, or premium entitlement is assumed.
- [Market-data options research](../research/MARKET_DATA_MCP_OPTIONS_2026-10-15.md) records provider comparisons and access limitations. If a selected source cannot supply required inputs, retain the gap and resolve scope/access before claiming that dependent exit criterion passes.

## Distinct worker responsibilities

- Buy-Side Analyst has its own prompt and meaningful tool access for market/estimate snapshots and valuation-premise inspection. It selects comparable peers/periods, identifies assumptions, requests checked calculations, and explains the investment interpretation.
- Financial Data establishes reported inputs and definitions; Filings Research supports disclosure interpretation; Risk Summary supplies cited disclosure changes. Reuse their results without silently changing their accounting or revision basis.
- Quant owns independently checked arithmetic and reproducible table/chart/ledger artifacts. Extend its supported schemas/validators for required valuation calculations; do not perform unchecked arithmetic in the Buy-Side narrative or execute arbitrary provider-generated code.
- Supervisor owns the bounded M8 route and handoff trace. A simple quote lookup need not invoke every specialist. Adding the role brings the selected design to five specialized workers plus one supervisor.

## Valuation and interpretation scope

- Compute trailing and forward P/E, EV/revenue, EV/EBITDA, and free-cash-flow yield when the required inputs and definitions are established. Explain unavailable or non-meaningful metrics explicitly.
- Obtain latest eligible financial periods and compatible TTM inputs, diluted EPS/share definitions, current shares, cash/debt dates, currencies, and split adjustments. Preserve the original historical observations separately. Current price divided by an older fiscal-year result must retain that fiscal-year label.
- Define enterprise-value components and EBITDA/free-cash-flow conventions before calculation. Show whether a forward denominator is next fiscal year or next twelve months and whether estimates are GAAP or adjusted. Unknown definitions remain gaps; do not silently mix bases.
- Compare peers with fiscal dates, business mix, growth, margins, cash conversion, and risks. Explain evidence that supports or challenges a premium/discount. A low multiple alone does not establish undervaluation.
- Build explicit earnings/multiple sensitivity grids and implied share-price/upside/downside scenarios. Attribute assumptions to the user, analyst consensus, management guidance, or a labeled analytical judgment; keep those categories inspectable. Scenarios are conditional estimates, not reported results or guaranteed forecasts.
- Support historical multiple/price comparisons and price-versus-earnings contribution analysis when compatible price and financial history exists. Retain period/adjustment limits; unsupported historical decompositions remain partial.
- Return a concise brief, comparison table, scenario chart, source/calculation inspection, strongest supporting/opposing evidence, questions for management, and clear missing outputs. Reuse current complete/partial/clarification/coverage-gap behavior and answer-token SSE.
- Trading/order execution, personalized portfolio recommendations, autonomous alerts, and a general DCF engine are outside this milestone.

## Demonstration and correctness evidence

| Check | Required evidence |
| --- | --- |
| Three real MCP connections | Actual initialization/discovery/calls for Twelve Data, Alpha Vantage, and Tavily; credential-free records of returned scope, failures, quota, and timestamps. Fixtures alone do not establish live integration. |
| Four-company market snapshot | Actual NVDA/AMD/INTC/QCOM responses, correct ticker identity, dates/currencies/session, and comparable or explicitly qualified financial/estimate periods. Reject sample-symbol substitution and stale/ambiguous values. |
| Checked multiples | Independently recomputed eligible trailing/forward multiples with frozen inputs, formulas, share/cash/debt definitions, and meaningful loss/zero-denominator exclusions. Missing data remains missing. |
| Scenario analysis | At least one real company EPS/multiple sensitivity grid and implied-price/upside/downside calculation, independently checked and replayed from recorded assumptions and inputs. |
| Investment interpretation | Peer premium/discount explanation grounded in reported performance and dated Tavily evidence; include the strongest counterargument and explain unresolved evidence. |
| Role and application | Reproducible direct Buy-Side Analyst subscription run, separate full LangGraph/API turn, browser citations/tables/chart/downloads, and local container acceptance with all three integrations. Preserve distinct prompts/tools and bounded handoff traces. |
| Failure paths | Missing/denied estimates, loss/zero earnings, incompatible periods/definitions, splits, stale prices, closed markets, 429/quota exhaustion, timeout, malformed data, contradictory sources, and prompt-injection attempts in retrieved material. Verify useful partial results and request isolation. |

- Demonstration questions include “Compare the four companies' trailing and next-fiscal-year P/E; explain the premium after accounting for growth and cash generation,” “What happens to Qualcomm's implied value if estimated EPS falls 10% and its multiple contracts to 18×?” and “What evidence supports or challenges AMD's valuation premium?”
- Select exact replay fixtures, tolerances, and dated live cases after observing actual source schemas. Add unfamiliar exploratory questions to check that the workflow is useful beyond the demonstration wording. Formal held-out/model-judge evaluation remains M12 work unless the feedback-approved evaluation checkpoint starts earlier.
- Record implementation scope, actual questions/answers, provider observations, independently checked results, costs/credit usage where observable, latency, gaps, commands, and direct/application/container evidence in the appropriate research report. Update active documentation from verified behavior and obtain feedback before the next increment.
- Planning this milestone does not authorize its implementation or mark any source integration complete.
