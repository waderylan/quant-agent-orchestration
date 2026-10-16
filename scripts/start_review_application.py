"""Freeze application code and start a guarded offline-market review service.

Source data, market cache/ledger and calculation bundles remain shared by explicit
paths. No .env, credentials, questions or prior answers enter the code snapshot.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.source_collection import ROOT, digest, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8086)
    parser.add_argument("--market-cache", type=Path, default=ROOT / "artifacts/market/cache")
    args = parser.parse_args()
    paths = [ROOT / "main.py", ROOT / "web/index.html", ROOT / "data/source_inventory.json", ROOT / "scripts/review_application.py", ROOT / "scripts/review_filing_conditions.py"]
    paths += sorted((ROOT / "src").glob("*.py")) + sorted((ROOT / "prompts").glob("*.md"))
    files = {str(p.relative_to(ROOT)).replace("\\", "/"): p.read_bytes() for p in paths}
    manifest = {"files": {name: digest(body) for name, body in files.items()}, "implementation_parent": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    identity = digest(json.dumps(manifest, sort_keys=True).encode())
    snapshot = ROOT / ".codex-tmp" / ("application-" + identity[:16])
    for name, body in files.items():
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == body, "Never mutate an existing review snapshot"
        else:
            target.write_bytes(body)
    write_json(snapshot / "SNAPSHOT_MANIFEST.json", {**manifest, "identity": identity})
    env = dict(os.environ)
    for key in ("ALPHA_VANTAGE_API_KEY", "TWELVE_DATA_API_KEY", "TWELVE_DATA_GMAIL_API_KEY", "TAVILY_API_KEY"):
        env.pop(key, None)
    env.update(PYTHON_DOTENV_DISABLED="1", MARKET_MODE="frozen", SOURCE_CORPUS=str(ROOT / "data/corpus"), RESEARCH_INDEX_DIR=str(ROOT / "chroma_index"), FINANCIAL_DATA_DIR=str(ROOT / "data/financials"), QUANT_ARTIFACT_DIR=str(ROOT / "artifacts/quant"), MARKET_CACHE=str(args.market_cache.resolve()), MARKET_LEDGER=str(ROOT / "artifacts/market/usage.sqlite3"))
    output = ROOT / "artifacts" / ("review-app-" + identity[:16])
    with output.with_suffix(".log").open("w", encoding="utf-8") as stdout, output.with_suffix(".err").open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "scripts.review_application:app", "--host", "127.0.0.1", "--port", str(args.port)], cwd=snapshot, env=env, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    record = {"snapshot": str(snapshot.relative_to(ROOT)), "identity": identity, "pid": process.pid, "url": f"http://127.0.0.1:{args.port}", "market_mode": "frozen", "market_credentials_copied": False}
    write_json(output.with_suffix(".json"), record)
    print(json.dumps(record))


if __name__ == "__main__":
    main()
