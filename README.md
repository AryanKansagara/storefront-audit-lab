# storefront-audit-lab

A dependency-free, deterministic static analyzer for merchant storefront HTML. It reports a narrow set of accessibility and loading-risk signals without executing scripts, fetching network resources, or sending storefront data anywhere.

This independent portfolio project is not affiliated with Shopify. The checked-in storefront is synthetic.

## Capabilities

- Document language, title, viewport, and main-landmark checks.
- Missing image alternative text and dimensions.
- Duplicate IDs and statically resolvable form-control names (`label`, `aria-label`, and valid `aria-labelledby`).
- Statically resolvable names for links and buttons from text/image alternatives, ARIA, or `title`.
- Empty, fragment-only placeholder, and `javascript:` link destinations.
- Heading-level jumps.
- Parser-blocking classic scripts in `head` that lack `async` or `defer`.
- Strict UTF-8 input with a 1 MiB bound and deterministic JSON output.
- Python 3.11/3.14 tests and CI.
- Versioned, machine-readable rule metadata and explicit report schema versioning.
- Auditable whole-rule suppressions that retain suppressed error/warning counts.
- Stable zero-complete per-rule counts for both visible and suppressed findings, alongside severity totals.

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

Suppressions accept only IDs from `--list-rules`, apply to the entire input document, and are recorded in `suppressions` with severity totals in `suppressed_counts`; they are not invisible inline exceptions. Reports also include catalog-bounded `rule_counts` and `suppressed_rule_counts` maps. Every known rule is present even when its count is zero, so consumers can compare deterministic summaries without reconstructing counts from findings or treating a missing key as zero. A suppressed finding no longer contributes to the process exit status, so suppression configuration should be reviewed and version controlled with the consuming system.

## Scope and limitations

This is a static heuristic audit, not a browser, accessibility conformance certification, Lighthouse replacement, Core Web Vitals measurement, or production release gate. It does not compute an accessibility score, execute JavaScript, resolve CSS, apply the full browser accessible-name algorithm, inspect rendered names, test keyboard behavior, follow URLs, measure network timing, or represent people using assistive technology. Static link/button checks cannot account for CSS-hidden text, dynamic content, every ARIA relationship, router-specific placeholders, or the safety and availability of destination content. The link-destination rule deliberately recognizes only three high-signal static patterns; it does not validate general URLs. Empty `alt` text is permitted because it can intentionally mark a decorative image. A valid static report can still miss serious rendered-page issues, and warnings require human review.

Only audit storefronts you are authorized to inspect. The tool performs no network access and the repository contains no merchant or customer data.
