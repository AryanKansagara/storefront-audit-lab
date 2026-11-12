import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from storefront_audit import audit_html, rule_catalog
from storefront_audit.audit import RULES, report
from storefront_audit.cli import MAX_BYTES, _read_html, main


CLEAN = """<!doctype html><html lang="en"><head><title>Demo shop</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script type="module" src="app.js"></script></head><body><main><h1>Catalog</h1>
<img src="item.jpg" alt="Blue mug" width="400" height="300">
<label for="quantity">Quantity</label><input id="quantity">
<a href="/catalog">Browse catalog</a><button aria-label="Open cart"></button></main></body></html>"""


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

    def test_links_and_buttons_require_static_names(self):
        document = CLEAN.replace(
            '<a href="/catalog">Browse catalog</a><button aria-label="Open cart"></button>',
            '<a href="/catalog"></a><button></button>',
        )
        findings = [item for item in audit_html(document) if item.rule == "interactive-name"]
        self.assertEqual([item.message.split()[0] for item in findings], ["a", "button"])

    def test_interactive_names_accept_content_image_alt_and_valid_aria_reference(self):
        document = CLEAN.replace(
            '<a href="/catalog">Browse catalog</a><button aria-label="Open cart"></button>',
            '<span id="account-name">Account</span>'
            '<a href="/account" aria-labelledby="account-name"></a>'
            '<button><img src="cart.svg" alt="Open cart" width="20" height="20"></button>',
        )
        self.assertNotIn("interactive-name", {item.rule for item in audit_html(document)})

    def test_anchor_without_href_is_not_treated_as_interactive(self):
        document = CLEAN.replace('<a href="/catalog">Browse catalog</a>', '<a></a>')
        self.assertNotIn("interactive-name", {item.rule for item in audit_html(document)})

    def test_placeholder_and_script_link_destinations_are_reported(self):
        document = CLEAN.replace(
            '<a href="/catalog">Browse catalog</a>',
            '<a href=" ">Empty</a>\n<a href="#">Placeholder</a>\n'
            '<a href=" JAVA\tSCRIPT&#58;alert(1)">Script</a>',
        )
        findings = [item for item in audit_html(document) if item.rule == "link-destination"]
        self.assertEqual(
            [item.message for item in findings],
            [
                "link destination is empty",
                "link destination is a fragment-only placeholder",
                "link destination uses the javascript scheme",
            ],
        )

    def test_static_link_destination_check_accepts_common_destinations(self):
        document = CLEAN.replace(
            '<a href="/catalog">Browse catalog</a>',
            '<a href="/catalog">Catalog</a><a href="#details">Details</a>'
            '<a href="mailto:help@example.test">Help</a>',
        )
        self.assertNotIn("link-destination", {item.rule for item in audit_html(document)})

    def test_heading_jump_and_blocking_script(self):
        document = CLEAN.replace('<script type="module" src="app.js"></script>', '<script src="app.js"></script>').replace("</h1>", "</h1><h3>Sale</h3>")
        self.assertEqual({item.rule for item in audit_html(document)}, {"blocking-script", "heading-order"})

    def test_catalog_covers_findings_with_matching_severity(self):
        findings = audit_html("<p id='same'><img id='same'><input><h1>A</h1><h3>B</h3>")
        catalog = rule_catalog()
        self.assertEqual([item["id"] for item in catalog], sorted(RULES))
        self.assertEqual(len(catalog), len(RULES))
        for finding in findings:
            self.assertEqual(RULES[finding.rule].severity, finding.severity)

    def test_report_suppression_is_explicit_and_counted(self):
        document = CLEAN.replace(' alt="Blue mug" width="400" height="300"', "")
        result = report(document, "shop.html", frozenset({"image-alt"}))
        self.assertEqual(result["suppressions"], ["image-alt"])
        self.assertEqual(result["counts"], {"errors": 0, "warnings": 1})
        self.assertEqual(result["suppressed_counts"], {"errors": 1, "warnings": 0})
        findings = result["findings"]
        self.assertIsInstance(findings, list)
        assert isinstance(findings, list)
        self.assertEqual([item["rule"] for item in findings], ["image-dimensions"])

    def test_report_rejects_unknown_suppression(self):
        with self.assertRaisesRegex(ValueError, "unknown suppression rule"):
            report(CLEAN, "shop.html", frozenset({"not-a-rule"}))

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

    def test_cli_lists_rules_and_suppression_changes_exit_status(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main(["--list-rules"]), 0)
        catalog = json.loads(stream.getvalue())
        self.assertEqual(len(catalog["rules"]), len(RULES))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shop.html"
            path.write_text(CLEAN.replace(' alt="Blue mug"', ""), encoding="utf-8")
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(main(["--suppress", "image-alt", str(path)]), 0)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["suppressed_counts"]["errors"], 1)

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
