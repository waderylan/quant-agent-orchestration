"""Real sockets protect bridge authentication and child cleanup on disconnect."""

import asyncio
import sys
import os
from contextlib import asynccontextmanager

import pytest

from scripts.codex_bridge import Bridge
from src.codex_transport import connection, terminate_owned


@pytest.mark.asyncio
async def test_owned_cli_descendant_cannot_hold_stdout_open_after_disconnect():
    # Real CLI plugins can inherit stdio: killing only the parent leaks the tree.
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-u", "-c",
        "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print('ready',flush=True); time.sleep(60)",
        stdout=asyncio.subprocess.PIPE, start_new_session=os.name != "nt",
    )
    try:
        assert (await asyncio.wait_for(process.stdout.readline(), 5)).strip() == b"ready"
        terminate_owned(process)
        await asyncio.wait_for(process.wait(), 3)
        assert await process.stdout.read() == b""
    finally:
        terminate_owned(process)


@pytest.mark.asyncio
async def test_bridge_rejects_bad_token_and_kills_owned_child(tmp_path, monkeypatch):
    children = []

    @asynccontextmanager
    async def echo_process():
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "-c",
            "import sys; [print(line.strip(), flush=True) for line in sys.stdin]",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        )
        children.append(process)
        try:
            yield process
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()

    token_file = tmp_path / "token"
    token_file.write_text("a" * 48)
    bridge = Bridge("a" * 48, echo_process)
    server = await asyncio.start_server(bridge.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setenv("CODEX_BRIDGE_URL", f"tcp://127.0.0.1:{port}")
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN_FILE", str(token_file))
    async with server:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"incorrect\n")
        await writer.drain()
        assert await reader.readline() == b"REJECTED\n"
        writer.close()
        await writer.wait_closed()
        assert not children

        async with connection() as (reader, writer):
            writer.write(b'{"method":"initialize"}\n')
            await writer.drain()
            assert (await reader.readline()).strip() == b'{"method":"initialize"}'
            assert children[0].returncode is None
        await asyncio.wait_for(children[0].wait(), 2)
        async with asyncio.timeout(2):
            while bridge.children:
                await asyncio.sleep(0.01)
        assert not bridge.children
