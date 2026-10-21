# M11 — Provider routing

Owner: Rylan Wade. The [milestone index](../README.md) owns status and order.

## Runtime and ownership

`GENERATION_PROFILE=codex` uses the authenticated local Codex app-server. `GENERATION_PROFILE=api` calls NVIDIA and Nebius directly; keys alone never enable this profile. API generation has no CLI or host-bridge fallback.

| Module | Responsibility |
| --- | --- |
| [generation.py](../../../src/generation.py) | Profile selection, invocation deadline, recovery, event stream |
| [generation_context.py](../../../src/generation_context.py) | Immutable request/activity IDs, phase, scope and evidence facts |
| [provider_models.py](../../../src/provider_models.py), [provider_policy.py](../../../src/provider_policy.py) | Named model identities and deterministic routing |
| [provider_client.py](../../../src/provider_client.py) | Fixed endpoints, price verification, bounded SSE/tool-call assembly |
| [generation_tools.py](../../../src/generation_tools.py) | JSON Schema validation, serial execution and completion budget |
| [provider_limits.py](../../../src/provider_limits.py) | Atomic local spending reservations and shared rate permits |

The supervisor supplies typed context through its bounded handler. Planner and reviewer receive their phase and activity explicitly. Each request owns its context; there are no mutable routing globals. Injectable streams remain usable by deterministic tests. Evidence validation, isolated Quant execution, citations and request review retain their existing owners.

The browser Models selector and optional HTTP `generation_profile` field select Codex or hosted generation per request. The server environment supplies the default. Both profiles emit the same model-route interface to activity details, retaining the exact models actually used. Concurrent selections remain isolated; the selector locks during streaming.

## Models and routing

Policy `m11-v2` identifies the serving organization separately from the publisher. Normal supported requests exercise two serving providers.

| Condition, in precedence order | Serving provider / model | Rationale |
| --- | --- | --- |
| Local capability shortcut | No generation | Implemented local facts |
| Request Planner | Nebius / `deepseek-ai/DeepSeek-V4-Flash-0731` | Reasoning model; planning errors cascade to every worker |
| Multiple companies/years, amendment conflict, mixed evidence kinds, or input bound over 64,000 | Nebius / DeepSeek | Larger evidence set or comparison |
| Assigned filing explanation, checked calculation, risk change, current development, reaction or official update | Nebius / DeepSeek | Grounded synthesis and tool orchestration |
| Other review and financial lookup | NVIDIA / `nvidia/nemotron-3.5-super-vl-120b-a12b` | Free grounded response and citation compliance |
| Other supported work | NVIDIA / Super | Free specialist synthesis |

DeepSeek replaces the earlier non-reasoning Qwen route and NVIDIA Lightning planner: the hosted full workflows remained partial on multi-step filing and risk work, and Lightning was not measured against a planner reference. DeepSeek V4 Flash is the lowest-priced Nebius reasoning model with tools and structured outputs ($0.14/M input, $0.28/M output). Super supplies narrow financial answers and simple review. Complex review is a separate DeepSeek invocation; independent review does not require another publisher.

Super disables thinking using `chat_template_kwargs.enable_thinking=false`, with a 2,048-token planner fallback cap and 4,096 otherwise. DeepSeek reasons; its `reasoning_content` is never streamed or replayed. Reasoning tokens count toward completion limits, so DeepSeek caps are 16,384 for planning and 32,768 otherwise. Acceptance calls use at most 3,882 completion tokens; the caps are a deliberate grading-reliability margin beyond expected use, bounded by invocation deadlines and spending reservations. The complete serialized history, schemas and tool results are bounded conservatively by UTF-8 bytes plus framing allowance before every continuation. Configured context ceilings are 1,024,000 for DeepSeek and 1,048,576 for Super; these are endpoint limits, not measured large-context accuracy. Oversized DeepSeek context can use Super once; evidence is never silently truncated.

Named function selection handles the sole structured/completion tool; multiple tools use automatic choice. Tool-bearing responses can finish with `stop`; actual tool calls take precedence over final prose. Fragments are assembled before validation; explicit JSON nulls for absent stream fields are treated as absent. Unknown tools, duplicate IDs, missing terminals and truncated output fail explicitly. Invalid arguments receive at most two corrections; omitted optional null fields are removed before validation. Required and undeclared fields retain validation.

