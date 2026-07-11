"""
EU AI Act Article 50(3) — Emotion Recognition / Biometric Categorisation Disclosure
Requirement: Deployers of an emotion-recognition system or a biometric
categorisation system must inform the natural persons exposed to it that the
system is operating, and process their personal data in accordance with
applicable data-protection law.

Usage: Call notice_for() before/at the point of exposure and render it to the
affected person (banner, spoken notice, printed sign, etc.).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class BiometricSystemKind(StrEnum):
    EMOTION_RECOGNITION = "emotion_recognition"
    BIOMETRIC_CATEGORISATION = "biometric_categorisation"


DISCLOSURE_TEMPLATES = {
    BiometricSystemKind.EMOTION_RECOGNITION: (
        "This area uses an emotion-recognition system (EU AI Act, Art. 50(3))."
    ),
    BiometricSystemKind.BIOMETRIC_CATEGORISATION: (
        "This area uses a biometric-categorisation system (EU AI Act, Art. 50(3))."
    ),
}


@dataclass
class EmotionExposureNotice:
    """Disclosure record for one exposure of a person to the system."""

    system_kind: BiometricSystemKind
    location: str  # where the exposure occurs, e.g. "store entrance camera"
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = datetime.now(UTC).isoformat(timespec="seconds")

    @property
    def text(self) -> str:
        return DISCLOSURE_TEMPLATES[self.system_kind]


def notice_for(system_kind: BiometricSystemKind, location: str) -> EmotionExposureNotice:
    """Build the disclosure notice for a given exposure point."""
    return EmotionExposureNotice(system_kind=system_kind, location=location)


def html_banner(notice: EmotionExposureNotice) -> str:
    """Signage-style HTML banner for physical or on-screen display."""
    return (
        '<div class="ai-biometric-notice" role="status">\n'
        f"  {notice.text}\n"
        "</div>"
    )


if __name__ == "__main__":
    notice = notice_for(BiometricSystemKind.EMOTION_RECOGNITION, location="support call IVR")
    print(notice.text)
    print(html_banner(notice))
