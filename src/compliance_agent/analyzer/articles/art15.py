"""Article 15 — Accuracy, robustness, and cybersecurity."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    has_ai,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art15Analyzer(ArticleAnalyzer):
    article_number = 15
    article_title = "Accuracy, robustness, and cybersecurity"

    def applies(self, scan_result: ScanResult) -> bool:
        return has_ai(scan_result)

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return "no AI usage detected"

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        has_accuracy = probe.docs_mention(
            "accuracy", "accurate", "precision", "recall", "f1", "benchmark"
        )
        has_error_handling = probe.code_mentions("try:", "except ")
        # Explicit terms only — the bare token "auth" used to match "__author__"
        # and mark cybersecurity as satisfied on projects with no controls.
        has_security = probe.code_mentions(
            "validate",
            "sanitize",
            "rate_limit",
            "ratelimit",
            "authentication",
            "authorization",
            "authenticate",
            "access_control",
            "escape(",
        )
        has_robustness = probe.any_file("tests/*", "test/*") or probe.docs_mention(
            "adversarial", "robustness"
        )
        return [
            Requirement(
                name="Accuracy metrics should be documented",
                met=has_accuracy,
                severity=Severity.WARNING,
                details="AI systems should have documented accuracy levels per Art. 15(1).",
                suggestion="Document model accuracy, precision, recall, and known error rates",
            ),
            Requirement(
                name="Error handling mechanisms required",
                met=has_error_handling,
                severity=Severity.HIGH,
                details=(
                    "No error handling was found around AI usage. Systems must "
                    "handle errors and inconsistencies per Art. 15."
                ),
                suggestion="Add try/except around model calls, fallbacks, and error logging",
            ),
            Requirement(
                name="Cybersecurity measures required",
                met=has_security,
                severity=Severity.HIGH,
                details="Systems must be resilient against attacks and misuse per Art. 15(5).",
                suggestion="Implement input validation, rate limiting, and access controls",
            ),
            Requirement(
                name="Robustness testing recommended",
                met=has_robustness,
                severity=Severity.WARNING,
                details=(
                    "No test suite or robustness documentation found. Systems "
                    "should be robust against errors and adversarial inputs."
                ),
                suggestion="Add a test suite including edge cases and adversarial inputs",
            ),
        ]
