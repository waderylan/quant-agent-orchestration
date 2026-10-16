# M4 — Local container

The multi-stage Python 3.13 image is digest-pinned, runs as UID 10001, honors `PORT`, and excludes credentials and local data from its build context. It mounts the corpus/model read-only and a separate writable index. An authenticated host bridge owns local Codex app-server children; container users do not receive the CLI login. Disconnect and timeout close owned processes.

Run with Docker Desktop's Linux engine, an authenticated host Codex CLI, collected sources, and an ingested index:

```powershell
uv run --locked python scripts/demo_container.py
```

The demonstration checks startup, assets, non-root identity, absent credentials, cited SSE, source inspection, Chromium interaction, model rejection, and cancellation. The original acceptance has 22 passing focused tests. Local timing and resource snapshots are exploratory, not cloud measurements.

Verified milestone commit: `66e5517`. [Container](evidence/M4_CONTAINER_RESULTS.json) and [browser](evidence/M4_BROWSER_RESULTS.json) retain the run.
