# Alternative: Pinecone Vector Store

- Role: instructor reference guidance. Example models, files, and interfaces are not verified HW2 implementation. Current project decisions are in the [project spec](planning/PROJECT_SPEC.md).

Pinecone is the **named/default vector-store option in the syllabus**. The reference implementation uses embedded Chroma only as a convenient canonical implementation. Students using Pinecone are graded identically.

## Swap surface

Pinecone requires ingestion and retrieval integration through its current SDK and LangChain. Example module locations:

- `src/rag/ingest.py`
- `src/rag/retriever.py`

Use the current Pinecone SDK and LangChain `PineconeVectorStore` integration in those components.

Add current Pinecone dependencies to `requirements.txt` and variables to `.env.example`, for example:

```text
PINECONE_API_KEY=...
PINECONE_INDEX=assignment2-rag
```

Verify the current Pinecone SDK/API and account terms before implementation; do not rely on old free-tier assumptions.

## Deployment consequence

With Pinecone, the vector index is external, so the Cloud Run image does not need to bake and carry the Chroma index. The application's durable conversation/checkpoint state remains a separate concern (Firestore, GCS/GCSFuse, Cloud SQL, etc.).
