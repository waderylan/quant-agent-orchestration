# M11 — Provider routing

Owner: Rylan Wade. The [milestone index](../README.md) owns status and order.

## Runtime and ownership

`GENERATION_PROFILE=codex` uses the authenticated local Codex app-server. `GENERATION_PROFILE=api` calls NVIDIA and Nebius directly; keys alone never enable this profile. API generation has no CLI or host-bridge fallback.

| Module | Responsibility |
| --- | --- |
| [generation.py](../../../src/generation.py) | Profile selection, invocation deadline, recovery, event stream |
| [generation_context.py](../../../src/generation_context.py) | Immutable request/activity IDs, phase, scope and evidence facts |
| [provider_models.py](../../../src/provider_models.py), [provider_policy.py](../../../src/provider_policy.py) | Named model identities and deterministic routing |
| [provider_client.py](../../../src/provider_client.py) | Fixed endpoints, bounded SSE/tool-call assembly, failure cause codes |
| [generation_tools.py](../../../src/generation_tools.py) | JSON Schema validation, serial execution and completion budget |
| [provider_limits.py](../../../src/provider_limits.py) | NVIDIA rate pacing and recorded usage; no spend stops |

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

DeepSeek V4 Flash handles planning and multi-step evidence work because it reasons before acting; it is the lowest-priced Nebius reasoning model with tools and structured outputs ($0.14/M input, $0.28/M output). Super supplies narrow financial answers and simple review. Complex review is a separate DeepSeek invocation; independent review does not require another publisher.

Super disables thinking using `chat_template_kwargs.enable_thinking=false`, with a 2,048-token planner fallback cap and 4,096 otherwise. DeepSeek reasons; its `reasoning_content` is never streamed or replayed. Reasoning tokens count toward completion limits, so DeepSeek caps are 16,384 for planning and 32,768 otherwise. Acceptance calls use at most 3,882 completion tokens; the caps are a deliberate grading-reliability margin beyond expected use, bounded by invocation deadlines. The complete serialized history, schemas and tool results are bounded conservatively by UTF-8 bytes plus framing allowance before every continuation. Configured context ceilings are 1,024,000 for DeepSeek and 1,048,576 for Super; these are endpoint limits, not measured large-context accuracy. Oversized DeepSeek context can use Super once; evidence is never silently truncated.

Named function selection handles the sole structured/completion tool; multiple tools use automatic choice. Tool-bearing responses can finish with `stop`; actual tool calls take precedence over final prose. Fragments are assembled before validation; explicit JSON nulls for absent stream fields are treated as absent. Unknown tools, duplicate IDs, missing terminals and truncated output fail explicitly. Invalid arguments receive at most two corrections; omitted optional null fields are removed before validation. Required and undeclared fields retain validation.

Workers keep existing call budgets and the reserved `report_outcome` slot. Only final answer text streams as tokens; reasoning and tool arguments do not. Final composition preserves checked calculations when a filing explanation omits them.

Model inputs use assigned output descriptions; original questions remain available to the supervisor/reviewer. Completion reports require a separate round after the model reads retrieval results. An oversized batch receives correction feedback without partial execution. Verbatim long text already present in the original prompt is referenced by identity/hash in later tool messages; full text remains in the original prompt and inspection event. Distinct text is preserved.

A context-based selection before dispatch does not consume the HTTP recovery allowance. Recovery never selects a smaller endpoint when the complete context exceeds its verified limit.

## Recovery and inspectability

Every model call is an invocation with its own deadline. Before the first request, a call whose complete context exceeds DeepSeek's window goes to Super instead; context larger than both endpoints fails without truncating evidence. After dispatch, failures are handled as follows:

| Failure | Result |
| --- | --- |
| Any NVIDIA failure: HTTP error (including 429, 401/403, 404 and 5xx), connection or read timeout, malformed or truncated stream, missing key | The call moves to DeepSeek immediately, with no NVIDIA retry. If the context is too large for DeepSeek, a transient failure retries Super once instead |
| Local NVIDIA pacing window full (40 requests/minute or two active requests) | The call moves to DeepSeek instead of waiting; if the context is too large for DeepSeek, it waits for a pacing slot |
| DeepSeek transient failure: HTTP 429, 5xx, connection or read timeout | One retry on DeepSeek after `Retry-After` (numeric or date) or 0.5 s; if it fails again, the call moves to Super, or fails if it already moved from NVIDIA |
| DeepSeek non-transient failure: malformed or truncated stream, other HTTP error, missing key | The call moves to Super |
| DeepSeek invalid credentials (401/403) | The call fails; no retry or provider change |
| Failure after answer text has streamed | The call fails; visible text is never replaced by another model |
| Both providers fail for one call | The call fails. A failed worker is recorded as failed while earlier verified findings remain; a failed planner leaves rule-based routing with a coverage gap; a failed review prevents a complete result |

