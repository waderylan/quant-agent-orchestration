"""Capture real static Research runs and score them with the four pinned RAGAS metrics."""

import argparse
import asyncio
import importlib.metadata
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")

from ragas.metrics.collections import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness
from scripts.ragas_support import ADAPTER_VERSION, JUDGMENT_CONTEXT, CodexJudge, LocalJudgeEmbedding, capture_case, runtime_hashes
from src.research_index import CONFIG, ResearchIndex
from src.source_collection import ROOT, digest, now, write_json


def dataset(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data["cases"]
    ids = [c["id"] for c in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError("Dataset requires nonempty unique case IDs")
    return cases


def verify_references(cases, index):
    checked = 0
    for case in cases:
        for ref in case.get("reference_contexts", []):
            doc = index.documents[ref["document_id"]]
            text = index.text(doc)
            if ref["text_sha256"] != doc["extraction"]["text_sha256"] or text[ref["start"]:ref["end"]] != ref["text"]:
                raise ValueError(f"Reference checksum/span mismatch: {case['id']}")
            checked += 1
        if case.get("metric_eligible", True) and case.get("reference") and not case.get("reference_contexts"):
            raise ValueError(f"Reference answer has no reviewed source: {case['id']}")
    return checked


def metadata():
    return {"checked_at": now(), "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "runtime_hashes": runtime_hashes(), "adapter": ADAPTER_VERSION,
            "evaluator_hashes": {p.name: digest(p.read_bytes()) for p in (ROOT / "scripts/evaluate_ragas.py", ROOT / "scripts/ragas_support.py")},
            "versions": {name: importlib.metadata.version(name) for name in ("ragas", "langchain-community", "langchain-core", "chromadb", "onnxruntime", "pydantic")},
            "embedding": CONFIG, "judge": "Codex subscription / gpt-6.1-sol",
            "web": "disabled by direct static Research invocation; no live_check supplied"}


def formatted_context(context):
    # Metadata is evidence too: the worker sees period_end/form/version even when
    # the fragment itself contains no fiscal label. Never add reference metadata.
    fields = {k: v for k, v in context.items()
              if k not in ("text", "context", "model_visible_text", "first_seen_rank")}
    return "Source metadata: " + json.dumps(fields, sort_keys=True) + "\n" + context["model_visible_text"]


async def capture(args):
    cases = dataset(args.dataset)
    index = ResearchIndex(args.corpus.resolve(), args.index.resolve())
    spans = verify_references(cases, index)
    identity = {"dataset_sha256": digest(args.dataset.read_bytes()), "corpus_fingerprint": index.fingerprint,
                "profile": args.profile, "runtime_hashes": runtime_hashes()}
    report = {**metadata(), **identity, "kind": "Direct static Filings Research worker; actual Chroma and generation, no supervisor/browser/cloud",
              "reference_spans_checked": spans, "cases": []}
    if args.resume and args.output.exists():
        report = json.loads(args.output.read_text(encoding="utf-8"))
        if any(report.get(k) != v for k, v in identity.items()):
            raise ValueError("Resume requires identical dataset, runtime, corpus and profile")
    done = {r["id"] for r in report["cases"]}
    semaphore = asyncio.Semaphore(args.concurrency)

    async def one(case):
        if case["id"] in done:
            return
        async with semaphore:
            try:
                row = await capture_case(index, case, profile=args.profile)
            except Exception as error:
                row = {"id": case["id"], "capture_error": f"{type(error).__name__}: {error}"}
            report["cases"].append(row)
            report["runtime_unchanged"] = runtime_hashes() == identity["runtime_hashes"]
            write_json(args.output, report)
            print(json.dumps({"id": case["id"], "captured": "capture_error" not in row,
                              "partial": row.get("result", {}).get("partial"),
                              "contexts": len(row.get("contexts", [])), "timing": row.get("timing")}), flush=True)

    await asyncio.gather(*(one(case) for case in cases))


async def score_row(row, case, judge, embeddings):
    answer = row.get("result", {}).get("answer", "")
    contexts = [formatted_context(c) for c in row.get("contexts", [])]
    if not answer or not contexts or not case.get("reference"):
        return {"id": case["id"], "status": "unavailable", "reason": "Capture answer, model-visible context or reviewed reference missing", "metrics": {}}
    inputs = {"user_input": case["question"], "response": answer,
              "retrieved_contexts": contexts, "reference": case["reference"]}
    definitions = [(Faithfulness(llm=judge), ("user_input", "response", "retrieved_contexts")),
                   (AnswerRelevancy(llm=judge, embeddings=embeddings, strictness=3), ("user_input", "response")),
                   (ContextPrecision(llm=judge), ("user_input", "retrieved_contexts", "reference")),
                   (ContextRecall(llm=judge), ("user_input", "retrieved_contexts", "reference"))]
    values = {}
    started = time.monotonic()
    async def evaluate_metric(metric, fields):
        token = JUDGMENT_CONTEXT.set(case["id"] + ":" + metric.name)
        began = time.monotonic()
        try:
            result = await metric.ascore(**{k: inputs[k] for k in fields})
            value = float(result.value)
            values[metric.name] = {"value": value if math.isfinite(value) else None,
                                   "status": "scored" if math.isfinite(value) else "undefined",
                                   "reason": result.reason}
        except Exception as error:
            values[metric.name] = {"value": None, "status": "error", "reason": f"{type(error).__name__}: {error}"}
        finally:
            JUDGMENT_CONTEXT.reset(token)
        values[metric.name]["seconds"] = round(time.monotonic() - began, 3)
    await asyncio.gather(*(evaluate_metric(metric, fields) for metric, fields in definitions))
    return {"id": case["id"], "status": "scored" if all(v["status"] == "scored" for v in values.values()) else "incomplete",
            "answer_sha256": digest(answer.encode()), "contexts": len(contexts), "metrics": values,
            "seconds": round(time.monotonic() - started, 3)}


async def score(args):
    cases = {c["id"]: c for c in dataset(args.dataset)}
    captures = json.loads(args.capture.read_text(encoding="utf-8"))
    if captures["dataset_sha256"] != digest(args.dataset.read_bytes()):
        raise ValueError("Scoring dataset differs from captured questions")
    errata = None
    if args.reference_errata:
        errata = json.loads(args.reference_errata.read_text(encoding="utf-8"))
        seen = set()
        for correction in errata["corrections"]:
            identity = correction["id"]
            if identity in seen or identity not in cases:
                raise ValueError("Reference errata contains duplicate or unknown case")
            seen.add(identity)
            case = cases[identity]
            if digest(case["reference"].encode()) != correction["original_reference_sha256"]:
                raise ValueError("Reference erratum does not match the preserved original")
            if not set(correction["source_context_ids"]) <= {c["context_id"] for c in case["reference_contexts"]}:
                raise ValueError("Reference erratum cites unknown source context")
            case["reference"] = correction["corrected_reference"]
    judge, embeddings = CodexJudge(args.cache), LocalJudgeEmbedding()
    report = {**metadata(), "kind": "Unmodified ragas.metrics.collections algorithms and prompts with custom local transports",
              "capture_sha256": digest(args.capture.read_bytes()), "dataset_sha256": captures["dataset_sha256"],
              "context_policy": "All unique model-visible chunks in first-seen adaptive retrieval order; inspected context replaces its chunk text; no reference injection",
              "context_format": "metadata-v2: actual observed source metadata plus widest observed text; no reference metadata",
              "reference_errata": errata,
              "reference_errata_sha256": digest(args.reference_errata.read_bytes()) if args.reference_errata else None,
              "cases": []}
    if args.resume and args.output.exists():
        old = json.loads(args.output.read_text(encoding="utf-8"))
        if (old["capture_sha256"] != report["capture_sha256"] or old["runtime_hashes"] != report["runtime_hashes"]
                or old.get("reference_errata_sha256") != report["reference_errata_sha256"]
                or old.get("context_format") != report["context_format"]):
            raise ValueError("Score resume requires identical capture and runtime")
        report = old
    done = {r["id"] for r in report["cases"]}
    previous_calls = [c for c in report.get("judge_calls", []) if c.get("context", "").rsplit(":", 1)[0] in done]
    semaphore = asyncio.Semaphore(args.concurrency)

    async def one(row):
        if row["id"] in done:
            return
        async with semaphore:
            result = await score_row(row, cases[row["id"]], judge, embeddings)
            report["cases"].append(result)
            completed_ids = {r["id"] for r in report["cases"]}
            report["judge_calls"] = previous_calls + [c for c in judge.calls if c.get("context", "").rsplit(":", 1)[0] in completed_ids]
            write_json(args.output, report)
            print(json.dumps({"id": row["id"], "status": result["status"],
                              "metrics": {k: v["value"] for k, v in result["metrics"].items()}}), flush=True)
    await asyncio.gather(*(one(row) for row in captures["cases"]))


async def calibrate(args):
    context = "Northstar's FY2025 revenue was $120 million. Its largest customer accounted for 25% of revenue."
    irrelevant = "Paris is the capital of France."
    question = "What were Northstar's FY2025 revenue and largest-customer revenue share?"
    reference = "Northstar reported $120 million of revenue and a 25% largest-customer revenue share in FY2025."
    judge, embeddings = CodexJudge(args.cache), LocalJudgeEmbedding()
    cases = []
    for name, answer, contexts in [("supported", reference, [context, irrelevant]),
                                    ("contradicted", "Northstar's FY2025 revenue was $900 million and its largest customer represented 75% of revenue.", [context]),
                                    ("irrelevant", irrelevant, [context]),
                                    ("missing_context", reference, [irrelevant])]:
        row = {"result": {"answer": answer}, "contexts": [{"model_visible_text": c} for c in contexts]}
        cases.append(await score_row(row, {"id": name, "question": question, "reference": reference}, judge, embeddings))
        print(json.dumps({"calibration": name, "status": cases[-1]["status"]}), flush=True)
    write_json(args.output, {**metadata(), "kind": "Synthetic judge calibration, not corpus evaluation",
                             "question": question, "reference": reference, "contexts": [context, irrelevant],
                             "cases": cases, "judge_calls": judge.calls})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "score", "calibrate"))
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--reference-errata", type=Path, help="Explicit source-backed reference corrections; preserves captured dataset and questions")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=Path(os.getenv("SOURCE_CORPUS", "data/corpus")))
    parser.add_argument("--index", type=Path, default=Path(os.getenv("RESEARCH_INDEX_DIR", "chroma_index")))
    parser.add_argument("--cache", type=Path, default=Path("artifacts/ragas/judge"))
    parser.add_argument("--profile", choices=("codex", "api"), default="codex")
    parser.add_argument("--concurrency", type=int, choices=(1, 2), default=1)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.command in ("capture", "score") and args.dataset is None:
        parser.error("--dataset is required")
    if args.command == "score" and args.capture is None:
        parser.error("--capture is required for score")
    asyncio.run({"capture": capture, "score": score, "calibrate": calibrate}[args.command](args))
