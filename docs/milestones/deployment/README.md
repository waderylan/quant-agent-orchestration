# M13 — Deployment and submission

Owner: Rylan Wade. This milestone turns the verified local application into a public Cloud Run service, repeats acceptance against the deployed runtime, and assembles the assignment deliverables. The [milestone index](../README.md) owns status and order.

## Release inputs

- M11 supplies two working generation providers with visible routing; M12 supplies the fixed evaluation method and browser checks. M10 supplies real Tavily and shared-MCP traffic. The [assignment](../../reference/assignment/Assignment_2_Description.md) governs the final archive, URL, metrics, and grading requirements.
- Use the deployment providers and managed secrets. The authenticated local Codex CLI/bridge is a development tool and cannot serve Cloud Run. Keep the service self-contained or connect it to explicitly deployed source/market MCP services.
- The app currently treats turns as self-contained. Add an external state store only if the final product claims memory across instances. Verify analysis bundle links across Cloud Run instances or define a reliable storage/retention path before exposing downloads.

## Work to implement

- Build and run the production image with pinned dependencies, the selected corpus/index or a reproducible mount/build step, embedding model, static browser assets, correct `PORT`, non-root identity, and no bundled credentials. Verify cold startup within platform limits.
- Configure Cloud Run service identity, secret injection, provider/MCP endpoints, resource limits, request timeout, concurrency, and budget caps. Document exact reproducible build/deploy commands and required roles/environment variables in the [root README](../../../README.md) without committing secret values.
- Make source inspection, original downloads, financial snapshots, and hashed Quant artifacts work across real HTTP requests. Check persistence or instance affinity assumptions explicitly; a link that works only on the instance that generated it is not accepted.
- Preserve SSE token streaming, scope validation, route/provider reasons, worker/tool trace, partial outcomes, citation identity, and credential redaction. A provider/MCP outage must produce an inspectable result instead of an unexplained crash.
- Re-run the relevant fixed evaluation and fresh unfamiliar questions against the public URL. Record retrieval/model/total latency, token time to first token, first idle/cold request versus warm requests, concurrency, failures, token/billing-based cost per query, and provider comparison. Use actual cloud/provider observations, not local subscription timings.

## Acceptance and submission

1. The public Cloud Run URL loads after an idle cold start and answers arbitrary reasonable questions. Exercise filing RAG, GAAP data, Quant, risk, valuation, live retrieval, and unsupported scope in browser and API; inspect sources and downloads.
2. Trace normal calls to both serving providers and the same shared MCP tool from two specialists. Verify real Tavily current retrieval, correct dates, bounded quota behavior, and no exposed keys.
3. Run concurrent requests and cancellation; inspect resource use, timeout behavior, result isolation, artifact access across requests/instances, and application logs. Re-run the final fixed evaluation and publish measured numbers in [evaluation](../../evaluation.md).
4. Package source without `.env`, credentials, or generated secret-bearing artifacts. Include pinned `requirements.txt`, placeholder `.env.example`, current architecture diagram/state/roles/routing table, evaluation report, deploy/setup commands, and the public URL.
5. Rylan Wade writes his own 200–300-word [process log](../../../PROCESS_LOG.md) across its four required sections. Do not fabricate or ghostwrite that personal reflection. Check the final archive contains the completed log before claiming submission readiness.

Resolve the GCP project/region, secret path, artifact retention, model access, MCP hosting, and cost ceiling from actual resources during implementation. A local-only image or a URL that answers only rehearsed questions does not meet the assignment.
