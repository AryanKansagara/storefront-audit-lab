from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import REPORT_SCHEMA_VERSION, RULE_CATALOG_VERSION, RULES, report, rule_catalog

MAX_BYTES = 1_048_576


def _read_html(path: Path) -> str:
    payload = path.read_bytes()
    if len(payload) > MAX_BYTES:
        raise ValueError(f"input exceeds {MAX_BYTES} bytes")
    if b"\x00" in payload:
        raise ValueError("input contains a NUL byte")
    try:
        return payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("input is not valid UTF-8") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit static storefront HTML")
    parser.add_argument("html", type=Path, nargs="?")
    parser.add_argument(
        "--suppress",
        action="append",
        choices=sorted(RULES),
        default=[],
        metavar="RULE",
        help="suppress a known rule; repeat for multiple rules",
    )
    parser.add_argument("--list-rules", action="store_true", help="print rule metadata and exit")
    args = parser.parse_args(argv)
    if args.list_rules:
        if args.html is not None or args.suppress:
            parser.error("--list-rules cannot be combined with an HTML path or --suppress")
        catalog = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "rule_catalog_version": RULE_CATALOG_VERSION,
            "rules": rule_catalog(),
        }
        print(json.dumps(catalog, indent=2, sort_keys=True))
        return 0
    if args.html is None:
        parser.error("an HTML path is required unless --list-rules is used")
    try:
        document = _read_html(args.html)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    result = report(document, str(args.html), frozenset(args.suppress))
    print(json.dumps(result, indent=2, sort_keys=True))
    counts = result["counts"]
    assert isinstance(counts, dict)
    return 1 if counts["errors"] or counts["warnings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
