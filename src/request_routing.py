"""Inspectable request plans constrained by the available financial capabilities."""

import re
from dataclasses import dataclass
from decimal import Decimal

COMPANY_ALIASES = {
    "NVDA": ("NVIDIA", r"\b(nvidia|nvda)\b"),
    "AMD": ("AMD", r"\b(amd|advanced micro devices)\b"),
    "INTC": ("Intel", r"\b(intel|intc)\b"),
    "QCOM": ("Qualcomm", r"\b(qualcomm|qcom)\b"),
}
COMPONENT_ALIASES = {
    "automotive": r"\b(automotive|automobiles?|automotive business)\b",
    "handsets": r"\b(handsets?|mobile handsets?)\b",
    "iot": r"\b(iot|internet of things)\b",
}
METRIC_PATTERNS = {
    "revenue": r"\brevenues?\b",
    "gross_profit": r"\bgross (profit|margin)\b",
    "operating_income": r"\boperating (income|loss|margin)\b",
    "operating_cash_flow": r"\b(?:operating )?cash flows?\b",
    "net_income": r"\b(net income|net loss|earnings)\b",
    "cost_of_revenue": r"\bcost of (revenue|sales)\b",
}


def mentioned_companies(question):
    # Exclusions apply to their clause, including coordinated company lists.
    positive = re.sub(
        r"\b(?:do\s+not\s+include|don't\s+include|exclude|excluding|without|but\s+not)\b[^,.;!?\n]*",
        "",
        question,
        flags=re.I,
    )
    return [
        c
        for c, (_, pattern) in COMPANY_ALIASES.items()
        if re.search(pattern, positive, re.I)
    ]


def mentioned_years(question):
    years = {int(y) for y in re.findall(r"\b(?:FY\s*)?(20\d{2})\b", question, re.I)}
    years.update(2000 + int(y) for y in re.findall(r"\bFY\s*(2\d)\b", question, re.I))
    for start, end in re.findall(r"\bfrom\s+(2\d)\s+to\s+(2\d)\b", question, re.I):
        years.update((2000 + int(start), 2000 + int(end)))
    return years


def requested_metrics(question):
    metrics = [
        m
        for m, pattern in METRIC_PATTERNS.items()
        if re.search(pattern, question, re.I)
    ]
    if re.search(r"\bmargin", question, re.I) and "revenue" not in metrics:
        metrics.insert(0, "revenue")
    return metrics


def earnings_order(question):
    """Identify the requested ordering, rather than incidental display units."""
    if re.search(
        r"\b(?:rank|order|sort)\b[^.;!?]{0,90}\bdollar\s+(?:change|improvement|increase)",
        question,
        re.I,
    ):
        return "dollars"
    if re.search(
        r"\b(?:largest|highest|fastest|most)\s+percentage\s+(?:growth|increase|change)",
        question,
        re.I,
    ):
        return "percentage"
    if re.search(
        r"\bmost\s+dollars\b|\b(?:absolute\s+dollar|dollar)\s+(?:changes?|improvements?|increases?)\b",
        question,
        re.I,
    ):
        return "dollars"
    return "percentage"


@dataclass(frozen=True)
class RequestPlan:
    worker: str
    reason: str
    revenue_component: str | None = None
    revenue_share: bool = False
    earnings_ranking: bool = False
    earnings_order: str = "percentage"
    revenue_components: tuple[str, ...] = ()
    revenue_denominator: str = "consolidated"
    synthesize: bool = False
    scenario: dict | None = None
    required_calculations: tuple[str, ...] = ()


def scenario_request(question):
    """Only explicit user assumptions can authorize scenario arithmetic."""
    if not re.search(
        r"\b(scenario|hypothetical|assum(?:e|ed|ption))\b", question, re.I
    ):
        return None
    rates = re.findall(r"1\s*EUR\s*=\s*(\d+(?:\.\d+)?)\s*USD", question, re.I)
    if len(rates) == 1:
        rate = Decimal(rates[0])
        if rate.is_finite() and 0 < rate <= 1000000:
            return {
                "kind": "currency",
                "usd_per_eur": str(rate),
                "origin": "user",
                "assumption": f"1 EUR = {rate} USD",
            }
    if re.search(r"\b(?:double[ds]?|twice)\b", question, re.I):
        components = [
            name
            for name, pattern in COMPONENT_ALIASES.items()
            if re.search(pattern, question, re.I)
        ]
        if len(components) == 1 and re.search(
            r"(?:every|all)\s+other.*(?:unchanged|stayed)", question, re.I
        ):
            return {
                "kind": "component",
                "component": components[0],
                "factor": "2",
                "origin": "user",
                "assumption": f"{components[0]} revenue doubles; all other revenue unchanged",
            }
    return None


