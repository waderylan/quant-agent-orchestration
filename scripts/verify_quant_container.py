"""Check the Linux interpreter with explicit fixtures, without providers or app mounts."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.source_collection import ROOT, now, write_json


def main(args):
    program = "results=[{'label':'fixture growth','kind':'growth','inputs':['F2','F1'],'value':(values['F2']/values['F1']-1)*100}]"
    cases = [
        ("valid arithmetic", program, {"F1": 100, "F2": 150}, None),
        ("imports", "import os", {}, "Only simple variable assignments"),
        ("loops", "while True: pass", {}, "Only simple variable assignments"),
        ("zero denominator", program, {"F1": 0, "F2": 150}, "Zero denominator"),
        ("missing identifier", program, {"F2": 150}, "Missing financial input"),
        ("numeric magnitude", "x=1e100", {}, "Numeric literal exceeds"),
    ]
    checks = []
    for name, code, values, expected_error in cases:
        result = subprocess.run([
            "docker", "run", "--rm", "-i", "--cpus", "1", "--memory", "256m",
            "--entrypoint", "python", args.image, "-I", "-S", "-B", "/app/src/quant_runner.py",
        ], input=json.dumps({"code": code, "values": values}), text=True,
            capture_output=True, timeout=20)
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            output = {"error": "Invalid child result", "stderr": result.stderr[:500]}
        passed = (result.returncode == 1 and expected_error in output.get("error", "")) if expected_error else (
            result.returncode == 0 and output.get("results", [{}])[0].get("value") == "50.0"
            and output["results"][0]["used_inputs"] == ["F1", "F2"])
        checks.append({"case": name, "exit_code": result.returncode, "output": output, "passed": passed})
    report = {"checked_at": now(), "image": args.image,
              "evidence_kind": "Linux interpreter-only synthetic fixtures; no provider generation or company observations",
              "checks": checks, "passed": all(c["passed"] for c in checks)}
    write_json(args.output, report)
    print(f"Saved {args.output}; passed={report['passed']}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="hw2-research:m6")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/research/M6_LINUX_EXECUTION_RESULTS.json")
    main(parser.parse_args())
