from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import report

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
    parser.add_argument("html", type=Path)
    args = parser.parse_args(argv)
    try:
        document = _read_html(args.html)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    result = report(document, str(args.html))
    print(json.dumps(result, indent=2, sort_keys=True))
    counts = result["counts"]
    assert isinstance(counts, dict)
    return 1 if counts["errors"] or counts["warnings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
