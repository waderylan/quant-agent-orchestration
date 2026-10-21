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

Policy `m11-v1` identifies the serving organization separately from the publisher. Normal supported requests exercise two serving providers.

| Condition, in precedence order | Serving provider / model | Rationale |
| --- | --- | --- |
| Local capability shortcut | No generation | Implemented local facts |
| Request Planner | NVIDIA / `nvidia/nemotron-3.5-lightning-30b-a3b` | Small free model for bounded structured decomposition |
| Multiple companies/years, amendment conflict, mixed evidence kinds, or input bound over 64,000 | Nebius / `Qwen/Qwen3-235B-A22B-Instruct-2507` | Larger evidence set or comparison |
| Assigned filing explanation, checked calculation, risk change, current development, reaction or official update | Nebius / Qwen | Grounded synthesis and tool orchestration |
| Other review and financial lookup | NVIDIA / `nvidia/nemotron-3.5-super-vl-120b-a12b` | Free grounded response and citation compliance |
| Other supported work | NVIDIA / Super | Free specialist synthesis |

Lightning is confined to planning: real financial answers intermittently omit required citation brackets. Super supplies narrow financial answers. Complex review is a separate Qwen invocation; independent review does not require another publisher.

Both NVIDIA routes disable thinking using `chat_template_kwargs.enable_thinking=false`. The planner has a 2,048-token output cap; other calls have 4,096. The complete serialized history, schemas and tool results are bounded conservatively by UTF-8 bytes plus framing allowance before every continuation. Configured context ceilings are 262,144 for Lightning/Qwen and 1,048,576 for Super; these are endpoint limits, not measured large-context accuracy. Oversized Qwen context can use Super once; evidence is never silently truncated.

Named function selection handles the sole structured/completion tool; multiple tools use automatic choice. Tool-bearing Qwen responses can finish with `stop`; actual tool calls take precedence over final prose. Fragments are assembled before validation. Unknown tools, duplicate IDs, missing terminals and truncated output fail explicitly. Invalid arguments receive at most two corrections; omitted optional null fields are removed before validation. Required and undeclared fields retain validation.

Workers keep existing call budgets and the reserved `report_outcome` slot. Only final answer text streams as tokens; reasoning and tool arguments do not. Final composition preserves checked calculations when a filing explanation omits them.

Model inputs use assigned output descriptions; original questions remain available to the supervisor/reviewer. Completion reports require a separate round after the model reads retrieval results. An oversized batch receives correction feedback without partial execution. Verbatim long text already present in the original prompt is referenced by identity/hash in later tool messages; full text remains in the original prompt and inspection event. Distinct text is preserved.

A context-based selection before dispatch does not consume the HTTP recovery allowance. Recovery never selects a smaller endpoint when the complete context exceeds its verified limit.

## Recovery and inspectability

Each invocation permits one recovery: one retry or one provider fallback, within its original deadline. HTTP 429 honors numeric/date `Retry-After` without holding a concurrency lease during backoff. Invalid credentials do not retry. Nebius accounting/availability stops can use free Super; transient Super failure can use guarded Qwen. Completed tool results stay in the conversation without replay. Recovery stops after visible answer text. Cancellation closes the transport and releases the concurrency lease.

Before each generation request, `provider_route` records request/activity/invocation IDs, provider, publisher, exact model, policy/rule/reason, task facts, input bound, output/context limits, maximum reserved cost and queue duration. Usage traces record tokens, request duration, answer TTFT and token-based cost. Missing usage remains unknown and retains its reservation. Final events include route summaries; activity details show actual model and selection reason. `GET /api/runtime` exposes the profile without credentials.

## Account limits and spending policy

**Scope:** the SQLite provider ledger is local development/testing infrastructure. The assignment requires working provider routing and inspectable decisions; it does not require a spending ledger. This ledger is not an assignment deliverable or an intended production component. M13 decides production spending controls separately; it does not inherit a requirement to build a distributed ledger. The $100 promotional no-overage constraint still applies wherever these credentials are used.

