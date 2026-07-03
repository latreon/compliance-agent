"""Risk tier classifier: maps scan findings to EU AI Act risk tiers."""

import re
from pathlib import Path

from compliance_agent.classifier.annex3 import Annex3Category, load_categories
from compliance_agent.models.findings import (
    Finding,
    RiskAssessment,
    RiskTier,
    ScanResult,
)

# Confidence contribution per keyword hit, capped at 1.0.
CONFIDENCE_PER_HIT = 0.25
# Minimum hits in a category before we classify the project as high-risk.
HIGH_RISK_HIT_THRESHOLD = 1


class RiskClassifier:
    """Classifies a scanned project into an EU AI Act risk tier.

    Strategy:
    - Match Annex III keywords against finding file paths, messages, and
      descriptions.
    - Any Annex III match => HIGH tier.
    - AI usage with user interaction but no Annex III match => LIMITED.
    - AI usage without user interaction => MINIMAL.
    - No AI usage at all => MINIMAL with full confidence.
    """

    def __init__(self, rules_path: Path | None = None):
        self.categories: list[Annex3Category] = load_categories(rules_path)

    def classify(self, scan_result: ScanResult) -> RiskAssessment:
        """Assign a risk tier with confidence score and reasoning."""
        findings = scan_result.findings
        if not findings:
            return RiskAssessment(
                tier=RiskTier.MINIMAL,
                confidence=1.0,
                reasoning=["No AI usage detected in the project."],
            )

        matched = self._match_annex3(findings)
        if matched:
            hits = sum(count for _, count in matched)
            confidence = min(1.0, hits * CONFIDENCE_PER_HIT)
            reasoning = [
                f"Matched Annex III category '{cat.name}' ({cat.article}) "
                f"with {count} keyword hit(s)."
                for cat, count in matched
            ]
            return RiskAssessment(
                tier=RiskTier.HIGH,
                confidence=confidence,
                reasoning=reasoning,
                matched_categories=[cat.id for cat, _ in matched],
            )

        has_provider = any(f.category.startswith("provider:") for f in findings)
        has_user_interaction = any(
            f.category in ("pattern:user-input", "pattern:chat-interface") for f in findings
        )

        if has_provider and has_user_interaction:
            return RiskAssessment(
                tier=RiskTier.LIMITED,
                confidence=0.7,
                reasoning=[
                    "AI provider usage combined with user-facing interaction detected; "
                    "transparency obligations (Art. 50) apply, but no Annex III "
                    "high-risk domain matched."
                ],
            )

        if has_provider:
            return RiskAssessment(
                tier=RiskTier.MINIMAL,
                confidence=0.6,
                reasoning=[
                    "AI provider usage detected without user-facing interaction or "
                    "Annex III domain indicators."
                ],
            )

        return RiskAssessment(
            tier=RiskTier.MINIMAL,
            confidence=0.8,
            reasoning=["Only generic patterns detected; no direct AI provider usage found."],
        )

    def _match_annex3(self, findings: list[Finding]) -> list[tuple[Annex3Category, int]]:
        """Count keyword hits per Annex III category across all findings."""
        corpus = "\n".join(f"{f.file_path}\n{f.message}\n{f.description}" for f in findings).lower()
        matches: list[tuple[Annex3Category, int]] = []
        for category in self.categories:
            count = 0
            for keyword in category.keywords:
                # keyword may contain spaces or underscores; match loosely, but
                # require word boundaries so a keyword like "migration" does not
                # match inside common paths such as "migrations/" or
                # "data_migration/" and produce a false high-risk classification.
                inner = re.escape(keyword.lower()).replace(r"\ ", r"[\s_-]")
                pattern = rf"(?<![\w]){inner}(?![\w])"
                count += len(re.findall(pattern, corpus))
            if count >= HIGH_RISK_HIT_THRESHOLD:
                matches.append((category, count))
        return matches
