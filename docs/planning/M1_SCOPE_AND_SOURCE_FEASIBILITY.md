# M1 — Scope and source feasibility

- Owner: Rylan Wade.
- Status: scope/source feasibility and [M2 collection/preparation](M2_SOURCE_COLLECTION_AND_PREPARATION.md) are verified; M2 accepted. Local research and Docker are implemented and verified; see the current [project spec](PROJECT_SPEC.md).
- Verification date: 2026-10-13 America/Los_Angeles (2026-10-14 UTC).
- Governing documents: [AGENTS.md](../../AGENTS.md), [assignment](../assignment/Assignment_2_Description.md), and [project spec](PROJECT_SPEC.md).
- Scope decisions below apply to initial collection. Coverage can change after working demonstrations and feedback; this is not a fixed evaluation dataset.

## 1. Selected scope

| Scope area | Current decision | Evidence / boundary |
| --- | --- | --- |
| Semiconductor sector; 3–5 domestic reporters | NVIDIA (NVDA), AMD (AMD), Intel (INTC), Qualcomm (QCOM). | SEC identities and 10-K/10-Q histories verified for all four; financial-input audit passed for each. |
| Completed annual/quarterly coverage | All companies cover FY2024/FY2025; NVIDIA retains FY2026. | Actual dates appear below. NVIDIA's year label is offset from the other companies. These are historical coverage windows, not a claim of latest coverage as of October 2026. |
| Filing families | Full original 10-K and Q1–Q3 10-Q documents; related amendments as separate versions. | 32 original reports discovered plus one in-window AMD 10-K/A. Q4 is represented by the 10-K and earnings release, not an invented fourth 10-Q. |
| Relevant earnings releases | Initially include the eight Q4/full-year releases listed in §4. | Each downloaded from an original company site or its official document CDN. Q1–Q3 releases can be added when a demonstration needs them. |
| Corpus size / retrieval structure | Verified corpus: **41 source documents** = 8 annual reports + 24 quarterly reports + 8 earnings releases + 1 amendment. | All bodies and readable extractions are verified, with no collection gaps. Documents span business descriptions, MD&A, financial statements/notes, and risk disclosures. Local MiniLM/Chroma ingestion and retrieval are implemented and verified. |
| Initial numerical scope | Consolidated US GAAP revenue growth, gross margin, operating margin, and operating cash flow in USD. | All 32 original reports have matching-duration financial inputs in SEC Company Facts; Qualcomm gross profit must be derived from revenue minus cost of revenue. |
| Supported investigations | Management explanations, within-company financial changes, qualified company comparisons, disclosure changes, and dated current developments relevant to those questions. | Original narrative reports, structured observations, and public company news are available. Tavily application integration remains unverified. |
| Request / output boundary | Self-contained request; cited research brief, optional financial table/chart, relevant risk changes, explicit gaps. | Preserve the spec's single-turn boundary. No conversation-memory promise. |
| Expansion | Start with four companies; broader company coverage is planned toward approximately 20. Third full years, transcripts, and segment metrics remain optional additions. | Expansion requires verified source coverage, working demonstrations, and feedback. The initial collection target remains 41 documents for four companies. |
| Exclusions | Market quotes, price-move explanations, valuation, trading, forecasts, watchlists, background alerts. | Preserve the spec's exclusions. Quoted management outlook can be reported as a dated statement; do not generate forecasts. |

## 2. Company and period coverage

| Company | SEC CIK | Selected fiscal years | Fiscal start → end |
| --- | --- | --- | --- |
| NVIDIA | 0001045810 | FY2024; FY2025; FY2026 | 2023-01-30 → 2024-01-28; 2024-01-29 → 2025-01-26; 2025-01-27 → 2026-01-25 |
| AMD | 0000002488 | FY2024; FY2025 | 2023-12-31 → 2024-12-28; 2024-12-29 → 2025-12-27 |
| Intel | 0000050863 | FY2024; FY2025 | 2023-12-31 → 2024-12-28; 2024-12-29 → 2025-12-27 |
| Qualcomm | 0000804328 | FY2024; FY2025 | 2023-09-25 → 2024-09-29; 2024-09-30 → 2025-09-28 |

