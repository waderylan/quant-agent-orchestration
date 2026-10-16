# M2 — Source preparation

Owner: Rylan Wade.

The collector retrieves declared official sources with SEC identity, URL, retrieval time, body hash, fiscal dates, and version. It removes hidden HTML/XBRL content while retaining table cells; PDF extraction keeps page offsets and layout text with a fallback. Refresh preserves originals and run history. Sequential requests use a one-per-second ceiling, a 30-second timeout, and at most two transient retries; HTTP 403/404 are reported directly.

The selected [inventory](../../../data/source_inventory.json) has 46 verified documents. The original milestone collection report records its 41-document snapshot; the [aligned corpus check](evidence/ALIGNED_CORPUS_VERIFICATION.json) records the later 46-document selection. Both are dated evidence. Commands:

```powershell
uv run --locked python scripts/collect_sources.py collect
uv run --locked python scripts/collect_sources.py verify
uv run --locked python scripts/collect_sources.py status
uv run --locked python scripts/collect_sources.py inspect DOCUMENT_ID --section risk_factors
```

`collect --refresh` fetches again; `collect --offline` prepares saved bodies. `discover` and `add-release` build a separate future inventory; see `--help` before use. Collected bodies in `data/corpus/` are ignored and reproducible. Complex tables still require original inspection.

## Contracts to preserve

- The manifest links each prepared text/section/table to a hashed original and source identity. Reuse cached bytes only after hash checks; refresh is explicit and leaves a record of prior versions.
- Keep PDF page offsets and HTML text offsets stable enough for exact citation inspection. Tables retain cell boundaries, but a parser cannot infer every financial table's meaning; inspect the original when deriving a new metric.
- Missing or blocked retrieval is a named collection gap, not a zero-length successful document. The collector does not bypass access restrictions or silently substitute third-party copies.
- A new inventory can use `discover` and `add-release` with a separate output directory. Re-ingest the changed corpus and restart the app before treating the new documents as chat coverage.

Verified milestone commit: `b4b2208`. [Collection](evidence/M2_COLLECTION_RESULTS.json), [demonstration](evidence/M2_DEMONSTRATION_RESULTS.json), and [verification](evidence/M2_VERIFICATION_RESULTS.json) contain the original checks.
