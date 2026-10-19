# M10 — Current Developments

Owner: Rylan Wade. The [milestone index](../README.md) owns status and order.

Current Developments reports dated events after each selected company's latest collected source date. Filings Research shares Tavily search for an official update to one specific filed statement. The application has five specialists. Prices, multiples and analyst forecasts are outside scope; Quant valuation is unsupported.

## Verified behavior

- The supervisor chooses live intent before execution. Negated acquisition and historical markers suppress it; verification wins over development triggers. Accounting terms and latest-collected-filing language stay historical. The [17-row routing fixture](../../../tests/fixtures/live_routing.json) checks exact worker sequences and price gaps without changing its expected values.
- Developments run last, after any Data, Quant, Risk or Research tasks. Verification selects Research with one general-topic search and no Current Developments task. Price-only requests have no worker; mixed supported clauses continue with the exact scope-gap message. All requests still require supported company/year scope.
- Current Developments owns W sources and post-anchor events. Research owns filed S explanations, Data reported F figures, Quant C calculations and Risk Summary filing comparisons. A live worker relates handed-off facts in one clause and does not duplicate earlier answers.
- The code derives each anchor from the maximum inventory `source_date`. Dates before or equal to the anchor are background; absent publication metadata does not establish a post-anchor event. Each selected company without a cited dated development remains a named missing output.
- W records contain company, URL, registrable-domain publisher, title, tier, publication/retrieval times, freshness, bounded text/hash, snapshot/tool/agent and inspection URL. The browser shows these labels, safe excerpts and an external source link. `/api/live/{snapshot_id}` checks snapshot hashes and returns scrubbed MCP evidence.

## MCP contract and limits

`tavily_search` is the shared Remote MCP tool on `tavily-mcp` 4.1.0 over Streamable HTTP. Runtime query-parameter authentication stays outside stored data, trace and image. Both workers emit `live_mcp` trace events with agent, server, tool, arguments, result count, snapshot, cache and outcome. Research reports filed content with S citations before an official W update. Third-party results do not establish an official update. [Architecture](../../architecture.md) owns the complete sharing rationale and contracts.

Current Developments has eight model calls, at most two searches and two single-URL extracts per request across all selected companies. Research verification has one search. Search uses basic depth, five results, no raw content and the discovered year time range; extract uses basic depth and a URL returned in that request. Search/extract cache lifetimes are six/24 hours. Refresh bypasses caching within the same budgets.

Every uncached call checks usage and reserves two credits before execution. Failures count. The monthly stop is 600 projected credits in a per-host SQLite ledger. A throttled usage read retains a verified monthly observation plus every subsequent local reservation and makes output partial; without a verified current-month floor, acquisition stops. Tavily's usage endpoint permits [10 requests per 10 minutes](https://docs.tavily.com/documentation/rate-limits). `LIVE_MODE` supports live, frozen and off; the key enables live by default. Environment paths are `LIVE_CACHE` and `LIVE_LEDGER`.

Official tiers use the selected issuer domains, sec.gov and registrable domains ending in .gov. Publication within 90 days is fresh, older evidence dated, and absent metadata undated. Current-status claims supported only by non-fresh W sources are partial. Unknown W citations become unverified-source markers. Search text is bounded to 1,000 characters; extraction stores at most 20,000 and supplies at most 6,000 to the model inside untrusted-content blocks.

## Acceptance — 2026-10-19

| Item | Result and evidence |
| --- | --- |
| 1. Regression and phase gates | 209 passed, zero failed; [tests](evidence/TESTS_2026-10-19.json) |
| 2. Direct worker | Real search/extraction and registered W sources; [direct](evidence/DIRECT_2026-10-19.json) |
| 3. Native application | All five required cases match worker plans, citations and terminal contracts; [application](evidence/APPLICATION_2026-10-19.json) |
| 4. Shared tool | Real searches from both agent contexts use the same server/tool; [sharing](evidence/SHARING_2026-10-19.json) |
| 5. Chromium | Both new examples run; W/S/C inspection in one session, safe external link and no stock buttons; [browser](evidence/BROWSER_2026-10-19.json) |
| 6. Linux container | Runtime-only key, real uncached search and extraction on refresh; [container](evidence/DOCKER_2026-10-19.json), [security scan](evidence/SECURITY_2026-10-19.json) |
| 7. Failures | Blank key, 429, timeout and off return partial and preserve earlier Data; [tests](evidence/TESTS_2026-10-19.json) |
| 8. Budget | Atomic reservations, conservative usage floor and monthly stop; [ledger](evidence/BUDGET_2026-10-19.json) |
| 9–10. Docs and removal | Local links, paths, coverage, compile and removal classifications; [checks](evidence/CHECKS_2026-10-19.json), [file manifest](evidence/FILES_2026-10-19.json) |
| 11. Transcript | One local M10 event is finalized after documentation; [acceptance metadata](evidence/ACCEPTANCE_2026-10-19.json) identifies the entry and its final read-only checks. |

```powershell
uv run --locked pytest -q
uv run --locked python scripts/demo_current.py --direct --output artifacts/current-direct.json
uv run --locked python scripts/demo_current.py --url http://127.0.0.1:8088 --output artifacts/current-app.json
uv run --locked python scripts/demo_current.py --browser --url http://127.0.0.1:8088 --output artifacts/current-browser.json
uv run --locked python scripts/start_local_container.py --live-mode live
uv run --locked python scripts/demo_current.py --url http://127.0.0.1:8084 --case nvda --refresh --output artifacts/current-container.json
```

## Evidence limits

Native, direct-worker, fixture, Chromium and Linux-container evidence are distinct; these runs do not establish Cloud Run or serving-provider behavior. Partial results retain dated third-party findings and identify missing publication dates or unavailable account usage. Publication metadata and source tier do not prove semantic truth. The SQLite monthly floor is per host; M13 decides cross-instance coordination. Coverage is limited to the four selected companies. Raw runs and cached snapshots stay in ignored `artifacts/`; the evidence links retain credential-free summaries.
