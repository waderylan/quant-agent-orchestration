"""Local public-company research and financial analysis API with streamed answers."""

import asyncio
import json
import os
from contextlib import aclosing, asynccontextmanager, suppress

import anyio
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dataclasses import dataclass
from collections.abc import Callable, AsyncIterator

from src.research_index import INDEX, ResearchIndex
from src.research_workflow import events
from src.codex_transport import request_connections
from src.financial_data import FinancialStore, FINANCIALS
from src.analysis_artifacts import ArtifactStore
from src.source_collection import DEFAULT_OUTPUT, ROOT
from src.source_collection import digest
from src.live_mcp import LiveGateway

load_dotenv()


@asynccontextmanager
async def lifespan(app):
    app.state.index = ResearchIndex(
        (ROOT / os.getenv("SOURCE_CORPUS", str(DEFAULT_OUTPUT))).resolve(),
        (ROOT / os.getenv("RESEARCH_INDEX_DIR", str(INDEX))).resolve(),
    )
    app.state.turns = asyncio.Semaphore(2)
    app.state.financials = FinancialStore(
        (ROOT / os.getenv("FINANCIAL_DATA_DIR", str(FINANCIALS))).resolve()
    )
    app.state.artifacts = ArtifactStore()
    app.state.gateway = LiveGateway()
    yield


app = FastAPI(title="Public-Company Research Assistant", lifespan=lifespan)
app.mount("/static/vendor", StaticFiles(directory=ROOT / "web/vendor"), name="vendor")


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    companies: list[str] = Field(min_length=1, max_length=4)
    years: list[int] = Field(min_length=1, max_length=2)


@dataclass(frozen=True)
class TurnServices:
    """Request-local service injection for controlled application acceptance."""

    gateway: LiveGateway | None = None
    worker_overrides: dict | None = None
    index: ResearchIndex | None = None
    financials: FinancialStore | None = None
    model_stream: Callable[..., AsyncIterator[dict]] | None = None


def turn_services(request: Request):
    return TurnServices(gateway=getattr(request.app.state, "gateway", None))


class ClosingStreamingResponse(StreamingResponse):
    """ASGI 2.4 send errors must also close a generator suspended at yield."""

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                await self.body_iterator.aclose()


@app.get("/")
def home():
    return FileResponse(ROOT / "web/index.html")


@app.get("/api/coverage")
def coverage():
    return app.state.index.coverage()


@app.get("/api/sources/{chunk_id}")
def source(chunk_id: str):
    try:
        return app.state.index.inspect(chunk_id)
    except (KeyError, ValueError, FileNotFoundError) as error:
        raise HTTPException(404, str(error)) from error


@app.get("/api/originals/{document_id}")
def original(document_id: str):
    document = app.state.index.documents.get(document_id)
    if not document:
        raise HTTPException(404, "Document is outside collected coverage")
    path = (app.state.index.corpus / document["body"]["path"]).resolve()
    if not path.is_relative_to(app.state.index.corpus.resolve()) or not path.is_file():
        raise HTTPException(404, "Original body unavailable")
    if digest(path.read_bytes()) != document["body"]["sha256"]:
        raise HTTPException(409, "Original body checksum mismatch")
    return FileResponse(
        path,
        filename=document_id + path.suffix,
        media_type="application/pdf"
        if path.suffix == ".pdf"
        else "application/octet-stream",
    )


@app.get("/api/risks/{document_id}")
def risk_source(document_id: str, start: int, end: int):
    from src.risk_summary import inspect_span

    try:
        return inspect_span(app.state.index, document_id, start, end)
    except (KeyError, ValueError, FileNotFoundError) as error:
        raise HTTPException(404, str(error)) from error


@app.get("/api/live/{snapshot_id}")
def live_source(snapshot_id: str):
    try:
        return {"kind": "live_source", **app.state.gateway.inspect(snapshot_id)}
    except (KeyError, ValueError, FileNotFoundError):
        raise HTTPException(404, "Live snapshot unavailable") from None


