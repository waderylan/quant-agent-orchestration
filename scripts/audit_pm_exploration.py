"""Recompute saved exploratory calculations and verify downloadable artifact hashes."""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def bundle_ids(value):
    if isinstance(value, dict):
        if isinstance(value.get("bundle_id"), str):
            yield value["bundle_id"]
        for item in value.values():
            yield from bundle_ids(item)
    elif isinstance(value, list):
        for item in value:
            yield from bundle_ids(item)


def recompute(bundle):
    values = {sid: Decimal(str(row["value"])) for sid, row in bundle["sources"].items()}
    checks = []
    for row in bundle["calculations"]:
        inputs = [values[sid] for sid in row["inputs"]]
        kind = row["calculation_kind"]
        if kind == "value":
            expected = inputs[0]
        elif kind in ("difference", "quarter"):
            expected = inputs[0] - inputs[1]
        elif kind == "growth":
            expected = (inputs[0] / inputs[1] - 1) * 100
        elif kind in ("margin", "share", "scenario_share"):
            expected = inputs[0] / inputs[1] * 100
        elif kind == "ratio":
            expected = inputs[0] / inputs[1]
        elif kind == "currency":
            assert row["scenario"]["origin"] == "user"
            expected = inputs[0] / Decimal(row["scenario"]["usd_per_eur"])
        elif kind == "scenario_scale":
            assert row["scenario"]["origin"] == "user"
            expected = inputs[0] * Decimal(row["scenario"]["factor"])
        elif kind == "scenario_total":
            assert row["scenario"]["origin"] == "user"
            expected = inputs[0] + (Decimal(row["scenario"]["factor"]) - 1) * inputs[1]
        else:
            raise ValueError(f"Unexpected operation {kind}")
        tolerance = (
            Decimal("1e-8")
            if row["unit"] in ("percent", "percentage_points", "multiple", "EUR")
            else Decimal(0)
        )
        actual = Decimal(row["value"])
        checks.append(
            {
                "source_id": row["source_id"],
                "kind": kind,
                "expected": str(expected),
                "actual": str(actual),
                "matches": abs(actual - expected) <= tolerance,
            }
        )
        values[row["source_id"]] = actual
    return checks


def main(args):
    records = [
        case
        for path in args.reports
        for case in json.loads(path.read_text(encoding="utf-8"))["cases"]
    ]
    result = {
        "method": "Independent Decimal arithmetic over frozen inputs, without executing generated code; exact download SHA-256 checks. Does not establish semantic completeness or claim-level faithfulness.",
        "cases": [],
    }
    with httpx.Client(base_url=args.url, timeout=30) as client:
        for case in records:
            raw = json.loads(
                (ROOT / case["raw_events_path"]).read_text(encoding="utf-8")
            )
            identities = set(case["bundles"]) | set(bundle_ids(raw))
            checked = []
            for identity in sorted(identities):
                response = client.get(f"/api/analysis/{identity}/files/bundle.json")
                response.raise_for_status()
                bundle = response.json()
                hashes = {}
                for name, expected in bundle["files"].items():
                    response = client.get(f"/api/analysis/{identity}/files/{name}")
                    response.raise_for_status()
                    hashes[name] = (
                        hashlib.sha256(response.content).hexdigest() == expected
                    )
                checked.append(
                    {
                        "bundle_id": identity,
                        "calculations": recompute(bundle),
                        "download_hashes_match": hashes,
                        "exposed_in_final_sources": identity in case["bundles"],
                    }
                )
            result["cases"].append(
                {
                    "id": case["id"],
                    "source_checks": len(case["source_checks"]),
                    "source_check_failures": [
                        check
                        for check in case["source_checks"]
                        if check.get("error")
                        or any(
                            check.get(key) is False
                            for key in (
                                "exact_text_match",
                                "exact_value_match",
                                "scope_match",
                            )
                        )
                    ],
                    "bundles": checked,
                }
            )
    result["summary"] = {
        "chats": len(records),
        "source_inspections": sum(row["source_checks"] for row in result["cases"]),
        "source_check_failures": sum(
            len(row["source_check_failures"]) for row in result["cases"]
        ),
        "bundles": sum(len(row["bundles"]) for row in result["cases"]),
        "calculations": sum(
            len(bundle["calculations"])
            for row in result["cases"]
            for bundle in row["bundles"]
        ),
        "calculation_failures": sum(
            not check["matches"]
            for row in result["cases"]
            for bundle in row["bundles"]
            for check in bundle["calculations"]
        ),
        "download_hash_failures": sum(
            not matches
            for row in result["cases"]
            for bundle in row["bundles"]
            for matches in bundle["download_hashes_match"].values()
        ),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    assert not any(
        result["summary"][key]
        for key in (
            "source_check_failures",
            "calculation_failures",
            "download_hash_failures",
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8086")
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
