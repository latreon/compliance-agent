"""Article 13 — Transparency and provision of information to deployers."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
    has_user_interaction,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art13Analyzer(ArticleAnalyzer):
    article_number = 13
    article_title = "Transparency and provision of information to deployers"

    def applies(self, scan_result: ScanResult) -> bool:
        return has_user_interaction(scan_result)

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return "no user-facing AI interaction detected"

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        return [
            Requirement(
                name="Instructions of use must be provided",
                status=evidence(
                    mechanism=probe.any_file("docs/instructions*"),
                    mention=probe.docs_mention("instructions", "## usage", "quick start"),
                ),
                severity=Severity.HIGH,
                details=(
                    "AI systems interacting with users require clear instructions "
                    "of use per Art. 13(1)."
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
