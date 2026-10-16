# M11 — Provider routing

Owner: Rylan Wade. This milestone routes real generation across two distinct serving providers under an inspectable cost/capability policy. The [milestone index](../README.md) owns status and order.

## Provider decision and boundary

- Nebius Token Factory is the selected first serving provider. NVIDIA-hosted NIM is the tentative second; verify current model IDs, availability, account limits, API behavior, and prices before binding it. If NVIDIA cannot serve ordinary supported requests, document the evidence and choose an accessible second provider with Rylan Wade before accepting the milestone.
- The local Codex app-server route remains a separate development profile. An OpenAI-compatible client talking to Nebius does not make OpenAI the serving provider. Record serving provider, model publisher, model ID, and client library separately.
- M11 verifies local runtime calls and routing. M13 packages the deployment profile for Cloud Run and repeats checks against the public service. Do not route deployment traffic through the host Codex bridge or local CLI login.

## Work to implement

- Introduce a generation interface that preserves the existing worker contract: dynamic tools, token streaming, cancellation, timeouts, usage metadata, and explicit terminal errors. Adapt each chosen provider without changing evidence IDs or tool semantics.
- Choose a documented routing rule based on task needs and measured capability/cost. For example, a short source lookup and a multi-step synthesis can take different routes when verified models support them. Do not assign every normal request to one provider or call a second provider only in a contrived test.
- Put the route decision in request state and SSE trace: selected provider/model, reason, estimated or observed cost/usage, and any fallback. Provider failure may trigger one bounded fallback only if the same tool/evidence contract remains intact; otherwise return an explicit partial/failed result.
- Keep keys in ignored environment or secret files. Redact provider requests and errors before persistence or display. Bound retries, concurrency, context size, and spend; preserve request cancellation and source checks.

## Acceptance evidence

1. Demonstrate actual successful generation and tool use on both serving providers under ordinary supported questions. Record the selected route and reason in both API trace and browser; show two distinct serving organizations, not just two model names.
2. Compare each route on the same small, source-checked question set: answer validity, citation/calculation checks, latency, token use, and dated price estimate. Keep local Codex results labeled separately.
3. Test invalid credentials, provider timeout, rate limit, malformed tool call, cancellation, and fallback. Assert no secret leaks, orphaned processes, unverified final answer, or endless retries.
4. Run focused adapter/routing tests, real local application turns, and a container profile with credentials injected at run time. Update [architecture](../../architecture.md) with provider roles, routing dimensions, trace fields, and measured limits; retain credential-free evidence under `evidence/`.

Resolve exact models, thresholds, and budget from observed access and measured cases. The [assignment](../../reference/assignment/Assignment_2_Description.md) requires two providers exercised in normal supported use and a visible rationale; configuration alone is insufficient.
