# M8 — Buy-Side Analyst

Owner: Rylan Wade. This milestone adds a sourced public-equity valuation brief: dated multiples, qualified peer comparisons, explicit upside/downside scenarios, supporting and opposing evidence, and visible missing inputs. The [milestone index](../README.md) owns status and order.

## Dependencies and boundary

- Reuse M5 Financial Data, M6 independently checked Quant and artifacts, M7 risk evidence, and the request-local LangGraph state. Implement the bounded route and handoffs needed for valuation. M9 generalizes cooperation across all five specialists.
- Start with NVDA, AMD, INTC, and QCOM. The historical [corpus windows](../../project.md) do not establish latest-report or current-price coverage. Acquire and label any newer financial period separately.
- Use local subscription generation for direct-role and application tests. M10 extends current research and shared MCP across other workers; M11–M13 cover deployment providers and cloud acceptance.

## Selected MCP sources

| Source | Purpose | Must verify under the actual account |
| --- | --- | --- |
| [Twelve Data official MCP](https://github.com/twelvedata/mcp) | Dated price snapshots and eligible price history | Four tickers, currency, timestamp/timezone, market session, feed/delay, split adjustments, quota, and display rights |
| [Alpha Vantage official MCP](https://github.com/alphavantage/alpha_vantage_mcp) | EPS/revenue estimates, financial and share inputs | Four tickers, fiscal horizon, analyst count/as-of data, GAAP versus adjusted basis, actual free/student entitlement, and quota |
| [Tavily Remote MCP](https://docs.tavily.com/documentation/mcp) | Recent guidance, earnings news, and outside evidence | Real tool discovery/calls, publication and retrieval dates, bounded usage, and the student credits Rylan Wade reports |

[Market-data research](../../research/market-data.md) compares alternatives and access limits. Prefer official MCP implementations; prove initialization, tool discovery, and real tool calls through the application. An ordinary HTTP function is not MCP acceptance. Tavily uses the assignment's Streamable HTTP pattern with the API key in the endpoint query parameter; redact that URL from traces. Use read-only tool allowlists, scoped symbols, timeouts/call budgets, rate-limit handling, dated frozen snapshots, and explicit cache freshness. Keep keys in ignored configuration. Confirm public-coursework display rights before deployment. If a selected source lacks a needed entitlement, show the affected output as missing and resolve access or scope before claiming acceptance.

## Distinct worker and calculation ownership

- Buy-Side Analyst gets its own prompt and market/estimate inspection tools. It chooses eligible peers and periods, states assumptions, requests checked calculations, and explains a premium or discount. It does not perform unverified arithmetic in prose.
- Financial Data supplies reported GAAP observations; Filings Research supplies disclosure context; Risk Summary supplies cited changes. Quant extends its validator for valuation formulas and freezes every input, assumption, calculation, table, and chart in a replayable bundle.
- The supervisor traces each handoff. A quote lookup can finish with one worker; a valuation explanation invokes only the needed specialists. Preserve `complete`, `partial`, `needs_clarification`, and `coverage_gap` outcomes.

## Valuation contract

- Support trailing and forward P/E, EV/revenue, EV/EBITDA, and free-cash-flow yield **when each required input and definition is verified**. Show formulas and exclude loss/zero denominators. A price divided by FY2025 EPS is labeled an FY2025 multiple unless current trailing results are built from compatible periods.
- Match quote date, share count and dilution, cash/debt dates, currencies, accounting basis, fiscal horizon, and split treatment. Define EV, EBITDA, and free-cash-flow conventions before using them. Separate reported GAAP values, analyst consensus, management guidance, user assumptions, and labeled analytical judgments.
- Compare peers with actual fiscal dates, growth, margins, cash conversion, business mix, and risks. Give the strongest counterargument to a premium/discount claim; a low multiple alone is not a fair-price conclusion.
- Build an EPS/multiple sensitivity grid and implied-price/upside/downside scenarios from explicit assumptions. Keep scenarios conditional, source-linked, and reproducible. Historical multiples and price-versus-earnings attribution require compatible adjusted history; otherwise return a partial result.
- Return a brief, peer table, scenario chart, calculation/source inspection, and missing-input list. Trading, personalized portfolio advice, autonomous alerts, and a general DCF engine are outside this increment.

## Acceptance evidence

1. Record real discovery and calls for all three MCP servers, credential-free response metadata, quota/failure behavior, and four-company quote/estimate identity checks. Reject sample-symbol substitution and stale or ambiguous observations.
2. Independently recompute every published eligible multiple and one company sensitivity grid from frozen source values. Replay the bundle and verify formulas, units, periods, hashes, chart/table consistency, and loss/zero/missing exclusions.
3. Run a direct Buy-Side role test, a full LangGraph/API turn, browser source/chart/download checks, and local container acceptance. Keep fixture, real MCP, generation, browser, and Docker evidence distinct.
4. Exercise unavailable estimates, incompatible GAAP/adjusted bases, closed markets, stale quotes, splits, 429/quota exhaustion, timeout, malformed data, contradictory sources, and retrieved prompt injection. The answer preserves useful checked findings and names the gaps.

Try: “Compare the four companies' trailing and next-fiscal-year P/E, then explain the premium after growth and cash generation”; “What happens to Qualcomm's implied value if estimated EPS falls 10% and its multiple contracts to 18×?”; and “What evidence supports or challenges AMD's valuation premium?” Decide exact source schemas, cache age, call budget, replay fixtures, and tolerances from real responses. Record those decisions and actual results in this page and `evidence/`; formal held-out evaluation belongs to M12.
