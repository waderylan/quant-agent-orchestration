# M1 — Source feasibility

The four selected companies have identifiable FY2024/FY2025 filings and matching SEC Company Facts USD inputs; NVIDIA also has FY2026. [Project coverage](../../project.md) gives the exact fiscal windows. SEC Archives returned HTTP 403 locally, so the [inventory](../../../data/source_inventory.json) uses verified official IR mirrors and CDNs where needed. Source bodies, financial definitions, and amendment identities are checked before analysis. Qualcomm FY2024 has 53 weeks and gross profit needs revenue minus cost of revenue. AMD's FY2025 amendment corrects MD&A, not the original risk section.

Verified milestone commit: `93372e5`. The current collection is reproduced with `uv run --locked python scripts/collect_sources.py verify` and the checks in [M2](../source-preparation/README.md).
