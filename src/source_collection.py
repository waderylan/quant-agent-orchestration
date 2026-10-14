"""Deterministic source preparation; no models, embeddings, or financial resolver."""
from __future__ import annotations

import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "data/source_inventory.json"
DEFAULT_OUTPUT = ROOT / "data/corpus"
EXTRACTOR_VERSION = "m2-v1"
USER_AGENT = "Rylan Wade CSCI599-HW2 academic source collection"
COMPANIES = {
    "NVDA": ("0001045810", "NVIDIA Corporation"),
    "AMD": ("0000002488", "Advanced Micro Devices"),
    "INTC": ("0000050863", "Intel Corporation"),
    "QCOM": ("0000804328", "QUALCOMM Incorporated"),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_inventory(path: Path) -> list[dict]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    docs = obj["documents"]
    identities = set()
    for doc in docs:
        if not re.fullmatch(r"[a-z0-9-]+", doc["document_id"]):
            raise ValueError("Unsafe document ID")
        if doc["document_id"] in identities:
            raise ValueError("Duplicate logical document; mirrors belong in candidates")
        identities.add(doc["document_id"])
        if doc["company"] not in COMPANIES or doc["cik"] != COMPANIES[doc["company"]][0]:
            raise ValueError("Company/CIK mismatch")
        for field in ("period_end", "source_date", "fiscal_start", "fiscal_end"):
            date.fromisoformat(doc[field])
        if not doc["fiscal_start"] <= doc["period_end"] <= doc["fiscal_end"]:
            raise ValueError("Period outside declared fiscal year")
        if doc["kind"] == "filing":
            if doc["form"] not in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
                raise ValueError("Unsupported filing form")
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", doc["accession"]):
                raise ValueError("Invalid accession")
            if doc["document_id"] != f'{doc["company"].lower()}-{doc["accession"]}':
                raise ValueError("Filing identity must use accession")
            if doc["version"] != ("amendment" if doc["form"].endswith("/A") else "original"):
                raise ValueError("Amendments must remain distinct versions")
        elif doc["kind"] != "earnings_release":
            raise ValueError("Unsupported source kind")
        if not doc["candidates"]:
            raise ValueError("Source needs a retrieval candidate")
        for candidate in doc["candidates"]:
            validate_url(candidate["url"])
            if candidate["format"] not in ("html", "pdf"):
                raise ValueError("Unsupported body format")
    return docs


def validate_url(url: str) -> None:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or ""
    allowed = {"www.sec.gov", "data.sec.gov", "ir.amd.com", "www.intc.com",
               "investor.nvidia.com", "nvidianews.nvidia.com", "investor.qualcomm.com",
               "s201.q4cdn.com", "s204.q4cdn.com", "d18rn0p25nwr6d.cloudfront.net"}
    if parsed.scheme != "https" or host not in allowed or parsed.username or parsed.password:
        raise ValueError("Use a public HTTPS original or official company mirror/CDN")
    if parsed.query:
        raise ValueError("Source URLs must not contain credentials or query parameters")


class Fetcher:
    """Sequential, <=1 request/sec, two attempts for transient failures only."""

    def __init__(self, user_agent: str = USER_AGENT):
        if not user_agent.strip():
            raise ValueError("An identifying User-Agent is required")
        self.user_agent = user_agent
        self.last_request = 0.0

    def get(self, url: str, *, data: bytes | None = None) -> tuple[bytes, dict]:
        validate_url(url)
        for attempt in range(1, 3):
            time.sleep(max(0, 1 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            headers = {"User-Agent": self.user_agent, "Accept": "application/json,text/html,application/pdf"}
            if data is not None:
                headers["Content-Type"] = "application/json"
            request = urllib.request.Request(url, data=data, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    validate_url(response.url)
                    body = response.read(50 * 1024 * 1024 + 1)
                    if len(body) > 50 * 1024 * 1024:
                        raise ValueError("Source exceeds 50 MiB limit")
                    return body, {"requested_url": url, "retrieval_url": response.url,
                                  "retrieved_at": now(), "http_status": response.status,
                                  "content_type": response.headers.get("Content-Type"),
                                  "attempts": attempt, "bytes": len(body), "sha256": digest(body)}
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
                time.sleep(2)
            except (TimeoutError, urllib.error.URLError):
                if attempt == 2:
                    raise
                time.sleep(2)
        raise RuntimeError("Unreachable")


def clean_inline(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def extract_html(body: bytes, kind: str) -> dict:
    soup = BeautifulSoup(body, "html.parser")
    # iXBRL hidden facts, scripts and hidden navigation must not enter readable text.
    for element in list(soup.find_all(True)):
        if element.name is None or element.attrs is None:
            continue
        style = re.sub(r"\s", "", element.get("style", "")).lower()
        if element.name in {"script", "style", "noscript", "ix:hidden", "ix:header", "head"} or \
                "display:none" in style or "visibility:hidden" in style or element.has_attr("hidden"):
            element.decompose()
    container = soup.body or soup
    if kind == "earnings_release":
        # Restrict company news to article content when the publisher supplies it.
        for selector in (".article", "article", ".article-content", ".article-body", ".news-details", ".module-news-details", "main"):
            selected = soup.select_one(selector)
            if selected and len(selected.get_text()) > 2000:
                container = selected
                break
    parts: list[str] = []
    tables: list[dict] = []

    def walk(node):
        if isinstance(node, NavigableString):
            parts.append(str(node))
            return
        if not isinstance(node, Tag):
            return
        if node.name == "table":
            nested = node.find("table")
            # Some SEC documents use tables as layout wrappers; recurse into those.
            if nested:
                for child in node.children:
                    walk(child)
                return
            rows = []
            for tr in node.find_all("tr"):
                cells = [{"text": clean_inline(td.get_text("", strip=False)),
                          "colspan": td.get("colspan", "1"), "rowspan": td.get("rowspan", "1")}
                         for td in tr.find_all(["td", "th"], recursive=False)]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append({"table_index": len(tables) + 1, "rows": rows})
                parts.append("\n" + "\n".join(" | ".join(c["text"] for c in row) for row in rows) + "\n")
            return
        block = node.name in {"div", "p", "section", "h1", "h2", "h3", "h4", "li", "br", "hr"}
        if block:
            parts.append("\n")
        for child in node.children:
            walk(child)
        if block:
            parts.append("\n")

    walk(container)
    lines = [clean_inline(line) for line in "".join(parts).splitlines()]
    text = "\n".join(line for line in lines if line) + "\n"
    return {"text": text, "tables": tables, "pages": [], "table_mode": "HTML cells with original row/column spans; readable rows use |"}


def extract_pdf(body: bytes) -> dict:
    if not body.startswith(b"%PDF-"):
        raise ValueError("Response is not a PDF")
    reader = PdfReader(io.BytesIO(body))
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("PDF requires a password")
    pages, parts, position = [], [], 0
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text(extraction_mode="layout") or ""
        mode = "layout"
        # Layout mode can omit an entire cover drawn through a Form XObject.
        if len(text.strip()) < 100:
            plain = page.extract_text() or ""
            if len(plain.strip()) > len(text.strip()):
                text, mode = plain, "plain_fallback"
        value = f"[PDF page {number}]\n{text}\n"
        pages.append({"page": number, "start": position, "end": position + len(value), "mode": mode})
        position += len(value)
        parts.append(value)
    return {"text": "".join(parts), "pages": pages, "tables": [],
            "blank_text_pages": [p["page"] for p, text in zip(pages, parts) if len(text.strip()) < 30],
            "table_mode": "PDF fixed-width layout text; visual/column semantics require original page inspection"}


ITEM = re.compile(r"(?im)^[ \t]*ITEM\s+(\d+[A-C]?)\s*[.:\-]?\s*([^\n]{0,180})")


def extract_sections(text: str, form: str | None, company: str | None = None) -> dict:
    if not form:
        return {}
    matches = list(ITEM.finditer(text))
    sections = {}
    if company == "INTC":
        # Intel supplies a cross-reference index and custom report order. The index
        # identifies SEC Items but the body uses title headings, not Item numbers.
        patterns = {
            "risk_factors": (r"Risk Factors", r"Other Key Information|Quantitative and Qualitative Disclosures About Market Risk|Controls and Procedures"),
            "mda": (r"Management['’]s Discussion and Analysis(?: \(MD&A\))?", r"Properties|Risk Factors(?: and Other Key Information)?|Quantitative and Qualitative Disclosures About Market Risk"),
        }
        for name, (start_title, end_title) in patterns.items():
            starts = list(re.finditer(r"(?im)^[ \t]*" + start_title + r"[ |\t]*$", text))
            ends = list(re.finditer(r"(?im)^[ \t]*" + "(?:" + end_title + r")[ |\t]*$", text))
            candidates = []
            for match in starts:
                finish = next((m.start() for m in ends if m.start() > match.end()), None)
                if finish and any(match.end() < other.start() < finish for other in starts):
                    # A TOC title can have no page number while the body repeats
                    # it. Only the last title before its closing boundary is body.
                    continue
                if finish and finish-match.start() > (80 if name == "risk_factors" else 500):
                    candidates.append((finish-match.start(), match.start(), finish))
            if candidates:
                _, start, end = max(candidates)
                sections[name] = {"start": start, "end": end, "characters": end-start,
                                  "heading": text[start:text.find("\n", start)].strip(),
                                  "selection": "Intel body title boundaries; SEC cross-reference index retained in full text"}
            else:
                sections[name] = {"status": "missing"}
        return sections
    for name, number, title, minimum in [
        ("risk_factors", "1A", r"Risk\s+Factors", 80),
        ("mda", "7" if form.startswith("10-K") else "2", r"Management.{0,12}Discussion", 500),
    ]:
        candidates = []
        for i, match in enumerate(matches):
            if match[1].upper() != number or not re.search(title, match[2], re.I):
                continue
            # A TOC row often ends in a page number; its next item follows immediately.
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            if end - match.start() >= minimum:
                candidates.append((end - match.start(), match.start(), end))
        if candidates:
            _, start, end = max(candidates)
            sections[name] = {"start": start, "end": end, "characters": end-start,
                              "heading": text[start:text.find("\n", start)].strip(),
                              "selection": "Longest headed span ending at next Item heading; reviewed in M2"}
        else:
            sections[name] = {"status": "not_present" if form.endswith("/A") else "missing"}
    return sections


def flattened(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def validate_extraction(doc: dict, extraction: dict) -> dict:
    text = flattened(extraction["text"].replace("|", " "))
    cover = text[:24000]
    failures = []
    expected_name = {"NVDA": r"NVIDIA\s+CORPORATION", "AMD": r"ADVANCED\s+MICRO\s+DEVICES",
                     "INTC": r"INTEL\s+CORPORATION", "QCOM": r"QUALCOMM\s+(?:Incorporated|Inc\.)"}[doc["company"]]
    company_ok = bool(re.search(expected_name, cover, re.I))
    if not company_ok:
        failures.append("Expected company name absent from cover/article")
    end = date.fromisoformat(doc["period_end"])
    date_pattern = rf'(?:{end.strftime("%B")}|{end.strftime("%b")}\.?)\s+0?{end.day}(?:,\s*|\s+){end.year}'
    if doc["kind"] == "filing":
        form_pattern = re.escape(doc["form"])
        form_ok = bool(re.search(rf"\bFORM\s+{form_pattern}(?![A-Z/])", cover, re.I))
        period_ok = bool(re.search(rf"(?:fiscal\s+year|quarterly\s+period|quarter)\s+ended\s+{date_pattern}", cover, re.I))
        if not form_ok:
            failures.append("Cover form does not match inventory")
        if not period_ok:
            failures.append("Cover reporting period does not match inventory")
        if doc["form"].endswith("/A"):
            if not re.search("explanatory note", text, re.I):
                failures.append("Amendment explanatory note missing")
        else:
            for label, pattern in [("revenue", r"revenues?|net\s+sales"), ("cash_flow", r"cash\s+flows")]:
                if not re.search(pattern, text, re.I):
                    failures.append(f"Financial statement marker missing: {label}")
            for name in ("risk_factors", "mda"):
                if "start" not in extraction["sections"][name]:
                    failures.append(f"Section not extracted: {name}")
    else:
        form_ok = None
        # Release fiscal end and published date both need to survive extraction.
        published = date.fromisoformat(doc["source_date"])
        published_pattern = rf'{published.strftime("%B")}\.?\s+0?{published.day},?\s+{published.year}'
        short_pattern = rf'{published.strftime("%b")}\.?\s+0?{published.day},?\s+{published.year}'
        period_ok = bool(re.search(date_pattern, text, re.I))
        if not period_ok:
            failures.append("Release fiscal-end date missing")
        if not re.search(published_pattern + "|" + short_pattern, text, re.I):
            failures.append("Release publication date missing")
        for label, pattern in [("revenue", r"revenues?|net\s+sales"), ("GAAP", r"GAAP"), ("non_GAAP", r"non[ -]GAAP")]:
            if not re.search(pattern, text, re.I):
                failures.append(f"Release marker missing: {label}")
    if len(text) < (2000 if doc["version"] == "amendment" else 10000):
        failures.append("Body too short for expected source")
    return {"company_name_matches": company_ok, "form_matches": form_ok,
            "period_matches": period_ok, "failures": failures,
            "status": "verified" if not failures else "validation_failed"}


def prepare(doc: dict, body: bytes, body_format: str) -> dict:
    if body_format == "html":
        if not re.search(br"<(?:html|body|!doctype)\b", body[:5000], re.I):
            raise ValueError("Response is not HTML")
        extraction = extract_html(body, doc["kind"])
    else:
        extraction = extract_pdf(body)
    extraction["extractor_version"] = EXTRACTOR_VERSION
    extraction["sections"] = extract_sections(extraction["text"], doc["form"], doc["company"])
    extraction["validation"] = validate_extraction(doc, extraction)
    return extraction


def verify_filing_metadata(doc: dict, submissions: dict) -> None:
    recent = submissions["filings"]["recent"]
    try:
        index = recent["accessionNumber"].index(doc["accession"])
    except ValueError:
        raise ValueError("Accession not in SEC snapshot; older windows need continuation discovery") from None
    expected = {"form": doc["form"], "reportDate": doc["period_end"], "filingDate": doc["source_date"]}
    if int(submissions["cik"]) != int(doc["cik"]):
        raise ValueError("SEC CIK mismatch")
    for key, value in expected.items():
        if recent[key][index] != value:
            raise ValueError(f"SEC metadata mismatch: {key}")
    if not doc["canonical_url"].endswith("/" + recent["primaryDocument"][index]):
        raise ValueError("SEC primary document mismatch")


def store_blob(output: Path, body: bytes, extension: str) -> str:
    path = output / "raw" / f"{digest(body)}.{extension}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if digest(path.read_bytes()) != digest(body):
            raise ValueError("Existing content-addressed blob is corrupt")
    else:
        path.write_bytes(body)
    return path.relative_to(output).as_posix()


def collect(inventory: Path, output: Path, *, refresh=False, offline=False, user_agent=USER_AGENT) -> dict:
    if refresh and offline:
        raise ValueError("Refresh and offline preparation are mutually exclusive")
    docs = load_inventory(inventory)
    output.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(user_agent)
    previous_path = output / "manifest.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {"documents": []}
    previous_docs = {d["document_id"]: d for d in previous["documents"]}
    metadata = {}
    metadata_records = {}
    for ticker in sorted({d["company"] for d in docs if d["kind"] == "filing"}):
        cik = COMPANIES[ticker][0]
        cache = output / "metadata" / f"{ticker}.json"
        try:
            if cache.exists() and not refresh:
                record = json.loads(cache.read_text(encoding="utf-8"))
                raw = output / record["path"]
                if digest(raw.read_bytes()) != record["sha256"]:
                    raise ValueError("SEC snapshot checksum mismatch")
                body = raw.read_bytes()
            else:
                if offline:
                    raise ValueError("No cached SEC snapshot for offline preparation")
                body, record = fetcher.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
                record["path"] = store_blob(output, body, "json")
                write_json(cache, record)
            metadata[ticker] = json.loads(body)
            metadata_records[ticker] = record
        except Exception as exc:
            metadata[ticker] = {"error": f"{type(exc).__name__}: {exc}"}
    records = []
    for doc in docs:
        record = dict(doc, status="failed", attempts=[], checked_at=now())
        old = previous_docs.get(doc["document_id"])
        try:
            if doc["kind"] == "filing":
                if "error" in metadata[doc["company"]]:
                    raise ValueError(metadata[doc["company"]]["error"])
                verify_filing_metadata(doc, metadata[doc["company"]])
                record["sec_metadata"] = metadata_records[doc["company"]]
            cached = False
            if old and (old.get("status") == "verified" or offline) and not refresh and all(old.get(k) == v for k, v in doc.items()):
                old_body = old.get("body") or next((a["body"] for a in old.get("attempts", []) if "body" in a), None)
                path = output / old_body["path"] if old_body else output / "missing-body"
                if old_body and path.exists() and digest(path.read_bytes()) == old_body["sha256"]:
                    body = path.read_bytes()
                    body_record = old_body
                    body_format = body_record["format"]
                    cached = True
            if cached:
                extraction = prepare(doc, body, body_format)
            else:
                if offline:
                    raise ValueError("No intact cached body for offline preparation")
                extraction = None
                for candidate in doc["candidates"]:
                    try:
                        body, body_record = fetcher.get(candidate["url"])
                        body_format = candidate["format"]
                        body_record.update(path=store_blob(output, body, body_format), format=body_format)
                        attempt_record = {"url": candidate["url"], "body": body_record}
                        record["attempts"].append(attempt_record)
                        extraction = prepare(doc, body, body_format)
                        attempt_record["validation"] = extraction["validation"]
                        if extraction["validation"]["status"] == "verified":
                            break
                    except Exception as exc:
                        record["attempts"].append({"url": candidate["url"], "error": f"{type(exc).__name__}: {exc}"})
                if extraction is None:
                    raise ValueError("No candidate produced a readable body")
            # Prepared outputs keyed by logical ID + source hash; raw versions remain immutable.
            base = output / "prepared" / doc["document_id"] / EXTRACTOR_VERSION / body_record["sha256"]
            text_path = base.with_suffix(".txt")
            json_path = base.with_suffix(".json")
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(extraction["text"], encoding="utf-8", newline="\n")
            details = {k: v for k, v in extraction.items() if k != "text"}
            details.update(text_sha256=digest(text_path.read_bytes()), text_characters=len(extraction["text"]))
            write_json(json_path, details)
            record.update(status=extraction["validation"]["status"], body=body_record,
                          extraction={"text_path": text_path.relative_to(output).as_posix(),
                                      "details_path": json_path.relative_to(output).as_posix(), **details},
                          cache_used=cached)
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        records.append(record)
        print(f'{doc["document_id"]}: {record["status"]}', flush=True)
    result = {"schema_version": 1, "completed_at": now(), "inventory_sha256": digest(inventory.read_bytes()),
              "extractor_version": EXTRACTOR_VERSION,
              "summary": {"targets": len(docs), "verified": sum(d["status"] == "verified" for d in records)},
              "documents": records}
    result["summary"]["gaps"] = len(docs) - result["summary"]["verified"]
    # Every run keeps a provenance history, including failed refreshes.
    run_name = result["completed_at"].replace(":", "-")
    write_json(output / "runs" / f"{run_name}.json", result)
    write_json(previous_path, result)
    return result


def verify_local(inventory: Path, output: Path) -> dict:
    docs = load_inventory(inventory)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    records = {d["document_id"]: d for d in manifest["documents"]}
    failures = []
    if manifest["inventory_sha256"] != digest(inventory.read_bytes()):
        failures.append("Inventory differs from collected snapshot")
    if set(records) != {d["document_id"] for d in docs}:
        failures.append("Manifest identities differ from inventory")
    for doc in docs:
        record = records.get(doc["document_id"], {})
        try:
            if record.get("status") != "verified":
                raise ValueError("Source is not verified")
            raw = (output / record["body"]["path"]).read_bytes()
            if digest(raw) != record["body"]["sha256"]:
                raise ValueError("Raw checksum mismatch")
            prepared = prepare(doc, raw, record["body"]["format"])
            text = (output / record["extraction"]["text_path"]).read_bytes()
            if digest(text) != record["extraction"]["text_sha256"] or text.decode("utf-8") != prepared["text"]:
                raise ValueError("Prepared text differs from original extraction")
            details = json.loads((output / record["extraction"]["details_path"]).read_text(encoding="utf-8"))
            for key in ("sections", "pages", "tables", "validation", "extractor_version"):
                if details[key] != prepared[key] or record["extraction"][key] != prepared[key]:
                    raise ValueError(f"Prepared details mismatch: {key}")
            if prepared["validation"]["status"] != "verified":
                raise ValueError(str(prepared["validation"]["failures"]))
            if doc["kind"] == "filing":
                snap = record["sec_metadata"]
                body = (output / snap["path"]).read_bytes()
                if digest(body) != snap["sha256"]:
                    raise ValueError("SEC metadata checksum mismatch")
                verify_filing_metadata(doc, json.loads(body))
        except Exception as exc:
            failures.append(f'{doc["document_id"]}: {exc}')
    return {"targets": len(docs), "failures": failures, "passed": not failures}


def inspection(output: Path, document_id: str, section: str | None = None) -> str:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    record = next((d for d in manifest["documents"] if d["document_id"] == document_id), None)
    if not record or record["status"] != "verified":
        raise ValueError("Document is absent or unverified")
    text = (output / record["extraction"]["text_path"]).read_text(encoding="utf-8")
    header = f'{document_id}\nCanonical: {record["canonical_url"]}\nRetrieved: {record["body"]["retrieval_url"]}\nOriginal: {output / record["body"]["path"]}\nText: {output / record["extraction"]["text_path"]}\n'
    if section:
        span = record["extraction"]["sections"].get(section, {})
        if "start" not in span:
            raise ValueError(f"Section {section} is not present")
        text = text[span["start"]:span["end"]]
        header += f'Characters: {span["start"]}..{span["end"]}\n'
    return header + "\n" + text
