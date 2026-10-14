"""Run with uv run python scripts/collect_sources.py --help."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from src.source_collection import (DEFAULT_INVENTORY, DEFAULT_OUTPUT, USER_AGENT,
                                   collect, inspection, verify_local)
from src.source_inventory import add_release, discover


def main():
    parser = argparse.ArgumentParser(description="Collect, refresh, verify and inspect original company sources")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("collect", help="Resume verified bodies; retry failed targets")
    command.add_argument("--refresh", action="store_true", help="Retrieve current bodies/metadata; preserve old raw bodies and run records")
    command.add_argument("--offline", action="store_true", help="Reprepare cached bodies and SEC metadata without network requests")
    command.add_argument("--user-agent", default=USER_AGENT)
    command = sub.add_parser("verify", help="Offline body/checksum/identity/section verification")
    command.add_argument("--write", type=Path, help="Save the actual verification result as JSON")
    sub.add_parser("status", help="Show every target and collection gaps")
    command = sub.add_parser("inspect", help="Print source paths and readable text")
    command.add_argument("document_id")
    command.add_argument("--section", choices=["risk_factors", "mda"])
    command.add_argument("--limit", type=int, default=6000, help="Characters to print; zero means full text")
    command = sub.add_parser("report", help="Export compact provenance evidence without full text/tables")
    command.add_argument("--write", type=Path, required=True)
    command = sub.add_parser("discover", help="Discover filings in an explicit future fiscal window; write a NEW inventory")
    command.add_argument("--company", choices=["NVDA", "AMD", "INTC", "QCOM"], required=True)
    command.add_argument("--fiscal-year", type=int, required=True)
    command.add_argument("--fiscal-start", required=True)
    command.add_argument("--fiscal-end", required=True)
    command.add_argument("--write", type=Path, required=True)
    command.add_argument("--user-agent", default=USER_AGENT)
    command = sub.add_parser("add-release", help="Add an official Q4/full-year release to a future inventory")
    command.add_argument("--company", choices=["NVDA", "AMD", "INTC", "QCOM"], required=True)
    command.add_argument("--fiscal-year", type=int, required=True)
    command.add_argument("--fiscal-start", required=True)
    command.add_argument("--fiscal-end", required=True)
    command.add_argument("--published", required=True)
    command.add_argument("--url", required=True)
    command.add_argument("--format", choices=["html", "pdf"], required=True)
    args = parser.parse_args()
    if args.command == "discover":
        result = discover(args.company, args.fiscal_year, args.fiscal_start, args.fiscal_end, args.write, args.user_agent)
        print(f'{len(result["documents"])} filings discovered; inventory: {args.write}')
        return 0
    if args.command == "add-release":
        add_release(args.inventory, args.company, args.fiscal_year, args.fiscal_start, args.fiscal_end,
                    args.published, args.url, args.format)
        print(f"Release added: {args.inventory}")
        return 0
    if args.command == "collect":
        result = collect(args.inventory, args.output, refresh=args.refresh, offline=args.offline, user_agent=args.user_agent)
        print(json.dumps(result["summary"], indent=2))
        return 0 if not result["summary"]["gaps"] else 1
    if args.command == "verify":
        result = verify_local(args.inventory, args.output)
        if args.write:
            args.write.parent.mkdir(parents=True, exist_ok=True)
            args.write.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    if args.command == "inspect":
        text = inspection(args.output, args.document_id, args.section)
        print(text[:args.limit] if args.limit else text)
        return 0
    manifest = json.loads((args.output / "manifest.json").read_text(encoding="utf-8"))
    if args.command == "status":
        print(json.dumps(manifest["summary"], indent=2))
        for doc in manifest["documents"]:
            print(doc["document_id"], doc["status"], doc.get("error", ""),
                  doc.get("extraction", {}).get("validation", {}).get("failures", []))
    else:
        for doc in manifest["documents"]:
            extraction = doc.get("extraction", {})
            extraction.pop("tables", None)
            extraction["table_count"] = len(json.loads((args.output / extraction["details_path"]).read_text(encoding="utf-8"))["tables"]) if "details_path" in extraction else 0
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(args.write)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
