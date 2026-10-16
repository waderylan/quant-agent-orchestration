# M1 — Source feasibility

Owner: Rylan Wade.

The four selected companies have identifiable FY2024/FY2025 filings and matching SEC Company Facts USD inputs; NVIDIA also has FY2026. [Project coverage](../../project.md) gives the exact fiscal windows. SEC Archives returned HTTP 403 locally, so the [inventory](../../../data/source_inventory.json) uses verified official IR mirrors and CDNs where needed. Source bodies, financial definitions, and amendment identities are checked before analysis. Qualcomm FY2024 has 53 weeks and gross profit needs revenue minus cost of revenue. AMD's FY2025 amendment corrects MD&A, not the original risk section.

## Decisions and evidence

- Use one selected company/fiscal window per source. SEC submissions establish CIK, form, accession, and report date; Company Facts establishes matching-duration USD inputs. An accessible financial API alone does not supply the narrative filing.
- Use 10-K and Q1–Q3 10-Q originals plus full-year/Q4 releases. A Q4 10-Q is not invented; Q4 figures need annual and nine-month inputs. Keep amendments as separate versions.
- Show actual fiscal dates in cross-company analysis. Qualcomm's 53-week FY2024 needs a comparability note. The initial metric definitions are consolidated US GAAP revenue, gross profit or its checked inputs, operating income/loss, and operating cash flow.
- Direct SEC Archives probes returned 403 in this environment; official company mirrors/CDNs were checked for accessible originals. The selected URLs and identities live in the [inventory](../../../data/source_inventory.json), not in a duplicate filing list here.

Verified milestone commit: `93372e5`. Current source-body/hash verification runs with `uv run --locked python scripts/collect_sources.py verify` and is recorded under [M2](../source-preparation/README.md). Add a company or fiscal year only after checking report identity, accessible original, extraction, matching financial intervals, and its effect on request coverage.
