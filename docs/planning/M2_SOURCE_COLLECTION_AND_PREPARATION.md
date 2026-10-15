# M2 — Source collection and preparation

- Owner: Rylan Wade.
- Status: implemented and verified; accepted.
- Verification date: 2026-10-13 America/Los_Angeles (2026-10-14 UTC); exact source retrieval/check times are in the evidence files.
- Scope: NVIDIA FY2025–2026; AMD, Intel, and Qualcomm FY2024–2025, with the exact fiscal dates in [M1 coverage](M1_SCOPE_AND_SOURCE_FEASIBILITY.md#2-company-and-period-coverage).
- Governing requirements: [assignment](../assignment/Assignment_2_Description.md) and [M2 project scope](PROJECT_SPEC.md#m2--source-collection-and-preparation).
- Environment: uv 0.10.3, Python 3.13.12, Beautiful Soup 4.15.0, pypdf 6.19.0. `pyproject.toml` and `uv.lock` govern local dependencies; `requirements.txt` is their exact-pinned assignment export.

## Verified collection

| Company | Annual reports | Quarterly reports | Q4/full-year releases | Amendments | Verified / targets |
| --- | ---: | ---: | ---: | ---: | ---: |
| NVIDIA | 2 | 6 | 2 | 0 | 10 / 10 |
| AMD | 2 | 6 | 2 | 1 | 11 / 11 |
| Intel | 2 | 6 | 2 | 0 | 10 / 10 |
| Qualcomm | 2 | 6 | 2 | 0 | 10 / 10 |
| Total | 8 | 24 | 8 | 1 | **41 / 41** |

- All 41 original bodies are downloaded and have verified readable extraction. No selected document is missing or excluded. Collection gaps: **0**.
- SEC submissions snapshots validate accession, CIK, form, filing date, period end, and primary document for all 33 filing identities.
- NVIDIA and Qualcomm filings use official PDF links from their public investor-relations Q4 feeds. AMD and Intel use official HTML filing mirrors. Earnings releases use original company HTML and official Qualcomm PDFs.
- Exact URLs, source dates, retrieval times, hashes, validation outcomes, and prepared-file paths are in [collection results](../research/M2_COLLECTION_RESULTS.json). [Demonstration results](../research/M2_DEMONSTRATION_RESULTS.json) contain source samples, financial rows, risk boundaries, and AMD passages.
- [Offline verification results](../research/M2_VERIFICATION_RESULTS.json) record the full corpus check against fresh extraction and SEC snapshots.

## Implemented decisions

- [Source inventory](../../data/source_inventory.json) holds 41 logical documents. Canonical SEC identities and actual retrieval URLs are separate. Mirrors are candidates for one identity; they do not increase corpus size.
- AMD's original annual report and amendment remain separate. The original Client passage reports **31% unit-shipment growth and 15% ASP growth**; the amended MD&A reports **15% and 31%**, respectively. Its explanatory note identifies the transposition and limits the change. The amendment has no replacement risk section.
- Quarterly risks are update disclosures. Their annual context is recorded, including cases whose prior annual report is outside the selected corpus. The first selected year's prior annual reports are not added to coverage. NVIDIA FY2026 Q3 retains references to the annual and earlier quarterly reports.
- Original bytes and SEC metadata snapshots use content-addressed SHA-256 files. Prepared text uses document identity, extractor version, and source hash. Each run saves a manifest; refresh preserves original bodies and run history, including failed refreshes.
- Collection is explicit. There is no automatic refresh cadence or current-coverage promise. Future discovery creates a new inventory; it does not modify the approved M2 scope.
- Requests are sequential, at most one per second per collector, with truthful project identification, a 30-second timeout, and at most two attempts for transient errors. HTTP 403/404 are not retried. Sources remain public original/official paths; the collector does not bypass archive restrictions.
- Run one collector per output directory. Use separate output directories for future inventories.

## Extraction and correctness

- HTML extraction removes scripts, styles, hidden content, and hidden inline-XBRL facts. It joins inline narrative text and retains table cells with row/column spans. Readable table rows use `|`; details retain original cell structure, empty cells, signs, and units in source text.
- News extraction retains article titles, publication dates, body text, financial tables, and GAAP/non-GAAP labels.
- PDF extraction retains page offsets and fixed-width text. Pages omitted by layout extraction use ordinary text fallback. Empty-password public PDFs are readable; password-required PDFs fail explicitly. No OCR or structured PDF cell resolver is implemented.
- Standard filings use headed Item spans, excluding short table-of-contents entries. Intel's custom report order uses body title boundaries, with its SEC cross-reference index retained in the full extraction.
- All **32 original reports** have extracted annual/quarterly risk and MD&A sections. AMD's amendment also has MD&A. Risk boundaries end at the following appropriate source heading rather than at a table-of-contents reference or EOF.
- Eight annual revenue and operating-cash-flow rows match the independent original-accession M1 observations in USD millions. This validates source readability; it does not implement structured financial observation selection or financial calculations.
- Original NVIDIA FY2026 PDF page 37 and Qualcomm FY2025 PDF page 59 are visually inspected against extracted tables. NVIDIA retains the 215,938 / 130,497 revenue columns and units; Qualcomm retains 44,284 / 38,962 / 35,820 and the fiscal-date headers.
- Offline verification checks raw/text hashes, fresh extraction equality, page/section/table details, validation results, and original SEC metadata. Targeted tests protect wrong-company/period rejection, hidden-data contamination, section boundaries, news dates, mirror/amendment identity, bounded retries, refresh history, and tamper detection.

## Demonstration and reproduction

- Run from the repository root:

```powershell
uv sync --locked
uv run --locked python scripts/collect_sources.py collect
uv run --locked python scripts/collect_sources.py status
uv run --locked python scripts/collect_sources.py verify
uv run --locked python scripts/demo_sources.py
uv run --locked python -m unittest discover -s tests -v
```

- `collect` resumes intact bodies and checks extraction; failed targets remain visible. `verify` and `demo_sources.py` use local files only. PDF preparation/verification can take several minutes.
- `demo_sources.py` prints original/extracted paths for one annual source per company, checks eight annual financial rows and 32 risk boundaries, and prints AMD's two MD&A passages. It is a deterministic M2 demonstration, not an agent/RAG evaluation harness.
- Inspect exact evidence:

```powershell
uv run --locked python scripts/collect_sources.py inspect nvda-0001045810-26-000021 --section mda
uv run --locked python scripts/collect_sources.py inspect amd-0000002488-26-000018 --section mda --limit 0
uv run --locked python scripts/collect_sources.py inspect amd-0000002488-26-000021 --section mda --limit 0
uv run --locked python scripts/collect_sources.py inspect intc-0000050863-26-000011 --section risk_factors
uv run --locked python scripts/collect_sources.py inspect qcom-0000804328-25-000045 --section risk_factors
```

- Terminal inspection shows canonical/retrieval links, raw/text paths, and section offsets. Open the printed original path in a browser or PDF reader; compare with its UTF-8 text and adjacent extraction-details JSON.
- Refresh explicitly, or reprepare cached bodies without network access:

```powershell
uv run --locked python scripts/collect_sources.py collect --refresh
uv run --locked python scripts/collect_sources.py collect --offline
```

- Export current compact evidence:

```powershell
uv run --locked python scripts/collect_sources.py report --write docs/research/M2_COLLECTION_RESULTS.json
uv run --locked python scripts/demo_sources.py --write docs/research/M2_DEMONSTRATION_RESULTS.json
uv run --locked python scripts/collect_sources.py verify --write docs/research/M2_VERIFICATION_RESULTS.json
```

- Verified outcomes: 41/41 collected/prepared; offline verification passes; demonstration passes; targeted tests pass. These are source-preparation checks, with no model/provider calls or evaluation scores.

## Future data from the CLI

- Use explicit company fiscal dates and a new inventory path. The following supported-window example is verified: discovery returns four AMD FY2025 originals plus its amendment, release addition yields six targets, and separate collection/verification and refresh pass for all six. NVIDIA FY2026 and Qualcomm FY2025 discovery each return four originals with the selected official PDF paths.
- For a new year, replace the year, start/end, publication date, and release URL with verified source values. Discovery supports the four approved companies; new company/reporting-format support requires additional source checks. It does not infer fiscal dates from a calendar-year label.

```powershell
uv run --locked python scripts/collect_sources.py discover --company AMD --fiscal-year 2025 --fiscal-start 2024-12-29 --fiscal-end 2025-12-27 --write data/amd-fy2025-example.json
uv run --locked python scripts/collect_sources.py --inventory data/amd-fy2025-example.json add-release --company AMD --fiscal-year 2025 --fiscal-start 2024-12-29 --fiscal-end 2025-12-27 --published 2026-02-03 --url https://ir.amd.com/news-events/press-releases/detail/1276/amd-reports-fourth-quarter-and-full-year-2025-financial-results --format html
uv run --locked python scripts/collect_sources.py --inventory data/amd-fy2025-example.json --output data/corpus/amd-fy2025-example collect
uv run --locked python scripts/collect_sources.py --inventory data/amd-fy2025-example.json --output data/corpus/amd-fy2025-example verify
uv run --locked python scripts/collect_sources.py --inventory data/amd-fy2025-example.json --output data/corpus/amd-fy2025-example collect --refresh
```

- Discovery refuses to overwrite an existing inventory. Review new inventory coverage and collection failures before treating additional data as supported. Mirror URLs can be added to a target's `candidates` without changing its identity.
- The SEC recent-array metadata path validates current supported windows. Filings absent from that array remain an explicit collection failure; older historical windows require continuation-aware collection before acceptance.

## Files and remaining limits

- Track: source inventory, collection/discovery code, demonstration script, targeted tests, uv project/lockfile, exported requirements, documentation, and compact evidence reports.
- Ignore: `data/corpus/` originals, extracted text, table/page metadata, source snapshots, and run manifests; `.venv/` and temporary inspection material. Files are local reproducible artifacts and can change during refresh.
- Material collection gaps: none within the 41-document scope. Complex PDF tables still require original-page inspection; source text is not a universal structured financial parser. No guarantee is made about every table, arbitrary companies, unsupported forms, future publisher markup, or historical sources outside declared coverage.
- RAG ingestion/indexing, Filings Research, a minimal supervisor, direct Codex generation, local Docker, Financial Data, and Quant are implemented and verified. Risk-change classification, live/shared MCP, full cooperation, formal evaluation, and deployment remain pending.
- M2 is accepted. Local research, Docker, Financial Data, and Quant are implemented and verified; later milestones require feedback and authorization.
