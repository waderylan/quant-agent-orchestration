# Independent engineering review — round 2

The fresh reviewer inspects an orphan snapshot of the design after first-round fixes. Its 34 allowed input files include the product brief, supported scope, assignment, architecture and implementation, but no prior questions, answers, tests, review evidence, credentials or implementation history. [Isolation](isolation.json) preserves input blob hashes, the actual delegation text, orphan commit and file seals. Access restrictions and a separate worktree provide instruction-based isolation, not an OS sandbox. Only the parent runs the product or providers.

The [24 sealed questions](questions.json) contain eight cases per investor perspective. [Findings](REVIEW_FINDINGS.md) record independent design observations. Questions and failure criteria remain unchanged. Answers enter the reviewer's workspace only after sealing. The [baseline adjudication](adjudication-baseline.json) reports 14 passes, nine failures and one unverified condition; the [final adjudication](adjudication-final.json) reports 24 passes, zero failures and zero unverified conditions. R2-015 retains a nonblocking redundant scope explanation and unsupported source-security aside.

[Application results](results.json) combine actual production POST/SSE runs and affected-case reruns with subscription generation, original filings and frozen real MCP responses. Controlled faults are explicitly labeled. Source audits independently check 190 inspection links with zero failures and replay 73 calculations. They verify exact text, metadata, checksums and arithmetic rather than scoring every narrative claim. Licensed market answers and raw traces remain in ignored artifacts.

Verified fixes preserve explicit company exclusions, distinguish calendar timestamps from fiscal years, bind separate issuer assumptions and horizons, require clarification for ambiguous currency and absent prior-turn inputs, retain completed issuer risk results after a later timeout, prepare annual and quarterly risk contexts separately, select Quant for Q4 amounts, and distinguish AMD MD&A amendment analysis from annual risk comparison. Explicit stock quotes still select market work in mixed filing requests. Direct fixtures also exercise the aggregate risk deadline before the supervisor's outer timeout.

The corrupted-text setup mutates a disposable copy of one prepared risk section while retaining its original recorded hash; the real validator rejects it and financial snapshots remain usable. The timeout setup completes NVIDIA risk generation before raising at AMD's start. The closed-market fixture pairs the newer extended-session price with its own past timestamp. Its initial future-timestamp setup is recorded as unverified in the baseline, then corrected without changing the question or criteria.

Every review service runs without market credentials and blocks MCP connections and live reservations; denied attempts remain zero. The final extra run overlaps separately authorized parent live testing, so its shared global ledger changes. Those calls do not originate in the frozen review service. Earlier runs retain their unchanged-ledger checks. [Real MCP review evidence](../../../buy-side-analyst/evidence/MCP_REVIEW_2026-10-16.json) accounts for parent live calls separately.

```powershell
uv run --locked pytest -q
uv run --locked python scripts/start_review_application.py --port 8094 --market-cache artifacts/review-2-market-cache
uv run --locked python scripts/run_review_cases.py docs/milestones/supervisor/evidence/review-round-2/questions.json --url http://127.0.0.1:8094 --output artifacts/review-2-baseline.json
uv run --locked python scripts/audit_review_results.py docs/milestones/supervisor/evidence/review-round-2/questions.json --run http://127.0.0.1:8094=artifacts/review-2-baseline.json --run http://127.0.0.1:8095=artifacts/review-2-fixed.json --run http://127.0.0.1:8096=artifacts/review-2-injection-final.json --run http://127.0.0.1:8097=artifacts/review-2-final-extra.json --output docs/milestones/supervisor/evidence/review-round-2/results.json
```

Replay requires the original prepared corpus and locally retained cache. Immutable application identities distinguish baseline and fixed runs. These engineering reviews do not substitute for M12's formal evaluation or establish deployed-provider behavior.
