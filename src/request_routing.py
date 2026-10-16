"""Inspectable request plans constrained by the available financial capabilities."""

import re
from dataclasses import dataclass

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
    return [
        c
        for c, (_, pattern) in COMPANY_ALIASES.items()
        if re.search(pattern, question, re.I)
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


@dataclass(frozen=True)
class RequestPlan:
    worker: str
    reason: str
    revenue_component: str | None = None
    revenue_share: bool = False
    earnings_ranking: bool = False


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
