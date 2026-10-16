"""Stock research routing and assumption integrity; no external services."""

import pytest

from src.buy_side import BuyTools, collect_market, market_request, valuation_request
from src.analysis_artifacts import ArtifactStore
from src.quant_valuation import replay
from src.supervisor import tasks_for


@pytest.mark.parametrize("question", [
    "What are their stock prices?",
    "Show the selected companies' share prices.",
    "What is its current price?",
    "Which selected stock looks expensive?",
    "Is it cheap relative to its peers?",
    "What is its market cap?",
    "Show their analyst expectations.",
    "Compare their price-to-earnings ratios.",
    "What is its free cash flow yield?",
])
def test_selected_stock_questions_use_buy_side(question):
    plan, _ = tasks_for(question)
    assert market_request(question)
    assert "buy" in [task.worker for task in plan]


@pytest.mark.parametrize("question", [
    "Quote the original filing passage about pricing.",
    "What changed in the annual risk wording?",
    "Show reported annual revenue.",
])
def test_filing_questions_do_not_acquire_market_data(question):
    assert not market_request(question)


@pytest.mark.parametrize("question", [
    "Which selected stock looks expensive?",
    "Compare their price-to-earnings ratios.",
    "What is its market cap?",
    "What is its free cash flow yield?",
])
def test_valuation_language_acquires_relevant_context(question):
    assert valuation_request(question)


@pytest.mark.parametrize("question", [
    "Hypothetical EPS grid: 1e3, 8; P/E grid: 16, 18. Show implied prices.",
    "Hypothetical EPS grid: 8, 10; P/E grid: 1e2, 18. Show implied prices.",
    "Hypothetical EPS grid: 8, 10; P/E grid: 16, 18, 20, 22. Show implied prices.",
    "Hypothetical EPS grid: 1,000, 8; P/E grid: 16, 18. Show implied prices.",
    "Assume EPS of $10 and P/E of 18x; actually use EPS of $8 and P/E of 20x. Show implied price.",
])
def test_ambiguous_or_unsupported_assumptions_are_not_partially_registered(question):
    tools = BuyTools({"question": question, "companies": ["QCOM"], "years": [2025]}, [])
    assert not tools.inputs
    assert tools.missing and tools.clarification_needed


@pytest.mark.parametrize("currency", ["CAD", "AUD", "EUR", "GBP", "JPY"])
def test_currency_suffix_is_never_silently_relabelled_usd(currency):
    tools = BuyTools({"question": f"Assume EPS of $10 {currency} per share and P/E of 18x. Show implied price.", "companies": ["QCOM"], "years": [2025]}, [])
    assert not tools.inputs and tools.clarification_needed


@pytest.mark.parametrize(("horizon", "expected"), [("2-year", "24 months"), ("120-month", "120 months"), ("9 months", "9 months")])
def test_explicit_horizon_is_preserved(horizon, expected):
    tools = BuyTools({"question": f"Assume EPS of $10 and P/E of 18x for a {horizon} implied price.", "companies": ["QCOM"], "years": [2025]}, [])
    assert {s["horizon"] for s in tools.inputs.values()} == {expected}


def test_zero_horizon_needs_clarification():
    tools = BuyTools({"question": "Assume EPS of $10 and P/E of 18x for a 0-month implied price.", "companies": ["QCOM"], "years": [2025]}, [])
    assert not tools.inputs and tools.clarification_needed


def test_valuation_tool_tells_model_about_published_artifacts(tmp_path):
    tools = BuyTools({"question": "Assume EPS of $10 and P/E of 18x for a 24-month implied price.", "companies": ["QCOM"], "years": [2025]}, [], artifacts=ArtifactStore(tmp_path))
    ids = {s["metric"]: sid for sid, s in tools.inputs.items()}
    result = tools("checked_valuation", {"calculations": [{"kind": "implied_price", "inputs": [ids["eps"], ids["multiple"]], "label": "Conditional value"}]})
    assert result["artifacts"]["bundle_id"] == result["bundle_id"]
    assert result["artifacts"]["chart_url"].endswith("/files/chart.png")
    assert any(item["url"].endswith("/files/table.csv") for item in result["artifacts"]["downloads"])
    assert replay(ArtifactStore(tmp_path).load(result["bundle_id"]))["verified"]


@pytest.mark.asyncio
@pytest.mark.parametrize("question", [
    "Hypothetical only: assume EPS of $10 and P/E of 18x. No quotes, consensus or web research.",
    "Hypothetical only: assume EPS of $10 and P/E of 18x. Do not fetch quotes, analyst estimates or supporting evidence.",
    "Hypothetical only: assume EPS=10 and P/E=18. No quotes, consensus or web research.",
])
async def test_explicit_market_exclusions_make_no_acquisition(question):
    class Forbidden:
        async def fetch(self, *args, **kwargs):
            pytest.fail("An explicit exclusion must not spend provider calls")

    evidence, gaps = await collect_market(Forbidden(), {"question": question, "companies": ["QCOM"]}, lambda event: None)
    assert not evidence and not gaps