def has_unstructured_revenue_scope(question):
    """A recognized revenue noun does not establish a consolidated observation.

    Reject extra business/geography qualifiers instead of silently dropping them.
    Unknown requests can still be answered from filing passages by Research.
    """
    plain = {
        "total",
        "consolidated",
        "gaap",
        "reported",
        "annual",
        "quarterly",
        "company",
        "the",
        "its",
        "their",
        "was",
        "were",
        "is",
        "are",
        "show",
        "list",
        "compare",
        "much",
        "and",
        "in",
        "of",
        "revenue",
    }
    company_words = {"nvidia", "nvda", "amd", "intel", "intc", "qualcomm", "qcom"}
    plain.update({"only", "quarter", "year", "ytd", "cumulative"})
    for previous in re.findall(r"\b([\w']+)\s+revenues?\b", question, re.I):
        word = previous.lower().removesuffix("'s")
        if word not in plain | company_words and not re.fullmatch(
            r"(?:fy|q)?\d+", word
        ):
            return True
    for qualifier in re.findall(
        r"\brevenues?\b.*?\b(?:from|by|in|excluding|attributable to)\s+([\w']+)",
        question,
        re.I,
    ):
        if not re.fullmatch(
            r"(?:fy)?\d+|the|fiscal|exact|actual|usd|dollars?|millions?|billions?|thousands?|years?|company",
            qualifier,
            re.I,
        ):
            return True
    return False


