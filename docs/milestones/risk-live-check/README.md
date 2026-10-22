# M12 — Risk Summary live check

Owner: Rylan Wade. The [milestone index](../README.md) owns status and order.

M12 is implemented and compared in the separate local `main` commit `6aa5a47`. Both additional Tavily callers remain available pending Rylan Wade's selection; Risk Summary checks every registered finding by default, while Research handles an explicitly requested official update. Current Developments remains the broader live specialist.

This `eval/ragas` branch starts from remote `main` at `aec3b3c` and intentionally excludes M12's code and comparison artifacts. Its [static RAGAS evaluation](../../evaluation.md) supplies no web tools and does not depend on the caller selection. The comparison is available from the local M12 commit:

```powershell
git show 6aa5a47:docs/milestones/risk-live-check/evidence/COMPARISON_2026-10-22.md
```

Merge the selected M12 configuration separately; no caller-selection decision is made by this evaluation branch.
