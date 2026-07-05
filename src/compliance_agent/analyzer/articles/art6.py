"""Article 6 — Classification rules for high-risk AI systems."""

from compliance_agent.analyzer.articles.base import (
    MIN_ARTIFACT_CHARS,
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art6Analyzer(ArticleAnalyzer):
    article_number = 6
    article_title = "High-risk AI systems"

    def applies(self, scan_result: ScanResult) -> bool:
        return is_high_risk(scan_result)

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        return [
            Requirement(
                name="Intended purpose must be documented",
                status=evidence(
                    mechanism=probe.any_file(
                        "docs/intended-purpose.md", min_content_chars=MIN_ARTIFACT_CHARS
                    ),
                    mention=probe.docs_mention("intended purpose"),
                ),
                severity=Severity.CRITICAL,
                details=(
                    "High-risk AI systems are classified under Art. 6(2) (Annex III "
                    "use cases); a documented intended purpose is required and the "
                    "classification depends on it."
                ),
                suggestion=(
                    "Document the intended purpose in the project README or "
                    "docs/intended-purpose.md"
                ),
            ),
            Requirement(
                name="Annex III category must be identified",
                # Evidence must be the deployer's OWN documentation of the
                # category — not the scanner's keyword match. Grading this on the
                # classifier's own match made it always MET whenever the analyzer
                # ran, silently inflating Art. 6 coverage.
                status=evidence(
                    mechanism=False,
                    mention=probe.docs_mention("annex iii", "annex 3", "high-risk category"),
                ),
                severity=Severity.HIGH,
                details=(
                    "The applicable Annex III category must be specified in the "
                    "system's documentation (Art. 6(2))."
                ),
                suggestion="Add the Annex III category classification to your documentation",
            ),
        ]
