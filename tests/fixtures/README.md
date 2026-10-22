# Reusable fixtures

- [PM questions](pm/questions.json), [controls](pm/controls.json), and [checked references](pm/references.json) support exploratory regression runs.
- [Live routing](live_routing.json) contains the fixed M10 truth table.
- [Risk live comparison](risk_live_comparison.json) contains six independently authored M12 questions and source/usefulness rubrics. They were held out during implementation; subsequent reuse is regression evaluation, not a fresh holdout.
- [Frozen live sources](live_sources.json) contain official/third-party, dated/undated, extraction and injection cases without network access.
- [Source baseline](sources/baseline.json) holds the 41 original document identities and hashes used by the offline alignment check. The full dated collection report lives in [M2 evidence](../../docs/milestones/source-preparation/evidence/M2_COLLECTION_RESULTS.json).