- Company names/CIKs were checked in SEC submissions and Company Facts JSON. Filing and report dates were read from submissions; fiscal starts were checked against annual financial observations.
- The combined source-period envelope is 2023-01-30 through 2026-01-25. It does not mean each company has coverage throughout that entire envelope. [Aligned coverage](ALIGNED_FISCAL_COVERAGE.md) records the verified current inventory and the original-source NVIDIA FY2024 inputs.
- Use explicit company fiscal dates in answers and charts. NVIDIA's January-end year, Qualcomm's September-end year, and AMD/Intel's December-end years are different reporting windows.
- Qualcomm FY2024 contains **53 weeks**; FY2025 contains 52. Its annual filing explicitly warns that these periods are not exactly comparable. Report ordinary growth with that qualification; do not silently normalize or claim matched calendar exposure. [Qualcomm FY2025 10-K](https://www.sec.gov/Archives/edgar/data/804328/000080432825000085/qcom-20250928.htm)
- Prefer within-company comparisons initially. A cross-company fiscal comparison must show dates and explain timing and business-mix limits; do not label it a synchronized calendar-year comparison.
- Revenue growth between the two selected years has verified source inputs. Comparative figures for earlier periods may be cited from a selected report, but they do not establish full earlier-year narrative/risk coverage.

## 3. Source checks and access evidence

### SEC discovery and structured data

- Public SEC submissions and Company Facts APIs require no API key. They provide filing history and financial observations; they do not replace original narrative filings. [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- All eight JSON requests below returned **HTTP 200**, parsed successfully, and identified the expected company during local Python source probes.
- The current submissions arrays contained every selected report; historical continuation files were not needed for this window.

| Company | Filing discovery | Structured financial observations | Selected originals / aligned inputs |
| --- | --- | --- | --- |
| NVDA | [Submissions](https://data.sec.gov/submissions/CIK0001045810.json) | [Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json) | 8 / 8 |
| AMD | [Submissions](https://data.sec.gov/submissions/CIK0000002488.json) | [Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000002488.json) | 8 / 8; one additional 10-K/A |
| INTC | [Submissions](https://data.sec.gov/submissions/CIK0000050863.json) | [Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000050863.json) | 8 / 8 |
| QCOM | [Submissions](https://data.sec.gov/submissions/CIK0000804328.json) | [Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000804328.json) | 8 / 8 |

- “Aligned inputs” means revenue, gross-profit input, operating income/loss, and operating cash flow have a common start/end interval, USD unit, and the selected report's exact accession. This check found no missing required input in the 32 originals.
- This is availability and basic period consistency evidence. It does not prove an extractor, revision policy, complete reconciliation, or application calculation workflow.
- SEC automation must remain below its aggregate 10-request/second limit and identify its client. The collector uses truthful project identification, sequential requests at most once per second, and bounded transient retries; it preserves failures and does not bypass access restrictions. [SEC rate-control guidance](https://www.sec.gov/filergroup/announcements-old/new-rate-control-limits)
- SEC requests belong on the backend: SEC documents that data.sec.gov does not support browser CORS. [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

### Original document bodies

| Path checked | Observed result | What it establishes |
| --- | --- | --- |
| Direct local SEC Archives requests for newest NVDA, AMD, and Intel 10-Ks | **HTTP 403** for all three. | Local API access does not guarantee filing-body access. Do not design collection around untested archive downloads. |
| AMD official HTML filing mirrors | **HTTP 200 for all 8 originals and the amendment**. | A usable local original-document path exists for AMD. |
| Intel official HTML filing mirrors | **HTTP 200 for all 8 originals**. | A usable local original-document path exists for Intel. |
| NVIDIA FY2026 official annual PDF | **HTTP 200**, 15,850,437 bytes, valid PDF signature. | Official PDF access is verified. M2 collects the official standalone 10-K PDF and verifies readable extraction and section/table samples. |
| Qualcomm FY2025 Q3 official filing PDF | **HTTP 200**, 408,448 bytes, valid PDF signature; 52 pages and 213,352 extracted text characters in the source probe. | Official quarterly filing access is verified. M2 verifies page/section extraction and source identity. |
| Browser research tool: NVIDIA FY2026 10-K and FY2026 Q3 10-Q; Qualcomm FY2024/FY2025 10-Ks | Original SEC document text opened and inspected. | Narrative availability is verified for these samples; this is not a successful local collector run for every NVDA/QCOM report. |
| Qualcomm corporate FY2025 release URL | Local response was **HTTP 200**, but the body did not contain the expected financial text markers. | Status alone is insufficient. Use the verified official earnings PDF instead. |

- All 32 originals have verified risk and MD&A extraction in M2, plus financial statement markers. Standard Item headings and Intel's custom body headings have separate boundary handling.
- AMD's amendment has verified MD&A but no replacement Risk Factors section; it cannot replace the full original filing.
- Source entry points: [NVIDIA annual reports](https://investor.nvidia.com/financial-info/annual-reports-and-proxies/default.aspx), [NVIDIA financial reports](https://investor.nvidia.com/financial-info/financial-reports/default.aspx), [AMD financial results](https://ir.amd.com/financial-information/financial-results), [Intel financial results](https://www.intc.com/financial-info/financial-results), [Qualcomm historical results](https://investor.qualcomm.com/financial-info-sec-filings/historical-financial-results/default.aspx).
- NVIDIA/Qualcomm financial-report pages populate historical listings through public Q4 feeds. The collection/discovery CLI resolves official PDF links from those feeds. Qualcomm's historical-results page above is the supported entry point.
- Verified alternate downloads: [NVIDIA FY2026 annual PDF](https://s201.q4cdn.com/141608511/files/doc_financials/2026/ar/2026-Annual-Report-Web.pdf), [Qualcomm FY2025 Q3 PDF](https://s204.q4cdn.com/645488518/files/doc_financials/2025/q3/QCOM-06-29-25-10-Q-final.pdf).
- Use SEC identity/accession as canonical provenance and retain the actual retrieval URL separately. A mirror and its SEC counterpart are one source document, not two corpus documents.
- All selected NVIDIA/Qualcomm bodies are collected and verified. The [M2 source inventory](../../data/source_inventory.json) holds official download paths; [M2 results](../research/M2_COLLECTION_RESULTS.json) hold actual provenance and checksums for all 41 sources.

## 4. Verified earnings releases

- Select Q4/full-year releases for both covered years to retain management explanations, quarter-four results, and GAAP/non-GAAP distinctions.
- Every URL below returned HTTP 200 locally. Qualcomm PDFs were parsed with the already-installed pypdf package: 10 pages each, 31,760 and 33,597 extracted text characters, with revenue and cash-flow text.
- Published release dates are retained as source dates, separate from filing dates and retrieval dates. These releases are historical corpus sources; live search is a separate channel.

| Company / fiscal year | Release date | Original company release |
| --- | --- | --- |
| NVDA FY2025 | 2025-02-26 | [Q4 / FY2025](https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-fourth-quarter-and-fiscal-2025) |
| NVDA FY2026 | 2026-02-25 | [Q4 / FY2026](https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-fourth-quarter-and-fiscal-2026) |
| AMD FY2024 | 2025-02-04 | [Q4 / FY2024](https://ir.amd.com/news-events/press-releases/detail/1236/amd-reports-fourth-quarter-and-full-year-2024-financial-results) |
| AMD FY2025 | 2026-02-03 | [Q4 / FY2025](https://ir.amd.com/news-events/press-releases/detail/1276/amd-reports-fourth-quarter-and-full-year-2025-financial-results) |
| INTC FY2024 | 2025-01-30 | [Q4 / FY2024](https://www.intc.com/news-events/press-releases/detail/1726/intel-reports-fourth-quarter-and-full-year-2024-financial) |
| INTC FY2025 | 2026-01-22 | [Q4 / FY2025](https://www.intc.com/news-events/press-releases/detail/1759/intel-reports-fourth-quarter-and-full-year-2025-financial) |
| QCOM FY2024 | 2024-11-06 | [Q4 / FY2024 official PDF](https://s204.q4cdn.com/645488518/files/doc_financials/2024/q4/FY2024-4th-Quarter-Earnings-Release.pdf) |
| QCOM FY2025 | 2025-11-05 | [Q4 / FY2025 official PDF](https://s204.q4cdn.com/645488518/files/doc_financials/2025/q4/FY2025-4th-Quarter-Earnings-Release.pdf) |

## 5. Financial feasibility and comparison boundaries

### Observed US GAAP input tags

| Company | Revenue | Gross-profit input | Operating income / cash flow |
| --- | --- | --- | --- |
| NVDA | us-gaap:Revenues | us-gaap:GrossProfit; CostOfRevenue also present | us-gaap:OperatingIncomeLoss; us-gaap:NetCashProvidedByUsedInOperatingActivities |
| AMD | us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax | us-gaap:GrossProfit; CostOfGoodsAndServicesSold also present | Same operating income/cash-flow tags |
| INTC | us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax | us-gaap:GrossProfit | Same operating income/cash-flow tags |
| QCOM | us-gaap:Revenues | Revenue minus us-gaap:CostOfRevenue; **no GrossProfit tag** in the fetched facts | Same operating income/cash-flow tags |

- These are verified candidate mappings for consolidated metrics, not a finished universal tag resolver.
- Initial formulas: revenue growth = (new revenue / old revenue − 1) × 100; gross margin = gross profit / revenue × 100; operating margin = operating income / revenue × 100.
- Qualcomm gross profit is a derived input, not a directly reported Company Facts observation. Carry both cited inputs and the subtraction formula. Its FY2025 10-K reports gross margin rounded to 55%, versus 56% for FY2024, consistent with the available revenue/cost figures. [Qualcomm 10-K, MD&A](https://www.sec.gov/Archives/edgar/data/804328/000080432825000085/qcom-20250928.htm)
- Annual operating cash flow is reported directly. Quarterly cash-flow statements provide YTD amounts: Q2-only = six-month YTD − Q1; Q3-only = nine-month YTD − six-month YTD; Q4-only = annual − nine-month YTD. Require compatible inputs, fiscal starts, and revision basis before subtraction.
- Revenue, gross profit, and operating income have quarter-only and YTD observations in Q2/Q3. Select by actual start/end dates, not by fp or a “quarter” label alone.
- Do not subtract margins or average quarterly percentages to construct an annual margin. Derive a Q4 numerator and denominator separately when needed.
- Keep USD observations at original precision; filing displays commonly use millions. Preserve negative operating income/loss. Margin changes use percentage points.
- Refuse or qualify calculations with missing inputs, incompatible intervals, zero denominators, or unresolved revisions. Missing is not zero.
- Separate GAAP from adjusted/non-GAAP release figures. Segment comparisons and broad extension-tag handling remain later decisions.

### Annual observations inspected

- Values below are **USD millions**, converted from the exact USD Company Facts observations in each original annual accession.
- Qualcomm gross profit is shown as a subtraction for inspection. These figures demonstrate source feasibility; they are not generated application results or formal evaluations.
- Source links: [NVDA facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json), [AMD facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000002488.json), [Intel facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000050863.json), [Qualcomm facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000804328.json). Exact report accessions are in §9.

| Company / FY | Revenue | Gross profit / derived input | Operating income (loss) | Operating cash flow |
| --- | ---: | ---: | ---: | ---: |
| NVDA FY2025 | 130,497 | 97,858 | 81,453 | 64,089 |
| NVDA FY2026 | 215,938 | 153,463 | 130,387 | 102,718 |
| AMD FY2024 | 25,785 | 12,725 | 1,900 | 3,041 |
| AMD FY2025 | 34,639 | 17,152 | 3,694 | 7,709 |
| INTC FY2024 | 53,101 | 17,345 | -11,678 | 8,288 |
| INTC FY2025 | 52,853 | 18,375 | -2,214 | 9,697 |
| QCOM FY2024 | 38,962 | 38,962 − 17,060 = 21,902 | 10,071 | 12,202 |
| QCOM FY2025 | 44,284 | 44,284 − 19,738 = 24,546 | 12,355 | 14,012 |

### Amendments and disclosure comparison

- AMD FY2025 original accession: 0000002488-26-000018. Amendment: 0000002488-26-000021, also filed 2026-02-04.
- The amendment corrects transposed changes in Client processor shipment volume and average selling price in MD&A. It states that other disclosures are unchanged. Preserve both documents; use the corrected passage when explaining that change. Do not treat this as a full financial-statement restatement or replace original risks/statements with the amendment. [AMD explanatory note](https://ir.amd.com/financial-information/sec-filings/content/0000002488-26-000021/amd-20251227.htm)
- Company Facts includes repeated historical intervals in later filings; fy/fp may identify the containing report rather than uniquely identify the observation period. Retain accession, start/end, unit, filed date, and the chosen revision basis.
- Initially compare the two annual risk sections per company; quarterly Item 1A supplies intervening updates or references to earlier reports.
- NVIDIA FY2026 Q3 explicitly refers to its FY2025 annual report and FY2026 Q1/Q2 risks and then lists changes. It is not a full replacement risk inventory. This supports retaining all six 10-Qs and their parent annual relationships. [NVIDIA FY2026 Q3 Item 1A](https://www.sec.gov/Archives/edgar/data/1045810/000104581025000230/nvda-20251026.htm)
- Alignment, relocated boilerplate detection, and change classification remain implementation work. Source availability does not prove a working risk-comparison agent.

## 6. Current-source feasibility

- Original company news/release sites are public source candidates; the dated release checks establish access to source material.
- Tavily documentation confirms its hosted MCP endpoint and search/extract tools. Preserve the assignment's query-parameter API-key connection shape and Streamable HTTP requirement. [Tavily MCP documentation](https://docs.tavily.com/documentation/mcp)
- Authenticated Tavily initialize, tools/list, search, and extract calls are unverified. A public webpage opened with the browsing tool does not establish Tavily access or the deployed live-knowledge requirement.
- Keep account access, available quota, transport/client compatibility, extraction failures, and usable current-source coverage pending until the live-tool increment.
- Record publication date, retrieval time, source URL, and source type. Keep original management statements separate from outside reporting and assistant interpretation.
- The static coverage ends at each company's selected fiscal end. For later/current developments, use live retrieval and make the source date explicit. If retrieval fails or is stale, report the limitation without asserting current conditions.
- Document/observation refresh cadence remains undecided. Selected coverage is a fixed historical window with no automatic-update promise.

## 7. Remaining decisions and gaps

| Decision / gap | Current status | Resolve before |
| --- | --- | --- |
| NVDA/QCOM local document-body paths | All 16 selected report PDFs are downloaded, identity checked, and prepared; no collection gaps. M2 demonstrates section/table fidelity. | Verified in M2 |
| Financial definitions / fiscal alignment | M5 implements consolidated GAAP USD observations with exact accession/date/unit selection, explicit quarter/YTD basis, and missing/conflicting statuses. M6 implements compatible quarter derivations and independently checked calculations. | M5/M6 verified |
| Amendments / restatements | Original statements and AMD's narrative-only amendment remain separate. M5 selects original-report values and retains later conflicting comparatives without substitution. | M5 verified; latest-restatement selection is unsupported |
| Chunking, embeddings, filters/k, Chroma versus Pinecone | CPU MiniLM, persistent cosine Chroma, 220-token chunks/40-token overlap, scoped retrieval. | Verified in M3 |
| NVIDIA confirmation; Nebius/NVIDIA models, budgets, routing thresholds | Deferred. No runtime-provider generation calls or pricing conclusions. | Final provider integration; reverify current access and pricing then |
| Local generation and Docker host access | Direct Codex app-server and authenticated host bridge; CLI credentials remain on the host. | Verified in M3/M4 |
| Formal evaluation checkpoint, task families, RAGAS/AgentEvals compatibility | Deferred until research and analysis demonstrations inform behavior. | Agreed later evaluation checkpoint |
| Judge model, dataset sizes/splits, calibration, integration budgets | Deferred; no paid judges, benchmark, scores, or thresholds. | First model-judged evaluations |
| Quant execution limits / allowed libraries | Restricted arithmetic interpreter, isolated process, three-second deadline, Linux resource bounds, independent financial/lineage checks, and application-controlled Matplotlib. | M6 verified |
| Optional hosted LangSmith reporting | Deferred; no hosted experiment uploads. | Requested hosted integration |
| Brief/chart design and source inspection | Research passages, financial observations, formulas, source lineage, CSV tables, and PNG charts are implemented. Broader presentation refinement remains M12 work. | M3–M6 verified; M12 refinement pending |
| Conversation memory / durability | Initial requests remain self-contained; future memory decision deferred. | Any multi-turn or persistence promise |
| Refresh policy / current-source freshness | Explicit source and financial-snapshot CLI refresh are implemented. Saved analysis inputs remain frozen. M8 defines market/estimate/current-evidence freshness for Buy-Side Analyst; M10 generalizes current-source research. No automatic refresh promise. | Live-source freshness promises |
| Cloud Run resources/concurrency/latency | Deferred; no deployment or performance measurements. | Final deployment acceptance |
| Product name / broader coverage | Deferred; four-company initial scope only. | Feedback on working workflows |

- No assignment/spec conflict requiring a change was found for this increment: four companies fit the 3–5 limit; domestic forms, roughly two years, and the initial metrics are retained.
- The assignment's eventual RAGAS, multi-provider routing, shared MCP, SSE frontend, and Cloud Run requirements remain required. M1 source probes do not satisfy them.

## 8. Verification status and inspection

- Source evidence comprises public primary-source documentation, SEC JSON, original filings, official IR mirrors, and official company CDNs.
- Recorded source checks: eight SEC JSON endpoints with HTTP 200; 32 originals and one amendment in metadata; aligned USD inputs for 32/32 original reports.
- All 41 selected bodies and extractions are verified in M2. Source samples, annual financial rows, and annual/quarterly risk boundaries are inspected; AMD's original/amended MD&A remains distinguishable.
- Verification uses uv-managed Python 3.13 with standard-library HTTP/JSON, Beautiful Soup, and pypdf. The independent financial-availability recipe returns eight originals and eight aligned-input successes for every company.
- The filing inventory contains 33 rows. Markdown whitespace, encoding, and code-fence checks pass.
- Source bodies, SEC metadata snapshots, prepared text, and run manifests reside in ignored `data/corpus/`. The tracked inventory, CLI, lockfile, and compact evidence reports reproduce collection. RAG ingestion indexes all 41 sources into 10,681 chunks.
- Filings Research, a minimal supervisor, direct Codex generation, RAG, browser SSE, and local Docker are implemented and verified. Financial Data and Quant are implemented and verified. Risk Summary, live/shared MCP, multi-provider routing, deployment, and formal evaluations remain pending.
- M1–M6 are implemented and verified; M2 and M3 are accepted. M7–M13 remain pending; see the [milestone skeleton](PROJECT_SPEC.md#milestones).

### Inspection path

1. Review company/year decisions in §§1–2.
2. Open SEC facts links in §3 and find an annual accession from §9; compare its USD inputs with §5.
3. Read AMD's amendment explanatory note and Qualcomm's 53-week comparability warning.
4. Open the earnings links in §4 and original report links in §9.
5. Run the [M2 source demonstration](M2_SOURCE_COLLECTION_AND_PREPARATION.md#demonstration-and-reproduction); review §7 for decisions required by later milestones.

### Reproduce the financial availability check

- Run the following in a uv-managed Python session with standard-library modules only (`uv run --locked python`).
- It makes eight public SEC JSON requests and does not call generation providers or judges.
- The recipe uses an identifying academic-source header. The supported collector uses the project identification and request bounds documented in M2.
- Verified result: eight selected original filings and eight aligned-input successes for each company. Live endpoints can change; retain the new retrieval date and investigate differences.

~~~python
import json
import time
import urllib.request

scope = {
    "NVDA": ("0001045810", "2024-01-29", "2026-01-25",
             "Revenues", "GrossProfit"),
    "AMD": ("0000002488", "2023-12-31", "2025-12-27",
            "RevenueFromContractWithCustomerExcludingAssessedTax", "GrossProfit"),
    "INTC": ("0000050863", "2023-12-31", "2025-12-27",
             "RevenueFromContractWithCustomerExcludingAssessedTax", "GrossProfit"),
    "QCOM": ("0000804328", "2023-09-25", "2025-09-28",
             "Revenues", "CostOfRevenue"),
}

def get_json(url):
    request = urllib.request.Request(
        url, headers={
            "User-Agent": "HW2-M1-source-feasibility Rylan Wade academic research"
        })
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    time.sleep(0.5)
    return result

for ticker, (cik, first, last, revenue, gross_input) in scope.items():
    filings = get_json(
        f"https://data.sec.gov/submissions/CIK{cik}.json")["filings"]["recent"]
    facts = get_json(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    )["facts"]["us-gaap"]
    selected = [
        i for i, form in enumerate(filings["form"])
        if form in ("10-K", "10-Q")
        and first <= filings["reportDate"][i] <= last
    ]
    passed = 0
    for i in selected:
        intervals = []
        for tag in (revenue, gross_input, "OperatingIncomeLoss",
                    "NetCashProvidedByUsedInOperatingActivities"):
            intervals.append({
                (v["start"], v["end"])
                for v in facts[tag]["units"]["USD"]
                if v.get("accn") == filings["accessionNumber"][i]
                and v["end"] == filings["reportDate"][i]
                and v.get("start")
            })
        passed += bool(set.intersection(*intervals))
    print(ticker, "originals", len(selected), "aligned inputs", passed)
~~~

### Questions for later exploratory demonstrations

- “For NVIDIA's fiscal years ended January 26, 2025 and January 25, 2026, did revenue growth coincide with better operating margin and cash flow?”
- “Why did Qualcomm's gross margin change between FY2024 and FY2025, and how does the extra week affect comparison?”
- “What does AMD's amended FY2025 explanation say, and how does it differ from the original?”
- “What changed in Intel's annual risk disclosures, and which quarterly updates are relevant?”

- These are research/analysis demonstration ideas, not a benchmark set or scored evaluation.

## 9. Verified filing inventory

- All rows were discovered in SEC submissions metadata.
- AMD/Intel links have verified HTML bodies and extraction.
- NVIDIA/Qualcomm links identify canonical SEC originals. Their verified local bodies use official PDFs; exact retrieval paths and checks are in the M2 inventory/results.
- This inventory retains filing dates and accessions; fiscal-year windows and starts are in §2.

| Company | Form | Period end | Filed | Accession / primary source | Body probe |
| --- | --- | --- | --- | --- | --- |
| NVDA | 10-Q | 2024-04-28 | 2024-05-29 | [0001045810-24-000124](https://www.sec.gov/Archives/edgar/data/1045810/000104581024000124/nvda-20240428.htm) | Verified official PDF and extraction; M2 provenance |
| NVDA | 10-Q | 2024-07-28 | 2024-08-28 | [0001045810-24-000264](https://www.sec.gov/Archives/edgar/data/1045810/000104581024000264/nvda-20240728.htm) | Verified official PDF and extraction; M2 provenance |
| NVDA | 10-Q | 2024-10-27 | 2024-11-20 | [0001045810-24-000316](https://www.sec.gov/Archives/edgar/data/1045810/000104581024000316/nvda-20241027.htm) | Verified official PDF and extraction; M2 provenance |
| NVDA | 10-K | 2025-01-26 | 2025-02-26 | [0001045810-25-000023](https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm) | Verified official PDF and extraction; M2 provenance |
| NVDA | 10-Q | 2025-04-27 | 2025-05-28 | [0001045810-25-000116](https://www.sec.gov/Archives/edgar/data/1045810/000104581025000116/nvda-20250427.htm) | Verified official PDF and extraction; M2 provenance |
| NVDA | 10-Q | 2025-07-27 | 2025-08-27 | [0001045810-25-000209](https://www.sec.gov/Archives/edgar/data/1045810/000104581025000209/nvda-20250727.htm) | Verified official PDF and extraction; M2 provenance |
| NVDA | 10-Q | 2025-10-26 | 2025-11-19 | [0001045810-25-000230](https://www.sec.gov/Archives/edgar/data/1045810/000104581025000230/nvda-20251026.htm) | Verified official PDF and extraction; M2 provenance |
| NVDA | 10-K | 2026-01-25 | 2026-02-25 | [0001045810-26-000021](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm) | Verified official PDF and extraction; M2 provenance |
| AMD | 10-Q | 2024-03-30 | 2024-05-01 | [0000002488-24-000056](https://ir.amd.com/financial-information/sec-filings/content/0000002488-24-000056/amd-20240330.htm) | Verified HTML and extraction |
| AMD | 10-Q | 2024-06-29 | 2024-07-31 | [0000002488-24-000123](https://ir.amd.com/financial-information/sec-filings/content/0000002488-24-000123/amd-20240629.htm) | Verified HTML and extraction |
| AMD | 10-Q | 2024-09-28 | 2024-10-30 | [0000002488-24-000163](https://ir.amd.com/financial-information/sec-filings/content/0000002488-24-000163/amd-20240928.htm) | Verified HTML and extraction |
| AMD | 10-K | 2024-12-28 | 2025-02-05 | [0000002488-25-000012](https://ir.amd.com/financial-information/sec-filings/content/0000002488-25-000012/amd-20241228.htm) | Verified HTML and extraction |
| AMD | 10-Q | 2025-03-29 | 2025-05-07 | [0000002488-25-000047](https://ir.amd.com/financial-information/sec-filings/content/0000002488-25-000047/amd-20250329.htm) | Verified HTML and extraction |
| AMD | 10-Q | 2025-06-28 | 2025-08-06 | [0000002488-25-000108](https://ir.amd.com/financial-information/sec-filings/content/0000002488-25-000108/amd-20250628.htm) | Verified HTML and extraction |
| AMD | 10-Q | 2025-09-27 | 2025-11-05 | [0000002488-25-000166](https://ir.amd.com/financial-information/sec-filings/content/0000002488-25-000166/amd-20250927.htm) | Verified HTML and extraction |
| AMD | 10-K | 2025-12-27 | 2026-02-04 | [0000002488-26-000018](https://ir.amd.com/financial-information/sec-filings/content/0000002488-26-000018/amd-20251227.htm) | Verified HTML and extraction |
| AMD | 10-K/A | 2025-12-27 | 2026-02-04 | [0000002488-26-000021](https://ir.amd.com/financial-information/sec-filings/content/0000002488-26-000021/amd-20251227.htm) | Verified HTML and extraction |
| INTC | 10-Q | 2024-03-30 | 2024-04-26 | [0000050863-24-000076](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-24-000076/intc-20240330.htm) | Verified HTML and extraction |
| INTC | 10-Q | 2024-06-29 | 2024-08-02 | [0000050863-24-000124](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-24-000124/intc-20240629.htm) | Verified HTML and extraction |
| INTC | 10-Q | 2024-09-28 | 2024-11-01 | [0000050863-24-000149](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-24-000149/intc-20240928.htm) | Verified HTML and extraction |
| INTC | 10-K | 2024-12-28 | 2025-01-31 | [0000050863-25-000009](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000009/intc-20241228.htm) | Verified HTML and extraction |
| INTC | 10-Q | 2025-03-29 | 2025-04-25 | [0000050863-25-000074](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000074/intc-20250329.htm) | Verified HTML and extraction |
| INTC | 10-Q | 2025-06-28 | 2025-07-24 | [0000050863-25-000109](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000109/intc-20250628.htm) | Verified HTML and extraction |
| INTC | 10-Q | 2025-09-27 | 2025-11-06 | [0000050863-25-000179](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000179/intc-20250927.htm) | Verified HTML and extraction |
| INTC | 10-K | 2025-12-27 | 2026-01-23 | [0000050863-26-000011](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000011/intc-20251227.htm) | Verified HTML and extraction |
| QCOM | 10-Q | 2023-12-24 | 2024-01-31 | [0000804328-24-000017](https://www.sec.gov/Archives/edgar/data/804328/000080432824000017/qcom-20231224.htm) | Verified official PDF and extraction; M2 provenance |
| QCOM | 10-Q | 2024-03-24 | 2024-05-01 | [0000804328-24-000039](https://www.sec.gov/Archives/edgar/data/804328/000080432824000039/qcom-20240324.htm) | Verified official PDF and extraction; M2 provenance |
| QCOM | 10-Q | 2024-06-23 | 2024-07-31 | [0000804328-24-000056](https://www.sec.gov/Archives/edgar/data/804328/000080432824000056/qcom-20240623.htm) | Verified official PDF and extraction; M2 provenance |
| QCOM | 10-K | 2024-09-29 | 2024-11-06 | [0000804328-24-000075](https://www.sec.gov/Archives/edgar/data/804328/000080432824000075/qcom-20240929.htm) | Verified official PDF and extraction; M2 provenance |
| QCOM | 10-Q | 2024-12-29 | 2025-02-05 | [0000804328-25-000011](https://www.sec.gov/Archives/edgar/data/804328/000080432825000011/qcom-20241229.htm) | Verified official PDF and extraction; M2 provenance |
| QCOM | 10-Q | 2025-03-30 | 2025-04-30 | [0000804328-25-000031](https://www.sec.gov/Archives/edgar/data/804328/000080432825000031/qcom-20250330.htm) | Verified official PDF and extraction; M2 provenance |
| QCOM | 10-Q | 2025-06-29 | 2025-07-30 | [0000804328-25-000045](https://www.sec.gov/Archives/edgar/data/804328/000080432825000045/qcom-20250629.htm) | Verified official PDF and extraction; M2 provenance |
| QCOM | 10-K | 2025-09-28 | 2025-11-05 | [0000804328-25-000085](https://www.sec.gov/Archives/edgar/data/804328/000080432825000085/qcom-20250928.htm) | Verified official PDF and extraction; M2 provenance |
