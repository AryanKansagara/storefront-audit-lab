"""Deterministic static storefront HTML audit."""

from .audit import Finding, Rule, audit_html, rule_catalog

__all__ = ["Finding", "Rule", "audit_html", "rule_catalog"]
