"""Risk tier classifier: maps scan findings to EU AI Act risk tiers."""

import re
from pathlib import Path

from compliance_agent.classifier.annex3 import (
    Annex3Category,
    load_categories,
    load_prohibited_categories,
)
from compliance_agent.models.findings import (
    Finding,
    RiskAssessment,
    RiskTier,
    ScanResult,
)
from compliance_agent.scanner.engine import _is_test_path

# Confidence contribution per keyword hit, capped at 1.0.
CONFIDENCE_PER_HIT = 0.25
# Floor confidence for a matched high-risk classification, so a HIGH tier is
# never reported at an implausibly low confidence like 0.25.
HIGH_RISK_MIN_CONFIDENCE = 0.5
# Minimum hits in a category before we classify the project as high-risk.
HIGH_RISK_HIT_THRESHOLD = 1

# Appended to every non-HIGH/UNACCEPTABLE result. Domain detection is
# keyword-based and cannot recognise a high-risk use expressed in ordinary
# business wording, so a LIMITED/MINIMAL tier must never read as "safe".
DOMAIN_CAVEAT = (
    "Domain risk is keyword-detected and may miss high-risk uses. If this "
    "system supports hiring, credit, biometrics, education, policing, migration, "
    "or justice (EU AI Act Annex III), self-classify as HIGH and verify with "
    "qualified legal counsel."
)

# Appended when no AI usage is detected. Detection is signature-based, so a
# "no AI" result must never read as a guarantee — many common integration
# methods are not (and cannot cheaply be) recognised.
UNDETECTED_AI_CAVEAT = (
    "Detection covers common providers (OpenAI, Anthropic, Google, Mistral, "
    "local model stacks) and frameworks (LangChain, LangGraph, CrewAI, AutoGen). "
    "AI reached through other SDKs (AWS Bedrock, Azure OpenAI, Vertex AI, Cohere, "
    "Groq, LiteLLM) or raw HTTP calls may not be detected — a 'no AI' result is "
    "not a guarantee that the project contains no AI system."
)


