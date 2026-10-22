"""Linux acceptance: actual scoped Chroma retrieval plus a FastAPI capability SSE.

The research model is a deterministic tool fixture; this is not a hosted/model score.
Run inside the built image with the corpus, isolated index and ONNX model mounted.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from main import app
from src.research_index import ResearchIndex
from src.research_workflow import research_turn


async def check():
    index = ResearchIndex()
    events = []

    async def fixture(prompt, tools, handler, **kwargs):
        found = handler("search_sources", {"query": "gross margin 40% 49% inventory related charges MI308",
                                            "company": "AMD", "year": 2025, "form": "10-Q", "quarter": 2,
                                            "section": "mda"})
        assert found["sources"] and all(s["period_end"] == "2025-06-28" for s in found["sources"])
        source = next(s for s in found["sources"] if "40%" in s["text"] and "49%" in s["text"])
        handler("report_outcome", {"status": "complete", "missing": []})
        yield {"type": "token", "data": f"AMD's Q2 FY2025 filing reports gross margin of 40% versus 49% in the prior-year quarter. [{source['source_id']}]"}

    result = await research_turn(index, {"question": "Explain AMD FY2025 Q2 10-Q gross margin using only filings.",
                                         "companies": ["AMD"], "years": [2025]}, events.append, model_stream=fixture)
    assert result["citation_verified"] and not result["partial"]
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://container.test") as client:
            home = await client.get("/")
            assert home.status_code == 200
            response = await client.post("/api/chat", json={"question": "What can this system do?", "companies": ["AMD"], "years": [2025]})
            assert response.status_code == 200 and "event: complete" in response.text and '"status": "completed"' in response.text
            assert "event: error" not in response.text
    print(json.dumps({"kind": "Linux actual Chroma + deterministic Research tool fixture + actual FastAPI capability SSE",
                      "filing_scoped_retrieval": "pass", "cited_research": "pass", "capability_sse": "pass", "root_http": home.status_code,
                      "generation_api_calls": 0, "tavily_calls": 0, "ragas_scores": False, "corpus_fingerprint": index.fingerprint}))


if __name__ == "__main__":
    asyncio.run(check())
