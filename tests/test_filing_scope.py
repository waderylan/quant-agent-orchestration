"""Keep explicit reporting windows out of unrelated semantic candidates."""

from src.filing_scope import filing_scope


DOCS = {
    "q1": {"company": "QCOM", "fiscal_year": 2024, "form": "10-Q", "fiscal_start": "2023-09-25", "period_end": "2023-12-24"},
    "q2": {"company": "QCOM", "fiscal_year": 2024, "form": "10-Q", "fiscal_start": "2023-09-25", "period_end": "2024-03-24"},
    "k": {"company": "QCOM", "fiscal_year": 2024, "form": "10-K"},
    "amended": {"company": "QCOM", "fiscal_year": 2024, "form": "10-K/A"},
    "release": {"company": "QCOM", "fiscal_year": 2024, "form": "Earnings release"},
}


def test_interim_scope_uses_fiscal_elapsed_period_not_calendar_quarter():
    assert filing_scope("FY2024 Q2 10-Q", DOCS, ["QCOM"], [2024]) == {"form": "10-Q", "document_ids": ["q2"]}
    assert filing_scope("FY2024 fourth-quarter 10-Q", DOCS, ["QCOM"], [2024]) == {"form": "10-Q", "document_ids": []}
    assert filing_scope("FY2024 fourth-quarter results", DOCS, ["QCOM"], [2024]) == {}


def test_mixed_sources_remain_available_and_amendments_keep_both_versions():
    assert filing_scope("Compare annual report with Q2 10-Q", DOCS, ["QCOM"], [2024]) == {}
    assert filing_scope("Compare annual report with Q2", DOCS, ["QCOM"], [2024]) == {}
    assert filing_scope("Compare Q1 and Q2 10-Q", DOCS, ["QCOM"], [2024]) == {"form": "10-Q"}
    assert filing_scope("Explain the 10-K/A correction", DOCS, ["QCOM"], [2024]) == {"document_ids": ["k", "amended"]}
    assert filing_scope("Explain annual report", DOCS, ["QCOM"], [2024]) == {"form": "10-K"}
