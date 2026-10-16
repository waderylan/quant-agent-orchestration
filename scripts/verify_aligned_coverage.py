"""Check added coverage and parent GAAP earnings against inspected filing rows."""

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.financial_data import FinancialStore
from src.source_collection import DEFAULT_OUTPUT, ROOT, digest, now, write_json

# Values in millions, independently inspected in each original annual statement.
# Intel's parent line excludes noncontrolling interests; ProfitLoss is a different line.
EARNINGS_MILLIONS = {
    ("NVDA", 2024): 29760,
    ("NVDA", 2025): 72880,
    ("NVDA", 2026): 120067,
    ("AMD", 2024): 1641,
    ("AMD", 2025): 4335,
    ("INTC", 2024): -18756,
    ("INTC", 2025): -267,
    ("QCOM", 2024): 10142,
    ("QCOM", 2025): 5541,
}
NVIDIA_2024_MILLIONS = {
    "revenue": (60922, "Revenue"),
    "gross_profit": (44301, "Gross profit"),
    "operating_income": (32972, "Operating income"),
    "operating_cash_flow": (28090, "Net cash provided by operating activities"),
}


def statement_row(text, label, expected_millions):
    """Require the first amount after the statement label, not a later comparative."""
    for match in re.finditer(
        r"(?im)^\s*" + re.escape(label) + r"(?!\s+per\s+share)[^\n]*", text
    ):
        row = re.sub(r"\s+", " ", match.group()).strip()
        rest = row[len(label) :]
        amount = re.search(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", rest)
        if not amount:
            continue
        value = amount.group().replace(",", "")
        numeric = Decimal(value.strip("()")) * (-1 if value.startswith("(") else 1)
        if numeric == expected_millions:
            return row, match.start()
    raise AssertionError(
        f"Original statement row not found: {label} {expected_millions}"
    )


def verify():
    store = FinancialStore()
    corpus = json.loads((DEFAULT_OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    documents = {d["document_id"]: d for d in corpus["documents"]}
    baseline = json.loads(
        (ROOT / "docs/research/M2_COLLECTION_RESULTS.json").read_text(encoding="utf-8")
    )
    # Added years must preserve collected source bodies and prepared text. Context
    # relationships can change when a formerly absent prior annual enters scope.
    preserved = []
    for original in baseline["documents"]:
        current = documents[original["document_id"]]
        for key in ("accession", "canonical_url", "period_end", "version"):
            assert current[key] == original[key]
        assert current["body"]["sha256"] == original["body"]["sha256"]
        assert (
            current["extraction"]["text_sha256"]
            == original["extraction"]["text_sha256"]
        )
        preserved.append(original["document_id"])
    checks = []
    for (company, year), millions in EARNINGS_MILLIONS.items():
        result = store.query([company], [year], metrics=["net_income"])
        assert not result["gaps"] and len(result["observations"]) == 1
        observation = result["observations"][0]
        assert observation["value"] == millions * 1_000_000
        assert observation["tag"] == "us-gaap:NetIncomeLoss"
        doc = documents[observation["document_id"]]
        text = (DEFAULT_OUTPUT / doc["extraction"]["text_path"]).read_text(
            encoding="utf-8"
        )
        label = (
            "Net income (loss) attributable to Intel"
            if company == "INTC"
            else "Net income"
        )
        row, offset = statement_row(text, label, millions)
        checks.append(
            {
                "company": company,
                "fiscal_year": year,
                "value_usd": observation["value"],
                "start": observation["start"],
                "end": observation["end"],
                "accession": observation["accession"],
                "document_id": doc["document_id"],
                "canonical_url": doc["canonical_url"],
                "original_sha256": doc["body"]["sha256"],
                "statement_row": row,
                "row_character_start": offset,
                "page": next(
                    (
                        p["page"]
                        for p in doc["extraction"]["pages"]
                        if p["start"] <= offset < p["end"]
                    ),
                    None,
                ),
                "passed": True,
            }
        )
    nvidia = []
    for metric, (millions, label) in NVIDIA_2024_MILLIONS.items():
        row = store.query(["NVDA"], [2024], metrics=[metric])["observations"][0]
        assert row["value"] == millions * 1_000_000
        assert (row["start"], row["end"], row["accession"]) == (
            "2023-01-30",
            "2024-01-28",
            "0001045810-24-000029",
        )
        doc = documents[row["document_id"]]
        text = (DEFAULT_OUTPUT / doc["extraction"]["text_path"]).read_text(
            encoding="utf-8"
        )
        statement, offset = statement_row(text, label, millions)
        nvidia.append(
            {
                "metric": metric,
                "value_usd": row["value"],
                "statement_row": statement,
                "row_character_start": offset,
                "passed": True,
            }
        )
    observations = list(store.observations.values())
    coverage = {
        c: sorted({r["fiscal_year"] for r in observations if r["company"] == c})
        for c in ("AMD", "INTC", "NVDA", "QCOM")
    }
    for years in coverage.values():
        assert {2024, 2025} <= set(years)
    ranking = []
    for company in ("AMD", "INTC", "NVDA", "QCOM"):
        prior, current = (
            EARNINGS_MILLIONS[(company, year)] * 1_000_000 for year in (2024, 2025)
        )
        ranking.append(
            {
                "company": company,
                "fy2024_usd": prior,
                "fy2025_usd": current,
                "change_usd": current - prior,
                "growth_percent": str((Decimal(current) / prior - 1) * 100)
                if prior > 0
                else None,
                "growth_limit": None
                if prior > 0
                else "Negative prior earnings; percentage growth is not meaningful.",
            }
        )
    report = {
        "verified_at": now(),
        "kind": "offline original-filing/reference checks; no model generation",
        "coverage": coverage,
        "corpus": corpus["summary"],
        "preserved_baseline": {
            "source": "docs/research/M2_COLLECTION_RESULTS.json",
            "documents": preserved,
            "checks": "identity, original-body SHA256, prepared-text SHA256",
            "passed": True,
        },
        "observations": len(observations),
        "available": sum(r["status"] == "available" for r in observations),
        "counts_by_metric": {
            metric: {
                "slots": sum(r["metric"] == metric for r in observations),
                "available": sum(
                    r["metric"] == metric and r["status"] == "available"
                    for r in observations
                ),
            }
            for metric in sorted({r["metric"] for r in observations})
        },
        "earnings_checks": checks,
        "nvidia_fy2024_additional_checks": nvidia,
        "independent_earnings_comparison": ranking,
        "financial_manifest_sha256": digest(
            (store.path / "manifest.json").read_bytes()
        ),
        "passed": True,
    }
    destination = ROOT / "docs/research/ALIGNED_FINANCIAL_COVERAGE_RESULTS.json"
    write_json(destination, report)
    print(
        json.dumps(
            {k: report[k] for k in ("coverage", "observations", "available", "passed")},
            indent=2,
        )
    )
    return report


if __name__ == "__main__":
    verify()
