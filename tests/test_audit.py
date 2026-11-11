import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from storefront_audit import audit_html
from storefront_audit.cli import MAX_BYTES, _read_html, main


CLEAN = """<!doctype html><html lang="en"><head><title>Demo shop</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script type="module" src="app.js"></script></head><body><main><h1>Catalog</h1>
<img src="item.jpg" alt="Blue mug" width="400" height="300">
<label for="quantity">Quantity</label><input id="quantity"></main></body></html>"""


class AuditTests(unittest.TestCase):
    def test_clean_document_has_no_findings(self):
        self.assertEqual(audit_html(CLEAN), [])

    def test_document_metadata_and_landmark_findings(self):
        rules = {finding.rule for finding in audit_html("<html><head></head><body></body></html>")}
        self.assertEqual(rules, {"document-language", "document-title", "main-landmark", "viewport"})

    def test_image_alt_and_dimensions_are_distinct(self):
        findings = audit_html(CLEAN.replace('alt="Blue mug" width="400" height="300"', ""))
        self.assertEqual([item.rule for item in findings], ["image-alt", "image-dimensions"])

    def test_duplicate_ids_report_original_line(self):
        findings = audit_html(CLEAN.replace("</main>", '\n<div id="quantity"></div></main>'))
        duplicate = next(item for item in findings if item.rule == "duplicate-id")
        self.assertIn("first used on line", duplicate.message)

    def test_controls_accept_wrapping_label_and_valid_aria_reference(self):
        document = CLEAN.replace('<label for="quantity">Quantity</label><input id="quantity">', '<label>Quantity<input></label><span id="search-name">Search</span><input aria-labelledby="search-name">')
        self.assertNotIn("control-name", {item.rule for item in audit_html(document)})

    def test_broken_aria_reference_does_not_name_control(self):
        findings = audit_html(CLEAN.replace('<label for="quantity">Quantity</label><input id="quantity">', '<input aria-labelledby="missing">'))
        self.assertIn("control-name", {item.rule for item in findings})

    def test_heading_jump_and_blocking_script(self):
        document = CLEAN.replace('<script type="module" src="app.js"></script>', '<script src="app.js"></script>').replace("</h1>", "</h1><h3>Sale</h3>")
        self.assertEqual({item.rule for item in audit_html(document)}, {"blocking-script", "heading-order"})

    def test_cli_output_is_deterministic_and_finding_exit_is_one(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shop.html"
            path.write_text(CLEAN.replace(' alt="Blue mug"', ""), encoding="utf-8")
            outputs = []
            for _ in range(2):
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    self.assertEqual(main([str(path)]), 1)
                outputs.append(stream.getvalue())
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(json.loads(outputs[0])["counts"]["errors"], 1)

    def test_reader_rejects_invalid_utf8_and_nul(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.html"
            for payload in (b"\xff", b"<html>\x00</html>"):
                path.write_bytes(payload)
                with self.assertRaises(ValueError):
                    _read_html(path)

    def test_reader_enforces_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.html"
            path.write_bytes(b"x" * (MAX_BYTES + 1))
            with self.assertRaises(ValueError):
                _read_html(path)


if __name__ == "__main__":
    unittest.main()
