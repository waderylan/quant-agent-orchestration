# M4 — Local container acceptance

- Owner: Rylan Wade.
- Status: implemented and verified locally. Cloud Run acceptance is pending under M12.
- Evidence: [container checks](../research/M4_CONTAINER_RESULTS.json) and [Chromium checks](../research/M4_BROWSER_RESULTS.json). These are local Docker observations, not cloud measurements or formal evaluations.

## Runtime and authentication

- `Dockerfile` uses a digest-pinned Python 3.13-slim multi-stage build, the exact exported dependency pins, `/opt/venv`, and UID 10001. Uvicorn binds to `0.0.0.0` and the injected `PORT`.
- The build context is an allowlist. Application code, prompts, frontend, requirements, and inventory enter the image. Credentials, Git history, local configurations, downloads, indexes, and development artifacts do not.
- Corpus data mounts read-only. A separate writable copy of Chroma mounts at `/app/chroma_index`; Chroma needs writable SQLite/index access. The CPU MiniLM cache mounts read-only. Native and container processes do not share a writable index.
- The local subscription path is container → authenticated TCP bridge → host-owned Codex app-server over stdio. `src/codex_transport.py` owns native processes/connections; `scripts/codex_bridge.py` owns one child per authenticated request. The JSON-RPC behavior follows the [official app-server protocol](https://learn.chatgpt.com/docs/app-server).
- The CLI and its authentication remain on the host. A separate random capability token gates the bridge; the token is stored under ignored `artifacts/` and mounted read-only. It is not a Codex credential. Neither the token nor the CLI credential is embedded in image layers.
- The bridge defaults to loopback. Docker Desktop acceptance explicitly binds `0.0.0.0` to permit `host.docker.internal` access. This plaintext bridge is for a trusted local development machine/network; it is not a public or deployed provider adapter. Do not expose it through a public port or tunnel.
- Two bridge children can run concurrently. Authentication has a five-second deadline; each connection has a 200-second bound. Client disconnect explicitly closes the transport, cancels forwarding, kills the owned CLI process tree, and waits for exit. This includes descendants inheriting stdio. Request ownership and explicit response-generator closure also cover ASGI 2.4 send failures. Application generation has a 180-second deadline; Research uses a scope-dependent 8–24 executed-call limit and other phases use eight. [Comparison research](RESEARCH_COMPARISONS.md) specifies bounded final synthesis and its native/browser checks.

## Reproduce acceptance

Prerequisites: Docker Desktop's Linux engine, an authenticated host Codex CLI, the collected corpus, ingested index, and cached embedding model.

```powershell
uv sync --locked
uv run --locked pytest -q
uv run --locked python scripts/demo_container.py
```

- The demonstration builds `hw2-research:m4`, copies the index into ignored `artifacts/local-container/index` if absent, starts the host bridge, and runs a container with 2 CPUs/2 GiB. It maps host loopback port 8084 to container port 9090, proving that `PORT` is honored.
- It verifies fresh startup, coverage/assets, non-root identity, absent Codex installation/credential home, a real cited SSE question, exact citation inspection, a live disconnect, and an unavailable model through the container's actual transport. Chromium separately exercises the deployed-to-local-container browser interface, traces, and citation viewer.
- It records image identity, size, startup time, answer-token TTFT/completion, and a post-query Docker resource snapshot. The resource snapshot is not a peak-memory or load benchmark.
- The script removes its container and stops its bridge on completion. Build/bridge logs and index copies remain ignored. `--skip-build` reuses an existing image; `--image NAME` selects a separately built image.
- After source refresh/reingestion, use a fresh staging index directory; an existing staging copy is deliberately preserved. Do not modify the staging index while its container is running.

## Verification and boundaries

- The full focused suite has 22 passing tests, including real-socket rejection of an incorrect token, owned process-tree termination with inherited pipes, and response closure after an ASGI 2.4 send failure. Existing extraction, provenance, scope, citation, SSE, and ASGI cancellation checks remain applicable.
- Actual application and Chromium checks pass with host subscription generation. The container has no Codex executable, `.codex` home, or application `.env`; generation is available only through the explicitly configured bridge.
- An unavailable model fails explicitly. The unavailable-model check exercises the real adapter inside Docker; fixture tests separately protect the HTTP terminal-failure contract.
- Local timing and memory observations live in the evidence JSON. No Nebius/NVIDIA calls, paid judges, cloud resources, durable-memory promises, or deployment performance claims are made.
- Financial observations, Quant analysis, Risk Summary, full supervisor cooperation, live/shared MCP, two-provider routing, and formal evaluation are separate milestones.
