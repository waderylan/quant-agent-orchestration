# Independent engineering review — round 1

The [48 sealed cases](questions.json) contain 16 questions each from portfolio-manager, equity-researcher and self-directed-investor perspectives. They specify evidence and failure criteria, not invented financial answers. [Isolation](isolation.json) records the actual delegation text, orphan worktree commit, input hashes and question seal. The fresh reviewer receives only the product brief and supported scope when generating cases. It receives application answers only after sealing. This is instruction-based worktree isolation, not an OS security boundary.

[Results](results.json) record actual production POST/SSE responses using subscription generation, original filings, frozen real MCP responses and explicitly labeled controlled faults. Immutable application snapshots identify the tested code. Live MCP connections and ledger reservations are forbidden in the review service. The shared live ledger stays unchanged. Boundary validation, cancellation and generated answers remain distinct outcomes. Licensed market answers and raw traces stay in ignored artifacts.

The final source audit independently revisits 416 inspection links with zero failures and replays 136 calculations. It checks exact passage text, common value/unit/period/lineage metadata, bundle checksums and artifact files. It does not score arbitrary narrative faithfulness. Interrupted review services are restarted from unchanged snapshots; synthetic inspection registries are reconstructed from their fixture definitions, never from recorded answers.

The initial diagnostic [adjudication](adjudication-initial.json), [review before final fixes](adjudication-before-final-fixes.json), [affected-case supplement](adjudication-supplement.json) and [conflict wording check](wording-check.json) retain reviewer findings. Effective reviewer verdicts are 44 pass, zero fail and four condition-unverified. The original cases and criteria remain unchanged. R1-007, R1-009 and R1-036 require qualified-consensus premises that real accounts do not establish. R1-019's QCOM quarterly-omission fixture is visibly synthetic; its answer conservatively declines to authenticate actual management disclosure. The final conflict handoff explicitly distinguishes existing ineligible observations from missing eligible calculation inputs.

Verified fixes cover complete-section absence eligibility, bounded per-issuer risk context, exact source preservation, AMD amendment scope, mixed-request requirements, signed cash-conversion exclusions, QCT/consolidated denominators, net margin, supported annual shares alongside unsupported quarterly detail, inspectable conflicting observations, provider quota diagnostics, scenario units/horizons, replay metadata and completion-tool reservation. Failed or missing later work retains earlier cited evidence. Overlapping requests return interleaved worker outcomes without company leakage; cancellation occurs after checked historical work and before a deliberately delayed provider delivery.

```powershell
uv run --locked pytest -q
uv run --locked python scripts/start_review_application.py --port 8086
uv run --locked python scripts/run_review_cases.py docs/milestones/supervisor/evidence/review-round-1/questions.json --url http://127.0.0.1:8086 --output artifacts/review-rerun.json
```

Replay requires the prepared original corpus and locally retained market cache. No market credentials enter the frozen review service. `scripts/audit_review_results.py` merges complete runs and affected-case reruns, checks the question seal, inspects sources and replays calculations. These engineering checks are separate from M12's formal RAGAS and trajectory evaluation.
