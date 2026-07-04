"""Article 24 — Obligations of distributors.

Note: distributor obligations are set out in Article 24 of Regulation (EU)
2024/1689 (Article 28 concerns notifying authorities). Distribution is inferred
here from the presence of deployment/packaging artifacts.
"""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
)
from compliance_agent.models.findings import ScanResult, Severity

DEPLOYMENT_MARKERS = (
    "Dockerfile",
    "docker-compose*",
    "Procfile",
    "helm/*",
    "deploy/*",
    ".github/workflows/deploy*",
    "k8s/*",
)


class Art24Analyzer(ArticleAnalyzer):
    article_number = 24
    article_title = "Obligations of distributors"

    def applies(self, scan_result: ScanResult) -> bool:
        # Heuristic: deployment/packaging artifacts imply the system is being
        # made available to others (distribution).
        return ProjectProbe(scan_result.project_path).any_file(*DEPLOYMENT_MARKERS)

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return "no distribution/deployment artifacts detected"

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        return [
            Requirement(
                name="Verify conformity assessment before distribution",
                status=evidence(mechanism=False, mention=probe.docs_mention("conformity")),
                severity=Severity.HIGH,
                details=(
                    "Distributors must verify the provider carried out the "
                    "conformity assessment before making the system available."
                ),
                suggestion="Verify and record the provider's conformity assessment",
            ),
            Requirement(
                name="Technical documentation must be available",
                status=evidence(
                    mechanism=probe.any_file("TECHNICAL_DOC.md", "docs/technical*"),
                    mention=probe.docs_mention("technical documentation"),
                ),
                severity=Severity.WARNING,
                details="Technical documentation must accompany the distributed system.",
                suggestion="Request and maintain the provider's technical documentation",
            ),
            Requirement(
                name="Instructions of use must be provided to users",
                status=evidence(
                    mechanism=probe.any_file("docs/instructions*"),
                    mention=probe.docs_mention("instructions", "## usage"),
                ),
                severity=Severity.WARNING,
                details="Users must receive the instructions of use.",
                suggestion="Ship the provider's instructions of use with the deployment",
            ),
        ]
