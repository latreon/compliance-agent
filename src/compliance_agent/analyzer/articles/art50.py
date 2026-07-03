"""Article 50 — Transparency obligations for AI interacting with users."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    has_ai,
    has_user_interaction,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art50Analyzer(ArticleAnalyzer):
    article_number = 50
    article_title = "Transparency obligations (user-facing AI)"

    def applies(self, scan_result: ScanResult) -> bool:
        return has_ai(scan_result) and has_user_interaction(scan_result)

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return "no user-facing AI interaction detected"

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        has_disclosure = probe.code_mentions(
            "ai-disclosure", "transparency_notice", "x-ai-disclosure", "ai_transparency"
        ) or probe.docs_mention("ai disclosure", "interacting with an ai")
        return [
            Requirement(
                name="AI interaction disclosure required",
                met=has_disclosure,
                severity=Severity.WARNING,
                details=(
                    "Users appear to interact with AI output but no disclosure "
                    "mechanism was found. They must be informed they are "
                    "interacting with an AI system."
                ),
                suggestion=(
                    "Add a clear AI disclosure notice (templates/art50/transparency_notice.py)"
                ),
            ),
        ]
