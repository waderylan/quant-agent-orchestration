"""Accession-scoped SEC observations with explicit fiscal intervals and provenance."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from src.source_collection import (
    COMPANIES,
    DEFAULT_INVENTORY,
    ROOT,
    Fetcher,
    digest,
    load_inventory,
    now,
    write_json,
)

FINANCIALS = ROOT / "data/financials"
METRICS = ("revenue", "gross_profit", "operating_income", "operating_cash_flow")
TAGS = {
    "revenue": {
        "NVDA": "Revenues",
        "QCOM": "Revenues",
        "AMD": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "INTC": "RevenueFromContractWithCustomerExcludingAssessedTax",
    },
    "gross_profit": "GrossProfit",
    "operating_income": "OperatingIncomeLoss",
    "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
    "cost_of_revenue": {
        "NVDA": "CostOfRevenue",
        "QCOM": "CostOfRevenue",
        "AMD": "CostOfGoodsAndServicesSold",
        "INTC": "CostOfRevenue",
    },
}


def exact_fact(facts, doc, tag, start):
    """Repeated identical facts collapse; conflicting originals remain unresolved."""
    candidates = facts.get(tag, {}).get("units", {}).get("USD", [])
    interval = [
        r
        for r in candidates
        if r.get("start") == start and r.get("end") == doc["period_end"]
    ]
    selected = [
        r
        for r in interval
        if r.get("accn") == doc["accession"]
        and r.get("form") == doc["form"]
        and r.get("filed") == doc["source_date"]
    ]
    values = {r["val"] for r in selected if type(r.get("val")) is int}
    if len(values) != 1:
        return {
            "status": "conflicting" if values else "missing",
            "tag": "us-gaap:" + tag,
        }
    value = values.pop()
    return {
        "status": "available",
        "tag": "us-gaap:" + tag,
        "value": value,
        "accession": doc["accession"],
        "start": start,
        "end": doc["period_end"],
        "unit": "USD",
        "conflicting_comparatives": sorted(
            (
                {"accession": r["accn"], "filed": r["filed"], "value": r["val"]}
                for r in interval
                if r.get("accn") != doc["accession"] and r.get("val") != value
            ),
            key=lambda r: (r["filed"], r["accession"]),
        ),
    }


def prepare_observations(documents, snapshots):
    observations = []
    originals = [
        d for d in documents if d["kind"] == "filing" and d["version"] == "original"
    ]
    for company in sorted({d["company"] for d in originals}):
        snapshot = snapshots[company]
        facts = snapshot["facts"]["facts"]["us-gaap"]
        for year in sorted(
            {d["fiscal_year"] for d in originals if d["company"] == company}
        ):
            reports = sorted(
                (
                    d
                    for d in originals
                    if d["company"] == company and d["fiscal_year"] == year
                ),
                key=lambda d: d["period_end"],
            )
            for ordinal, doc in enumerate(reports):
                annual = doc["form"] == "10-K"
                period = "FY" if annual else f"Q{ordinal + 1}"
                if not annual and ordinal >= 3:
                    raise ValueError(
                        "Review the inventory: more than three original quarterly reports"
                    )
                intervals = [("annual" if annual else "ytd", doc["fiscal_start"])]
                if not annual:
                    start = (
                        doc["fiscal_start"]
                        if ordinal == 0
                        else (
                            date.fromisoformat(reports[ordinal - 1]["period_end"])
                            + timedelta(days=1)
                        ).isoformat()
                    )
                    intervals.append(("quarter", start))
                for basis, start in intervals:
                    for metric in (*METRICS, "cost_of_revenue"):
                        tag = TAGS[metric]
                        if isinstance(tag, dict):
                            tag = tag[company]
                        selected = exact_fact(facts, doc, tag, start)
                        inputs = []
                        formula = None
                        if company == "QCOM" and metric == "gross_profit":
                            inputs = [
                                exact_fact(facts, doc, t, start)
                                for t in ("Revenues", "CostOfRevenue")
                            ]
                            if all(r["status"] == "available" for r in inputs):
                                selected = {
                                    "status": "available",
                                    "tag": None,
                                    "value": inputs[0]["value"] - inputs[1]["value"],
                                    "conflicting_comparatives": [],
                                }
                                formula = "revenue - cost_of_revenue"
                            else:
                                selected = {"status": "missing", "tag": None}
                        observation = {
                            "kind": "financial_observation",
                            "company": company,
                            "fiscal_year": year,
                            "period": period,
                            "basis": basis,
                            "start": start,
                            "end": doc["period_end"],
                            "fiscal_start": doc["fiscal_start"],
                            "fiscal_end": doc["fiscal_end"],
                            "metric": metric,
                            "unit": "USD",
                            "accounting_basis": "US GAAP consolidated",
                            "revision_basis": "original_report",
                            "version": "original",
                            "document_id": doc["document_id"],
                            "accession": doc["accession"],
                            "form": doc["form"],
                            "filed": doc["source_date"],
                            "canonical_url": doc["canonical_url"],
                            "facts_url": snapshot["record"]["requested_url"],
                            "snapshot_sha256": snapshot["record"]["sha256"],
                            "retrieved_at": snapshot["record"]["retrieved_at"],
                            "warnings": [
                                "FY2024 contains 53 weeks; FY2025 contains 52. Do not silently normalize."
                            ]
                            if company == "QCOM" and year == 2024
                            else [],
                            "inputs": inputs,
                            "formula": formula,
                            **selected,
                        }
                        observation["observation_id"] = digest(
                            json.dumps(observation, sort_keys=True).encode()
                        )
                        observations.append(observation)
    return observations


def collect_financials(
    output=FINANCIALS, inventory=DEFAULT_INVENTORY, *, refresh=False
):
    """Publish only after all four snapshots validate; keep content-addressed history."""
    documents = load_inventory(inventory)
    existing = output / "manifest.json"
    cached = (
        json.loads(existing.read_text(encoding="utf-8")) if existing.exists() else {}
    )
    fetcher = Fetcher()
    snapshots, records = {}, {}
    for company, (cik, _) in COMPANIES.items():
        record = cached.get("snapshots", {}).get(company)
        if record and not refresh:
            body = safe_blob(output, record).read_bytes()
        else:
            body, record = fetcher.get(
                f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            )
            record["path"] = f"raw/{record['sha256']}.json"
            path = output / record["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(body)
        if digest(body) != record["sha256"]:
            raise ValueError(f"Financial snapshot checksum mismatch: {company}")
        facts = json.loads(body)
        if int(facts["cik"]) != int(cik):
            raise ValueError("Financial snapshot company/CIK mismatch")
        snapshots[company] = {"facts": facts, "record": record}
        records[company] = record
    observations = prepare_observations(documents, snapshots)
    result = {
        "schema_version": 1,
        "prepared_at": now(),
        "inventory_sha256": digest(inventory.read_bytes()),
        "snapshots": records,
        "observations": observations,
    }
    version = digest(json.dumps(result, sort_keys=True).encode())
    write_json(output / f"runs/{version}.json", result)
    write_json(existing, result)
    return {
        "observations": len(observations),
        "available": sum(r["status"] == "available" for r in observations),
        "snapshots": len(records),
        "manifest_sha256": digest(existing.read_bytes()),
    }


def safe_blob(root, record):
    path = (root / record["path"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Financial snapshot path escapes its directory")
    return path


class FinancialStore:
    def __init__(self, path: Path = FINANCIALS, inventory: Path = DEFAULT_INVENTORY):
        self.path, self.inventory = path, inventory
        self._observations = None

    @property
    def observations(self):
        if self._observations is None:
            try:
                manifest = json.loads(
                    (self.path / "manifest.json").read_text(encoding="utf-8")
                )
            except FileNotFoundError as error:
                raise ValueError(
                    "Financial data is unavailable. Run scripts/financials.py collect."
                ) from error
            if manifest["inventory_sha256"] != digest(self.inventory.read_bytes()):
                raise ValueError(
                    "Financial inventory changed; reprepare financial observations"
                )
            snapshots = {}
            for company, record in manifest["snapshots"].items():
                body = safe_blob(self.path, record).read_bytes()
                if digest(body) != record["sha256"]:
                    raise ValueError("Financial snapshot checksum mismatch")
                snapshots[company] = {"facts": json.loads(body), "record": record}
                if int(snapshots[company]["facts"]["cik"]) != int(
                    COMPANIES[company][0]
                ):
                    raise ValueError("Financial snapshot company/CIK mismatch")
            expected = prepare_observations(load_inventory(self.inventory), snapshots)
            if expected != manifest["observations"]:
                raise ValueError(
                    "Prepared financial observations differ from source snapshots"
                )
            self._observations = {r["observation_id"]: r for r in expected}
        return self._observations

    def query(self, companies, years, *, metrics=METRICS, period="FY", basis="annual"):
        if not companies or not years or set(metrics) - TAGS.keys() or not metrics:
            raise ValueError(
                "Specify supported companies, years, and financial metrics"
            )
        if period not in ("FY", "Q1", "Q2", "Q3") or basis not in (
            "annual",
            "quarter",
            "ytd",
        ):
            raise ValueError(
                "Unsupported period/basis. Q4-only inputs require Quant derivation."
            )
        if (period == "FY") != (basis == "annual"):
            raise ValueError("FY uses annual; Q1-Q3 use quarter or ytd basis")
        rows = [
            r
            for r in self.observations.values()
            if r["company"] in companies
            and r["fiscal_year"] in years
            and r["metric"] in metrics
            and r["period"] == period
            and r["basis"] == basis
        ]
        gaps = [
            {
                "company": c,
                "fiscal_year": y,
                "metric": m,
                "period": period,
                "basis": basis,
                "status": "missing",
            }
            for c in companies
            for y in years
            for m in metrics
            if not any(
                r["company"] == c and r["fiscal_year"] == y and r["metric"] == m
                for r in rows
            )
        ]
        return {
            "observations": [r for r in rows if r["status"] == "available"],
            "gaps": gaps + [r for r in rows if r["status"] != "available"],
        }

    def inspect(self, observation_id):
        return self.observations[observation_id]

    def snapshot(self, sha256):
        if sha256 not in {r["snapshot_sha256"] for r in self.observations.values()}:
            raise KeyError("Snapshot is outside the prepared observations")
        path = safe_blob(self.path, {"path": f"raw/{sha256}.json"})
        if digest(path.read_bytes()) != sha256:
            raise ValueError("Financial snapshot checksum mismatch")
        return path
