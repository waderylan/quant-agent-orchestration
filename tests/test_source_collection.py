import copy
import contextlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfWriter

from src.source_collection import (DEFAULT_INVENTORY, Fetcher, extract_html,
                                   extract_pdf, extract_sections, load_inventory,
                                   collect, digest, now, prepare, validate_url,
                                   verify_filing_metadata, verify_local)


class ExtractionTests(unittest.TestCase):
    def test_hidden_inline_facts_do_not_contaminate_rows(self):
        body = b'''<html><body><ix:hidden><div>9999 fake revenue</div></ix:hidden>
        <script>wrong period</script><div style="display: none"><span>hidden</span></div>
        <p>Revenue increased <b>because</b> of demand.</p><table>
        <tr><th rowspan="2">Revenue</th><th colspan="2">Year</th></tr>
        <tr><td>(2,214)</td><td>53,101</td></tr></table></body></html>'''
        result = extract_html(body, "filing")
        self.assertNotIn("9999", result["text"])
        self.assertNotIn("wrong period", result["text"])
        self.assertNotIn("hidden", result["text"])
        self.assertIn("Revenue increased because of demand.", result["text"])
        self.assertIn("(2,214) | 53,101", result["text"])
        self.assertEqual(result["tables"][0]["rows"][0][1]["colspan"], "2")
        self.assertEqual(result["tables"][0]["rows"][0][0]["rowspan"], "2")

    def test_toc_and_annual_quarter_boundaries(self):
        annual = "Item 1A. Risk Factors 12\nItem 1B. Unresolved Staff Comments 30\n"
        annual += "Item 1A. Risk Factors\n" + "actual annual risk. " * 100
        annual += "\nItem 1B. Unresolved Staff Comments\nNone\nItem 7. Management's Discussion\n" + "actual MD&A. " * 100
        annual += "\nItem 7A. Market Risk\nnext section"
        sections = extract_sections(annual, "10-K")
        self.assertIn("actual annual risk", annual[sections["risk_factors"]["start"]:sections["risk_factors"]["end"]])
        self.assertEqual(annual[sections["risk_factors"]["end"]:][:7], "Item 1B")
        self.assertEqual(annual[sections["mda"]["end"]:][:7], "Item 7A")
        quarterly = "Item 2. Management's Discussion\n" + "MD&A. " * 100 + "\nItem 3. Market Risk\n"
        quarterly += "Item 1A. Risk Factors\n" + "No material changes; see prior annual filing. " * 2 + "\nItem 2. Unregistered Sales\n"
        sections = extract_sections(quarterly, "10-Q")
        self.assertEqual(quarterly[sections["mda"]["end"]:][:6], "Item 3")
        risk = quarterly[sections["risk_factors"]["start"]:sections["risk_factors"]["end"]]
        self.assertIn("see prior annual filing", risk)
        self.assertNotIn("Unregistered Sales", risk)

    def test_wrong_company_or_period_cannot_pass_http_success(self):
        doc = copy.deepcopy(load_inventory(DEFAULT_INVENTORY)[8])
        def html(name, period):
            return (f'<html><body>FORM 10-Q {name} For the quarterly period ended {period}\n'
                    "ITEM 2. Management's Discussion\n" + "Revenue and cash flows. " * 500 +
                    "\nITEM 3. Market Risk\nITEM 1A. Risk Factors\n" + "Risk factors. " * 50 +
                    "\nITEM 2. Unregistered Sales</body></html>").encode()
        self.assertEqual(prepare(doc, html("Advanced Micro Devices", "March 30, 2024"), "html")["validation"]["status"], "verified")
        result = prepare(doc, html("Intel Corporation", "March 30, 2024"), "html")
        self.assertFalse(result["validation"]["company_name_matches"])
        result = prepare(doc, html("Advanced Micro Devices", "June 29, 2024"), "html")
        self.assertFalse(result["validation"]["period_matches"])

    def test_amendment_does_not_supply_replacement_risks(self):
        text = "FORM 10-K/A\nEXPLANATORY NOTE\nItem 7. Management's Discussion\n" + "Corrected MD&A. " * 100
        result = extract_sections(text, "10-K/A")
        self.assertEqual(result["risk_factors"]["status"], "not_present")
        self.assertIn("start", result["mda"])

    def test_intel_cross_reference_index_is_not_the_risk_body(self):
        text = "Management's Discussion and Analysis | |\nOperating Segment Results | | 21\nRisk Factors | | 37\n"
        text += "Business\n" + "Business description. " * 100
        text += "\nManagement's Discussion and Analysis |\n" + "Real MD&A. " * 100
        text += "\nRisk Factors and Other Key Information |\nRisk Factors\n" + "Actual risk. " * 100
        text += "\nQuantitative and Qualitative Disclosures About Market Risk\nDifferent content\n"
        text += "Item 1A. | Risk Factors | Page 39\nItem 2. | Unregistered Sales | Page 40\n"
        result = extract_sections(text, "10-Q", "INTC")
        risk = text[result["risk_factors"]["start"]:result["risk_factors"]["end"]]
        self.assertIn("Actual risk", risk)
        self.assertNotIn("Page 39", risk)
        self.assertNotIn("Different content", risk)
        mda = text[result["mda"]["start"]:result["mda"]["end"]]
        self.assertIn("Real MD&A", mda)
        self.assertNotIn("Operating Segment Results", mda)
        self.assertNotIn("Business description", mda)

    def test_pdf_signature_and_password_handling(self):
        with self.assertRaisesRegex(ValueError, "not a PDF"):
            extract_pdf(b"<html>challenge</html>")
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.encrypt("private-password")
        stream = io.BytesIO()
        writer.write(stream)
        with self.assertRaisesRegex(ValueError, "requires a password"):
            extract_pdf(stream.getvalue())

    def test_news_title_date_and_table_dates_survive_article_selection(self):
        doc = next(d for d in load_inventory(DEFAULT_INVENTORY) if d["document_id"] == "nvda-fy2025-earnings")
        body = ("<html><body>Unrelated navigation<div class='article'><h1>NVIDIA Corporation financial results</h1>"
                "<div>February 26, 2025</div><div class='article-body'>Quarter ended January 26,2025. "
                + "Revenue GAAP and non-GAAP financial results. " * 300 + "</div></div></body></html>").encode()
        result = prepare(doc, body, "html")
        self.assertEqual(result["validation"]["status"], "verified")
        self.assertNotIn("Unrelated navigation", result["text"])


