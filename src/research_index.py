"""Versioned semantic index over verified, immutable M2 passages."""

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from tokenizers import Tokenizer

from src.source_collection import DEFAULT_OUTPUT, ROOT, digest, write_json

INDEX = ROOT / "chroma_index"
CONFIG = {
    "schema": 1,
    "model": "all-MiniLM-L6-v2",
    "dimensions": 384,
    "artifact_sha256": ONNXMiniLM_L6_V2._MODEL_SHA256,
    "tokens": 220,
    "overlap": 40,
    "distance": "cosine",
}


class LocalEmbedding(ONNXMiniLM_L6_V2):
    """Bound CPU inference threads so embedding does not saturate the host."""

    @cached_property
    def model(self):
        options = self.ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        return self.ort.InferenceSession(
            str(self.DOWNLOAD_PATH / self.EXTRACTED_FOLDER_NAME / "model.onnx"),
            providers=["CPUExecutionProvider"],
            sess_options=options,
        )


def chunks(text, document, tokenizer):
    """Keep exact character offsets; never cross a page or selected section boundary."""
    sections = {
        name: section
        for name, section in document["extraction"].get("sections", {}).items()
        if "start" in section and "end" in section
    }
    pages = document["extraction"].get("pages", [])
    boundaries = {0, len(text)}
    boundaries.update(p[k] for p in pages for k in ("start", "end"))
    boundaries.update(s[k] for s in sections.values() if s for k in ("start", "end"))
    ordered = sorted(boundaries)
    for left, right in zip(ordered, ordered[1:]):
        offsets = tokenizer.encode(text[left:right], add_special_tokens=False).offsets
        for i in range(0, len(offsets), CONFIG["tokens"] - CONFIG["overlap"]):
            batch = offsets[i : i + CONFIG["tokens"]]
            start, end = left + batch[0][0], left + batch[-1][1]
            passage = text[start:end]
            if not passage.strip():
                continue
            section = next(
                (
                    name
                    for name, s in sections.items()
                    if s and s["start"] <= start < s["end"]
                ),
                "other",
            )
            page = next((p["page"] for p in pages if p["start"] <= start < p["end"]), 0)
            metadata = {
                key: document[key]
                for key in (
                    "document_id",
                    "company",
                    "fiscal_year",
                    "kind",
                    "period_end",
                    "version",
                    "canonical_url",
                )
            }
            metadata["form"] = document.get("form") or "Earnings release"
            metadata.update(
                start=start,
                end=end,
                page=page,
                section=section,
                text_sha256=document["extraction"]["text_sha256"],
            )
            chunk_id = digest(
                f"{metadata['document_id']}:{metadata['text_sha256']}:{start}:{end}".encode()
            )
            yield chunk_id, passage, metadata
            if i + CONFIG["tokens"] >= len(offsets):
                break


