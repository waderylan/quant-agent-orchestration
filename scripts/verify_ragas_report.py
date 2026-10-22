"""Recompute recorded RAGAS arithmetic without new judge or generation calls."""

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from src.research_index import LocalEmbedding
from src.source_collection import now, write_json


def verify(report):
    embed = LocalEmbedding(preferred_providers=["CPUExecutionProvider"])
    checked = []
    for cohort in report["cohorts"]:
        grouped = defaultdict(list)
        for judgment in cohort["judgments"]:
            grouped[judgment["context"]].append(judgment)
        for row in cohort["cases"]:
            for name, metric in row["metrics"].items():
                if metric["value"] is None:
                    continue
                records = grouped[row["id"] + ":" + name]
                responses = [r["response"] for r in records]
                extra = {}
                if name == "faithfulness":
                    nli = next(r["statements"] for r in responses if r.get("statements") and isinstance(r["statements"][0], dict))
                    supported = sum(bool(s["verdict"]) for s in nli)
                    value = supported / len(nli)
                    extra = {"supported_statements": supported, "total_statements": len(nli),
                             "rejected_statements": [s for s in nli if not s["verdict"]]}
                elif name == "answer_relevancy":
                    assert len(responses) == 3, "Strictness must retain three draws"
                    assert [r["sample_index"] for r in records] == [0, 1, 2]
                    questions = [r["question"] for r in responses if r["question"]]
                    vectors = np.asarray(embed([row["question"], *questions]))
                    similarities = vectors[1:] @ vectors[0] / (np.linalg.norm(vectors[1:], axis=1) * np.linalg.norm(vectors[0]))
                    value = float(similarities.mean()) * int(not all(r["noncommittal"] for r in responses if r["question"]))
                    extra = {"generated_questions": questions, "cosine_similarities": similarities.tolist(),
                             "noncommittal": [r["noncommittal"] for r in responses]}
                elif name == "context_precision":
                    verdicts = [r["verdict"] for r in responses]
                    assert len(verdicts) == len(row["contexts"]), "Every model-visible context must be judged"
                    value = sum(sum(verdicts[:i + 1]) / (i + 1) * v for i, v in enumerate(verdicts)) / (sum(verdicts) + 1e-10)
                    extra = {"relevant_contexts": sum(verdicts), "retrieved_contexts": len(verdicts), "verdicts": verdicts}
                elif name == "context_recall":
                    classifications = responses[0]["classifications"]
                    value = sum(r["attributed"] for r in classifications) / len(classifications)
                    extra = {"attributed_reference_statements": sum(r["attributed"] for r in classifications),
                             "reference_statements": len(classifications)}
                else:
                    raise ValueError("Unknown metric in evidence")
                if not math.isclose(value, metric["value"], rel_tol=1e-6, abs_tol=1e-6):
                    raise ValueError(f"Recorded judgment does not reproduce {cohort['name']} / {row['id']} / {name}: {value} vs {metric['value']}")
                checked.append({"cohort": cohort["name"], "id": row["id"], "metric": name,
                                "recorded": metric["value"], "recomputed": value, **extra})
    return {"checked_at": now(), "method": "Recorded structured judgments and pinned local embeddings; no model/API calls",
            "verified_metric_values": len(checked), "tolerance": 1e-6, "checks": checked}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(json.loads(args.report.read_text(encoding="utf-8")))
    write_json(args.output, result)
    print(json.dumps({"verified_metric_values": result["verified_metric_values"], "new_model_calls": 0}))
