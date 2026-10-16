# Aligned fiscal coverage and GAAP earnings

- Owner: Rylan Wade.
- Coverage: AMD, Intel, NVIDIA, and Qualcomm each have FY2024 and FY2025. NVIDIA also retains FY2026. Fiscal labels identify company fiscal years, not matching calendar intervals.
- Sources: 46 verified logical documents: nine original 10-Ks, twenty-seven original Q1–Q3 10-Qs, nine annual/Q4 earnings releases, and AMD's FY2025 10-K/A. Mirrors remain retrieval paths for one logical document. Original bodies and prepared text remain content-addressed; prior collection runs are retained.
- Retrieval: persistent Chroma contains 11,764 exact source passages. The five NVIDIA FY2024 documents contribute 1,083 passages. [Index evidence](../research/ALIGNED_INDEX_RESULTS.json) records the active fingerprint, actual collection count, fiscal coverage, new-document counts, and successful FY2024 annual vector retrieval with exact passage inspection.

## Fiscal windows

| Company | Fiscal year | Fiscal start | Fiscal end |
| --- | --- | --- | --- |
| NVIDIA | FY2024 | 2023-01-30 | 2024-01-28 |
| NVIDIA | FY2025 | 2024-01-29 | 2025-01-26 |
| NVIDIA | FY2026 | 2025-01-27 | 2026-01-25 |
| AMD | FY2024 | 2023-12-31 | 2024-12-28 |
| AMD | FY2025 | 2024-12-29 | 2025-12-27 |
| Intel | FY2024 | 2023-12-31 | 2024-12-28 |
| Intel | FY2025 | 2024-12-29 | 2025-12-27 |
| Qualcomm | FY2024 | 2023-09-25 | 2024-09-29 |
| Qualcomm | FY2025 | 2024-09-30 | 2025-09-28 |

- NVIDIA's FY2024 originals use accessions `0001045810-23-000093`, `0001045810-23-000175`, `0001045810-23-000227`, and `0001045810-24-000029`. SEC submissions metadata identifies the accessions, forms, publication dates, and reporting dates. Official investor-relations listings supply the PDF retrieval URLs; the official [FY2024 earnings release](https://investor.nvidia.com/news/press-release-details/2024/NVIDIA-Announces-Financial-Results-for-Fourth-Quarter-and-Fiscal-2024/) supplies annual/Q4 context.
- NVIDIA FY2025 quarter relationships reference the in-corpus FY2024 annual filing. Its FY2024 quarters refer to the FY2023 annual filing outside the selected corpus; quarterly disclosures remain updates, not complete annual risk inventories.
- Qualcomm FY2024 contains 53 weeks; FY2025 contains 52. Cross-company results require displayed fiscal dates and business/timing qualifications. Equal fiscal labels do not establish equal periods.

## Structured observations

- `src/financial_data.py` prepares 378 slots, with 346 available observations and 32 explicit missing slots. Revenue, gross profit, operating income, and net income each have 63/63 available slots; operating cash flow has 45/63 and cost of revenue has 49/63. The 18 missing cash-flow slots are Q2/Q3 quarter-only values; compatible cumulative values support Quant derivation. Intel's 14 cost-of-revenue slots remain unavailable under the selected tag.
- The four core default metrics remain revenue, gross profit, operating income, and operating cash flow. `net_income` is an explicitly queryable metric, backed by `us-gaap:NetIncomeLoss` across all selected periods. All nine annual net-income observations are available.
- Net income means GAAP income/loss attributable to the parent, including discontinued operations where applicable. `us-gaap:ProfitLoss`, which can include noncontrolling interests, is not a substitute. Intel FY2025 parent net loss is USD 267,000,000 even though its broader consolidated income before attribution is USD 26,000,000.
- Selection requires exact original accession, filed date, form, USD unit, and actual start/end. Fiscal labels in SEC Company Facts do not override intervals. Negative values remain negative; missing values remain missing. Later differing comparatives remain separate under the original-report revision policy.

## Independent source checks

| Parent net income/loss, exact USD | FY2024 | FY2025 |
| --- | ---: | ---: |
| NVIDIA | 29,760,000,000 | 72,880,000,000 |
| AMD | 1,641,000,000 | 4,335,000,000 |
| Intel | -18,756,000,000 | -267,000,000 |
| Qualcomm | 10,142,000,000 | 5,541,000,000 |

- [Financial evidence](../research/ALIGNED_FINANCIAL_COVERAGE_RESULTS.json) records nine independently inspected annual parent-earnings rows, including retained NVIDIA FY2026, plus NVIDIA FY2024 revenue, gross profit, operating income, and operating cash flow. Checks require the current-period amount immediately after the statement label, not a later comparative column. The evidence retains document IDs, accessions, fiscal dates, original hashes, exact source rows, and PDF page locations where applicable. It also verifies all 41 baseline document identities, original-body hashes, and prepared-text hashes against the recorded M2 source evidence.
- Independent arithmetic gives AMD the largest percentage earnings growth among companies with positive FY2024 earnings: approximately 164.1682%, or USD 2,694,000,000. NVIDIA has the largest absolute increase: USD 43,120,000,000, approximately 144.8925%. Intel's USD 18,489,000,000 improvement starts from a loss; conventional percentage growth is not meaningful. Qualcomm's earnings decline approximately 45.3658%.
- These are source/arithmetic checks, not formal model-quality scores. The application routing and ranking demonstrations are documented separately by the parent implementation.

## Reproduction

```powershell
uv run --locked python scripts/collect_sources.py collect
uv run --locked python scripts/collect_sources.py verify --write docs/research/ALIGNED_CORPUS_VERIFICATION.json
uv run --locked python scripts/financials.py collect
uv run --locked python scripts/financials.py query --company NVDA AMD INTC QCOM --year 2024 2025 --metric net_income
uv run --locked python scripts/verify_aligned_coverage.py
uv run --locked python scripts/research.py ingest
uv run --locked python scripts/research.py status
uv run --locked python scripts/research.py search "NVIDIA FY2024 revenue net income growth and data center demand" --company NVDA --year 2024 --form 10-K
```

- The checked-in inventory governs the scope. Ordinary collection resumes verified cached sources; `--refresh` deliberately requests newer bodies and preserves raw/run history. Financial collection reuses the four hashed SEC snapshots unless `--refresh` is requested. Corpus or inventory changes require financial preparation, index ingestion, and an application restart before serving the new scope.
- [Corpus verification](../research/ALIGNED_CORPUS_VERIFICATION.json) passes for all 46 targets with no failures. It checks full offline identity, original/prepared checksums, fresh extraction, tables, page/section boundaries, and SEC metadata. All 22 source/financial tests pass. The source tests require a complete annual/quarterly/release set for each selected company/year and preserve amendment identities. Financial tests protect parent-earnings selection, loss values, unavailable data, and rejection of `ProfitLoss` substitution.
