"""Authenticated host bridge for local Docker. Never use as a deployed service."""

import argparse
import asyncio
import hmac
import secrets
import sys
from contextlib import suppress
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.codex_transport import CLOSE, LIMIT, local_process


class Bridge:
    def __init__(self, token, process_factory=local_process):
        self.token = token
        self.process_factory = process_factory
        self.children = set()
        self.slots = asyncio.Semaphore(2)

    async def handle(self, reader, writer):
        tasks = []
        process = None
        try:
            supplied = await asyncio.wait_for(reader.readline(), timeout=5)
            if not hmac.compare_digest(supplied.strip(), self.token.encode()):
                writer.write(b"REJECTED\n")
                await writer.drain()
                return
            writer.write(b"OK\n")
            await writer.drain()
            async with asyncio.timeout(200), self.slots, self.process_factory() as process:
                self.children.add(process.pid)
                print(f"Codex child started: {process.pid}", flush=True)

                async def copy(source, target):
                    while block := await source.read(65536):
                        target.write(block)
                        await target.drain()

                async def forward_requests():
                    while line := await reader.readline():
                        if line.strip() == CLOSE.strip():
                            return
                        process.stdin.write(line)
                        await process.stdin.drain()

                tasks = [asyncio.create_task(forward_requests()),
                         asyncio.create_task(copy(process.stdout, writer))]
                try:
                    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        except (TimeoutError, OSError, ValueError):
            pass
        finally:
            if process is not None:
                self.children.discard(process.pid)
            writer.close()
            with suppress(OSError):
                await writer.wait_closed()
            if tasks:
                print(f"Codex child closed: {process.pid}; active children: {len(self.children)}", flush=True)


async def main(args):
    args.token_file.parent.mkdir(parents=True, exist_ok=True)
    if not args.token_file.exists():
        args.token_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    token = args.token_file.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise SystemExit("Bridge token must contain at least 32 characters")
    bridge = Bridge(token)
    server = await asyncio.start_server(bridge.handle, args.host, args.port, limit=LIMIT)
    print(f"Local Codex bridge listening on {args.host}:{args.port}; token file: {args.token_file}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token-file", type=Path, default=Path("artifacts/codex-bridge.token"))
    asyncio.run(main(parser.parse_args()))