Each invocation changes provider at most once and retries at most once, so it makes at most three provider attempts. Completed tool results stay in the conversation and are never re-executed. The HTTP client allows 10 seconds to connect and 65 seconds between received bytes; a response that keeps streaming past the invocation deadline fails that invocation. Cancellation closes the transport and releases the pacing lease.

Rejected streams record a fixed cause code (for example `malformed_TypeError` or `finish_length`), never provider response text. `provider_retry` and `provider_fallback` trace events name the failed provider, the cause and the replacement model; activity details list every model a call used.

Before each generation request, `provider_route` records request/activity/invocation IDs, provider, publisher, exact model, policy/rule/reason, task facts, input bound, output/context limits, maximum possible cost and queue duration. Usage traces record tokens, request duration, answer TTFT and token-based cost. Missing usage is recorded as unknown cost. Final events include route summaries. `GET /api/runtime` exposes the profile without credentials.

## Account limits and usage

No code blocks provider or Tavily spend. Credit limits are operating instructions in [AGENTS.md](../../../AGENTS.md); the hosted profile runs wherever its keys are present, including Cloud Run.

- **Nebius:** $100 promotional credit, received by Rylan Wade at a Nebius networking event during LA Tech Week. The application does not disable card billing; keep total use well below the credit and check the [dashboard](https://tokenfactory.nebius.com/) before large runs.
- **NVIDIA:** 40 requests per minute, shared across models, workers and local processes. A SQLite sliding window paces calls with at most two active NVIDIA requests. Reaching the window reroutes the call to DeepSeek instead of queueing.
- **Tavily:** Rylan Wade allows 2,000 credits for this project. Uncached calls are recorded at an estimated two credits each.
- **Usage record:** `scripts/providers.py` reports recorded calls and token-estimated cost per provider; `UsageLedger` records Tavily calls. Missing provider usage is recorded as unknown cost. Records are per host and provide visibility only.

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

[DeepSeek acceptance](evidence/DEEPSEEK_2026-10-20.json) records policy `m11-v2` on the native application with `LIVE_MODE=frozen`. Both full five-agent workflows complete Data, Quant, Risk Summary and Filings Research on DeepSeek with no provider fallback (131.6 s AMD, 140.2 s Qualcomm, $0.10–0.13 token cost each). Current Developments is partial because frozen replay has no snapshots for model-written queries, so both requests are **partial**. Route cases: reported figures, filing explanation and Data → Quant → Research complete; amendment and risk comparison are partial on reviewer content judgments; missing scope and price requests return coverage gaps without generation. One run per case does not establish intermittent reliability; formal RAGAS and Cloud Run results are pending. Each evidence file records the configuration it tested.

Provider-boundary behavior covered by regression tests:

| Behavior | Protects against |
| --- | --- |
| Explicit JSON nulls in stream chunks are treated as absent | Parser failure on every DeepSeek tool round |
| Transient DeepSeek failures retry the same model before changing provider | One hiccup dropping the reasoning model for the call |
| Financial Data cites only its own F identifiers; the planner describes content, not citation types | Unregistered `[S1]` citations failing the Data worker |
| A shared schema-aware [`normalize`](../../../src/tool_arguments.py) turns `"null"`/`"none"` into absent values at the hosted and Codex tool boundaries | Plans and tool calls rejected for string nulls |
| Malformed tool arguments are echoed as `{}` while the parse error returns to the model | Nebius HTTP 400 on the next request |
| Constraints such as "filings only" restrict outputs rather than becoming outputs | False partial results |
| Bracketed `(F1)`, `【F1】` and `[Source: F1]` resolve for registered IDs; bare labels stay uncited | Valid citations rejected for bracket style |

The fixed [development cases](../../../tests/fixtures/provider_routes.json) cover reported figures, filing explanation, Data → Quant → Research, amendment, risk comparison, missing scope and unsupported prices. [Provider tests](../../../tests/test_providers.py) cover fragmented streams, structured arguments, terminal failures, credentials, retries without repeated tools, NVIDIA failure and pacing reroutes to DeepSeek, cancellation, shared rate pacing and recorded usage. Ordinary tests block provider HTTP and isolate ledgers.

The [full-workflow cases](../../../tests/fixtures/provider_full_workflows.json) request every specialist for AMD and Qualcomm, including dated real MCP research. [Controlled comparisons](../../../scripts/compare_provider_models.py) run Super and DeepSeek on the same financial lookup and the same filing question. Comparison selection is confined to that development process; the normal client and tool validation apply.

M11 acceptance is an engineering check, not RAGAS or a general accuracy estimate. M13 owns the four required RAGAS metrics over a fixed vector-store-only set with web disabled; Data/Quant/current checks remain separate. M14 owns public deployment, cold/warm latency, concurrency and provider-access terms.
