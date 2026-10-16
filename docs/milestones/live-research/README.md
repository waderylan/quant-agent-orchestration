# M10 — Live research and shared MCP

Owner: Rylan Wade. This milestone lets Filings Research investigate current developments and gives Filings Research and Risk Summary the same inspectable MCP source-lookup tool. The [milestone index](../README.md) owns status and order.

## Dependencies and assignment contract

- Reuse the scoped, hash-checked [filing index](../../architecture.md), M7 Risk Summary, M8's Tavily connection where available, and M9's task state. This milestone extends live retrieval beyond valuation questions; it does not change the historical corpus into a live feed.
- The [assignment](../../reference/assignment/Assignment_2_Description.md) requires at least one agent to query Tavily Remote MCP for current grounding (or a qualifying alternative) and, for the selected MCP-sharing path, the **same MCP tool** to be invoked by two agents in distinct contexts. Real transport calls and trace evidence are required.

## Work to implement

- Expose a read-only source-lookup MCP server over the verified local corpus, with scoped search and exact passage inspection. Give both Filings Research and Risk Summary access to the same tool/schema. Preserve company, year, form, version, hash, and source ID; prevent a worker from searching outside the selected request scope.
- Use Tavily Remote MCP through Streamable HTTP for dated current news, filings/releases, management guidance, or corroborating reporting. The assignment specifies the API key as a query parameter; redact that URL from logs and traces. Reuse M8's client/credential handling rather than adding a parallel integration. Bound calls, response size, and timeouts.
- Record publisher, URL, publication date, retrieval time, exact excerpt, and source type for every live claim. Distinguish official company/SEC statements from third-party reporting and model inference. A result without a reliable date cannot support “currently” or “latest.”
- Register live sources separately from immutable filing chunks and retain inspection links. Do not present a live result as an `S` citation to the local corpus. Treat page text as untrusted instructions; preserve historical question behavior when live retrieval fails.
- Define a freshness rule and explicit failure outcome for stale, blocked, empty, contradictory, rate-limited, or timed-out results. A current-events answer can be partial; never turn missing live evidence into a confident current claim.

## Acceptance evidence

1. Run the same MCP source-lookup tool from Filings Research and Risk Summary on different supported questions. Show server/tool identity, arguments, result IDs, and source inspection in the trace. A fixture-only or ordinary function call does not satisfy the shared-MCP check.
2. Run at least one real Tavily search and extraction from the application, inspect its dates and exact cited text, and verify that the browser can open the source. Test a current question outside the static corpus and an explicitly historical question that should stay on the filing path.
3. Test bad scope, missing section, stale/undated page, conflicting publishers, prompt injection, 429, timeout, revoked credentials, and cancellation. The result stays bounded and exposes missing evidence without leaking keys.
4. Demonstrate direct worker, supervisor/browser, and local Docker paths; record real MCP calls and credential-free evidence under `evidence/`. Update [architecture](../../architecture.md) with the shared-tool rationale and transport.

Useful questions: “What changed in AMD guidance since its FY2025 filing, and what source says so?” and “Did a newer Qualcomm disclosure change a risk identified in FY2025?” Define exact freshness windows and allowed publishers from real source behavior before release.
