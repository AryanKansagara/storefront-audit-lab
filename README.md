# storefront-audit-lab

A dependency-free, deterministic static analyzer for merchant storefront HTML. It reports a narrow set of accessibility and loading-risk signals without executing scripts, fetching network resources, or sending storefront data anywhere.

This independent portfolio project is not affiliated with Shopify. The checked-in storefront is synthetic.

## Capabilities

- Document language, title, viewport, and main-landmark checks.
- Missing image alternative text and dimensions.
- Duplicate IDs and statically resolvable form-control names (`label`, `aria-label`, and valid `aria-labelledby`).
- Heading-level jumps.
- Parser-blocking classic scripts in `head` that lack `async` or `defer`.
- Strict UTF-8 input with a 1 MiB bound and deterministic JSON output.
- Python 3.11/3.14 tests and CI.
- Versioned, machine-readable rule metadata and explicit report schema versioning.
- Auditable whole-rule suppressions that retain suppressed error/warning counts.

Run the synthetic example:

```bash
python -m storefront_audit.cli examples/synthetic_storefront.html
```

Inspect the rule catalog or explicitly suppress a known rule:

```bash
python -m storefront_audit.cli --list-rules
python -m storefront_audit.cli --suppress image-dimensions examples/synthetic_storefront.html
```

Exit status is `0` when there are no findings, `1` when findings exist, and argparse's `2` for invalid input or invocation. Findings are ordered by source line and rule so repeated runs over identical bytes are stable.

Suppressions accept only IDs from `--list-rules`, apply to the entire input document, and are recorded in `suppressions` with severity totals in `suppressed_counts`; they are not invisible inline exceptions. A suppressed finding no longer contributes to the process exit status, so suppression configuration should be reviewed and version controlled with the consuming system.

## Scope and limitations

This is a static heuristic audit, not a browser, accessibility conformance certification, Lighthouse replacement, Core Web Vitals measurement, or production release gate. It does not compute an accessibility score, execute JavaScript, resolve CSS, inspect rendered names, test keyboard behavior, follow URLs, measure network timing, or represent people using assistive technology. Empty `alt` text is permitted because it can intentionally mark a decorative image. A valid static report can still miss serious rendered-page issues, and warnings require human review.

Only audit storefronts you are authorized to inspect. The tool performs no network access and the repository contains no merchant or customer data.