def plan_request(question):
    from src.buy_side import market_request
    if market_request(question):
        return RequestPlan("buy", "Buy-Side Analyst acquires dated market evidence and delegates arithmetic to Quant")
    if re.search(r"\brisks?\b|risk factors", question, re.I) and re.search(r"\b(chang\w*|add\w*|remov\w*|relocat\w*|mov\w*|compar\w*|reword\w*|unchanged)\b", question, re.I):
        return RequestPlan("risk", "Risk Summary compares complete original risk sections, not search-hit omissions")
    metrics = requested_metrics(question)
    components = [
        name
        for name, pattern in COMPONENT_ALIASES.items()
        if re.search(pattern, question, re.I)
    ]
    revenue = bool(re.search(r"\b(revenues?|sales)\b", question, re.I))
    numerical = bool(
        re.search(
            r"\b(calculate|compute|compare|margins?|growth|percentage|percent|share|proportion|chart|plot)\b",
            question,
            re.I,
        )
    )
    narrative = bool(re.search(r"\b(why|drove|drivers|risk|amend)\b", question, re.I))
    explanation = bool(
        re.search(
            r"\b(why|explain|diversif\w*|interpret\w*|evidence|verify|quote)\b",
            question,
            re.I,
        )
    )
    scenario = scenario_request(question)
    if (
        scenario
        and scenario["kind"] == "currency"
        and metrics
        and not components
        and not (
            revenue
            and has_unstructured_revenue_scope(
                re.sub(r"\bin\s+EUR\b", "", question, flags=re.I)
            )
        )
    ):
        return RequestPlan(
            "analysis_data",
            "Convert a reported USD amount using an explicit user FX assumption",
            scenario=scenario,
            required_calculations=("currency",),
        )
    if scenario and scenario["kind"] == "currency":
        return RequestPlan(
            "research",
            "The requested currency conversion needs a separately verified business/geographic input; do not substitute consolidated revenue",
        )
    if (
        components
        and revenue
        and not re.search(
            r"\b(non.gaap|adjusted|margins?|profit|income|cash flow)\b", question, re.I
        )
    ):
        qct = bool(
            re.search(
                r"\bQCT\s+(?:total\s+)?revenues?\b|\bof\s+(?:total\s+)?QCT\b",
                question,
                re.I,
            )
        )
        calculate = (
            numerical
            or len(components) > 1
            or bool(scenario)
            or bool(re.search(r"\b(compare|how much of|diversif\w*)\b", question, re.I))
        )
        if calculate:
            return RequestPlan(
                "data",
                "Establish requested annual revenue components, then calculate with the requested denominator and assumptions",
                components[0],
                True,
                revenue_components=tuple(components),
                revenue_denominator="qct" if qct else "consolidated",
                synthesize=explanation and scenario is None,
                scenario=scenario,
                required_calculations=(
                    "scenario_scale",
                    "scenario_total",
                    "scenario_share",
                )
                if scenario
                else ("share",),
            )
    cash_conversion = (
        "operating_cash_flow" in metrics
        and "net_income" in metrics
        and bool(re.search(r"\b(divided by|ratio|conversion)\b", question, re.I))
    )
    if cash_conversion:
        return RequestPlan(
            "analysis_data",
            "Compute checked same-period operating-cash-flow/net-income ratios",
            synthesize=explanation,
            required_calculations=("ratio",),
        )
    # Explanations add a filing-evidence step; they do not replace supported inputs.
    if (
        metrics
        and numerical
        and explanation
        and not re.search(
            r"\b(non.gaap|adjusted|eps|ebitda|segment|client|data cent(?:er|re)|gaming)\b",
            question,
            re.I,
        )
        and not components
    ):
        return RequestPlan(
            "analysis_data",
            "Calculate supported figures before synthesizing the filing explanation",
            synthesize=True,
        )
    if re.search(
        r"\b(non.gaap|adjusted|ebitda|eps|earnings per share)\b", question, re.I
    ) or (
        components
        and re.search(r"\b(margins?|profit|income|cash flow)\b", question, re.I)
    ):
        return RequestPlan(
            "research",
            "Requested financial definition is outside the verified consolidated/component schema; retrieve disclosure evidence",
        )
    if re.search(
        r"\bQCT\s+(?:total\s+)?revenues?\b|\bof\s+(?:total\s+)?QCT\b", question, re.I
    ):
        return RequestPlan(
            "research",
            "QCT is a different denominator from consolidated revenue; retrieve the disclosure without substituting company total",
        )
    # A registered business-stream figure is absent from the SEC consolidated store.
    # It must be established from a supported filing table before any arithmetic.
    if revenue and len(components) == 1 and not narrative:
        share = bool(
            re.search(
                r"%|\b(share|percentage|percent|proportion|portion|contribution|how much of)\b|\b(?:revenue|sales).*\bfrom\b",
                question,
                re.I,
            )
        )
        return RequestPlan(
            "data",
            "Revenue component requires filing evidence; Data supplies the compatible total before Research and Quant",
            components[0],
            share,
        )
    unsupported = re.search(
        r"\b(non.gaap|adjusted|ebitda|eps|earnings per share|segment|data cent(?:er|re)|gaming|client|geograph\w*|china|europe)\b",
        question,
        re.I,
    )
    if (
        narrative
        or unsupported
        or len(components) > 1
        or (revenue and has_unstructured_revenue_scope(question))
    ):
        return RequestPlan(
            "research",
            "Requested disclosure/metric is outside the structured financial schema; search the collected filings",
        )
    ranking = (
        "net_income" in metrics
        and bool(re.search(r"\b(growth|grew|increase|change)\b", question, re.I))
        and bool(
            re.search(
                r"\b(largest|highest|most|fastest|rank|which company)\b", question, re.I
            )
        )
    )
    if metrics and (numerical or ranking):
        return RequestPlan(
            "analysis_data",
            "Requested consolidated metrics are available to Data; Quant owns arithmetic and comparisons",
            earnings_ranking=ranking,
            earnings_order=earnings_order(question) if ranking else "percentage",
        )
    quarter_cash = re.search(
        r"\bQ[2-4](?:\b|-).*cash flow|cash flow.*\bQ[2-4](?:\b|-)", question, re.I
    )
    if quarter_cash and not re.search(
        r"\b(ytd|year.to.date|cumulative)\b", question, re.I
    ):
        return RequestPlan(
            "analysis_data",
            "Quarter-only cash flow needs compatible cumulative inputs and Quant derivation",
        )
    if metrics and re.search(
        r"\b(what|how much|figures|amounts|reported|show|list)\b", question, re.I
    ):
        return RequestPlan(
            "data",
            "Requested consolidated metrics are supported by the structured financial store",
        )
    return RequestPlan(
        "research",
        "Search filing evidence for requests outside a supported structured lookup",
    )
