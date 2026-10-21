# M12 — Risk Summary live check: implement and compare

Owner: Rylan Wade. This milestone adds a candidate replacement for the Filings Research official-update use of the shared Tavily MCP tool, then compares both before Rylan Wade selects one. The [milestone index](../README.md) owns status and order.

## Outcome

Risk Summary checks whether a registered material risk change has materialized after the filing, using the same `tavily_search` tool as Current Developments. The existing Filings Research official-update check remains implemented and unchanged until Rylan Wade selects the more useful option. This is a candidate swap, not a deletion.

## Dependencies

- Precedes M13 evaluation so RAGAS measures the selected MCP design.
- M7 risk classifications, M10 shared Tavily gateway and ledger, and M11 routing.
- Available Tavily monthly credit; a frozen-replay comparison is acceptable when live credit is unavailable.

## Scope

- After `record_risk_change`, allow at most one `tavily_search` per registered added/changed change, anchored on the before/after S-cited pair and the post-filing window.
- Return dated, tier-labeled W evidence as post-filing context. W evidence never changes the filed classification and never replaces S evidence.
- Choose a trigger rule that keeps ordinary risk comparisons within the project's Tavily allowance; record it.
- Share the existing gateway, credential, ledger, scrubber and `node=live_mcp` trace; add Risk Summary as a permitted caller.

## Comparison and handoff

- Run both options on the same fixed cases: risk comparisons, official-update questions, and full five-agent workflows.
- Report per option: how often it triggers in normal requests, answer usefulness, citation/tier correctness, extra credits and latency, and whether a grader can see two agents sharing the tool in different contexts.
- Rylan Wade selects which use to keep. Only after that decision, remove or retain the other, and update architecture, README and tests.

## Acceptance checks

1. Real or frozen MCP calls from Risk Summary appear as `node=live_mcp` with `agent=Risk Summary`, `server=tavily-mcp`, `tool=tavily_search`.
2. Filed classifications and S citations are identical with the check on and off.
3. Extra credit use per request is reported; unavailable acquisition yields an explicit gap, not a failure.
4. The dated comparison report is stored under this milestone's `evidence/`.

## Decisions to verify

- Trigger rule: always for registered changes, only full workflows, or only when the request asks for current context.
- Whether official-tier evidence is required or attributed independent reporting suffices for "materialized".
