# M9 — Supervisor cooperation

Owner: Rylan Wade. This milestone makes the LangGraph supervisor coordinate all five specialists according to the user's requested outputs and the evidence already gathered. The [milestone index](../README.md) owns status and order.

## Starting point and boundary

- The [current graph](../../architecture.md) has a scope supervisor and focused Research, Data, filing-input, and Quant paths. M7 adds Risk Summary; M8 adds Buy-Side Analyst with a bounded valuation route.
- Keep each specialist's distinct prompt and tools. M9 owns general task selection, evidence handoffs, and bounded recovery across them. M10 adds broader live research and shared MCP; M11 chooses generation providers.
- Requests remain self-contained. Do not claim durable conversation memory or silently broaden the company/year selection.

## Work to implement

- Define an inspectable task state: requested outputs, selected scope, required workers, completed outputs, registered evidence, missing inputs, retry/follow-up count, and terminal status. Document the state and transition rules in [architecture](../../architecture.md).
- Route a simple lookup to one worker. For mixed questions, order dependent work: Data before Quant; Risk before risk interpretation; market/estimate inputs before valuation; checked figures before final Research explanation. Avoid running every worker on every question.
- Pass typed source IDs, exact observations, calculation bundles, period/definition metadata, and unresolved needs between workers. A narrative worker can explain checked figures but cannot silently recalculate or change their basis. Each evidence source has one owner and remains inspectable in the final answer.
- Use worker outcomes to decide bounded follow-up. A missing structured figure may trigger the already supported filing extraction path; an unsupported metric stays missing. Cap turns/tool calls and prevent graph cycles. Worker exceptions or timeouts lead to a useful partial result when trusted evidence exists.
- Trace task selection, route reason, handoff, actual tool/worker outcome, follow-up reason, and final status through SSE. Keep request state isolated under concurrent turns and cancellation.

## Acceptance evidence

1. Test representative single-worker and mixed requests: a filing explanation; exact GAAP figures; a numerical comparison with explanation; risk changes with financial context; a valuation brief using reported numbers and current evidence. Show that each calls only the needed workers.
2. Inspect one full five-specialist trace and at least one shorter path. Verify source/calculation IDs, fiscal dates, and checked values survive each handoff and the browser opens them.
3. Inject a worker timeout, unavailable source, unsupported year, missing estimate, and conflicting observation. Assert bounded termination and an honest partial/gap/clarification rather than a graph crash or fabricated output.
4. Run direct worker checks, graph fixtures for transitions and failure paths, live application/browser questions, and local Docker acceptance. Retain dated traces and commands under `evidence/`; keep formal trajectory scoring for M12.

Try: “For Qualcomm FY2024–FY2025, compare revenue and margins, explain management's drivers and risk changes, and tell me what valuation evidence is missing.” Resolve exact state schema and follow-up budget from working M7/M8 traces before freezing the routing policy.