- NVIDIA's allowance is **40 RPM**, shared across models, workers, retries and local processes. SQLite serializes a sliding 60-second window, with at most two active requests per provider. Queue time counts toward the deadline. External account traffic is outside this limiter.
- Nebius promotional credit is **$100 total**. Paid overage and card charges are forbidden. The operational ceiling is $90, retaining a $10 buffer; the implementation campaign stops at $5 and an application request at $1. `NEBIUS_CAMPAIGN_USD` can lower the campaign cap.
- The user-confirmed starting balance is $100 at `2026-10-20T22:22:39Z`, with no displayed expiry. The cutoff is **2027-01-01T00:00:00Z**, or an earlier verified promo expiry. Pre-ledger probe reservations consume a further $0.105165 conservatively.
- A verified observation and exclusive tracked use establish the baseline. Observations expire after 24 hours. External/untracked account use requires reconciliation before paid calls. A key does not establish credit.
- Every Nebius attempt reserves a conservative input/output maximum before outbound acquisition. The verbose catalog must confirm Qwen's $0.20/M input and $0.60/M output prices and context snapshot. Missing/changing prices, stale/expired credit, unavailable accounting or unknown cost blocks paid acquisition.
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

[Acceptance evidence](evidence/ACCEPTANCE_2026-10-20.json) separates native application, browser, controlled model comparison and Linux-container runs. Real UI switching uses the same activity details for Codex and hosted model names, with source inspection and Stop checked.

The two concurrent full requests invoke Data, Quant, Risk, Research and Current Developments under normal hosted routing. Both remain **partial**. Data and Quant complete in both; Qualcomm risk comparison completes, while filed explanation coverage remains insufficient. AMD's risk classification remains unverified and live acquisition reaches the existing Tavily monthly stop. The capture has 16 successful source inspections and one replayed three-calculation bundle. No passing full-workflow quality result is claimed. Remaining acceptance work includes these model/evidence gaps and budget-safe live/frozen verification before accepting M11 or beginning M12.

The final filings-only Linux check completes Data → Quant → Research and independent review in 63.220 seconds using NVIDIA and Nebius. All five cited sources inspect successfully and its calculation bundle replays. This runtime retains the independent Quant brief during review repair and exposes handler limits in tool schemas. The evidence distinguishes its working-tree version from the earlier concurrent full-workflow image.

Controlled same-input comparisons complete on both candidate pairs. Lightning/Super financial-worker times are 4.424/4.528 seconds; Super/Qwen filing-worker times are 19.232/42.546 seconds. A single small comparison does not establish Qwen superiority or general accuracy. The route remains a capability policy with measured compatibility limits, rather than a model-quality ranking.

Local Nebius accounting retains conservative uncertain cost and stays below the promotional operational limits. The evidence records a dated starting observation and usage/reservations, not an API-read remaining balance. The application does not disable card billing. Current formal RAGAS and Cloud Run results remain pending.

[Direct endpoint evidence](evidence/MODEL_READINESS_2026-10-20.json) records streamed tool continuations and usage on all three selected models, plus unavailable endpoint diagnostics. It is separate from application acceptance.

The fixed [development cases](../../../tests/fixtures/provider_routes.json) cover reported figures, filing explanation, Data → Quant → Research, amendment, risk comparison, missing scope and unsupported prices. [Provider tests](../../../tests/test_providers.py) cover fragmented streams, structured arguments, terminal failures, credentials, retries without repeated tools, cancellation, atomic reservations, stale/expired balances, refresh without reset, shared rate limits and Cloud Run's closed gate. Ordinary tests block provider HTTP and isolate ledgers.

The [full-workflow cases](../../../tests/fixtures/provider_full_workflows.json) request every specialist for AMD and Qualcomm, including dated real MCP research. [Controlled comparisons](../../../scripts/compare_provider_models.py) run Lightning/Super on the same financial lookup and Super/Qwen on the same filing question. Comparison selection is confined to that development process; the normal client, tool validation and spending guards remain active.

M11 acceptance is an engineering check, not RAGAS or a general accuracy estimate. M12 owns the four required RAGAS metrics over a fixed vector-store-only set with web disabled; Data/Quant/current checks remain separate. M13 owns public deployment, production spending controls, cold/warm latency, concurrency and provider-access terms.
