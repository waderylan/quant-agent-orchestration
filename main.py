"""Local M3 application. Run: uv run --locked uvicorn main:app --port 8080."""

import asyncio
import json
import os
from contextlib import aclosing, asynccontextmanager, suppress

import anyio
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.research_index import INDEX, ResearchIndex
from src.research_workflow import events
from src.source_collection import DEFAULT_OUTPUT, ROOT
from src.source_collection import digest

load_dotenv()


@asynccontextmanager
async def lifespan(app):
    app.state.index = ResearchIndex(
        (ROOT / os.getenv("SOURCE_CORPUS", str(DEFAULT_OUTPUT))).resolve(),
        (ROOT / os.getenv("RESEARCH_INDEX_DIR", str(INDEX))).resolve(),
    )
    app.state.turns = asyncio.Semaphore(2)
    yield


app = FastAPI(title="Public-Company Research Assistant", lifespan=lifespan)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    companies: list[str] = Field(min_length=1, max_length=4)
    years: list[int] = Field(min_length=1, max_length=2)


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


@app.post("/api/chat")
async def chat(question: Question, request: Request):
    async def response():
        queue = asyncio.Queue(maxsize=128)

        async def produce():
            async with app.state.turns:
                async with aclosing(
                    events(
                        app.state.index,
                        question.question.strip(),
                        list(dict.fromkeys(question.companies)),
                        list(dict.fromkeys(question.years)),
                    )
                ) as stream:
                    async for event in stream:
                        await queue.put(event)
            await queue.put(None)

        task = asyncio.create_task(produce())
        try:
            while not await request.is_disconnected():
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
            # ASGI cancellation must not interrupt cancellation of graph-owned tasks.
            with anyio.CancelScope(shield=True):
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
