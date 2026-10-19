# M9 — Supervisor cooperation

Owner: Rylan Wade. The [milestone index](../README.md) owns status.

The LangGraph supervisor plans requested outputs and runs only their owners: Financial Data, Quant, Risk Summary, Filings Research and Current Developments. Data precedes arithmetic; an annual component gap permits a bounded filing extraction. Filing explanations follow checked values; live developments run last. Verification requests give Research one official-update search. Capability-only questions complete locally. Price-only requests end with a scope gap and no worker; supported mixed clauses continue.

`TaskState` records outputs, ordered dependencies and reasons, outcomes, typed `EvidenceRef` owners, missing inputs and execution counts. An isolated registry holds complete authoritative S/F/C/W records; handoffs contain bounded text and exact metadata. New passage and live identifiers start above existing IDs. The supervisor validates handoffs transactionally, rejects changed values/bases or reused identities, and copies inputs to prevent mutation. Failed later work preserves earlier verified findings.

Requests require explicit supported companies and fiscal years. Company exclusions narrow every worker; calendar timestamps do not add fiscal years. Prior-turn assumptions require clarification because requests are self-contained. One supported evidence follow-up can resolve structured absence. Limits are seven steps, one follow-up, 64 model tool calls and 210 seconds per worker. Cancellation closes owned generation. Final states distinguish completed, partial, clarification, coverage gap, unverified and failed.

The current five-worker handoff is verified with isolated fixtures in `tests/test_supervisor.py`; [M10 acceptance](../current-developments/README.md) verifies real Data → Quant → Research → Current Developments, short paths and shared live-search traces. Mixed risk/live answers retain worker headings. Unknown references never become evidence.

The dated 2026-10-16 [acceptance](evidence/M9_ACCEPTANCE_2026-10-16.json), [first review](evidence/review-round-1/README.md) and [second review](evidence/review-round-2/README.md) record the agent set at commit `5f9f1e0`.

```powershell
uv run --locked pytest -q
uv run --locked python scripts/demo_supervisor.py --url http://127.0.0.1:8080
uv run --locked python scripts/verify_cooperation_edges.py --url http://127.0.0.1:8080
```
