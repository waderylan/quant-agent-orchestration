# M8 — Buy-Side Analyst

Owner: Rylan Wade. The [milestone index](../README.md) owns status.

Buy-Side Analyst centers stock research on the companies selected in the controls: dated prices, available valuation references, analyst expectations, peer comparisons and counterarguments. Its distinct prompt and tools inspect market/estimate evidence and request Quant calculations. Ordinary stock questions do not require hypothetical inputs. Source-reported multiples remain labeled references when their date or basis is unspecified; they do not become verified current comparisons.

Each acquisition plan allows at most four quotes, four estimate calls, and one narrow basic Tavily search. Quote-only requests use one worker. Explicit user EPS/multiple scenarios are optional and do not require consensus; web evidence is acquired for broader valuation or explicitly requested recent/supporting/opposing evidence. Explicit quote, consensus and web exclusions constrain acquisition. Model tools inspect acquired evidence and cannot expand web searches. Explicit quote/estimate refresh requests bypass freshness caches within the same work budgets.

## MCP access and entitlements

The application uses official Twelve Data MCP over stdio, pinned to commit `d139a77ea0f7d40995e6979cd09c22dd142fbfe8`, official Alpha Vantage Remote MCP, and Tavily Remote MCP over Streamable HTTP with runtime credentials. Every live data call initializes the server, discovers the requested tool, and invokes `tools/call`. URLs containing credentials and account emails are scrubbed before persistence or trace emission. Docker contains the pinned official server but no credentials or CLI login.

Actual account probes on 2026-10-16 establish:

| Account/source | Returned evidence | Limits established by the response |
| --- | --- | --- |
| Twelve Yahoo | Four matching quotes; usage `plan_limit=800` | Statistics, earnings, and splits return plan restrictions. Feed/delay and plan name are not supplied. |
| Twelve Gmail | Sequential NVDA quote and usage audit; `plan_limit=800` | The same three datasets are restricted. Yahoo is restored after the diagnostic audit; no production quota fallback occurred. |
| Alpha Vantage | Four matching annual estimate responses; QCOM earnings and income statement | Company Overview is restricted. Balance sheet and cash flow are previews. Estimate GAAP/adjusted basis, dilution, currency, consensus as-of, split basis, and exact fiscal-date reconciliation remain unverified. |
| Tavily | Real discovery and basic searches through the analyst/application | Usage endpoint verifies Researcher and a 1,000-credit monthly account cap; the ledger records observed usage and the conservative projection. Search responses omit charge counts, so the ledger reserves two credits per basic call. |

Public display is not accepted. [Twelve Data terms §§2.2–2.4](https://twelvedata.com/terms) require explicit external-display rights; [Alpha Vantage terms](https://www.alphavantage.co/terms_of_service/) limit the default license to personal use. These accounts have no verified public-coursework redistribution authorization. Private local browser checks do not establish deployment rights. Cloud Run disables market data unless display rights are explicitly configured as confirmed. No plan was purchased or upgraded.

## Evidence and arithmetic

Quotes preserve symbol, currency, UTC price timestamp, closed/open session, provider trading date, retrieval time, and unspecified feed/delay. A newer extended-session observation uses its own price and timestamp together. Open-market observations older than 20 minutes and closed-market observations older than four days are stale. Quotes cache for 15 minutes; other responses cache for 24 hours. Frozen replay retains original dates and is labeled as replay. Full-metadata checksums protect immutable snapshots; request-cache pointers are separate.

If quote-only synthesis emits empty text or invalid source references, the worker discards that prose and renders validated quote fields with registered citations. The trace records recovery without another provider call. Valuation prose and calculations retain strict citation validation.

Unqualified consensus stays visible with its provider period and analyst count, but does not enter verified forward P/E. Historical annual earnings never become current TTM. Missing shares, cash/debt dates, split reconciliation, and EBITDA/FCF definitions exclude affected multiples. Quant supports qualified P/E, forward P/E, EV/revenue, EV/EBITDA, and positive FCF yield. EV is equity value plus total debt less cash equivalents; FCF is operating cash flow less capital expenditures. Nonpositive denominators and incompatible currencies, periods, dilution, or accounting/split bases fail validation.

Explicit user EPS and multiple assumptions support a conditional scenario even when consensus is unqualified. The default horizon is 12 months; an explicit alternative is preserved. Assumptions bind to each named issuer and its local horizon. Ambiguous bindings and foreign-currency grids without a conversion basis require clarification. `EPS grid: 8, 10, 12; P/E grid: 16, 18, 20` specifies a bounded 3×3 grid. A hypothetical-only request that excludes market inputs makes no provider calls. Quant executes the arithmetic in the isolated runner, independently recomputes results and actual input lineage, and freezes CSV/PNG/code/ledger bundles. Valuation-v2 replay also checks units, denominator-owned periods, basis, horizon and formula. Hypothetical EPS has no invented fiscal year. The analyst cites checked calculations, supplies supporting and opposing evidence, and names missing inputs; personalized portfolio instructions remain outside scope.

Whole-month horizons preserve explicit month/year intervals up to 100 years. Unsupported grid notation, excessive axis lengths and repeated ambiguous issuer assumptions are rejected before either axis is registered. Currency suffixes cannot silently relabel foreign EPS as USD. Quant returns the actual artifact URLs to the analyst; a published chart/CSV fulfills an artifact request without another file-creation tool.

One SQLite ledger reserves all live calls before execution, including failures, browser tests and account audits. Twelve Data uses one active account with no overlapping calls across keys; only a demonstrated provider daily exhaustion permits automatic fallback. Tavily usage is checked before uncached searches, with a monotonic conservative projection that includes locally reserved credits despite lagging dashboard readings. The current credential-free [usage ledger](evidence/PROVIDER_USAGE_LEDGER.json) owns work totals; account quotas are separate from these work budgets.

## Verification

[M8 acceptance](evidence/M8_ACCEPTANCE_2026-10-16.json) separates real account probes, actual direct-role generation, graph/API requests, native Chromium, Docker, and synthetic failures. The Docker API refresh performs real quote and estimate MCP calls; application searches establish Tavily access. Browser checks open citations and calculation inputs, render charts, and download bundles. Synthetic cases cover stale/closed prices, missing estimates, symbol substitution, negative/zero denominators, mixed bases, split mismatch, corrupt snapshots, quota stops, and prompt injection. Actual generation ignores an injected source allocation/credential command. All published scenario values are independently replayed. Formal held-out evaluation remains M12; the authorized engineering review questions are recorded under M9.

[Review integration evidence](evidence/MCP_REVIEW_2026-10-16.json) records additional real MCP application calls, four-issuer scenarios, mixed five-specialist requests, direct workers and browser/container checks. Acquisition metadata identifies live versus cached evidence. A successful uncached acquisition satisfies a refresh request; model synthesis cannot silently acquire another quote. Completeness follows requested outputs rather than unsolicited peer valuations.

[Selected-company stock review](evidence/STOCK_RESEARCH_REVIEW_2026-10-16.json) records the stock-overview and capability-question checks, discovered artifact handoff failure and identical-question retest. Reusable questions are in [the fixture](../../../tests/fixtures/buy_side_review.json); reproduction commands are in the [root README](../../../README.md). Browser evidence distinguishes replayed answers from actual model generation and fresh provider acquisition. These engineering checks do not establish formal investment-answer accuracy or provider quality scores.
