# M7 — Risk Summary

Owner: Rylan Wade. This milestone adds a distinct Risk Summary specialist that answers how a company's disclosed risks changed, with both filing passages openable from the answer. The [milestone index](../README.md) owns status and order.

## Scope and dependencies

- Use the verified [filing corpus](../../project.md), exact passage inspection, request scope, citations, and SSE trace. Start with annual FY2024/FY2025 comparisons for NVDA, AMD, INTC, and QCOM; NVIDIA FY2026 is also available. Display actual fiscal dates.
- Compare original risk sections with the corresponding original sections. AMD's FY2025 10-K/A corrects MD&A and does not replace its original risks. A 10-Q risk section may contain only updates, so an omitted annual paragraph in a quarter is not proof of removal.
- Add a separate role prompt, bounded tools, and a graph route for risk questions. M9 owns general five-worker planning; M10 owns live sources and shared MCP. This worker initially uses verified local filings.

## Work to implement

- Retrieve and inspect the complete relevant risk sections, retaining company, fiscal window, filing form, accession, version, section, and exact text offsets. A search hit alone cannot establish that a risk disappeared.
- Align passages by subject before comparing wording. Classify a supported change as **added, removed, changed, relocated, or unchanged**. For each material classification, link the before/after passages or state precisely which complete section was checked for an absence. Explain why a moved or rephrased paragraph is not a new risk.
- Produce a short risk-change brief: material changes first, stable risks where relevant, management's stated context if present, and unresolved cases. Distinguish disclosure language from the assistant's interpretation. Say “insufficient evidence” when a section or filing is unavailable.
- Keep source IDs request-local and hash-checked. Reuse the existing completion and partial-result contract, bounded generation, cancellation, and browser citation viewer.

## Acceptance evidence

1. A direct Risk Summary worker run and a full graph/API/browser run show distinct prompt/tool use, route trace, cited before/after passages, and inspectable originals. Local Docker runs the same path.
2. Reviewed cases cover at least two companies and an annual year-over-year comparison, a relocated/reworded paragraph, AMD's amendment, and a quarterly update. Record expected passages and why each label is justified.
3. Missing sections, unsupported years, corrupted/stale index data, model/tool failure, and document prompt injection yield an explicit partial, gap, or failure without fabricated change claims. Existing Research/Data/Quant routes still pass.
4. Update [architecture](../../architecture.md) with the worker, tools, state handoff, and limitations; put dated run evidence under this milestone's `evidence/`.

Useful questions: “What changed in AMD's risk factors from FY2024 to FY2025?” and “Did Qualcomm add a customer concentration risk, or move existing language?” Define exact comparison rules and any similarity thresholds from inspected filings before treating a diff score as evidence. Formal risk-label scoring belongs to M12.
