# C1 — Codebase cleanup

Owner: Rylan Wade. The [milestone index](../README.md) owns status and order.

## Current behavior

- `src/response_contract.py` owns the shared strict tool-schema builder. Risk Summary and Current Developments import it directly; live research has no dependency on the risk worker.
- Typed review models generate and validate the answer-review schema. Unsupported spans are removed at sentence boundaries, preserving supported neighboring sentences and avoiding incomplete clauses. The bounded second review checks the resulting answer.
- Demonstration scripts share `capture_turn` and readiness polling. Capture retains the latest authoritative answer, latest source set and terminal outcome; raw events are optional. Filing demonstrations inspect S passages, while financial and calculation inspections remain in their own demonstrations.
- Reusable demonstrations write local run output under ignored `artifacts/`. The obsolete import-time risk acceptance recorder is absent; dated milestone evidence stays preserved.
- Capability descriptions distinguish local answers from web research. Semantic wording can use the request planner and reviewer without invoking an external-research worker.

## Verification

`uv run --locked pytest -q` passes 271 tests. Mocked SSE cases exercise replacement answers, replaced source sets, mixed S/F/C records and partial terminal status. Review checks must explicitly include omissions and unsupported claims. Sentence-repair regressions preserve supported findings and handle company abbreviations. Tests block real Tavily transport.

[Acceptance evidence](evidence/ACCEPTANCE_2026-10-19.json) records native and Linux-container calculation checks, documentation links, preserved evidence and the unchanged Tavily ledger. [Image security](evidence/SECURITY_2026-10-19.json) records the credential scan. The [file manifest](evidence/FILES_2026-10-19.json) groups changes across usefulness and cleanup. These are local engineering checks; [evaluation](../../evaluation.md) separates them from formal provider and deployment results.

```powershell
uv run --locked pytest -q
uv run --locked python -m compileall -q src scripts main.py
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8080
```
