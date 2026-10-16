"""Start the local acceptance container with host-owned generation authentication.

No market credentials enter the image. Stop the printed container and bridge after
acceptance. The market adapter can use an explicitly mounted ignored runtime file.
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
        "--market-mode", choices=["off", "live", "frozen"], default="off"
    )
    parser.add_argument("--reuse-bridge", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
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
        if options.reuse_bridge
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
            ["docker", "build", "-t", "hw2-sequence", "."], cwd=ROOT, check=True
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
        "127.0.0.1:8084:9090",
        "-e",
        "PORT=9090",
        "-e",
        "CODEX_BRIDGE_URL=tcp://host.docker.internal:8765",
        "-e",
        "CODEX_BRIDGE_TOKEN_FILE=/run/secrets/codex-bridge",
    ]
    if options.market_mode != "off":
        market_path = ROOT / "artifacts/market"
        market_path.mkdir(parents=True, exist_ok=True)
        args.extend(
            [
                "-e",
                "MARKET_MODE=" + options.market_mode,
                "--mount",
                f"type=bind,source={market_path},target=/app/artifacts/market",
            ]
        )
        if options.market_mode == "live":
            values = dotenv_values(ROOT / ".env")
            runtime = staging / "market-runtime.env"
            runtime.write_text(
                "\n".join(
                    k + "=" + (values.get(k) or "")
                    for k in (
                        "TWELVE_DATA_API_KEY",
                        "TWELVE_DATA_GMAIL_API_KEY",
                        "ALPHA_VANTAGE_API_KEY",
                        "TAVILY_API_KEY",
                    )
                ),
                encoding="utf-8",
            )
            args.extend(["--env-file", str(runtime)])
    for source, target, readonly in [
        (ROOT / "data/corpus", "/app/data/corpus", True),
        (ROOT / "data/financials", "/app/data/financials", True),
        (index, "/app/chroma_index", False),
        (
            Path.home() / ".cache/chroma/onnx_models/all-MiniLM-L6-v2",
            "/home/appuser/.cache/chroma/onnx_models/all-MiniLM-L6-v2",
            True,
        ),
        (token, "/run/secrets/codex-bridge", True),
    ]:
        args.extend(
            [
                "--mount",
                f"type=bind,source={source},target={target}"
                + (",readonly" if readonly else ""),
            ]
        )
    args.append("hw2-sequence")
    container = subprocess.check_output(args, text=True).strip()
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
                "url": "http://127.0.0.1:8084",
                "market_mode": options.market_mode,
            }
        )
    )


if __name__ == "__main__":
    main()
