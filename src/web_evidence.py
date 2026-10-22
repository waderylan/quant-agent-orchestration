"""Normalize web evidence without inventing dates or publisher authority."""

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

OFFICIAL = {"nvidia.com", "amd.com", "intel.com", "intc.com", "qualcomm.com", "sec.gov"}
ISSUERS = {
    "NVDA": r"NVIDIA(?: Corporation)?",
    "AMD": r"(?:Advanced Micro Devices(?:,? Inc\.?)?|AMD)",
    "INTC": r"Intel(?: Corporation)?",
    "QCOM": r"Qualcomm(?: Incorporated| Inc\.?)?",
}
MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE = rf"(?:{MONTH}\.?\s+\d{{1,2}},?\s+20\d{{2}}|20\d{{2}}-\d{{2}}-\d{{2}})"
NAVIGATION = re.compile(r"^(?:skip to (?:main )?content|menu|close|search|sign in|log in|subscribe|share(?: this (?:article|release))?|print|back to top|cookie (?:settings|preferences)|accept all cookies|reject all cookies)$", re.I)


def canonical_url(url):
    """Remove tracking keys and fragments while preserving resource parameters."""
    parsed = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid"}]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, urlencode(query), ""))


def clean_text(raw):
    text = str(raw or "")
    text = re.sub(r"!\[[^\]]*\]\((?:[^()\n]|\([^()\n]*\))*\)", "", text)
    text = re.sub(r"data:image/[^\s\"'<>)]*", "", text, flags=re.I)
    if re.search(r"<(?:html|body|article|main|p|div)\b", text, re.I):
        soup = BeautifulSoup(text, "html.parser")
        for node in soup.select("script, style, nav, footer, aside, form, img, [role=navigation]"):
            node.decompose()
        body = soup.find("article") or soup.find("main") or soup
        text = body.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines()]
    headings = [(i, re.sub(r"^#+\s*", "", line).strip().casefold())
                for i, line in enumerate(lines) if re.match(r"^#{1,2}\s+\S", line)]
    if headings:
        title = headings[0][1]
        repeated = [i for i, heading in headings if heading == title]
        # Extraction often repeats the title before and after its navigation.
        prefix = "\n".join(lines[:headings[0][0]])
        links = re.findall(r"\[[^\]]+\]\([^)]*\)", prefix)
        navigation = len(prefix) > 500 and len(links) >= 3 and sum(map(len, links)) > len(prefix) / 2
        start = repeated[-1] if len(repeated) > 1 else headings[0][0] if navigation else 0
        lines = lines[start:]
    cleaned, body_started = [], False
    for line in lines:
        if NAVIGATION.fullmatch(line):
            continue
        link_only = re.fullmatch(r"(?:[-*]\s*)?(?:\[[^\]]+\]\([^)]*\)\s*[|·]?\s*)+", line)
        if link_only and not body_started:
            continue
        if len(line) > 100 and not line.startswith(("#", "[")):
            body_started = True
        cleaned.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned)).strip()