@app.get("/api/financial/observations/{observation_id}")
def financial_observation(observation_id: str):
    try:
        row = app.state.financials.inspect(observation_id)
        document = app.state.index.documents.get(row["document_id"], {})
        return {
            **row,
            "original_url": f"/api/originals/{row['document_id']}",
            "retrieval_url": document.get("body", {}).get("retrieval_url"),
            "snapshot_url": f"/api/financial/snapshots/{row['snapshot_sha256']}",
        }
    except (KeyError, ValueError, FileNotFoundError) as error:
        raise HTTPException(404, str(error)) from error


@app.get("/api/financial/snapshots/{sha256}")
def financial_snapshot(sha256: str):
    try:
        return FileResponse(
            app.state.financials.snapshot(sha256),
            media_type="application/json",
            filename=f"sec-companyfacts-{sha256}.json",
        )
    except (KeyError, ValueError, FileNotFoundError) as error:
        raise HTTPException(404, str(error)) from error


@app.get("/api/analysis/{identity}/calculations/{source_id}")
def calculation(identity: str, source_id: str):
    try:
        return app.state.artifacts.calculation(identity, source_id)
    except (KeyError, ValueError, FileNotFoundError) as error:
        raise HTTPException(404, str(error)) from error


@app.get("/api/analysis/{identity}/files/{name}")
def analysis_file(identity: str, name: str):
    try:
        path = app.state.artifacts.file(identity, name)
    except (KeyError, ValueError, FileNotFoundError) as error:
        raise HTTPException(404, str(error)) from error
    media_type = {
        "chart.png": "image/png",
        "table.csv": "text/csv",
        "analysis.py": "text/plain",
        "bundle.json": "application/json",
    }[name]
    return FileResponse(
        path, media_type=media_type, filename=None if name == "chart.png" else name
    )


@app.get("/api/analysis/{identity}/observations/{source_id}")
def analysis_observation(identity: str, source_id: str):
    try:
        bundle = app.state.artifacts.load(identity)
        return app.state.artifacts.observation_source(
            identity, bundle["sources"][source_id]
        )
    except (KeyError, ValueError, FileNotFoundError) as error:
        raise HTTPException(404, str(error)) from error


@app.get("/api/analysis/{identity}/snapshots/{sha256}")
def analysis_snapshot(identity: str, sha256: str):
    try:
        bundle = app.state.artifacts.load(identity)
        allowed = {
            s["snapshot_sha256"]
            for s in bundle["sources"].values()
            if s.get("snapshot_sha256")
        }
        path = app.state.financials.snapshot(sha256, allowed=allowed)
        return FileResponse(
            path,
            media_type="application/json",
            filename=f"sec-companyfacts-{sha256}.json",
        )
    except (KeyError, ValueError, FileNotFoundError) as error:
        raise HTTPException(404, str(error)) from error


@app.post("/api/chat")
async def chat(
    question: Question,
    request: Request,
    services: TurnServices = Depends(turn_services),
):
    async def response():
        queue = asyncio.Queue(maxsize=128)
        closers = []

        async def produce():
            with request_connections(closers):
                await produce_owned()

        async def produce_owned():
            async with app.state.turns:
                async with aclosing(
                    events(
                        services.index or app.state.index,
                        question.question.strip(),
                        list(dict.fromkeys(question.companies)),
                        list(dict.fromkeys(question.years)),
                        gateway=services.gateway,
                        worker_overrides=services.worker_overrides,
                        **({"model_stream": services.model_stream} if services.model_stream is not None else {}),
                        **(
                            {"financials": services.financials or app.state.financials}
                            if services.financials is not None or app.state.financials.path.exists()
                            else {}
                        ),
                    )
                ) as stream:
                    async for event in stream:
                        await queue.put(event)
            await queue.put(None)

        task = asyncio.create_task(produce())
        try:
            # StreamingResponse owns ASGI disconnect reception. Competing reads here
            # can consume the notification before its cancellation listener sees it.
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.5)
                except TimeoutError:
                    if task.done():
                        await task
                        break
                    yield ": keep-alive\n\n"
                    continue
                if event is None:
                    break
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
        finally:
            # Close external work before awaiting graph unwinding/cancellation.
            for close in list(closers):
                close()
            # ASGI cancellation must not interrupt cancellation of graph-owned tasks.
            with anyio.CancelScope(shield=True):
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return ClosingStreamingResponse(
        response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
