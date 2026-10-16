"""Protect original accessions, fiscal intervals, derived inputs, and missingness."""

import json

import pytest

from src.financial_data import FinancialStore, exact_fact, prepare_observations
from src.financial_workflow import FinancialTools, financial_turn
from src.source_collection import DEFAULT_INVENTORY, digest, write_json


def filing(company="QCOM", year=2024):
    return next(
        d
        for d in json.loads(DEFAULT_INVENTORY.read_text(encoding="utf-8"))["documents"]
        if d["company"] == company and d["fiscal_year"] == year and d["form"] == "10-K"
    )


def fact(doc, value, *, start=None, **extra):
    return {
        "start": start or doc["fiscal_start"],
        "end": doc["period_end"],
        "accn": doc["accession"],
        "form": doc["form"],
        "filed": doc["source_date"],
        "val": value,
        "fy": 2099,
        "fp": "Q3",
        **extra,
    }


def test_exact_accession_dates_units_and_conflicts_override_fiscal_labels():
    doc = filing()
    original = fact(doc, 100)
    facts = {
        "Revenues": {
            "units": {
                "USD": [
                    original,
                    dict(original),
                    fact(doc, 999, accn="later-report"),
                    fact(doc, 500, start="2024-01-01"),
                ],
                "shares": [fact(doc, 9000)],
            }
        }
    }
    selected = exact_fact(facts, doc, "Revenues", doc["fiscal_start"])
    assert selected["value"] == 100
    assert selected["conflicting_comparatives"][0]["value"] == 999
    facts["Revenues"]["units"]["USD"].append(fact(doc, 101))
    assert (
        exact_fact(facts, doc, "Revenues", doc["fiscal_start"])["status"]
        == "conflicting"
    )
    assert exact_fact({}, doc, "Revenues", doc["fiscal_start"])["status"] == "missing"


@pytest.fixture
def financial_store(tmp_path):
    doc = filing()
    facts = {
        "cik": int(doc["cik"]),
        "facts": {
            "us-gaap": {
                tag: {"units": {"USD": [fact(doc, value)]}}
                for tag, value in [
                    ("Revenues", 38962000000),
                    ("CostOfRevenue", 17060000000),
                    ("OperatingIncomeLoss", -100),
                    ("NetCashProvidedByUsedInOperatingActivities", 0),
                    ("NetIncomeLoss", -150),
                    ("ProfitLoss", -140),
                ]
            }
        },
    }
    inventory = tmp_path / "inventory.json"
    write_json(inventory, {"documents": [doc]})
    raw = json.dumps(facts).encode()
    record = {
        "sha256": digest(raw),
        "path": "raw/facts.json",
        "retrieved_at": "2026-10-15T00:00:00Z",
        "requested_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000804328.json",
    }
    path = tmp_path / "financials"
    (path / "raw").mkdir(parents=True)
    (path / record["path"]).write_bytes(raw)
    rows = prepare_observations([doc], {"QCOM": {"facts": facts, "record": record}})
    write_json(
        path / "manifest.json",
        {
            "inventory_sha256": digest(inventory.read_bytes()),
            "snapshots": {"QCOM": record},
            "observations": rows,
        },
    )
    return FinancialStore(path, inventory)


def test_derived_gross_profit_preserves_inputs_losses_zero_and_53_week_context(
    financial_store,
):
    rows = financial_store.query(["QCOM"], [2024])["observations"]
    gross = next(r for r in rows if r["metric"] == "gross_profit")
    assert gross["value"] == 21902000000
    assert [r["value"] for r in gross["inputs"]] == [38962000000, 17060000000]
    assert gross["formula"] == "revenue - cost_of_revenue" and gross["warnings"]
    assert next(r["value"] for r in rows if r["metric"] == "operating_income") == -100
    assert next(r["value"] for r in rows if r["metric"] == "operating_cash_flow") == 0
    missing = financial_store.query(["QCOM"], [2025])
    assert not missing["observations"] and len(missing["gaps"]) == 4


def test_net_income_preserves_parent_loss_and_does_not_substitute_profit_loss(
    financial_store,
):
    result = financial_store.query(["QCOM"], [2024], metrics=["net_income"])
    row = result["observations"][0]
    assert row["value"] == -150
    assert row["tag"] == "us-gaap:NetIncomeLoss"
    assert row["accession"] == filing()["accession"] and not result["gaps"]
    missing = financial_store.query(["QCOM"], [2025], metrics=["net_income"])
    assert not missing["observations"] and missing["gaps"][0]["metric"] == "net_income"
    doc = filing()
    snapshots = {
        "QCOM": {
            "facts": {
                "facts": {
                    "us-gaap": {"ProfitLoss": {"units": {"USD": [fact(doc, 50)]}}}
                }
            },
            "record": {
                "requested_url": "https://data.sec.gov",
                "sha256": "source",
                "retrieved_at": "date",
            },
        }
    }
    prepared = prepare_observations([doc], snapshots)
    row = next(r for r in prepared if r["metric"] == "net_income")
    assert row["status"] == "missing" and "value" not in row


