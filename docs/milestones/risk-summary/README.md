# M7 — Risk Summary

Owner: Rylan Wade. The [milestone index](../README.md) owns status.

Risk Summary has a distinct prompt and three tools: exact risk inspection, paged alignment candidates, and classification registration. It reads hash-checked complete original risk sections independently of top-k retrieval. Each company's complete inventories enter a separate generation context, capped at 600,000 characters; larger requests retain an explicit gap. Generation allows 16 tool calls per company within the supervisor's shared request budget and deadline.

Original 10-K comparisons support NVDA FY2024–FY2026 and AMD, INTC, QCOM FY2024–FY2025. Citations retain accession, form/version, actual fiscal dates, complete-section bounds, text hash, exact offsets, and original download. AMD's FY2025 amendment does not replace original risks. Explicit amendment questions also inspect its explanatory note: it corrects the MD&A Client processor shipment/ASP disclosure. Amendment context cannot establish an annual risk change. Quarterly requests inspect the requested quarter or quarter range and preceding annual inventory; missing prior context stays missing. Quarterly omission never proves annual removal.

Alignment matches whitespace/page-furniture-normalized exact wording globally. Remaining blocks receive subject-overlap candidates ranked by token sequence similarity; 0.55 admits a navigation candidate, not a risk classification. Exact wording can be unchanged or relocated according to inspected subject context. Rephrasing is changed. Added/removed wording needs a complete original annual opposite-side citation and absence rationale; a cited paragraph never inherits complete-section status. Existing exact language is rejected. A missing phrase does not prove new economic exposure. Semantic classification and materiality remain model judgments.

The brief prioritizes material changes, stable disclosures, management context, and unresolved cases. Classification records preserve both source IDs. `/api/risks/{document_id}?start=...&end=...` rechecks hashes and bounds and returns exact text with context. The existing browser citation viewer opens it. Missing sections, stale/corrupt data, unsupported windows, incomplete generation, and worker failure remain explicit. Multi-issuer collection has a 200-second aggregate deadline within the supervisor's 210-second worker limit; a later issuer failure retains completed issuers. Mixed annual and quarterly requests prepare both the annual comparison and the quarter's preceding annual context.

```powershell
uv run --locked pytest -q
uv run --locked python scripts/demo_risk.py --direct
uv run --locked python scripts/start_local_container.py
uv run --locked python scripts/demo_risk.py --url http://127.0.0.1:8084 --output artifacts/m7-docker.json
```

[Acceptance evidence](evidence/M7_ACCEPTANCE_2026-10-16.json) separates direct subscription generation, real filing API/graph turns, native Chromium, local Docker/Chromium, and synthetic failures. The AMD review distinguishes expanded export controls, infrastructure-support commitments, rephrased competition, and acquisition-stage changes. Qualcomm customer concentration persists across both complete annual sections. The quarterly AMD case rejects removal from omission. An actual generation run ignores an injected document recommendation. Fixture checks cover exact relocation, missing sections, corrupt data, annual/quarter absence rules, deadline failure, and existing route selection. Formal risk-label scoring remains M12.
