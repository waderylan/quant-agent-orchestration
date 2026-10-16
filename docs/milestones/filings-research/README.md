# M3 — Filings Research

The worker retrieves scoped filing passages from a persistent CPU MiniLM/Chroma index, inspects exact text, and streams cited answers through the local app. The current index contains 11,764 chunks from 46 documents. It uses 220 WordPiece tokens with 40 overlap, normalized 384-dimensional embeddings, cosine search, and a published index fingerprint that rejects stale or corrupt inputs. Company/year filters are mandatory; form, section, and version filters are optional.

Comparison retrieval covers each selected company/year. Research gets `min(24, max(8, 3 × pairs))` tool calls, capped at 24; other phases get eight. An exhausted budget can yield cited partial findings. Registered citations identify and hash-check exact passages; semantic support still needs review. Historical year-end questions work; genuinely live requests report a coverage gap.

```powershell
uv run --locked python scripts/research.py ingest
uv run --locked python scripts/research.py status
uv run --locked python scripts/research.py agent "What does AMD's amended FY2025 MD&A correct?" --company AMD --year 2025
uv run --locked python scripts/demo_research.py
```

Verified milestone commit: `c426de3`; native transport/comparison correction: `ec0a44e`. The first run records 19 passing tests, four company application turns, one direct worker turn, browser citation inspection, and explicit failure handling. [Demonstration](evidence/M3_DEMONSTRATION_RESULTS.json), [browser](evidence/M3_BROWSER_RESULTS.json), [transport](evidence/M3_HTTP_RESULTS.json), [model failure](evidence/M3_MODEL_FAILURE_RESULTS.json), [cancellation](evidence/M3_CANCELLATION_RESULTS.json), [comparison results](evidence/RESEARCH_COMPARISON_RESULTS.json), [comparison source checks](evidence/RESEARCH_COMPARISON_SOURCE_CHECKS.json), [comparison browser](evidence/RESEARCH_COMPARISON_BROWSER_RESULTS.json), and [aligned index](evidence/ALIGNED_INDEX_RESULTS.json) retain the runs.
