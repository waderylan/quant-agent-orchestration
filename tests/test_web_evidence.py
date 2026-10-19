"""Web normalization preserves article evidence and publication provenance."""

import pytest

from src.web_evidence import canonical_url, clean_text, publication_date, source_tier


def test_cleanup_preserves_article_beyond_navigation_and_base64():
    raw = "# Qualcomm acquisition\n" + "[Products](https://example.com/products)\n" * 200
    raw += "![logo](data:image/png;base64," + "x" * 7000 + ")\n"
    raw += "# Qualcomm acquisition\nJul 29, 2026, 09:01 ET\nQualcomm completed the acquisition.\n"
    cleaned = clean_text(raw)
    assert "completed the acquisition" in cleaned[:6000]
    assert "base64" not in cleaned and "Products" not in cleaned
    assert publication_date({}, cleaned) == {"published_date": "2026-07-29", "date_source": "dateline", "date_excerpt": "Jul 29, 2026, 09:01 ET"}


def test_html_uses_main_body_but_preserves_publication_metadata():
    raw = '<html><head><meta property="article:published_time" content="2026-07-29T09:01:00-04:00"></head><body><nav>'
    raw += "Navigation " * 1000 + '</nav><main><h1>Acquisition</h1><p>Qualcomm completed the acquisition.</p></main><footer>Cookies</footer></body></html>'
    assert clean_text(raw) == "Acquisition\nQualcomm completed the acquisition."
    result = publication_date({}, raw)
    assert result["published_date"] == "2026-07-29T09:01:00-04:00"
    assert result["date_source"] == "metadata" and "article:published_time" in result["date_excerpt"]


def test_flat_link_navigation_precedes_single_article_heading():
    raw = "Markets " + "[Product menu](https://example.com/products) " * 150
    raw += "\n## Qualcomm completes transaction\nDec 18, 2025 5:20am EST\nQualcomm completed the transaction."
    assert raw.index("Qualcomm completed") > 6000
    cleaned = clean_text(raw)
    assert cleaned.index("Qualcomm completed") < 6000 and "Product menu" not in cleaned
    assert publication_date({}, raw)["published_date"] == "2025-12-18"


@pytest.mark.parametrize("text, expected, source", [
    ("# Report\nDec 18, 2025 5:20am EST\nCompletion news.", "2025-12-18", "dateline"),
    ("Published: September 21, 2026\nReport.", "2026-09-21", "page_label"),
    ('<script type="application/ld+json">{"datePublished":"2026-09-21"}</script><p>Report.</p>', "2026-09-21T00:00:00", "metadata"),
    ("SAN DIEGO, July 29, 2026 /PRNewswire/ -- Qualcomm announces a deal.", "2026-07-29", "dateline"),
    ("AI demand is growing.\nSAN FRANCISCO – July 23, 2026 – AMD today launched infrastructure.", "2026-07-23", "dateline"),
    ("SANTA CLARA, Calif. – July 22, 2026 – AMD announced a partnership.", "2026-07-22", "dateline"),
    ("SANTA CLARA, Calif., Aug. 5, 2026 – AMD announced a solution.", "2026-08-05", "dateline"),
    ("Qualcomm agreed to buy a company on July 29, 2026.\nRetrieved October 19, 2026.", None, None),
    ("Qualcomm completed a major transaction after a long regulatory review.\nJuly 29, 2026\nThe deal was originally announced then.", None, None),
])
def test_only_explicit_publication_evidence_is_accepted(text, expected, source):
    result = publication_date({"url": "https://example.com/2026/10/19/story"}, text)
    assert result["published_date"] == expected and result["date_source"] == source
    assert result["date_excerpt"] is None or result["date_excerpt"] in text


def test_tavily_date_precedence_and_invalid_date_fallback():
    result = publication_date({"published_date": "Wed, 23 Sep 2026 22:20:27 GMT"}, "Published: July 29, 2026")
    assert result["published_date"] == "2026-09-23T22:20:27+00:00" and result["date_source"] == "tavily"
    assert publication_date({"published_date": "2026-02-31"}, "No date.")["published_date"] is None


def test_tracking_dedup_preserves_resource_identity():
    assert canonical_url("https://Example.com/release?id=42&utm_source=mail&fbclid=abc#top") == "https://example.com/release?id=42"
    assert canonical_url("https://example.com/release?id=43") != canonical_url("https://example.com/release?id=42")


@pytest.mark.parametrize("url, text, company, expected", [
    ("https://investor.qualcomm.com/news", "", "QCOM", "official"),
    ("https://qualcomm.com.attacker.test/news", "", "QCOM", "third_party"),
    ("https://www.prnewswire.com/release", "News provided by\nQualcomm Incorporated\nJul 29, 2026", "QCOM", "official"),
    ("https://www.prnewswire.com/release", "News provided by\n[Qualcomm Incorporated](https://qualcomm.com)\nJul 29, 2026", "QCOM", "official"),
    ("https://www.businesswire.com/release", "SOURCE: Intel Corporation", "INTC", "official"),
    ("https://www.prnewswire.com/release", "News provided by Qualcomm Fan Club", "QCOM", "third_party"),
    ("https://www.prnewswire.com/release", "A journalist said News provided by Qualcomm Incorporated.", "QCOM", "third_party"),
    ("https://www.prnewswire.com/release", "News provided by Qualcomm Incorporated", "AMD", "third_party"),
    ("https://news.example/release", "News provided by Qualcomm Incorporated", "QCOM", "third_party"),
])
def test_primary_syndication_requires_issuer_attribution(url, text, company, expected):
    assert source_tier(url, text, company) == expected
