# Reusable fixtures

- [PM questions](pm/questions.json), [controls](pm/controls.json), and [checked references](pm/references.json) support exploratory regression runs.
- [Live routing](live_routing.json) contains the fixed M10 truth table.
- [Frozen live sources](live_sources.json) contain official/third-party, dated/undated, extraction and injection cases without network access.
- [Source baseline](sources/baseline.json) holds the 41 original document identities and hashes used by the offline alignment check. The full dated collection report lives in [M2 evidence](../../docs/milestones/source-preparation/evidence/M2_COLLECTION_RESULTS.json).

- `ragas_development.json`: eight source-reviewed static Research questions used for retrieval refinement; exact document/span hashes and atomic reference facts.
- `ragas_heldout.json`: four questions sealed until frozen native captures completed, now published for reproducibility. Future tuning on these questions requires a new held-out set.
- `ragas_controls.json`: separate missing-coverage and missing-referent controls, excluded from metric denominators.
- `ragas_reference_errata.json`: source-backed narrow correction to the segment-platform reference; original dataset bytes remain unchanged and scoring records both hashes.