Workers keep existing call budgets and the reserved `report_outcome` slot. Only final answer text streams as tokens; reasoning and tool arguments do not. Final composition preserves checked calculations when a filing explanation omits them.

Model inputs use assigned output descriptions; original questions remain available to the supervisor/reviewer. Completion reports require a separate round after the model reads retrieval results. An oversized batch receives correction feedback without partial execution. Verbatim long text already present in the original prompt is referenced by identity/hash in later tool messages; full text remains in the original prompt and inspection event. Distinct text is preserved.

A context-based selection before dispatch does not consume the HTTP recovery allowance. Recovery never selects a smaller endpoint when the complete context exceeds its verified limit.

## Recovery and inspectability

Each invocation permits at most one same-model retry for a transient failure, then one provider fallback, within its original deadline. Rejected streams record a fixed cause code, never provider text. HTTP 429 honors numeric/date `Retry-After` without holding a concurrency lease during backoff. Invalid credentials do not retry. Nebius accounting/availability stops can use free Super; transient Super failure can use guarded DeepSeek. Completed tool results stay in the conversation without replay. Recovery stops after visible answer text. Cancellation closes the transport and releases the concurrency lease.

Before each generation request, `provider_route` records request/activity/invocation IDs, provider, publisher, exact model, policy/rule/reason, task facts, input bound, output/context limits, maximum reserved cost and queue duration. Usage traces record tokens, request duration, answer TTFT and token-based cost. Missing usage remains unknown and retains its reservation. Final events include route summaries; activity details show actual model and selection reason. `GET /api/runtime` exposes the profile without credentials.

## Account limits and spending policy

**Scope:** the SQLite provider ledger is local development/testing infrastructure. The assignment requires working provider routing and inspectable decisions; it does not require a spending ledger. This ledger is not an assignment deliverable or an intended production component. M13 decides production spending controls separately; it does not inherit a requirement to build a distributed ledger. The $100 promotional no-overage constraint still applies wherever these credentials are used.

- NVIDIA's allowance is **40 RPM**, shared across models, workers, retries and local processes. SQLite serializes a sliding 60-second window, with at most two active requests per provider. Queue time counts toward the deadline. External account traffic is outside this limiter.
- Nebius promotional credit is **$100 total**. Paid overage and card charges are forbidden. The operational ceiling is $90, retaining a $10 buffer; the implementation campaign stops at $5 and an application request at $1. `NEBIUS_CAMPAIGN_USD` can lower the campaign cap.
- The user-confirmed starting balance is $100 at `2026-10-20T22:22:39Z`, with no displayed expiry. The cutoff is **2027-01-01T00:00:00Z**, or an earlier verified promo expiry. Pre-ledger probe reservations consume a further $0.105165 conservatively.
- A verified observation and exclusive tracked use establish the baseline. Observations expire after 24 hours. External/untracked account use requires reconciliation before paid calls. A key does not establish credit.
- Every Nebius attempt reserves a conservative input/output maximum before outbound acquisition. The verbose catalog must confirm DeepSeek's $0.14/M input and $0.28/M output prices and 1,024,000-token context snapshot. Missing/changing prices, stale/expired credit, unavailable accounting or unknown cost blocks paid acquisition.
- Reservations survive restart. Valid usage settles downward; failure, cancellation or missing usage retains the maximum. An over-bound settlement freezes Nebius. A fresh observation never resets consumption or raises an existing credit ceiling; unresolved reservations stay charged conservatively.
- Native and Docker acceptance share one mounted ledger. Do not delete it, run an independent ledger against this account, or use a detached copy. Stop processes before moving between native and Docker on Windows.
- These application controls do **not** disable Nebius card billing. Provider-side credit-only billing and automatic balance reads are unverified. Account-wide protection also requires controlled exclusive usage.
- SQLite coordinates local testing only. The current API profile fails closed when `K_SERVICE` identifies Cloud Run. M13 replaces that development gate only after choosing and verifying appropriate production spending controls, such as provider-enforced credit-only limits. No distributed ledger is assumed or required by the assignment.

## Provider dashboards

