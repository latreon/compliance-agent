"""Article 27 — Fundamental rights impact assessment (FRIA).

Note: the legal duty to conduct a FRIA applies to a narrower set of deployers
(bodies governed by public law, private operators providing public services,
and deployers of the credit-scoring/insurance-risk systems in Annex III
points 5(b)-(c)) than "every high-risk deployer". This analyzer gates on the
same is_high_risk heuristic used throughout this tool for consistency, and
says so explicitly in the requirement text, so a HIGH-risk project outside
that narrower scope is not misread as non-compliant — verify applicability
against Art. 27(1) before treating this as a hard blocker.
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


class Art27Analyzer(ArticleAnalyzer):
    article_number = 27
    article_title = "Fundamental rights impact assessment"

    def applies(self, scan_result: ScanResult) -> bool:
        return is_high_risk(scan_result)

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        return [
            Requirement(
                name="Fundamental rights impact assessment required before deployment",
                status=evidence(
                    mechanism=probe.any_file(
                        "docs/fria*",
                        "FRIA*",
                        "docs/fundamental-rights*",
                        min_content_chars=MIN_ARTIFACT_CHARS,
                    ),
                    mention=probe.docs_mention("fundamental rights impact assessment", "fria"),
                ),
                severity=Severity.CRITICAL,
                details=(
                    "Certain deployers of high-risk AI systems (public bodies, "
                    "private operators providing public services, and "
                    "credit-scoring/insurance-risk deployers under Annex III "
                    "5(b)-(c)) must conduct a fundamental rights impact "
                    "assessment before first use (Art. 27(1)). Verify whether "
                    "this project falls in that narrower scope before treating "
                    "this as mandatory."
                ),
                suggestion=(
                    "Complete a FRIA with templates/art27/fria.py and commit "
                    "docs/fria.md before deployment"
                ),
            ),
            Requirement(
                name="FRIA must document mitigation measures and a complaint mechanism",
                status=evidence(
                    mechanism=False,
                    mention=probe.docs_mention(
                        "complaint mechanism", "redress", "mitigation measures"
                    ),
                ),
                severity=Severity.WARNING,
                details=(
                    "The FRIA must describe the risk-mitigation measures in "
                    "place and the governance arrangements for complaints and "
                    "redress (Art. 27(1)(e)-(f))."
                ),
                suggestion="Document mitigation measures and a complaint/redress path",
            ),
        ]
