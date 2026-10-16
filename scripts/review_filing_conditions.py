"""Request-local source faults for independent application acceptance.

Synthetic sources use separate immutable identifiers and explicit fixture labels.
Original corpus files, index records and financial snapshots are never changed.
"""

import copy
import json
from types import SimpleNamespace
from datetime import date

from src.financial_data import FinancialStore
from src.risk_summary import inspect_span
from src.source_collection import digest
from src.source_collection import ROOT
from src.research_index import ResearchIndex

OBSERVATIONS = {}
RISK_INDEXES = {}


class ReviewFinancials(FinancialStore):
    def __init__(self, original, condition):
        self.path = original.path
        self.original = original
        self.condition = condition

    @property
    def observations(self):
        if self.condition == "all_sources_missing":
            return {}
        rows = copy.deepcopy(self.original.observations)
        selected = {}
        for row in rows.values():
            changed = False
            if self.condition == "negative_financials" and row["company"] == "INTC" and row["period"] == "FY":
                if row["metric"] in ("net_income", "operating_income"):
                    row["value"] = (-100_000_000 if row["metric"] == "net_income" else 0) if row["fiscal_year"] == 2024 else 20_000_000
                    changed = True
            elif self.condition == "parent_income" and row["company"] == "INTC" and row["metric"] == "net_income":
                row["value"] = 20_000_000
                row["total_consolidated_net_income"] = 30_000_000
                changed = True
            elif self.condition == "conflicting_scale" and row["company"] == "AMD" and row["metric"] == "revenue" and row["fiscal_year"] == 2025:
                row.update(status="conflicting", structured_scale="thousands (incorrect fixture)", original_statement_scale="millions", conflicting_fixture_value=row["value"] * 1000)
                counterpart = copy.deepcopy(row)
                counterpart.update(value=row["value"] * 1000, provenance="synthetic_structured_scale_error", warnings=["SYNTHETIC REVIEW FIXTURE: conflicting scaled observation, not an actual company result"], evidence_kind="synthetic review fixture", canonical_url="https://example.org/synthetic-structured-scale-error")
                counterpart.pop("observation_id", None)
                counterpart["observation_id"] = digest(json.dumps(counterpart, sort_keys=True).encode())
                OBSERVATIONS[counterpart["observation_id"]] = counterpart
                selected[counterpart["observation_id"]] = counterpart
                row["provenance"] = "synthetic_original_statement_scale"
                changed = True
            elif self.condition == "mixed_units" and row["period"] == "FY":
                scale = 1_000_000 if row["company"] == "AMD" else 1000
                row.update(original_value=str(row["value"] / scale) if "value" in row else None, original_unit="USD millions" if scale == 1_000_000 else "USD thousands", normalization="Original amount multiplied by explicit scale; stored value remains USD")
                changed = True
            if self.condition == "q3_ytd_only" and (row["period"] == "Q2" or row["period"] == "Q3" and row["basis"] == "quarter"):
                continue
            if self.condition == "q2_missing" and row["period"] == "Q2":
                continue
            if changed:
                row.setdefault("warnings", []).append("SYNTHETIC REVIEW FIXTURE: substituted observation, not an actual company result")
                row["evidence_kind"] = "synthetic review fixture"
                row["canonical_url"] = "https://example.org/synthetic-review-observation"
                row.pop("observation_id", None)
                row["observation_id"] = digest(json.dumps(row, sort_keys=True).encode())
                OBSERVATIONS[row["observation_id"]] = row
            selected[row["observation_id"]] = row
        return selected