class RiskClassifier:
    """Classifies a scanned project into an EU AI Act risk tier.

    Strategy:
    - Match Annex III / Art. 5 keywords against the scanned project's file
      paths AND actual file content (not just generic finding messages), so a
      high-risk domain is caught regardless of how files are named.
    - Domain matching only escalates the tier when the project actually uses AI
      (a provider or framework was detected). The EU AI Act governs AI systems;
      domain keywords in a project with no AI are noise, so this also prevents
      false high-risk flags on, e.g., a compliance tool that merely names these
      practices in its own rules.
    - Any Annex III match (with AI) => HIGH tier.
    - Prohibited-practice match (with AI) => UNACCEPTABLE (outranks all).
    - AI usage with user interaction but no Annex III match => LIMITED.
    - AI usage without user interaction => MINIMAL.
    - No AI usage at all => MINIMAL with full confidence.
    """

    def __init__(self, rules_path: Path | None = None):
        self.categories: list[Annex3Category] = load_categories(rules_path)
        self.prohibited: list[Annex3Category] = load_prohibited_categories()

    def classify(self, scan_result: ScanResult, project_text: str = "") -> RiskAssessment:
        """Assign a risk tier with confidence score and reasoning.

        ``project_text`` is the scanner's domain corpus (lowercased file paths +
        bounded content). When omitted, matching falls back to finding text only.
        """
        findings = scan_result.findings
        # AI-presence and interaction gates must reflect the DEPLOYED system, not
        # test fixtures. A mocked ``from openai import OpenAI`` in tests/ is a
        # standard testing pattern and must not, on its own, drive the risk tier.
        production = [f for f in findings if not _is_test_path(Path(f.file_path))]

        has_provider = any(f.category.startswith("provider:") for f in production)
        has_framework = any(f.detector.startswith("frameworks:") for f in production)
        has_ai = has_provider or has_framework

        if not has_ai:
            # No production AI detected. Confidence is deliberately not 1.0 —
            # detection is signature-based and cannot see every integration path.
            return RiskAssessment(
                tier=RiskTier.MINIMAL,
                confidence=0.5,
                reasoning=[
                    "No supported AI provider or framework usage detected in the "
                    "project's non-test code.",
                    UNDETECTED_AI_CAVEAT,
                    DOMAIN_CAVEAT,
                ],
            )

        # Domain classification is only meaningful for actual AI systems.
        if has_ai:
            corpus = self._build_corpus(findings, project_text)

            # Prohibited practices (Art. 5) outrank every other tier.
            prohibited = self._match_in_corpus(corpus, self.prohibited)
            if prohibited:
                hits = sum(count for _, count in prohibited)
                reasoning = [
                    f"Matched prohibited practice '{cat.name}' ({cat.article}) "
                    f"with {count} keyword hit(s)."
                    for cat, count in prohibited
                ]
                reasoning.append(
                    "Prohibited AI practices cannot be deployed. Verify with qualified "
                    "legal counsel — this may be a false positive from keyword matching."
                )
                return RiskAssessment(
                    tier=RiskTier.UNACCEPTABLE,
                    confidence=min(1.0, max(HIGH_RISK_MIN_CONFIDENCE, hits * CONFIDENCE_PER_HIT)),
                    reasoning=reasoning,
                    matched_categories=[cat.id for cat, _ in prohibited],
                )

            matched = self._match_in_corpus(corpus, self.categories)
            if matched:
                hits = sum(count for _, count in matched)
                confidence = min(1.0, max(HIGH_RISK_MIN_CONFIDENCE, hits * CONFIDENCE_PER_HIT))
                reasoning = [
                    f"Matched Annex III category '{cat.name}' ({cat.article}) "
                    f"with {count} keyword hit(s)."
                    for cat, count in matched
                ]
                reasoning.append(
                    "High-risk tier is provisional: Art. 6(3) exempts systems performing "
                    "narrow procedural tasks that do not materially influence decisions. "
                    "Confirm the intended purpose before relying on this classification."
                )
                return RiskAssessment(
                    tier=RiskTier.HIGH,
                    confidence=confidence,
                    reasoning=reasoning,
                    matched_categories=[cat.id for cat, _ in matched],
                )

        has_user_interaction = any(
            f.category in ("pattern:user-input", "pattern:chat-interface") for f in production
        )

        # ``has_ai`` is True here (we returned early otherwise), so this covers
        # framework-only projects (LangChain/CrewAI/AutoGen/LangGraph) as well as
        # raw provider-SDK usage. Gating on ``has_provider`` alone previously
        # collapsed every framework-based app to MINIMAL.
        if has_user_interaction:
            return RiskAssessment(
                tier=RiskTier.LIMITED,
                confidence=0.7,
                reasoning=[
                    "AI usage (provider or framework) combined with user-facing "
                    "interaction detected; transparency obligations (Art. 50) apply, "
                    "but no Annex III high-risk domain matched.",
                    DOMAIN_CAVEAT,
                ],
            )

        return RiskAssessment(
            tier=RiskTier.MINIMAL,
            confidence=0.6,
            reasoning=[
                "AI usage (provider or framework) detected without user-facing "
                "interaction or Annex III domain indicators.",
                DOMAIN_CAVEAT,
            ],
        )

    @staticmethod
    def _build_corpus(findings: list[Finding], project_text: str) -> str:
        """Lowercased text to match domain keywords against.

        Combines the scanner's domain corpus (file paths + actual file content)
        with finding paths/messages, so classification reflects what the project
        does, not just how detectors phrase their messages.

        Test-fixture findings are excluded: a test file named after a high-risk
        domain is sample data, not the deployed system, and must not drive risk
        classification. The scanner already excludes test paths from
        ``project_text``; this applies the same rule to finding text so the
        safeguard cannot be defeated through the second corpus.
        """
        finding_text = "\n".join(
            f"{f.file_path}\n{f.message}\n{f.description}"
            for f in findings
            if not _is_test_path(Path(f.file_path))
        ).lower()
        return f"{project_text}\n{finding_text}" if project_text else finding_text

    def _match_in_corpus(
        self, corpus: str, categories: list[Annex3Category]
    ) -> list[tuple[Annex3Category, int]]:
        """Count keyword hits per category across the corpus."""
        matches: list[tuple[Annex3Category, int]] = []
        for category in categories:
            count = 0
            for keyword in category.keywords:
                # keyword may contain spaces, underscores, or hyphens; match the
                # separators interchangeably so a multi-word keyword also matches
                # snake_case identifiers ("real-time remote biometric
                # identification" -> "real_time_remote_biometric_identification",
                # which is how it actually appears in Python code). Word
                # boundaries still prevent "migration" matching "migrations/".
                inner = (
                    re.escape(keyword.lower())
                    .replace(r"\ ", r"[\s_-]")
                    .replace(r"\-", r"[\s_-]")
                )
                pattern = rf"(?<![\w]){inner}(?![\w])"
                count += len(re.findall(pattern, corpus))
            if count >= HIGH_RISK_HIT_THRESHOLD:
                matches.append((category, count))
        return matches
