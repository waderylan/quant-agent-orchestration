"""Start the local acceptance container with Codex or direct provider generation.

Stop the printed container and bridge after acceptance.
"""

import json
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.source_collection import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live-mode", choices=["off", "live", "frozen"], default="off"
    )
    parser.add_argument("--reuse-bridge", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--profile", choices=["codex", "api"], default="codex")
    parser.add_argument("--port", type=int, default=8084)
    parser.add_argument("--image", default="hw2-sequence")
    options = parser.parse_args()
    staging = ROOT / "artifacts/sequence-container"
    staging.mkdir(parents=True, exist_ok=True)
    active = json.loads((ROOT / "chroma_index/active.json").read_text(encoding="utf-8"))
    index = staging / ("index-" + active["fingerprint"][:16])
    if not index.exists():
        shutil.copytree(ROOT / "chroma_index", index)
    token = ROOT / "artifacts/codex-bridge.token"
    log = (staging / "bridge.log").open("w", encoding="utf-8")
    bridge = (
        None
        if options.reuse_bridge or options.profile == "api"
        else subprocess.Popen(
            [
                sys.executable,
                "scripts/codex_bridge.py",
                "--host",
                "0.0.0.0",
                "--token-file",
                str(token),
            ],
            cwd=ROOT,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    )
    if not options.skip_build:
        subprocess.run(
            ["docker", "build", "-t", options.image, "."], cwd=ROOT, check=True
        )
    args = [
        "docker",
        "run",
        "-d",
        "--memory",
        "2g",
        "--cpus",
        "2",
        "-p",
        f"127.0.0.1:{options.port}:9090",
        "-e",
        "PORT=9090",
    ]
    live_path = ROOT / "artifacts/live"
    live_path.mkdir(parents=True, exist_ok=True)
    runtime_env = dict(os.environ)
    args.extend(["-e", "GENERATION_PROFILE=" + options.profile])
    extra_mounts = []
    if options.profile == "api":
        config = dotenv_values(ROOT / ".env")
        for name in ("NEBIUS_API_KEY", "NVIDIA_API_KEY"):
            runtime_env[name] = os.getenv(name) or config.get(name) or ""
            args.extend(["-e", name])
        provider_dir = Path(os.getenv("PROVIDER_LEDGER", str(ROOT / "artifacts/providers/usage.sqlite3"))).resolve().parent
        provider_dir.mkdir(parents=True, exist_ok=True)
        args.extend(["-e", "PROVIDER_LEDGER=/app/artifacts/providers/usage.sqlite3"])
        extra_mounts.append((provider_dir, "/app/artifacts/providers", False))
    else:
        args.extend(["-e", "CODEX_BRIDGE_URL=tcp://host.docker.internal:8765", "-e", "CODEX_BRIDGE_TOKEN_FILE=/run/secrets/codex-bridge"])
        extra_mounts.append((token, "/run/secrets/codex-bridge", True))
    if options.live_mode != "off":
        args.extend(["-e", "LIVE_MODE=" + options.live_mode, "--mount", f"type=bind,source={live_path},target=/app/artifacts/live"])
        if options.live_mode == "live":
            runtime_env["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY") or dotenv_values(ROOT / ".env").get("TAVILY_API_KEY") or ""
            args.extend(["-e", "TAVILY_API_KEY"])
    else:
        args.extend(["-e", "LIVE_MODE=off"])
    for source, target, readonly in [
        (ROOT / "data/corpus", "/app/data/corpus", True),
        (ROOT / "data/financials", "/app/data/financials", True),
        (index, "/app/chroma_index", False),
        (
            Path.home() / ".cache/chroma/onnx_models/all-MiniLM-L6-v2",
            "/home/appuser/.cache/chroma/onnx_models/all-MiniLM-L6-v2",
            True,
        ),
    ] + extra_mounts:
        args.extend(
            [
                "--mount",
                f"type=bind,source={source},target={target}"
                + (",readonly" if readonly else ""),
            ]
        )
    args.append(options.image)
    container = subprocess.check_output(args, text=True, env=runtime_env).strip()
    (staging / "running.json").write_text(
        json.dumps(
            {"container": container, "bridge_pid": bridge.pid if bridge else None}
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "container": container,
                "bridge_pid": bridge.pid if bridge else None,
                "url": f"http://127.0.0.1:{options.port}",
                "generation_profile": options.profile,
                "live_mode": options.live_mode,
            }
        )
    )


if __name__ == "__main__":
    main()
