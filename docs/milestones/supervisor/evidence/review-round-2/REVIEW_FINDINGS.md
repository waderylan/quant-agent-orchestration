# Independent second design review

- Review: orphan current-design snapshot; static inspection only.
- Cases: 24 new sealed cases, eight per requested persona.
- Execution: none. No implementation imports, application runs, providers, network, installation, credential inspection, Git history or external state inspection.
- Financial answers: none invented. Numerical values in scenario questions are explicitly hypothetical user assumptions.
- Source references below describe observed code paths, not reproduced runtime failures.

## Substantive source-based findings

### R2-F1 — Actual fiscal-window dates are interpreted as extra fiscal-year requests
- Severity: high; supported requests can fail scope validation before any worker runs.
- Observation: `src/request_routing.py:43-48` extracts every four-digit year, including ISO calendar dates. `src/research_workflow.py:195-196` rejects any extracted year outside selected fiscal years.
- Concrete trigger: R2-016 includes NVIDIA FY2024's actual start date 2023-01-30 while selecting only FY2024. The supplied project explicitly defines this interval as FY2024.
- Expected correction boundary: distinguish fiscal selection labels from calendar dates and publication/quote timestamps.
- Runtime status: not executed.

### R2-F2 — Explicit company exclusions do not narrow the effective analysis scope
- Severity: high; extra companies can enter calculations and conclusions against the user's instruction.
- Observation: `src/request_routing.py:28-40` removes exclusion clauses only when detecting mentioned companies. `src/research_workflow.py:197-201` uses that result for missing-selection validation. The supervisor retains original `state["companies"]` in the plan/worker state (`src/supervisor.py:324-326,477-486`); financial tools query all selected companies by default (`src/financial_workflow.py:125-130`).
- Concrete trigger: R2-006 selects all four in the UI and explicitly asks for NVDA/AMD only, excluding INTC/QCOM.
- Expected correction boundary: a turn-specific effective scope or explicit clarification; preserve the user's exclusions across every worker.
- Runtime status: source flow inspected; whether generation independently filters every result is unverified.

### R2-F3 — EPS grids can lose explicit EUR denomination and become USD assumptions
- Severity: high; incorrect currency can contaminate checked financial outputs.
- Observation: `src/buy_side.py:263-264` parses EPS/P-E grids without currency metadata. The EUR guard at lines 271-273 applies only to the scalar EPS match. Every grid value is registered with `currency="USD"` at lines 297-305. `src/quant_valuation.py:13-24` then accepts the internally asserted USD basis.
- Concrete trigger: R2-020 gives a EUR EPS grid and requests USD targets without FX.
- Expected correction boundary: parse grid-wide currency or ask for clarification; never relabel EUR as USD.
- Runtime status: not executed. A careful model might abstain, but the trusted input registry itself encodes the wrong basis.

### R2-F4 — Multiple issuer-specific scalar scenarios are reduced to the first match
- Severity: high for incomplete or misbound multi-company scenario outputs.
- Observation: `src/buy_side.py:251-265` uses one `re.search` each for EPS, multiple and horizon. Lines 276-286 bind one issuer from the clause before that first EPS. Lines 287-320 create inputs for that issuer only; no loop parses later issuer clauses.
- Concrete trigger: R2-005 supplies separate NVDA and AMD assumptions with distinct horizons.
- Expected correction boundary: preserve each issuer-local assumption group or state the unrepresented scenario explicitly as missing. An honest partial answer is preferable to a completed one-issuer response.
- Runtime status: not executed; exact generated abstention/completion remains unverified.

### R2-F5 — A later issuer failure can discard an earlier verified risk review
- Severity: high; partial-result preservation breaks inside a multi-issuer specialist.
- Observation: `src/risk_summary.py:229-241` awaits each issuer recursively and only merges/emits successful answers after the entire loop. There is no per-issuer exception boundary. A later exception propagates to the supervisor, whose failure path resets `result={}` (`src/supervisor.py:638-672`); earlier per-issuer results have never entered its evidence registry.
- Concrete trigger: R2-015 completes the NVDA risk review, then injects TimeoutError when AMD generation starts.
- Expected correction boundary: preserve each completed issuer's source registry/classifications and expose remaining failures as partial.
- Runtime status: not executed.

### R2-F6 — Mixed annual and quarterly risk requests select a quarterly-only preparation path
- Severity: medium; a requested annual comparison can silently become unavailable.
- Observation: `src/risk_summary.py:243-244` sets quarterly mode if any quarter/10-Q mention exists and skips `tools.prepare()`. Lines 249-281 register requested quarterly sections and prior annual context, but do not build the original annual-to-annual comparison inventory/alignment.
- Concrete trigger: R2-002 requests FY2024-to-FY2025 annual changes and a separate FY2025 Q3 update review.
- Expected correction boundary: separately prepare both requested temporal analyses and distinguish their information-availability dates.
- Runtime status: annual-comparison omission is a hypothesis to verify; the model can inspect supplied context but cannot manufacture the absent FY2025 annual preparation.

### R2-F7 — Amount-only Q4 revenue requests miss the available Quant derivation route
- Severity: high for a core supported financial workflow.
- Observation: `src/request_routing.py:204-209,374-389` sends amount-only consolidated requests to Data; the special Q4 derivation trigger only covers cash flow. `src/supervisor.py:177-183` adds Quant only for analysis/component/numeric requests. `src/financial_workflow.py:148-152` rejects Q4 when no Quant prefetch exists, although `src/quant_workflow.py:51-55` implements the required annual/Q3 inputs.
- Concrete trigger: R2-021 asks how much Q4 revenue was reported and requests its source derivation without a growth/chart verb.
- Expected correction boundary: required derivation follows requested period/metric, independent of trigger verbs.
- Runtime status: not executed.

## Additional hypotheses encoded in held-out cases

- R2-003 requests two distinct earnings orderings; the request plan carries one `earnings_order` (`src/request_routing.py:358-373`), and deterministic earnings assessment validates only that order (`src/quant_workflow.py:270-290`). Verify both requested outputs survive.
- R2-010 requests both quarter and YTD cash-conversion ratios. Prefetch uses one initial quarter path (`src/quant_workflow.py:45-62`), and ratio coverage is keyed only by company/year (`src/quant_workflow.py:143-155`); verify both interval-specific outputs rather than treating one ratio as sufficient.
- R2-011 asks for two revenue denominators. Request routing carries one `revenue_denominator` (`src/request_routing.py:250-271`); deterministic coverage checks only that selected denominator (`src/quant_workflow.py:217-240`). Inputs may still permit both; verify final coverage.
- R2-014 deliberately corrupts a local prepared source while leaving recorded hashes unchanged. This tests integrity-failure isolation, not real financial content.
- R2-008 injects hostile instructions only into a clearly synthetic frozen source field. It cannot authenticate company facts and should never supply an authoritative citation or trade instruction.

## Limits and assumptions

- No prior review cases, outputs, tests, evidence, implementation history or provider entitlement findings were inspected.
- File inspection was limited to this snapshot's instructions, product brief, supplied assignment/project/architecture, design source files and prompts.
- Deferred multi-provider routing, public display rights, deployment and formal evaluation remain documented pending work; this review does not claim to verify or newly discover their completion status.
- The parent owns all execution and fixes. Acceptance uses real original filings or explicitly labeled controlled fixtures, frozen MCP schemas and injected failures; no live-provider authority was delegated.
- Questions and criteria are sealed before parent execution. Genuine missing evidence permits explicitly qualified partial results only where listed. A partial label alone does not pass a case if available supported outputs are dropped or facts are fabricated.
