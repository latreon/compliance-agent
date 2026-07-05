"""Article 13 — Transparency and provision of information to deployers."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art13Analyzer(ArticleAnalyzer):
    article_number = 13
    article_title = "Transparency and provision of information to deployers"

    def applies(self, scan_result: ScanResult) -> bool:
        # Art. 13 (instructions for use to deployers) is a Chapter III, Section 2
        # obligation for HIGH-RISK systems only. Previously it fired on any
        # user-facing AI, overstating the obligation (at HIGH severity) for
        # limited/minimal-risk chatbots.
        return is_high_risk(scan_result)

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return super().not_applicable_reason(scan_result)

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        return [
            Requirement(
                name="Instructions of use must be provided",
                status=evidence(
                    mechanism=probe.any_file("docs/instructions*", min_content_chars=40),
                    mention=probe.docs_mention("instructions", "## usage", "quick start"),
                ),
                severity=Severity.HIGH,
                details=(
                    "High-risk AI systems must be accompanied by clear instructions "
                    "for use for deployers (Art. 13(2)–(3))."
                ),
                suggestion=(
                    "Create docs/instructions.md with intended purpose, "
                    "limitations, and usage guidance"
                ),
            ),
            Requirement(
                name="Output interpretation guidance required",
                status=evidence(
                    mechanism=False,
                    mention=probe.docs_mention("interpret", "confidence", "limitations"),
                ),
                severity=Severity.WARNING,
                details="Users must be able to interpret AI outputs correctly per Art. 13.",
                suggestion=(
                    "Document how to interpret AI outputs, including confidence "
                    "levels and limitations"
                ),
            ),
            Requirement(
                name="Input data information required",
                status=evidence(
                    mechanism=False,
                    mention=probe.docs_mention("input format", "input data", "validation"),
                ),
                severity=Severity.WARNING,
                details="Deployers must be informed about input data requirements.",
                suggestion="Document required input formats, validation, and limitations",
            ),
        ]
