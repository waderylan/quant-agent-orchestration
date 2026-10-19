"""Local-only Codex process ownership and authenticated development transport."""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import subprocess
import tempfile
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlparse

LIMIT = 4 * 1024 * 1024
CLOSE = b'{"bridge_control":"close"}\n'
_request_closers: ContextVar[list | None] = ContextVar("codex_request_closers", default=None)


@contextmanager
def request_connections(closers=None):
    """Own transports at the HTTP boundary as well as inside graph child tasks."""
    if closers is None:
        closers = []
    token = _request_closers.set(closers)
    try:
        yield closers
    finally:
        for close in list(closers):
            close()
        _request_closers.reset(token)


@contextmanager
def register_close(close):
    closers = _request_closers.get()
    if closers is not None:
        closers.append(close)
    try:
        yield
    finally:
        if closers is not None:
            closers.remove(close)


def executable() -> str:
    command = shutil.which("codex")
    if command and Path(command).suffix.lower() in {".cmd", ".ps1"}:
        binaries = list(
            (Path(command).parent / "node_modules/@openai/codex").glob(
                "node_modules/@openai/codex-*/vendor/*/bin/codex.exe"
            )
        )
        if binaries:
            return str(binaries[0])
    if not command:
        raise RuntimeError("Install Codex CLI and run codex login before asking questions.")
    return command


def terminate_owned(process):
    """Kill the owned CLI tree; inherited MCP pipes must not keep wait() alive."""
    if process.returncode is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=5,
        )
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


@asynccontextmanager
async def local_process():
    disabled = [
        "shell_tool", "apply_patch_freeform", "multi_agent", "code_mode",
        "apps", "browser_use", "computer_use", "unified_exec",
    ]
    arguments = [executable(), "app-server", "-c", "project_doc_max_bytes=0",
                 "-c", 'web_search="disabled"', "-c", "mcp_servers={}"]
    for feature in disabled:
        arguments += ["-c", f"features.{feature}=false"]
    process = await asyncio.create_subprocess_exec(
        *arguments, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, limit=LIMIT, cwd=tempfile.gettempdir(),
        env=generation_environment(),
        start_new_session=os.name != "nt",
    )
    try:
        with register_close(lambda: terminate_owned(process)):
            yield process
    finally:
        terminate_owned(process)
        await process.wait()


def generation_environment():
    """Generation uses host CLI login, without live-source or provider credentials."""
    return {key: value for key, value in os.environ.items() if not key.upper().startswith("TAVILY") and not key.upper().endswith("_API_KEY")}


@asynccontextmanager
async def connection():
    """Yield reader/writer; credentials always remain with the host CLI."""
    endpoint = os.getenv("CODEX_BRIDGE_URL")
    if not endpoint:
        async with local_process() as process:
            yield process.stdout, process.stdin
        return
    url = urlparse(endpoint)
    if url.scheme != "tcp" or not url.hostname or not url.port or url.path:
        raise ValueError("CODEX_BRIDGE_URL must be tcp://HOST:PORT (local development only)")
    token = Path(os.environ["CODEX_BRIDGE_TOKEN_FILE"]).read_text().strip()
    if len(token) < 32:
        raise ValueError("Bridge token must contain at least 32 characters")
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(url.hostname, url.port, limit=LIMIT), timeout=5,
    )

    def close():
        if not writer.is_closing():
            # An explicit frame also works through Docker Desktop's TCP proxy,
            # whose half-close notification can arrive after the browser disconnect.
            writer.write(CLOSE)
            writer.close()

    try:
        writer.write(token.encode() + b"\n")
        await writer.drain()
        if await asyncio.wait_for(reader.readline(), timeout=5) != b"OK\n":
            raise RuntimeError("Local Codex bridge authentication rejected")
        with register_close(close):
            yield reader, writer
    finally:
        close()
        await writer.wait_closed()
