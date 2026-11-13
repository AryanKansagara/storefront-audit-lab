from __future__ import annotations

from dataclasses import asdict, dataclass
from html.parser import HTMLParser


REPORT_SCHEMA_VERSION = 2
RULE_CATALOG_VERSION = "2026-11-13"


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    summary: str


RULES = {
    rule.id: rule
    for rule in (
        Rule("blocking-script", "warning", "Head script may block HTML parsing."),
        Rule("control-name", "error", "Form control lacks a statically resolvable accessible name."),
        Rule("document-html", "error", "Document has no html element."),
        Rule("document-language", "error", "HTML language is missing or empty."),
        Rule("document-title", "error", "Document title is missing or empty."),
        Rule("duplicate-id", "error", "An id value is used by more than one element."),
        Rule("duplicate-label", "warning", "Form control has multiple explicit labels."),
        Rule("heading-order", "warning", "Heading levels skip a level."),
        Rule("image-alt", "error", "Image has no alt attribute."),
        Rule("image-dimensions", "warning", "Image lacks explicit width or height."),
        Rule("interactive-name", "error", "Link or button lacks a statically resolvable accessible name."),
        Rule("link-destination", "warning", "Link uses an empty, placeholder, or script-executing destination."),
        Rule("main-landmark", "warning", "Document has no statically detectable main landmark."),
        Rule("viewport", "warning", "Viewport metadata is missing or empty."),
    )
}


def rule_catalog() -> list[dict[str, str]]:
    """Return stable, machine-readable metadata for every implemented rule."""
    return [asdict(RULES[rule_id]) for rule_id in sorted(RULES)]


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    line: int
    message: str


@dataclass
class _Control:
    line: int
    element: str
    control_id: str | None
    aria_labelledby: tuple[str, ...]
    directly_named: bool


@dataclass
class _Interactive:
    line: int
    element: str
    aria_labelledby: tuple[str, ...]
    directly_named: bool
    text: list[str]


