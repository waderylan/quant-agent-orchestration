# M3 — First RAG research demo

- Owner: Rylan Wade.
- Status: implemented and verified; accepted.
- Verification date: 2026-10-14 America/Los_Angeles; exact check times are in the evidence files.
- Scope: 41 verified M2 documents; NVIDIA FY2025–2026 and AMD/Intel/Qualcomm FY2024–2025.
- Runtime: Python 3.13/uv, Chroma 1.5.9, CPU ONNX MiniLM, LangChain LCEL, LangGraph 1.2.15, FastAPI 0.143.0, vanilla JavaScript, direct Codex app-server 0.162.1 with `gpt-6.1-sol`.

## Implemented behavior and decisions

- Ingest **41/41 documents into 10,681 chunks**. Use 220 WordPiece tokens, 40-token overlap, page/section boundaries, and exact character offsets. MiniLM supplies normalized local 384-dimensional embeddings; Chroma uses cosine distance.
- Filter by company/fiscal year and optional form, section, and version. Preserve original/amendment distinctions and quarterly risk context. Initial augmentation retrieves four passages per company/year; tools retrieve six.
- Filings Research uses its actual role prompt and scoped retrieval/inspection tools. A minimal LangGraph supervisor validates coverage and delegates research. Direct Codex executes application-managed tool round trips and streams final answer text.
- The browser exposes routing/tool evidence, linked citations, highlighted exact passages, nearby context, fiscal dates, version, official links, collected originals, and Stop.
- Keep collection/index refresh reproducible through the CLI. A complete fingerprinted index publishes atomically; no scheduler or automatic freshness claim exists.
- Codex CLI owns authentication. Generation is bounded to eight tool calls/180 seconds and two simultaneous application turns per process.
- Citation validation checks registered evidence identity; comprehensive claim support remains a review/formal-evaluation task.

## Reproduce and inspect

Run from the repository root with Codex CLI installed/authenticated.

```powershell
uv sync --locked
codex login
uv run --locked python scripts/collect_sources.py collect
uv run --locked python scripts/research.py ingest
uv run --locked python scripts/research.py status
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8080
```

- Open `http://127.0.0.1:8080`. Select company/year, ask a question, inspect the trace, and click an answer citation. The highlighted passage is exact indexed text.
- NVDA/FY2026 example: “What drove NVIDIA's full-year revenue growth in FY2026?”
- AMD/FY2025 example: “What does AMD's amended FY2025 MD&A say about Client unit shipments and average selling prices, compared with the original?”
- Explicit current requests or unsupported API/CLI selections return the historical coverage boundary.

```powershell
uv run --locked python scripts/research.py search "Client unit shipments average selling price" --company AMD --year 2025 --section mda --version amendment
uv run --locked python scripts/research.py inspect CHUNK_ID
uv run --locked python scripts/research.py agent "What does AMD's amended FY2025 MD&A correct?" --company AMD --year 2025
uv run --locked python scripts/research.py ask "What drove NVIDIA's full-year revenue growth in FY2026?" --company NVDA --year 2026
uv run --locked pytest -q
```

- `agent` runs the actual worker independently of supervisor/browser. `ask` runs the graph in the terminal. Both use direct Codex.
- `search`, `inspect`, and `status` need no generation or network calls after the embedding model is cached.
- Refresh with `collect --refresh`, then `research.py ingest`, then restart the app. M2 `discover`/`add-release` prepare future inventories; review coverage before making new sources supported.
- `research.py --corpus PATH --index PATH ingest` accepts a separate verified corpus/index. Application settings `SOURCE_CORPUS` and `RESEARCH_INDEX_DIR` select those paths. Defaults use the accepted corpus; new coverage requires review.
- `data/corpus/`, `chroma_index/`, and `artifacts/` are gitignored. Track code, prompts, source inventories, lockfile/export, documentation, and compact evidence.

## Demonstration and actual evidence

With the application running in another terminal:

```powershell
uv run --locked python scripts/demo_research.py
uv run --locked playwright install chromium
uv run --locked python scripts/demo_browser.py
```

- [Demonstration evidence](../research/M3_DEMONSTRATION_RESULTS.json) contains four-company retrieval, real application turns, cited-passage checks, unsupported scope, and a separate direct worker run.
- [Browser evidence](../research/M3_BROWSER_RESULTS.json) contains Chromium status, answer, citation links, exact passage, routing visibility, and JavaScript errors. Screenshot: ignored `artifacts/m3-browser.png`.
- Focused correctness checks: **19 passed**, comprising 12 source-preparation tests and seven research tests. The HTTP disconnect regression uses a real ASGI connection and a waiting fixture worker. These are not formal scores.
- Actual model-backed results: **4/4 application questions**, **1/1 direct AMD worker run**, and **1/1 Chromium chat/citation/trace demonstration** pass. The AMD answer preserves amended shipments **15%** / ASP **31%** and original shipments **31%** / ASP **15%** with separate source passages.
- Actual unsupported/current coverage checks: **3/3** return coverage gaps before tool/model use. [HTTP evidence](../research/M3_HTTP_RESULTS.json) records a matching original-file hash, missing-source **404**, and invalid-request **422**.
- [Unavailable-model evidence](../research/M3_MODEL_FAILURE_RESULTS.json) records an explicit rejected model. [Cancellation evidence](../research/M3_CANCELLATION_RESULTS.json) records a live Codex child and **zero remaining children after disconnect**, checked after two seconds.
- Local single-run observations: application completion **14.881–27.638 seconds**, answer-token TTFT **11.465–15.284 seconds**. These subscription samples include local embedding/CLI overhead and establish no deployment performance or pricing.

## Exit criteria and limits

| Criterion | Evidence/status |
| --- | --- |
| Full ingestion | 41/41 documents; 10,681 chunks; complete fingerprinted index. |
| Correct company/year retrieval | Four-company checks pass with exact passages. |
| Cited model-backed answers | 4/4 real application turns pass; cited passages match exact indexed text and company/year. |
| Tool calls and source opening | Actual search/inspection calls are recorded; Chromium citation opening and trace inspection pass. |
| Unsupported coverage | 3/3 actual API coverage-gap cases pass before tools/model calls; missing source returns 404. |
| Independently runnable worker | Separate direct AMD worker demonstration passes with the same actual role prompt/tools. |
| Recorded settings/prompt | [Architecture](../architecture.md), actual prompt, exact dependency pins. |

- Collection gaps: **zero** within M2's 41 selected sources. Broader company/year coverage and current sources remain unavailable.
- Complex PDF tables require original-page inspection. M3 supplies semantic passages, not reconciled observations or computed financial comparisons.
- Registered citation IDs/exact text do not prove every claim. Retrieval can omit relevant passages; prompt instructions alone do not establish injection resistance.
- M3 contains one specialist and a minimal supervisor. Three-specialist cooperation, live/shared MCP, two-provider routing, formal evaluation, Docker, and Cloud Run remain M4–M12 work.
- M3 is accepted. M4 remains unstarted and requires authorization.