class ResearchIndex:
    def __init__(self, corpus: Path = DEFAULT_OUTPUT, index: Path = INDEX):
        self.corpus, self.path = corpus, index
        manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
        self.documents = {
            d["document_id"]: d
            for d in manifest["documents"]
            if d["status"] == "verified"
        }
        signature = {
            "config": CONFIG,
            "documents": [
                {
                    key: value
                    for key, value in d.items()
                    if key not in {"attempts", "checked_at", "sec_metadata"}
                }
                for d in self.documents.values()
            ],
        }
        self.fingerprint = digest(json.dumps(signature, sort_keys=True).encode())
        self.client = chromadb.PersistentClient(
            path=str(index), settings=Settings(anonymized_telemetry=False)
        )
        self.embedding = LocalEmbedding(preferred_providers=["CPUExecutionProvider"])

    def text(self, doc):
        path = (self.corpus / doc["extraction"]["text_path"]).resolve()
        if not path.is_relative_to(self.corpus.resolve()):
            raise ValueError("Prepared source path escapes corpus")
        body = path.read_bytes()
        if digest(body) != doc["extraction"]["text_sha256"]:
            raise ValueError(f"Prepared text checksum mismatch: {doc['document_id']}")
        return body.decode("utf-8")

    def collection(self):
        active = json.loads((self.path / "active.json").read_text(encoding="utf-8"))
        if active["fingerprint"] != self.fingerprint:
            raise ValueError(
                "Corpus/settings changed; run research.py ingest before querying."
            )
        return self.client.get_collection(active["collection"], embedding_function=None)

    def ingest(self):
        self.embedding(["Initialize local embedding model"])
        tokenizer = Tokenizer.from_str(self.embedding.tokenizer.to_str())
        tokenizer.no_truncation()
        tokenizer.no_padding()
        name = "filings-" + self.fingerprint[:24]
        collection = self.client.get_or_create_collection(
            name, embedding_function=None, configuration={"hnsw": {"space": "cosine"}}
        )
        total = 0
        for doc in self.documents.values():
            rows = list(chunks(self.text(doc), doc, tokenizer))
            for offset in range(0, len(rows), 128):
                batch = rows[offset : offset + 128]
                present = set(
                    collection.get(ids=[r[0] for r in batch], include=[])["ids"]
                )
                batch = [row for row in batch if row[0] not in present]
                if not batch:
                    continue
                ids, passages, metadata = map(list, zip(*batch))
                collection.upsert(
                    ids=ids,
                    documents=passages,
                    metadatas=metadata,
                    embeddings=self.embedding(passages),
                )
            total += len(rows)
            print(
                f"{doc['document_id']}: {len(rows)} chunks ({total} total)", flush=True
            )
        result = {
            "fingerprint": self.fingerprint,
            "collection": name,
            "documents": len(self.documents),
            "chunks": total,
            "config": CONFIG,
        }
        if collection.count() != total:
            raise ValueError("Index count differs from prepared chunk count")
        write_json(self.path / "active.json", result)
        return result

    def coverage(self):
        return {
            company: sorted(
                {
                    d["fiscal_year"]
                    for d in self.documents.values()
                    if d["company"] == company
                }
            )
            for company in sorted({d["company"] for d in self.documents.values()})
        }

    def search(
        self,
        query: str,
        companies: list[str],
        years: list[int],
        *,
        section=None,
        version=None,
        form=None,
        document_ids=None,
        k=6,
    ):
        if not companies or not years or not 1 <= k <= 12:
            raise ValueError("Specify companies, fiscal years, and k between 1 and 12")
        if document_ids is not None and not document_ids:
            return []
        filters = [{"company": {"$in": companies}}, {"fiscal_year": {"$in": years}}]
        if document_ids is not None:
            filters.append({"document_id": {"$in": document_ids}})
        for name, value in (("section", section), ("version", version), ("form", form)):
            if value:
                filters.append({name: value})
        found = self.collection().query(
            query_embeddings=self.embedding([query]),
            n_results=k,
            where={"$and": filters},
            include=["documents", "metadatas", "distances"],
        )
        return [
            {"chunk_id": cid, "text": text, **metadata, "distance": distance}
            for cid, text, metadata, distance in zip(
                found["ids"][0],
                found["documents"][0],
                found["metadatas"][0],
                found["distances"][0],
            )
        ]

    def inspect(self, chunk_id):
        result = self.collection().get(
            ids=[chunk_id], include=["metadatas", "documents"]
        )
        if not result["ids"]:
            raise KeyError("Passage unavailable in the active index")
        metadata = result["metadatas"][0]
        text = self.text(self.documents[metadata["document_id"]])
        if text[metadata["start"] : metadata["end"]] != result["documents"][0]:
            raise ValueError("Indexed passage differs from original prepared text")
        left, right = (
            max(0, metadata["start"] - 500),
            min(len(text), metadata["end"] + 500),
        )
        document = self.documents[metadata["document_id"]]
        return {
            "chunk_id": chunk_id,
            **metadata,
            "text": result["documents"][0],
            "context": text[left:right],
            "context_start": left,
            "retrieval_url": document["body"]["retrieval_url"],
            "original_url": f"/api/originals/{metadata['document_id']}",
            **{
                key: document.get(key)
                for key in (
                    "fiscal_start",
                    "fiscal_end",
                    "amends_document_id",
                    "risk_context_note",
                )
            },
        }
