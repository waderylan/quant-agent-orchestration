"""Explicit future inventories; discovery never changes the approved M2 inventory."""
import json
import re
from pathlib import Path

from src.source_collection import COMPANIES, DEFAULT_INVENTORY, Fetcher, now, validate_url, write_json


def official_reports(company: str, fiscal_year: int, fetcher: Fetcher) -> tuple[list, str]:
    host = "investor.nvidia.com" if company == "NVDA" else "investor.qualcomm.com"
    page = ("/financial-info/financial-reports/default.aspx" if company == "NVDA" else
            "/financial-info-sec-filings/historical-financial-results/default.aspx")
    body, _ = fetcher.get(f"https://{host}{page}")
    html = body.decode("utf-8")
    dto = {}
    for key in ("ViewType", "ViewDate", "RevisionNumber", "LanguageId", "Signature"):
        match = re.search(r"function Get" + key + r"\(\)\s*\{+\s*return (.*?);", html)
        if not match:
            raise ValueError("Official listing API shape changed; provide reviewed URLs in the inventory")
        value = match[1].strip().strip("'\"")
        dto[key] = int(value) if value.isdigit() else value
    dto.update(ItemCount=-1, StartIndex=0, TagList=[], IncludeTags=True)
    url = f"https://{host}/Services/FinancialReportService.svc/GetFinancialReportList"
    payload = dict(serviceDto=dto, reportSubTypeList=[], reportSubType=[], reportTypes="", excludeSelection=1, year=fiscal_year)
    body, _ = fetcher.get(url, data=json.dumps(payload).encode())
    return json.loads(body)["GetFinancialReportListResult"], url


def discover(company: str, fiscal_year: int, start: str, end: str, destination: Path,
             user_agent: str) -> dict:
    if destination.resolve() == DEFAULT_INVENTORY.resolve() or destination.exists():
        raise ValueError("Discovery writes a NEW inventory; use a new path to preserve existing scope")
    from datetime import date
    date.fromisoformat(start)
    date.fromisoformat(end)
    if start > end:
        raise ValueError("Fiscal start must precede end")
    cik, name = COMPANIES[company]
    fetcher = Fetcher(user_agent)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    body, sec_record = fetcher.get(url)
    submissions = json.loads(body)
    recent = submissions["filings"]["recent"]
    # Historical continuation files extend coverage when the recent array is insufficient.
    if recent["reportDate"] and min(d for d in recent["reportDate"] if d) > start:
        for continuation in submissions["filings"].get("files", []):
            body, _ = fetcher.get("https://data.sec.gov/submissions/" + continuation["name"])
            older = json.loads(body)
            for key in recent:
                recent[key].extend(older[key])
    selected = [i for i, form in enumerate(recent["form"])
                if form in ("10-K", "10-Q", "10-K/A", "10-Q/A")
                and start <= recent["reportDate"][i] <= end]
    originals = sorted((i for i in selected if not recent["form"][i].endswith("/A")),
                       key=lambda i: recent["reportDate"][i])
    reports, listing_url = official_reports(company, fiscal_year, fetcher) if company in ("NVDA", "QCOM") else ([], "")
    docs = []
    for i in sorted(selected, key=lambda i: (recent["reportDate"][i], recent["accessionNumber"][i])):
        form, accession, primary = recent["form"][i], recent["accessionNumber"][i], recent["primaryDocument"][i]
        period_end = recent["reportDate"][i]
        canonical = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}/{primary}'
        if company in ("AMD", "INTC"):
            prefix = "https://ir.amd.com/financial-information/sec-filings/content" if company == "AMD" else "https://www.intc.com/filings-reports/all-sec-filings/content"
            candidates = [{"url": f"{prefix}/{accession}/{primary}", "format": "html", "discovered_from": url}]
        else:
            ordinal = next((n for n, index in enumerate(originals) if recent["reportDate"][index] == period_end), None)
            subtype = "Fourth Quarter" if form.startswith("10-K") else ["First Quarter", "Second Quarter", "Third Quarter"][ordinal] if ordinal is not None and ordinal < 3 else None
            report = next((r for r in reports if r["ReportSubType"] == subtype), {})
            candidates = [{"url": d["DocumentPath"], "format": "pdf", "discovered_from": listing_url,
                           "discovery_fiscal_year": fiscal_year, "discovery_report_type": subtype}
                          for d in report.get("Documents", []) if d["DocumentTitle"] == form and d["DocumentPath"].lower().endswith(".pdf")]
            if not candidates:
                # A missing official mirror remains explicit and may fail collection; never invent a URL.
                candidates = [{"url": canonical, "format": "html", "discovered_from": url}]
        amended = form.endswith("/A")
        parent = next((index for index in originals if recent["reportDate"][index] == period_end and recent["form"][index] == form.removesuffix("/A")), None)
        prior = [index for index, f in enumerate(recent["form"]) if f == "10-K" and recent["reportDate"][index] < period_end]
        parent_annual = max(prior, key=lambda index: recent["reportDate"][index]) if prior else None
        docs.append(dict(document_id=f"{company.lower()}-{accession}", company=company, company_name=name,
                         cik=cik, kind="filing", form=form, period_end=period_end, fiscal_year=fiscal_year,
                         fiscal_start=start, fiscal_end=end, source_date=recent["filingDate"][i], accession=accession,
                         canonical_url=canonical, version="amendment" if amended else "original",
                         amends_document_id=f'{company.lower()}-{recent["accessionNumber"][parent]}' if amended and parent is not None else None,
                         prior_annual_document_id=f'{company.lower()}-{recent["accessionNumber"][parent_annual]}' if form.startswith("10-Q") and parent_annual is not None else None,
                         risk_context_note="Quarterly updates are not full annual risk inventories; prior annual may be outside this inventory." if form.startswith("10-Q") else None,
                         candidates=candidates))
    if not docs:
        raise ValueError("No supported SEC filings found in the declared fiscal window")
    result = {"schema_version": 1, "scope": f"Explicit future inventory: {company} FY{fiscal_year}; {start} through {end}",
              "discovered_at": now(), "sec_discovery": sec_record, "documents": docs}
    write_json(destination, result)
    return result


def add_release(inventory: Path, company: str, fiscal_year: int, start: str, end: str,
                published: str, url: str, body_format: str) -> None:
    if inventory.resolve() == DEFAULT_INVENTORY.resolve():
        raise ValueError("Keep approved M2 inventory fixed; use a separate future inventory")
    validate_url(url)
    obj = json.loads(inventory.read_text(encoding="utf-8"))
    cik, name = COMPANIES[company]
    identity = f"{company.lower()}-fy{fiscal_year}-earnings"
    if any(d["document_id"] == identity for d in obj["documents"]):
        raise ValueError("Release already in inventory; add mirrors to its candidates")
    obj["documents"].append(dict(document_id=identity, company=company, company_name=name, cik=cik,
                                 kind="earnings_release", form=None, period_end=end, fiscal_year=fiscal_year,
                                 fiscal_start=start, fiscal_end=end, source_date=published, accession=None,
                                 canonical_url=url, version="original", amends_document_id=None,
                                 candidates=[{"url": url, "format": body_format, "discovered_from": "Explicit CLI source URL"}]))
    from src.source_collection import load_inventory
    # Validate a temporary candidate before updating the existing inventory.
    temporary = inventory.with_suffix(".candidate.json")
    try:
        write_json(temporary, obj)
        load_inventory(temporary)
        write_json(inventory, obj)
    finally:
        temporary.unlink(missing_ok=True)