@pytest.mark.parametrize("damage", ["raw", "prepared", "inventory"])
def test_financial_store_rejects_tampered_or_stale_evidence(financial_store, damage):
    path = financial_store.path
    manifest = json.loads((path / "manifest.json").read_text())
    if damage == "raw":
        (path / "raw/facts.json").write_text("tampered")
    elif damage == "prepared":
        manifest["observations"][0]["value"] = 999
        write_json(path / "manifest.json", manifest)
    else:
        financial_store.inventory.write_text("changed inventory")
    with pytest.raises(ValueError, match="checksum|differ|changed"):
        financial_store.query(["QCOM"], [2024])


def test_quarter_and_cumulative_values_do_not_collapse_or_invent_cash_flow():
    docs = [
        d
        for d in json.loads(DEFAULT_INVENTORY.read_text(encoding="utf-8"))["documents"]
        if d["company"] == "AMD"
        and d["fiscal_year"] == 2025
        and d["version"] == "original"
        and d["kind"] == "filing"
    ]
    docs.sort(key=lambda d: d["period_end"])
    q2 = docs[1]
    facts = {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {
            "units": {"USD": [fact(q2, 210), fact(q2, 110, start="2025-03-30")]}
        },
        "NetCashProvidedByUsedInOperatingActivities": {
            "units": {"USD": [fact(q2, 50)]}
        },
    }
    snapshots = {
        "AMD": {
            "facts": {"facts": {"us-gaap": facts}},
            "record": {
                "requested_url": "https://data.sec.gov",
                "sha256": "source",
                "retrieved_at": "date",
            },
        }
    }
    amendment = dict(q2, version="amendment", form="10-Q/A")
    rows = prepare_observations(docs + [amendment], snapshots)
    selected = [r for r in rows if r["period"] == "Q2"]
    assert {r["basis"]: r["value"] for r in selected if r["metric"] == "revenue"} == {
        "ytd": 210,
        "quarter": 110,
    }
    cash = next(
        r
        for r in selected
        if r["metric"] == "operating_cash_flow" and r["basis"] == "quarter"
    )
    assert cash["status"] == "missing" and "value" not in cash
    assert all(r["version"] == "original" for r in rows)


def test_financial_tools_cannot_broaden_scope_or_substitute_unsupported_basis(
    financial_store,
):
    tools = FinancialTools(financial_store, ["QCOM"], [2024])
    with pytest.raises(ValueError, match="scope"):
        tools("query_financials", {"company": "NVDA"})
    with pytest.raises(ValueError, match="scope"):
        tools("query_financials", {"year": 2025})
    with pytest.raises(ValueError, match="annual"):
        tools("query_financials", {"period": "FY", "basis": "quarter"})
    with pytest.raises(ValueError, match="supported"):
        tools("query_financials", {"metrics": ["adjusted_ebitda"]})
    with pytest.raises(KeyError):
        tools("inspect_observation", {"source_id": "F99"})


@pytest.mark.asyncio
async def test_financial_worker_uses_distinct_tools_and_rejects_unregistered_citations(
    financial_store,
):
    async def model(prompt, tool_schema, handler, **kwargs):
        assert {t["name"] for t in tool_schema} == {
            "query_financials",
            "inspect_observation",
        }
        result = handler("query_financials", {"metrics": ["revenue"]})
        yield {"type": "tool", "data": {"name": "query_financials"}}
        assert result["sources"][0]["value"] == 38962000000
        yield {"type": "token", "data": "Revenue was 38,962 million USD [F1]."}

    state = {
        "question": "Show Qualcomm revenue",
        "companies": ["QCOM"],
        "years": [2024],
    }
    result = await financial_turn(
        financial_store, state, lambda e: None, model_stream=model
    )
    assert result["financial_sources"]["F1"]["accession"] == filing()["accession"]

    async def invented(*args, **kwargs):
        yield {"type": "token", "data": "A fabricated amount [F99]."}

    result = await financial_turn(
        financial_store, state, lambda e: None, model_stream=invented
    )
    assert result["error"] == "Financial evidence validation failed"


@pytest.mark.asyncio
async def test_missing_quarter_cash_flow_abstains_before_generation(financial_store):
    async def forbidden(*args, **kwargs):
        pytest.fail("An empty scoped result must not generate a financial figure")
        yield

    result = await financial_turn(
        financial_store,
        {
            "question": "Show Qualcomm FY2024 Q2-only operating cash flow",
            "companies": ["QCOM"],
            "years": [2024],
        },
        lambda e: None,
        model_stream=forbidden,
    )
    assert (
        result["partial"] and result["needs_evidence"]["kind"] == "structured_missing"
    )
    assert result["answer"] == ""
    assert (
        "no structured calculation is established"
        in result["needs_evidence"]["message"]
    )