class ProvenanceTests(unittest.TestCase):
    @patch("src.source_collection.Fetcher.get")
    def test_refresh_preserves_raw_versions_and_failed_run_and_detects_tampering(self, fetch):
        doc = next(d for d in load_inventory(DEFAULT_INVENTORY) if d["document_id"] == "nvda-fy2025-earnings")
        def response(suffix):
            body = ("<html><body>NVIDIA Corporation February 26, 2025. Quarter ended January 26,2025. "
                    + "Revenue GAAP non-GAAP. " * 600 + suffix + "</body></html>").encode()
            return body, {"requested_url": doc["canonical_url"], "retrieval_url": doc["canonical_url"],
                          "retrieved_at": now(), "http_status": 200, "content_type": "text/html",
                          "attempts": 1, "bytes": len(body), "sha256": digest(body)}
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            inventory = Path(tmp) / "inventory.json"
            inventory.write_text(json.dumps({"documents": [doc]}))
            output = Path(tmp) / "corpus"
            fetch.return_value = response("first version")
            first = collect(inventory, output)["documents"][0]
            self.assertTrue(verify_local(inventory, output)["passed"])
            (output / first["extraction"]["text_path"]).write_text("corrupted")
            self.assertIn("Prepared text differs", verify_local(inventory, output)["failures"][0])
            fetch.return_value = response("revised version")
            second = collect(inventory, output, refresh=True)["documents"][0]
            self.assertNotEqual(first["body"]["sha256"], second["body"]["sha256"])
            self.assertEqual(digest((output / first["body"]["path"]).read_bytes()), first["body"]["sha256"])
            fetch.side_effect = urllib.error.URLError("Unavailable")
            failed = collect(inventory, output, refresh=True)
            self.assertEqual(failed["summary"]["gaps"], 1)
            self.assertTrue((output / second["body"]["path"]).exists())
            self.assertEqual(len(list((output / "runs").glob("*.json"))), 3)

    def test_mirrors_and_amendments_have_distinct_correct_identities(self):
        docs = load_inventory(DEFAULT_INVENTORY)
        self.assertEqual(len(docs), 41)
        self.assertEqual(sum(d["form"] == "10-K" for d in docs), 8)
        self.assertEqual(sum(d["form"] == "10-Q" for d in docs), 24)
        amendment = next(d for d in docs if d["version"] == "amendment")
        self.assertNotEqual(amendment["document_id"], amendment["amends_document_id"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.json"
            path.write_text(json.dumps({"documents": [docs[0], docs[0]]}))
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_inventory(path)

    def test_sec_metadata_must_match_accession_form_date_and_primary(self):
        doc = load_inventory(DEFAULT_INVENTORY)[0]
        snapshot = {"cik": int(doc["cik"]), "filings": {"recent": {
            "accessionNumber": [doc["accession"]], "form": [doc["form"]],
            "reportDate": [doc["period_end"]], "filingDate": [doc["source_date"]],
            "primaryDocument": [doc["canonical_url"].rsplit("/", 1)[1]]}}}
        verify_filing_metadata(doc, snapshot)
        snapshot["filings"]["recent"]["form"][0] = "10-K/A"
        with self.assertRaisesRegex(ValueError, "form"):
            verify_filing_metadata(doc, snapshot)

    def test_nonofficial_urls_and_query_credentials_rejected(self):
        for url in ("http://data.sec.gov/submissions/a.json", "https://evil.test/document.pdf",
                    "https://data.sec.gov/submissions/a.json?token=secret"):
            with self.assertRaises(ValueError):
                validate_url(url)

    @patch("src.source_collection.time.sleep")
    @patch("src.source_collection.urllib.request.urlopen")
    def test_forbidden_has_no_retry_transient_failure_is_bounded(self, urlopen, sleep):
        url = "https://data.sec.gov/submissions/test.json"
        urlopen.side_effect = urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        with self.assertRaises(urllib.error.HTTPError):
            Fetcher().get(url)
        self.assertEqual(urlopen.call_count, 1)
        urlopen.reset_mock()
        urlopen.side_effect = urllib.error.HTTPError(url, 503, "Unavailable", {}, None)
        with self.assertRaises(urllib.error.HTTPError):
            Fetcher().get(url)
        self.assertEqual(urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
