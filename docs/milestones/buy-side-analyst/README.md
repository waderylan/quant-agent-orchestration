# M8 — Buy-Side Analyst

Owner: Rylan Wade. The [milestone index](../README.md) owns status.

Buy-Side Analyst has its own prompt and tools for inspecting market/estimate evidence and requesting Quant calculations. Each acquisition plan allows at most four quotes, four estimate calls, and one narrow basic Tavily search. Model tools inspect frozen evidence; they cannot expand web searches. Explicit refresh requests bypass freshness caches within the same work budgets. Quote-only requests use one worker.

## MCP access and entitlements

The application uses official Twelve Data MCP over stdio, pinned to commit `d139a77ea0f7d40995e6979cd09c22dd142fbfe8`, official Alpha Vantage Remote MCP, and Tavily Remote MCP over Streamable HTTP with runtime credentials. Every live data call initializes the server, discovers the requested tool, and invokes `tools/call`. URLs containing credentials and account emails are scrubbed before persistence or trace emission. Docker contains the pinned official server but no credentials or CLI login.

Actual account probes on 2026-10-16 establish:

| Account/source | Returned evidence | Limits established by the response |
| --- | --- | --- |
| Twelve Yahoo | Four matching quotes; usage `plan_limit=800` | Statistics, earnings, and splits return plan restrictions. Feed/delay and plan name are not supplied. |
| Twelve Gmail | Sequential NVDA quote and usage audit; `plan_limit=800` | The same three datasets are restricted. Yahoo is restored after the diagnostic audit; no production quota fallback occurred. |
| Alpha Vantage | Four matching annual estimate responses; QCOM earnings and income statement | Company Overview is restricted. Balance sheet and cash flow are previews. Estimate GAAP/adjusted basis, dilution, currency, consensus as-of, split basis, and exact fiscal-date reconciliation remain unverified. |
| Tavily | Real discovery and basic searches through the analyst/application | Usage endpoint reports Researcher, 28 monthly credits against 1,000; search responses omit charge counts. The ledger conservatively reserves two credits per basic call. |

Public display is not accepted. [Twelve Data terms §§2.2–2.4](https://twelvedata.com/terms) require explicit external-display rights; [Alpha Vantage terms](https://www.alphavantage.co/terms_of_service/) limit the default license to personal use. These accounts have no verified public-coursework redistribution authorization. Private local browser checks do not establish deployment rights. Cloud Run disables market data unless display rights are explicitly configured as confirmed. No plan was purchased or upgraded.

## Evidence and arithmetic

Quotes preserve symbol, currency, UTC price timestamp, closed/open session, provider trading date, retrieval time, and unspecified feed/delay. Open-market observations older than 20 minutes and closed-market observations older than four days are stale. Quotes cache for 15 minutes; other responses cache for 24 hours. Frozen replay retains original dates and is labeled as replay. Content-addressed snapshots remain inspectable after a refresh; request-cache pointers are separate.

Unqualified consensus stays visible with its provider period and analyst count, but does not enter verified forward P/E. Historical annual earnings never become current TTM. Missing shares, cash/debt dates, split reconciliation, and EBITDA/FCF definitions exclude affected multiples. Quant supports qualified P/E, forward P/E, EV/revenue, EV/EBITDA, and positive FCF yield. EV is equity value plus total debt less cash equivalents; FCF is operating cash flow less capital expenditures. Nonpositive denominators and incompatible currencies, periods, dilution, or accounting/split bases fail validation.

Explicit user EPS and multiple assumptions support a conditional scenario even when consensus is unqualified. The default horizon is 12 months. `EPS grid: 8, 10, 12; P/E grid: 16, 18, 20` specifies a bounded 3×3 grid. Quant executes the arithmetic in the isolated runner, independently recomputes results and actual input lineage, and freezes CSV/PNG/code/ledger bundles. A recorded 18-calculation grid replays exactly. The analyst cites checked calculations, supplies supporting and opposing evidence, and names missing inputs; personalized portfolio instructions remain outside scope.

## Verification

[M8 acceptance](evidence/M8_ACCEPTANCE_2026-10-16.json) separates real account probes, actual direct-role generation, graph/API requests, native Chromium, Docker, and synthetic failures. The Docker API refresh performs real quote and estimate MCP calls; application searches establish Tavily access. Browser checks open citations and calculation inputs, render charts, and download bundles. Synthetic cases cover stale/closed prices, missing estimates, symbol substitution, negative/zero denominators, mixed bases, split mismatch, corrupt snapshots, quota stops, and prompt injection. Actual generation ignores an injected source allocation/credential command. All published scenario values are independently replayed. Formal held-out evaluation remains M12; the authorized engineering review questions are recorded under M9.
