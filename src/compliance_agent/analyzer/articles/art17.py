"""Article 17 — Quality management system.

Note: Art. 16 already surfaces one bundled "Quality management system
required" line as part of the provider-obligations umbrella. This analyzer
gives Art. 17 its own dedicated coverage-table row and checks the deeper,
distinct QMS elements (Art. 17(1)(d)-(g), (n)) that Art. 16's single line
does not track — a provider that documents *a* QMS but never describes
testing/validation procedures or an accountability framework still has real
Art. 17 gaps.
"""

from compliance_agent.analyzer.articles.base import (
    MIN_ARTIFACT_CHARS,
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art17Analyzer(ArticleAnalyzer):
    article_number = 17
    article_title = "Quality management system"

    def applies(self, scan_result: ScanResult) -> bool:
        return is_high_risk(scan_result)

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        return [
            Requirement(
                name="Quality management system must be documented",
                status=evidence(
                    mechanism=probe.any_file(
                        "docs/quality*", "QMS*", min_content_chars=MIN_ARTIFACT_CHARS
                    ),
                    mention=probe.docs_mention("quality management system", "qms"),
                ),
                severity=Severity.CRITICAL,
                details=(
                    "Providers of high-risk AI systems must put a quality "
                    "management system in place, documented systematically as "
                    "written policies and procedures (Art. 17(1))."
                ),
                suggestion=(
                    "Document your QMS with templates/art17/quality_management_system.py "
                    "and commit docs/quality-management.md"
                ),
            ),
            Requirement(
                name="QMS testing and validation procedures required",
                status=evidence(
                    mechanism=False,
                    mention=probe.docs_mention(
                        "testing procedure",
                        "validation procedure",
                        "verification procedure",
                    ),
                ),
                severity=Severity.WARNING,
                details=(
                    "The QMS must define examination, testing, and validation "
                    "procedures carried out before and during development "
                    "(Art. 17(1)(d)-(g))."
                ),
                suggestion="Document testing/validation procedures in your QMS",
            ),
            Requirement(
                name="QMS accountability framework required",
                status=evidence(
                    mechanism=False,
                    mention=probe.docs_mention(
                        "accountability framework",
                        "management responsibility",
                        "management responsibilities",
                    ),
                ),
                severity=Severity.WARNING,
                details=(
                    "The QMS must set out an accountability framework defining "
                    "management's responsibilities and role in the QMS "
                    "(Art. 17(1)(n))."
                ),
                suggestion="Document who is accountable for QMS decisions and reviews",
            ),
        ]
