# M3 — Filings Research

Owner: Rylan Wade.

The worker retrieves scoped filing passages from a persistent CPU MiniLM/Chroma index, inspects exact text, and streams cited answers through the local app. The current index contains 11,764 chunks from 46 documents. It uses 220 WordPiece tokens with 40 overlap, normalized 384-dimensional embeddings, cosine search, and a published index fingerprint that rejects stale or corrupt inputs. Company/year filters are mandatory; form, section, and version filters are optional.

Comparison retrieval covers each selected company/year. Research gets `min(24, max(8, 3 × pairs))` tool calls, capped at 24; other phases get eight. An exhausted budget can yield cited partial findings. Registered citations identify and hash-check exact passages; semantic support still needs review. Historical year-end questions work; genuinely live requests report a coverage gap.

## Worker and application contract

- `prompts/filings_research.md` and scoped `search_sources`/`inspect_source` tools define the role. A direct `research.py agent` run exercises the worker without the supervisor or browser. The graph and browser use the same evidence IDs.
- Initial retrieval contributes passages from every selected company/year pair. Follow-up search cannot broaden scope. Inspecting a registered ID returns its exact text and nearby context, with original filing/version links.
- A completed answer needs registered citations; unknown IDs, missing cited text, stale index state, and model failure surface as explicit outcomes. This validates provenance, not claim-level support. The browser shows token streaming, route/tool trace, and clickable source passages.
- Local generation uses an authenticated host Codex app-server thread per request. Cancellation closes the owned process. The local subscription trace is not evidence for deployment providers.

```powershell
uv run --locked python scripts/research.py ingest
uv run --locked python scripts/research.py status
uv run --locked python scripts/research.py agent "What does AMD's amended FY2025 MD&A correct?" --company AMD --year 2025
uv run --locked python scripts/demo_research.py
```

Verified milestone commit: `c426de3`; native transport/comparison correction: `ec0a44e`. The first run records 19 passing tests, four company application turns, one direct worker turn, browser citation inspection, and explicit failure handling. [Demonstration](evidence/M3_DEMONSTRATION_RESULTS.json), [browser](evidence/M3_BROWSER_RESULTS.json), [transport](evidence/M3_HTTP_RESULTS.json), [model failure](evidence/M3_MODEL_FAILURE_RESULTS.json), [cancellation](evidence/M3_CANCELLATION_RESULTS.json), [comparison results](evidence/RESEARCH_COMPARISON_RESULTS.json), [comparison source checks](evidence/RESEARCH_COMPARISON_SOURCE_CHECKS.json), [comparison browser](evidence/RESEARCH_COMPARISON_BROWSER_RESULTS.json), and [aligned index](evidence/ALIGNED_INDEX_RESULTS.json) retain the runs.

When extending retrieval, preserve scoped pair coverage, exact source identity, and the published fingerprint. Re-run source inspection and browser checks after changing chunking or embeddings.
