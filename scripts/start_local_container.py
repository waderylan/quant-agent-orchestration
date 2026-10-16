"""Start the local acceptance container with host-owned generation authentication.

No market credentials enter the image. Stop the printed container and bridge after
acceptance. The market adapter can use an explicitly mounted ignored runtime file.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.source_collection import ROOT


def main():
    staging = ROOT / "artifacts/sequence-container"
    staging.mkdir(parents=True, exist_ok=True)
    active = json.loads((ROOT / "chroma_index/active.json").read_text(encoding="utf-8"))
    index = staging / ("index-" + active["fingerprint"][:16])
    if not index.exists():
        shutil.copytree(ROOT / "chroma_index", index)
    token = ROOT / "artifacts/codex-bridge.token"
    log = (staging / "bridge.log").open("w", encoding="utf-8")
    bridge = subprocess.Popen([sys.executable, "scripts/codex_bridge.py", "--host", "0.0.0.0", "--token-file", str(token)], cwd=ROOT, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    subprocess.run(["docker", "build", "-t", "hw2-sequence", "."], cwd=ROOT, check=True)
    args = ["docker", "run", "-d", "--memory", "2g", "--cpus", "2", "-p", "127.0.0.1:8084:9090", "-e", "PORT=9090", "-e", "CODEX_BRIDGE_URL=tcp://host.docker.internal:8765", "-e", "CODEX_BRIDGE_TOKEN_FILE=/run/secrets/codex-bridge"]
    for source, target, readonly in [(ROOT / "data/corpus", "/app/data/corpus", True), (ROOT / "data/financials", "/app/data/financials", True), (index, "/app/chroma_index", False), (Path.home() / ".cache/chroma/onnx_models/all-MiniLM-L6-v2", "/home/appuser/.cache/chroma/onnx_models/all-MiniLM-L6-v2", True), (token, "/run/secrets/codex-bridge", True)]:
        args.extend(["--mount", f"type=bind,source={source},target={target}" + (",readonly" if readonly else "")])
    args.append("hw2-sequence")
    container = subprocess.check_output(args, text=True).strip()
    (staging / "running.json").write_text(json.dumps({"container": container, "bridge_pid": bridge.pid}), encoding="utf-8")
    print(json.dumps({"container": container, "bridge_pid": bridge.pid, "url": "http://127.0.0.1:8084"}))


if __name__ == "__main__":
    main()