class ReviewIndex:
    def __init__(self, original, condition):
        self.original, self.condition = original, condition
        self.documents = copy.deepcopy(original.documents)
        self.replacements = {}
        self.corrupted = {}
        for old_id, doc in list(self.documents.items()):
            if condition == "hash_corruption" and doc.get("company") == "QCOM" and doc.get("fiscal_year") == 2025 and doc.get("form") == "10-K" and doc.get("version") == "original":
                text = original.text(original.documents[old_id])
                offset = doc["extraction"]["sections"]["risk_factors"]["start"] + 10
                altered = text[:offset] + ("X" if text[offset] != "X" else "Y") + text[offset + 1:]
                disposable = ROOT / "artifacts/review-corruption" / old_id
                target = disposable / doc["extraction"]["text_path"]
                assert target.resolve().is_relative_to(disposable.resolve())
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(altered.encode())
                self.corrupted[old_id] = disposable
            if condition == "quarterly_risk_omission" and doc.get("company") == "QCOM" and doc.get("fiscal_year") == 2025 and doc.get("form") == "10-Q":
                elapsed = (date.fromisoformat(doc["period_end"]) - date.fromisoformat(doc["fiscal_start"])).days
                bounds = doc["extraction"].get("sections", {}).get("risk_factors")
                if 150 < elapsed < 210 and bounds:
                    text = original.text(original.documents[old_id])
                    wording = "SYNTHETIC REVIEW FIXTURE; not original company language. There have been no material changes to the risk factors disclosed in the original FY2024 Annual Report on Form 10-K. The annual risk factors remain applicable."
                    altered = text[:bounds["start"]] + wording + text[bounds["end"]:]
                    bounds["end"] = bounds["start"] + len(wording)
                    doc["extraction"]["text_sha256"] = digest(altered.encode())
                    doc["document_id"] = "fixture-" + condition + "-" + old_id
                    doc["canonical_url"] = "https://example.org/synthetic-quarterly-risk-omission"
                    del self.documents[old_id]
                    self.documents[doc["document_id"]] = doc
                    self.replacements[doc["document_id"]] = altered
                    RISK_INDEXES[doc["document_id"]] = self
            if condition == "partial_risk" and doc.get("company") == "QCOM" and doc.get("fiscal_year") == 2025 and doc.get("form") == "10-K":
                doc["extraction"]["sections"].pop("risk_factors", None)
            if doc.get("form") != "10-K" or doc.get("version") != "original":
                continue
            bounds = doc["extraction"].get("sections", {}).get("risk_factors", {})
            if not bounds or condition not in ("relocated_risk", "added_risk", "clarified_risk"):
                continue
            text = original.text(original.documents[old_id])
            year = doc["fiscal_year"]
            if condition == "relocated_risk":
                wording = "Manufacturing execution: Delays ramping our manufacturing processes could increase costs and reduce our ability to meet customer demand. We rely on timely process execution and product quality."
                if year == 2025:
                    wording = "Operations and product delivery: Failure to execute manufacturing processes on time could raise costs and impair delivery to customers. Product quality and process execution remain material dependencies."
            elif condition == "added_risk":
                wording = "Supply constraints could reduce product availability and adversely affect revenue, profitability and customer relationships. We depend on third-party manufacturing capacity."
                if year == 2025:
                    wording += " Capacity constraints include advanced packaging availability and allocation of suppliers' production lines.\nA new export licensing requirement could prohibit sales to additional countries and materially reduce demand for products previously unrestricted."
            elif condition == "clarified_risk":
                wording = "We rely on external suppliers for semiconductor fabrication. Supply disruptions could delay product delivery and reduce revenue."
                if year == 2025:
                    wording = "External suppliers fabricate our semiconductors. Disruptions, including power outages and transport delays, could reduce revenue by delaying product delivery."
            wording = "SYNTHETIC REVIEW FIXTURE; not original company language.\n" + wording
            altered = text[:bounds["start"]] + wording + text[bounds["end"]:]
            bounds["end"] = bounds["start"] + len(wording)
            doc["extraction"]["text_sha256"] = digest(altered.encode())
            doc["document_id"] = "fixture-" + condition + "-" + old_id
            doc["canonical_url"] = "https://example.org/synthetic-review-risk"
            del self.documents[old_id]
            self.documents[doc["document_id"]] = doc
            self.replacements[doc["document_id"]] = altered
            RISK_INDEXES[doc["document_id"]] = self

    def __getattr__(self, name):
        return getattr(self.original, name)

    def text(self, doc):
        if doc["document_id"] in self.corrupted:
            return ResearchIndex.text(SimpleNamespace(corpus=self.corrupted[doc["document_id"]]), doc)
        if self.condition == "all_sources_missing":
            raise ValueError("Synthetic unavailable original filing; no cached evidence permitted")
        if self.condition == "quarterly_category_missing" and doc.get("form") != "10-K":
            raise ValueError("Synthetic missing quarterly category source; annual tables remain available")
        if self.condition == "q2_missing" and doc.get("form") == "10-Q":
            elapsed = (date.fromisoformat(doc["period_end"]) - date.fromisoformat(doc["fiscal_start"])).days
            if 150 < elapsed < 210:
                raise ValueError("Synthetic Q2 filing unavailable; no cached evidence permitted")
        return self.replacements.get(doc["document_id"]) or self.original.text(doc)

    def search(self, *args, **kwargs):
        if self.condition == "all_sources_missing":
            return []
        found = self.original.search(*args, **kwargs)
        if self.condition == "quarterly_category_missing":
            found = [p for p in found if self.documents[p["document_id"]].get("form") == "10-K"]
        if self.condition == "q2_missing":
            def not_q2(p):
                doc = self.documents[p["document_id"]]
                elapsed = (date.fromisoformat(doc["period_end"]) - date.fromisoformat(doc["fiscal_start"])).days
                return doc.get("form") != "10-Q" or not 150 < elapsed < 210
            found = [p for p in found if not_q2(p)]
        return found


def fixture_source(path, query):
    if path.startswith("/api/financial/observations/"):
        return OBSERVATIONS.get(path.rsplit("/", 1)[1])
    if path.startswith("/api/risks/"):
        document_id = path.rsplit("/", 1)[1]
        if document_id in RISK_INDEXES:
            return inspect_span(RISK_INDEXES[document_id], document_id, int(query["start"]), int(query["end"]))
    if path.startswith("/api/originals/fixture-"):
        return {"evidence_kind": "synthetic review fixture", "notice": "No company original exists for synthetic test language"}
    return None