def _date(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).isoformat()
    except (ValueError, TypeError, OverflowError):
        pass
    match = re.search(DATE, value, re.I)
    if not match:
        return None
    candidate = re.sub(r"\bSept\b\.?", "Sep", match[0], flags=re.I).replace(".", "")
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def publication_date(row, text):
    """Return an explicit publication date with the field or page excerpt behind it."""
    def result(value, source, excerpt):
        return {"published_date": value, "date_source": source, "date_excerpt": excerpt}

    for key in ("published_date", "datePublished", "publication_date", "date_published"):
        if parsed := _date(row.get(key)):
            return result(parsed, "tavily" if key == "published_date" else "metadata", str(row[key]))
    # Issuer filing listings explicitly label publication in their title. An
    # article's event date in its headline or a date in its URL is not equivalent.
    title = str(row.get("title") or "")
    filing_title = re.match(rf"^\s*({DATE}|\d{{2}}/\d{{2}}/20\d{{2}})\s*[-–—]\s*(?:10-[KQ](?:/A)?\b|.*(?:Inc\.|Corporation|Incorporated)\s*$)", title, re.I)
    if filing_title and source_tier(row.get("url", ""), "") == "official" and "/sec-filings/" in urlsplit(row.get("url", "")).path:
        value = filing_title[1]
        try:
            parsed = datetime.strptime(value, "%m/%d/%Y").date().isoformat() if "/" in value else _date(value)
        except ValueError:
            parsed = None
        if parsed:
            return result(parsed, "filing_title", title)
    raw = str(text or "")
    soup = BeautifulSoup(raw, "html.parser") if "<" in raw else None
    if soup:
        for meta in soup.find_all("meta"):
            name = str(meta.get("property") or meta.get("name") or meta.get("itemprop") or "").lower()
            value = meta.get("content")
            if name in {"article:published_time", "datepublished", "publication_date", "date", "pubdate"} and (parsed := _date(value)):
                return result(parsed, "metadata", str(meta))
        for time in soup.find_all("time", itemprop="datePublished"):
            if parsed := _date(time.get("datetime") or time.get_text(" ", strip=True)):
                return result(parsed, "metadata", str(time))
        for script in soup.find_all("script", type="application/ld+json"):
            match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', script.get_text())
            if match and (parsed := _date(match[1])):
                return result(parsed, "metadata", match[0])
    page = clean_text(raw)
    labeled = re.search(rf"(?im)^\s*(?:\*\*)?(?:published(?: on| at)?|publication date|date published|datePublished)\s*(?:\*\*)?\s*[:\-]?\s*({DATE}[^\n]*)", page)
    if labeled and (parsed := _date(labeled[1])):
        return result(parsed, "page_label", labeled[0].strip())
    dateline = re.search(rf"(?m)^([A-Z][A-Z .&/-]{{1,60}}(?:,\s*[A-Za-z. ]{{2,15}})?(?:\s+[–—-]\s*|,\s*)(?i:{DATE})\s+[–—-])", page[:2500])
    if dateline and (parsed := _date(dateline[1])):
        return result(parsed, "dateline", dateline[1].strip())
    # A standalone release timestamp near the header is a publication dateline.
    # Dates embedded in article sentences and URL paths are never considered.
    for line in page[:2500].splitlines():
        match = re.fullmatch(rf"\s*({DATE})(?:[,\s]+\d{{1,2}}:\d{{2}}\s*(?:am|pm)?\s*(?:ET|EST|EDT|PT|PST|PDT|UTC|GMT))?\s*", line, re.I)
        if match and (parsed := _date(match[1])):
            return result(parsed, "dateline", line.strip())
        wire = re.match(rf"^[A-Z][A-Z .,&/-]{{1,70}},\s*({DATE})\s*/(?:PRNewswire|Business Wire)/", line, re.I)
        if wire and (parsed := _date(wire[1])):
            return result(parsed, "dateline", wire[0])
        if len(line) > 50 and re.search(r"[.!?](?:\s|$)", line) and not line.startswith(("#", "[")):
            break
    return result(None, None, None)


def source_tier(url, text, company=None):
    """Recognize official hosts and explicitly issuer-authored wire releases."""
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    if any(host == d or host.endswith("." + d) for d in OFFICIAL) or host.endswith(".gov"):
        return "official"
    if not any(host == d or host.endswith("." + d) for d in ("prnewswire.com", "businesswire.com")):
        return "third_party"
    issuer = ISSUERS.get(str(company).upper())
    if not issuer:
        issuer = next((pattern for pattern in ISSUERS.values() if re.fullmatch(pattern, str(company or ""), re.I)), None)
    if not issuer:
        return "third_party"
    page = str(text or "")
    page = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", page)
    if re.search(r"<(?:html|body|article|main|p|div)\b", page, re.I):
        page = BeautifulSoup(page, "html.parser").get_text("\n", strip=True)
    attribution = rf"(?im)^\s*(?:News provided by|SOURCE)\s*:?\s*(?:\n\s*)?{issuer}\s*$"
    return "official" if re.search(attribution, page) else "third_party"
