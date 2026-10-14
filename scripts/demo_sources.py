"""Offline M2 inspection and source fidelity checks; not a model evaluation."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from src.source_collection import DEFAULT_OUTPUT, digest, now

# Independent M1 original-accession financial observations, USD millions.
# Only test readable source rows here; observation selection belongs to M5.
ANNUAL = {
    ("NVDA", 2025): ("130,497", "64,089"), ("NVDA", 2026): ("215,938", "102,718"),
    ("AMD", 2024): ("25,785", "3,041"), ("AMD", 2025): ("34,639", "7,709"),
    ("INTC", 2024): ("53,101", "8,288"), ("INTC", 2025): ("52,853", "9,697"),
    ("QCOM", 2024): ("38,962", "12,202"), ("QCOM", 2025): ("44,284", "14,012"),
}


def demo(output: Path) -> dict:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    failures, samples, annual_rows, risks = [], [], [], []
    texts = {}
    for doc in manifest["documents"]:
        if doc["status"] != "verified":
            failures.append(f'{doc["document_id"]}: not verified')
            continue
        text = (output / doc["extraction"]["text_path"]).read_text(encoding="utf-8")
        texts[doc["document_id"]] = text
        if digest(text.encode("utf-8")) != doc["extraction"]["text_sha256"]:
            failures.append(f'{doc["document_id"]}: text checksum mismatch')
        if "\ufffd" in text:
            failures.append(f'{doc["document_id"]}: replacement characters in extraction')
        if doc["form"] == "10-K":
            revenue, cash = ANNUAL[(doc["company"], doc["fiscal_year"])]
            revenue_row = next((line.strip() for line in text.splitlines()
                                if re.search(r"revenues?|net sales", line, re.I) and revenue in line), None)
            cash_row = next((line.strip() for line in text.splitlines()
                             if re.search(r"(?:operating activities|cash.*operations)", line, re.I) and cash in line), None)
            if not revenue_row or not cash_row:
                failures.append(f'{doc["document_id"]}: independently checked annual table row missing')
            annual_rows.append({"document_id": doc["document_id"], "revenue_usd_millions": revenue,
                                "cash_flow_usd_millions": cash, "revenue_row": revenue_row, "cash_flow_row": cash_row})
            if doc["fiscal_year"] == (2026 if doc["company"] == "NVDA" else 2025):
                samples.append({"company": doc["company"], "document_id": doc["document_id"],
                                "canonical_url": doc["canonical_url"], "retrieval_url": doc["body"]["retrieval_url"],
                                "body_path": doc["body"]["path"], "text_path": doc["extraction"]["text_path"],
                                "mda_opening": text[doc["extraction"]["sections"]["mda"]["start"]:][:1000]})
        if doc["form"] in ("10-K", "10-Q"):
            span = doc["extraction"]["sections"]["risk_factors"]
            risk = text[span["start"]:span["end"]]
            next_heading = text[span["end"]:].splitlines()[0].strip() if span["end"] < len(text) else "EOF"
            if next_heading == "EOF":
                failures.append(f'{doc["document_id"]}: risk section has no next boundary')
            risks.append({"document_id": doc["document_id"], "form": doc["form"], "characters": len(risk),
                          "opening": risk[:700].strip(), "following_heading": next_heading,
                          "prior_annual_document_id": doc.get("prior_annual_document_id"),
                          "risk_context_note": doc.get("risk_context_note")})
    passages = {}
    for identity, units, asp in [("amd-0000002488-26-000018", "31", "15"), ("amd-0000002488-26-000021", "15", "31")]:
        doc = next(d for d in manifest["documents"] if d["document_id"] == identity)
        text = texts.get(identity, "")
        span = doc.get("extraction", {}).get("sections", {}).get("mda", {})
        mda = text[span["start"]:span["end"]] if "start" in span else ""
        passage = next((line for line in mda.splitlines() if line.startswith("Client net revenue of $10.6 billion")), "")
        if f"{units}% increase in unit shipments" not in passage or f"{asp}% increase in average selling price" not in passage:
            failures.append(f"{identity}: AMD correction passage not retained in MD&A")
        passages[identity] = {"passage": passage, "unit_shipment_change_percent": int(units),
                              "asp_change_percent": int(asp), "canonical_url": doc["canonical_url"]}
    amended = next(d for d in manifest["documents"] if d["version"] == "amendment")
    if amended.get("extraction", {}).get("sections", {}).get("risk_factors", {}).get("status") != "not_present":
        failures.append("AMD amendment cannot serve as a replacement risk inventory")
    return {"checked_at": now(), "summary": manifest["summary"], "passed": not failures, "failures": failures,
            "source_samples": samples, "annual_table_checks": annual_rows,
            "risk_section_checks": risks, "amd_mda_passages": passages}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    result = demo(args.output)
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"summary": result["summary"], "passed": result["passed"], "failures": result["failures"]}, indent=2))
    for sample in result["source_samples"]:
        print(f'{sample["company"]}: {sample["document_id"]}\n  Original: {args.output / sample["body_path"]}\n  Text: {args.output / sample["text_path"]}')
    for identity, passage in result["amd_mda_passages"].items():
        print(identity, passage["passage"])
    print(f'{len(result["risk_section_checks"])} annual/quarterly risk boundaries checked; {len(result["annual_table_checks"])} annual revenue/cash-flow rows checked')
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