class _StorefrontParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.findings: list[Finding] = []
        self.ids: dict[str, int] = {}
        self.label_lines_for: dict[str, list[int]] = {}
        self.control_ids: set[str] = set()
        self.controls: list[_Control] = []
        self.interactives: list[_Interactive] = []
        self.active_interactives: list[_Interactive] = []
        self.headings: list[tuple[int, int]] = []
        self.seen_html = False
        self.has_lang = False
        self.has_viewport = False
        self.has_main = False
        self.in_head = 0
        self.label_depth = 0
        self.title_depth = 0
        self.title_text: list[str] = []
        self.has_title = False

    def _add(self, rule: str, severity: str, line: int, message: str) -> None:
        if rule not in RULES or RULES[rule].severity != severity:
            raise AssertionError(f"finding metadata does not match rule catalog: {rule}")
        self.findings.append(Finding(rule, severity, line, message))

    def handle_decl(self, decl: str) -> None:
        return

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in {"img", "input", "meta", "link", "source", "br", "hr"}:
            self.handle_endtag(tag)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        line = self.getpos()[0]
        values = {key.lower(): value for key, value in attrs}

        element_id = values.get("id")
        if element_id:
            if element_id in self.ids:
                self._add("duplicate-id", "error", line, f"id {element_id!r} was first used on line {self.ids[element_id]}")
            else:
                self.ids[element_id] = line

        if tag == "html":
            self.seen_html = True
            self.has_lang = bool((values.get("lang") or "").strip())
        elif tag == "head":
            self.in_head += 1
        elif tag == "title":
            self.title_depth += 1
        elif tag == "meta" and (values.get("name") or "").lower() == "viewport":
            self.has_viewport = bool((values.get("content") or "").strip())
        elif tag == "main" or values.get("role") == "main":
            self.has_main = True
        elif tag == "label":
            self.label_depth += 1
            if values.get("for"):
                target = values["for"] or ""
                self.label_lines_for.setdefault(target, []).append(line)
        elif tag == "img":
            if "alt" not in values:
                self._add("image-alt", "error", line, "image is missing an alt attribute")
            if not values.get("width") or not values.get("height"):
                self._add("image-dimensions", "warning", line, "image is missing explicit width or height")
            if (values.get("alt") or "").strip():
                for interactive in self.active_interactives:
                    interactive.text.append(values["alt"] or "")
        elif tag == "script" and self.in_head and not any(key in values for key in ("async", "defer")) and (values.get("type") or "").lower() != "module":
            self._add("blocking-script", "warning", line, "head script lacks async, defer, or type=module")

        if tag in {"input", "select", "textarea"}:
            input_type = (values.get("type") or "text").lower()
            if tag != "input" or input_type not in {"hidden", "button", "submit", "reset", "image"}:
                labelledby = tuple(part for part in (values.get("aria-labelledby") or "").split() if part)
                directly_named = self.label_depth > 0 or bool((values.get("aria-label") or "").strip())
                self.controls.append(_Control(line, tag, element_id, labelledby, directly_named))
                if element_id:
                    self.control_ids.add(element_id)

        if tag == "button" or (tag == "a" and "href" in values):
            labelledby = tuple(part for part in (values.get("aria-labelledby") or "").split() if part)
            directly_named = bool((values.get("aria-label") or "").strip() or (values.get("title") or "").strip())
            interactive = _Interactive(line, tag, labelledby, directly_named, [])
            self.interactives.append(interactive)
            self.active_interactives.append(interactive)

        if tag == "a" and "href" in values:
            destination = (values.get("href") or "").strip()
            normalized_destination = destination.translate({ord("\t"): None, ord("\n"): None, ord("\r"): None}).casefold()
            if not destination:
                self._add("link-destination", "warning", line, "link destination is empty")
            elif destination == "#":
                self._add("link-destination", "warning", line, "link destination is a fragment-only placeholder")
            elif normalized_destination.startswith("javascript:"):
                self._add("link-destination", "warning", line, "link destination uses the javascript scheme")

        if len(tag) == 2 and tag[0] == "h" and tag[1] in "123456":
            self.headings.append((int(tag[1]), line))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "head" and self.in_head:
            self.in_head -= 1
        elif tag == "label" and self.label_depth:
            self.label_depth -= 1
        elif tag == "title" and self.title_depth:
            self.title_depth -= 1
            if "".join(self.title_text).strip():
                self.has_title = True
        if tag in {"a", "button"}:
            for index in range(len(self.active_interactives) - 1, -1, -1):
                if self.active_interactives[index].element == tag:
                    del self.active_interactives[index]
                    break

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title_text.append(data)
        if data.strip():
            for interactive in self.active_interactives:
                interactive.text.append(data)

    def finish(self) -> list[Finding]:
        if not self.seen_html:
            self._add("document-html", "error", 1, "document has no html element")
        elif not self.has_lang:
            self._add("document-language", "error", 1, "html element is missing a non-empty lang attribute")
        if not self.has_title:
            self._add("document-title", "error", 1, "document is missing a non-empty title")
        if not self.has_viewport:
            self._add("viewport", "warning", 1, "document is missing a non-empty viewport meta tag")
        if not self.has_main:
            self._add("main-landmark", "warning", 1, "document has no main element or role=main landmark")

        for control in self.controls:
            named_by_for = bool(control.control_id and control.control_id in self.label_lines_for)
            named_by_aria = bool(control.aria_labelledby) and all(ref in self.ids for ref in control.aria_labelledby)
            if not (control.directly_named or named_by_for or named_by_aria):
                self._add("control-name", "error", control.line, f"{control.element} has no statically resolvable accessible name")

        for target in sorted(self.control_ids):
            label_lines = self.label_lines_for.get(target, [])
            if len(label_lines) > 1:
                self._add(
                    "duplicate-label",
                    "warning",
                    label_lines[1],
                    f"control id {target!r} has {len(label_lines)} explicit labels",
                )

        for interactive in self.interactives:
            named_by_aria = bool(interactive.aria_labelledby) and all(ref in self.ids for ref in interactive.aria_labelledby)
            named_by_content = bool("".join(interactive.text).strip())
            if not (interactive.directly_named or named_by_aria or named_by_content):
                self._add("interactive-name", "error", interactive.line, f"{interactive.element} has no statically resolvable accessible name")

        previous_level: int | None = None
        for level, line in self.headings:
            if previous_level is not None and level > previous_level + 1:
                self._add("heading-order", "warning", line, f"heading level jumps from h{previous_level} to h{level}")
            previous_level = level

        return sorted(self.findings, key=lambda finding: (finding.line, finding.rule, finding.message))


def audit_html(document: str) -> list[Finding]:
    """Audit one decoded HTML document without network or browser execution."""
    parser = _StorefrontParser()
    parser.feed(document)
    parser.close()
    return parser.finish()


def report(document: str, source: str, suppressions: frozenset[str] = frozenset()) -> dict[str, object]:
    unknown = sorted(suppressions - RULES.keys())
    if unknown:
        raise ValueError(f"unknown suppression rule: {unknown[0]}")
    all_findings = audit_html(document)
    findings = [item for item in all_findings if item.rule not in suppressions]
    suppressed = [item for item in all_findings if item.rule in suppressions]
    counts = {
        "errors": sum(item.severity == "error" for item in findings),
        "warnings": sum(item.severity == "warning" for item in findings),
    }
    suppressed_counts = {
        "errors": sum(item.severity == "error" for item in suppressed),
        "warnings": sum(item.severity == "warning" for item in suppressed),
    }
    rule_counts = {rule_id: 0 for rule_id in sorted(RULES)}
    suppressed_rule_counts = {rule_id: 0 for rule_id in sorted(RULES)}
    for item in findings:
        rule_counts[item.rule] += 1
    for item in suppressed:
        suppressed_rule_counts[item.rule] += 1
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "rule_catalog_version": RULE_CATALOG_VERSION,
        "source": source,
        "suppressions": sorted(suppressions),
        "counts": counts,
        "suppressed_counts": suppressed_counts,
        "rule_counts": rule_counts,
        "suppressed_rule_counts": suppressed_rule_counts,
        "findings": [asdict(item) for item in findings],
    }