| Provider | Link | Purpose |
| --- | --- | --- |
| Nebius | [Token Factory](https://tokenfactory.nebius.com/) | Usage, promo balance, billing and transactions |
| Nebius | [Prices](https://tokenfactory.nebius.com/organization/prices) | Current model prices |
| Nebius | [API keys](https://tokenfactory.nebius.com/project/api-keys) | Create/revoke credentials |
| NVIDIA | [Build dashboard](https://build.nvidia.com/) | Catalog and account rate allowance |
| NVIDIA | [API keys](https://build.nvidia.com/settings/api-keys) | Create/revoke credentials |

[Nebius model API](https://docs.tokenfactory.nebius.com/api-reference/models/list-models) documents the verbose catalog. [Nebius billing](https://docs.tokenfactory.nebius.com/other-capabilities/billing-new) describes card charges. [NVIDIA access FAQ](https://forums.developer.nvidia.com/t/nvidia-nim-faq/300317) describes free developer/evaluation access. Developer access is not an unrestricted production-service commitment.

## Verification and handoff

[DeepSeek acceptance](evidence/DEEPSEEK_2026-10-20.json) records policy `m11-v2` on the native application with `LIVE_MODE=frozen`, after the defects below were fixed. Both full five-agent workflows complete Data, Quant, Risk Summary and Filings Research on DeepSeek with no provider fallback (131.6 s AMD, 140.2 s Qualcomm, $0.10–0.13 token cost each). Current Developments remains partial because frozen replay has no snapshots for model-written queries, so both requests are **partial**. Route cases: reported figures, filing explanation and Data → Quant → Research complete; amendment and risk comparison are partial on reviewer content judgments; missing scope and price requests return coverage gaps without generation.

Defects found by real DeepSeek runs and fixed, each with a regression test:

| Defect | Evidence | Fix |
| --- | --- | --- |
| Explicit JSON nulls in stream chunks | Every early fallback recorded `malformed_TypeError` | Null-tolerant parsing |
| Provider switch before retry | One failure removed DeepSeek for the invocation | Same-model retry first |
| Planner prescribed S citations to Financial Data | 1 of 6 reproductions cited unregistered `[S1]`; 0 of 6 after | Citation ownership in both prompts |
| String `"null"` in tool fields | Plan parsing failed; request lost planning and review | Shared schema-aware [`normalize`](../../../src/tool_arguments.py) at the hosted and Codex tool boundaries |
| Malformed arguments echoed in history | Direct probe: HTTP 400; sanitized echo: HTTP 200 | Echo `{}` and return the parse error |
| Constraints planned as outputs | "Filings only" became an unaddressed output | Planner prompt rule |

Rejected streams record a fixed cause code. Bracketed `(F1)`, `【F1】` and `[Source: F1]` resolve for registered IDs; bare labels remain uncited.

[Policy `m11-v1` evidence](evidence/ACCEPTANCE_2026-10-20.json) records the earlier Lightning/Super/Qwen routes: both full workflows partial with Research and Risk gaps, a completed filings-only Linux-container run (63.220 s), controlled model comparisons, real UI profile switching, source inspection and Stop. [Direct endpoint evidence](evidence/MODEL_READINESS_2026-10-20.json) covers that model set's streamed tool continuations.

Local Nebius accounting retains conservative uncertain cost: $2.441004 accounted with 18 unsettled reservations, inside the $5 campaign stop. The evidence records a dated starting observation and usage/reservations, not an API-read remaining balance. The application does not disable card billing. One run per case does not establish intermittent reliability; formal RAGAS and Cloud Run results remain pending.

The fixed [development cases](../../../tests/fixtures/provider_routes.json) cover reported figures, filing explanation, Data → Quant → Research, amendment, risk comparison, missing scope and unsupported prices. [Provider tests](../../../tests/test_providers.py) cover fragmented streams, structured arguments, terminal failures, credentials, retries without repeated tools, cancellation, atomic reservations, stale/expired balances, refresh without reset, shared rate limits and Cloud Run's closed gate. Ordinary tests block provider HTTP and isolate ledgers.

The [full-workflow cases](../../../tests/fixtures/provider_full_workflows.json) request every specialist for AMD and Qualcomm, including dated real MCP research. [Controlled comparisons](../../../scripts/compare_provider_models.py) run Super and DeepSeek on the same financial lookup and the same filing question. Comparison selection is confined to that development process; the normal client, tool validation and spending guards remain active.

M11 acceptance is an engineering check, not RAGAS or a general accuracy estimate. M12 owns the four required RAGAS metrics over a fixed vector-store-only set with web disabled; Data/Quant/current checks remain separate. M13 owns public deployment, production spending controls, cold/warm latency, concurrency and provider-access terms.
