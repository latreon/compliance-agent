"""Article 15 — Accuracy, robustness, and cybersecurity."""

from compliance_agent.analyzer.articles.base import (
    MIN_ARTIFACT_CHARS,
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity

# Filename patterns for tests that specifically target adversarial/robustness
# behavior — a generic `tests/test_models.py` proves a test suite exists, but
# says nothing about robustness against errors or adversarial inputs, which is
# the actual Art. 15 obligation. Checked against both a top-level `tests/`
# and `test/` directory. `**/` alone (no separate zero-depth variant) already
# matches a file directly inside the directory too — `pathlib.Path.glob`
# treats `**` as zero-or-more directories, not one-or-more.
_ADVERSARIAL_TEST_KEYWORDS = ("adversarial", "robust", "security", "fuzz", "edge_case", "malicious")
_ADVERSARIAL_TEST_GLOBS = tuple(
    f"{test_dir}/**/*{keyword}*"
    for keyword in _ADVERSARIAL_TEST_KEYWORDS
    for test_dir in ("tests", "test")
)


class Art15Analyzer(ArticleAnalyzer):
    article_number = 15
    article_title = "Accuracy, robustness, and cybersecurity"

    def applies(self, scan_result: ScanResult) -> bool:
        # Art. 15 (accuracy, robustness, cybersecurity) is a Chapter III,
        # Section 2 obligation for HIGH-RISK systems only. Previously it fired on
        # any AI usage, emitting HIGH-severity gaps that cite statutory language
        # ("must ... per Art. 15") against limited/minimal-risk chatbots —
        # overstating the legal obligation. Mirrors the Art. 13 gating fix.
        return is_high_risk(scan_result)

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return super().not_applicable_reason(scan_result)

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        # These project-wide code signals cannot be localised to the AI call
        # site with static keyword matching: a ``try/except`` or a
        # ``validate_email`` helper elsewhere in the repo says nothing about
        # whether the model call itself is guarded. So they are treated as weak
        # evidence (mention -> UNVERIFIED, "verify manually"), never as a
        # confirmed mechanism (MET). Absence still yields MISSING.
        has_error_handling = probe.code_mentions("try:", "except ", "try {", "catch (", "catch(")
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
        return [
            Requirement(
                name="Accuracy metrics should be documented",
                status=evidence(
                    mechanism=False,
                    mention=probe.docs_mention(
                        "accuracy", "accurate", "precision", "recall", "f1", "benchmark"
                    ),
                ),
                severity=Severity.WARNING,
                details="AI systems should have documented accuracy levels per Art. 15(1).",
                suggestion="Document model accuracy, precision, recall, and known error rates",
            ),
            Requirement(
                name="Error handling mechanisms required",
                status=evidence(mechanism=False, mention=has_error_handling),
                severity=Severity.HIGH,
                details=(
                    "Error handling around AI usage could not be verified. Systems "
                    "must handle errors and inconsistencies per Art. 15. Confirm "
                    "that model calls specifically are wrapped with error handling "
                    "and fallbacks."
                ),
                suggestion="Add try/except around model calls, fallbacks, and error logging",
            ),
            Requirement(
                name="Cybersecurity measures required",
                status=evidence(mechanism=False, mention=has_security),
                severity=Severity.HIGH,
                details=(
                    "Cybersecurity controls around AI usage could not be verified. "
                    "Systems must be resilient against attacks and misuse per "
                    "Art. 15(5). Confirm input validation, rate limiting, and "
                    "access controls apply to the AI-facing surface."
                ),
                suggestion="Implement input validation, rate limiting, and access controls",
            ),
            Requirement(
                name="Robustness testing recommended",
                status=evidence(
                    # A generic test suite (any file under tests/) proves tests
                    # exist, not that any of them target robustness or
                    # adversarial-input behavior — the actual Art. 15(4)
                    # obligation. Require a test file whose name says so.
                    mechanism=probe.any_file(
                        *_ADVERSARIAL_TEST_GLOBS, min_content_chars=MIN_ARTIFACT_CHARS
                    ),
                    mention=probe.docs_mention("adversarial", "robustness"),
                ),
                severity=Severity.WARNING,
                details=(
                    "No adversarial/robustness-specific tests or documentation "
                    "found. Systems should be robust against errors and "
                    "adversarial inputs, not just covered by a general test suite."
                ),
                suggestion=(
                    "Add tests that specifically target edge cases, malformed "
                    "input, and adversarial prompts (e.g. tests/test_adversarial_inputs.py)"
                ),
            ),
        ]
