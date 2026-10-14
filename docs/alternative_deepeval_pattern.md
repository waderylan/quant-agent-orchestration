# Alternative Evaluation Pattern: DeepEval

- Role: instructor reference guidance. Example models, files, and interfaces are not verified HW2 implementation. Current project decisions are in the [project spec](planning/PROJECT_SPEC.md).

RAGAS is the required/reference evaluation surface for Assignment 2. DeepEval can be used as an additional engineering comparison, but it does not replace the required RAGAS report unless the instructor explicitly changes the assignment contract.

A DeepEval experiment can add pytest-style assertions around response quality, retrieval relevance, hallucination, or task-specific criteria. Keep it separate from the reference RAGAS evaluator (example path: `src/eval/ragas_eval.py`) so graders can still reproduce the required metrics.

If included, pin the current DeepEval version and document any evaluator-model costs.
