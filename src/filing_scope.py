"""Honor explicit annual/interim scope before semantic ranking."""

import re
from datetime import date


def filing_scope(question, documents, companies, years, *, form=None, quarter=None):
    """Narrow explicit source instructions; ambiguous/mixed requests stay broad."""
    explicit_annual = bool(re.search(r"\b10[ -]?K\b", question, re.I))
    annual = explicit_annual or bool(re.search(r"\bannual\s+(?:filings?|reports?)\b", question, re.I))
    interim = bool(re.search(r"\b10[ -]?Q\b", question, re.I))
    amendment = bool(re.search(r"\bamend\w*\b|10[ -]?K/A", question, re.I))
    found = set(map(int, re.findall(r"\bQ([1-4])\b", question, re.I)))
    for number, word in enumerate(("first", "second", "third", "fourth"), 1):
        if re.search(rf"\b{word}[ -]quarter\b", question, re.I):
            found.add(number)
    if quarter is None and len(found) == 1:
        quarter = found.pop()
    if form is None:
        if annual and not interim and not amendment and (explicit_annual or quarter is None):
            form = "10-K"
        elif (interim or quarter in (1, 2, 3)) and not annual and not amendment:
            form = "10-Q"
    options = {"form": form} if form else {}
    if form == "10-Q" and quarter is not None:
        identities = []
        for identity, document in documents.items():
            if (document.get("company") not in companies or document.get("fiscal_year") not in years
                    or document.get("form") != "10-Q"):
                continue
            try:
                elapsed = (date.fromisoformat(document["period_end"]) - date.fromisoformat(document["fiscal_start"])).days + 1
            except (KeyError, ValueError, TypeError):
                continue
            if abs(elapsed - quarter * 91) <= 20:
                identities.append(identity)
        options["document_ids"] = identities
    elif amendment and not form:
        options["document_ids"] = [identity for identity, doc in documents.items()
                                   if doc.get("company") in companies and doc.get("fiscal_year") in years
                                   and doc.get("form") in ("10-K", "10-K/A")]
    return options
