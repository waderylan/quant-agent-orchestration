# PM question exploration — 2026-10-15

The [questions](../../../tests/fixtures/pm/questions.json) and [controls](../../../tests/fixtures/pm/controls.json) probe ordinary portfolio-manager requests, unsupported scope, ambiguity, source gaps, and multi-step analysis. [References](../../../tests/fixtures/pm/references.json) contain independent checks. This is an exploratory set, not a held-out benchmark.

The baseline run has 26 questions and four controls. Review labels report 16 useful outcomes, four honest boundaries, three incomplete answers, and three workflow failures. Its audit checks 147 source references, 31 calculations, and nine bundles. The fixes and 30-chat retest are recorded in [M6](../../milestones/quant/README.md).

[Results](evidence/PM_EXPLORATION_2026-10-15_RESULTS.json), [review](evidence/PM_EXPLORATION_2026-10-15_REVIEW.json), [audit](evidence/PM_EXPLORATION_2026-10-15_AUDIT.json), and [control results](evidence/PM_EXPLORATION_2026-10-15_CONTROL_RESULTS.json) preserve the original runs.
