"""Build and verify local Docker with host-owned subscription authentication."""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.demo_research import application_turn
from src.source_collection import ROOT, now, write_json
from src.codex_transport import terminate_owned


def docker(*arguments):
    return subprocess.check_output(["docker", *arguments], text=True).strip()


async def main(args):
    staging = ROOT / "artifacts/local-container"
    staging.mkdir(parents=True, exist_ok=True)
    index = staging / "index"
    if not index.exists():
        shutil.copytree(ROOT / "chroma_index", index)
    cache = Path.home() / ".cache/chroma/onnx_models/all-MiniLM-L6-v2"
    token = staging / "bridge.token"
    log = (staging / "bridge.log").open("w", encoding="utf-8")
    bridge = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts/codex_bridge.py"), "--host", "0.0.0.0",
         "--token-file", str(token)], stdout=log, stderr=log,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        start_new_session=os.name != "nt",
    )
    container = None
    report = {"checked_at": now(), "kind": "local Docker acceptance; not Cloud Run"}
    try:
        for _ in range(100):
            if token.exists():
                break
            await asyncio.sleep(0.1)
        if bridge.poll() is not None:
            raise RuntimeError("Host bridge did not start; inspect artifacts/local-container/bridge.log")
        if not args.skip_build:
            with (staging / "build.log").open("w") as output:
                subprocess.run(["docker", "build", "-t", args.image, "."], cwd=ROOT,
                               check=True, stdout=output, stderr=subprocess.STDOUT)
        started = time.perf_counter()
        container = docker(
            "run", "-d", "--memory", "2g", "--cpus", "2", "-p", "127.0.0.1:8084:9090",
            "-e", "PORT=9090", "-e", "CODEX_BRIDGE_URL=tcp://host.docker.internal:8765",
            "-e", "CODEX_BRIDGE_TOKEN_FILE=/run/secrets/codex-bridge",
            "--mount", f"type=bind,source={ROOT / 'data/corpus'},target=/app/data/corpus,readonly",
            "--mount", f"type=bind,source={index},target=/app/chroma_index",
            "--mount", f"type=bind,source={cache},target=/home/appuser/.cache/chroma/onnx_models/all-MiniLM-L6-v2,readonly",
            "--mount", f"type=bind,source={token},target=/run/secrets/codex-bridge,readonly",
            args.image,
        )
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8084", timeout=240) as client:
            for _ in range(120):
                try:
                    response = await client.get("/api/coverage")
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.5)
            else:
                raise RuntimeError("Container startup failed: " + docker("logs", container))
            report["fresh_start_seconds"] = round(time.perf_counter() - started, 3)
            report["coverage"] = response.json()
            report["ui_status"] = (await client.get("/")).status_code
            report["identity"] = docker("exec", container, "id")
            report["credential_isolation"] = json.loads(docker(
                "exec", container, "python", "-c",
                "import pathlib,shutil,json; print(json.dumps({'codex_installed':bool(shutil.which('codex')),'codex_home_exists':pathlib.Path('/home/appuser/.codex').exists(),'root_auth_exists':pathlib.Path('/app/.env').exists()}))",
            ))
            report["application"] = await application_turn(
                client, "NVDA", 2026, "What drove NVIDIA's full-year revenue growth in FY2026?",
            )
            report["resources"] = docker("stats", "--no-stream", "--format", "{{json .}}", container)
            # Disconnect after an actual model starts, then inspect owned host PIDs.
            async with client.stream("POST", "/api/chat", json={
                "question": "Explain NVIDIA FY2026 revenue drivers in detail",
                "companies": ["NVDA"], "years": [2026],
            }) as response:
                async for line in response.aiter_lines():
                    if '"provider": "Codex subscription"' in line:
                        break
            disconnected = time.perf_counter()
            report["disconnect_cleanup"] = False
            for _ in range(100):
                bridge_log = (staging / "bridge.log").read_text(encoding="utf-8")
                if bridge_log.strip().endswith("active children: 0"):
                    report["disconnect_cleanup"] = True
                    break
                await asyncio.sleep(0.1)
            report["disconnect_cleanup_seconds"] = round(time.perf_counter() - disconnected, 3)
            if not report["disconnect_cleanup"]:
                print(docker("logs", container), flush=True)
            # Exercise unavailable models inside the actual image/transport.
            failed = docker("exec", container, "python", "-c",
                "import asyncio; from src.codex_model import stream\nasync def test():\n try:\n  async for e in stream('Answer briefly',[],lambda *a:None,model='unavailable-hw2-model'): pass\n except RuntimeError as e: print(str(e))\n else: raise SystemExit('Unavailable model unexpectedly succeeded')\nasyncio.run(test())")
            report["unavailable_model"] = {"passed": "not supported" in failed, "error": failed}
            browser = subprocess.run([
                sys.executable, str(ROOT / "scripts/demo_browser.py"), "--url", "http://127.0.0.1:8084",
                "--output", str(ROOT / "docs/research/M4_BROWSER_RESULTS.json"),
            ], check=True, capture_output=True, text=True)
            report["browser"] = browser.stdout.strip()
        report["image_id"] = docker("image", "inspect", "--format", "{{.Id}}", args.image)
        report["image_bytes"] = int(docker("image", "inspect", "--format", "{{.Size}}", args.image))
        isolation = report["credential_isolation"]
        report["passed"] = (report["application"]["passed"] and report["disconnect_cleanup"]
                            and report["unavailable_model"]["passed"]
                            and report["identity"].startswith("uid=10001")
                            and not any(isolation.values()))
        # Keep evidence compact; the cited answer and inspections remain reviewable.
        report["application"].pop("events")
        write_json(args.output, report)
        print(json.dumps(report, indent=2))
        if not report["passed"]:
            raise SystemExit(1)
    finally:
        if container:
            docker("rm", "-f", container)
        terminate_owned(bridge)
        bridge.wait(timeout=10)
        log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="hw2-research:m4")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/research/M4_CONTAINER_RESULTS.json")
    asyncio.run(main(parser.parse_args()))
