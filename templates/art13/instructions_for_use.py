"""
EU AI Act Article 13 — Instructions for Use (to Deployers)
Requirement: High-risk AI systems must be accompanied by concise, complete,
correct, and clear instructions for use covering the provider's identity,
intended purpose, accuracy/robustness/cybersecurity levels, known/foreseeable
limitations, human oversight measures, expected lifetime and maintenance,
and how to interpret outputs (Art. 13(2)-(3)).

Usage: Fill in InstructionsForUse, call write_instructions() to produce
docs/instructions.md, and keep it versioned alongside the system it describes.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class InstructionsForUse:
    """Inputs for the Art. 13(2)-(3) instructions-for-use document."""

    system_name: str
    version: str
    provider: str  # legal entity + contact details
    intended_purpose: str
    accuracy_metrics: dict[str, str] = field(default_factory=dict)
    known_limitations: list[str] = field(default_factory=list)
    foreseeable_misuse: list[str] = field(default_factory=list)
    human_oversight_measures: str = ""
    input_data_requirements: str = ""
    output_interpretation_guidance: str = ""
    expected_lifetime: str = ""  # e.g. "12 months between mandatory reviews"
    maintenance_measures: str = ""


def generate_markdown(doc: InstructionsForUse) -> str:
    """Render Art. 13(2)-(3) instructions for use in Markdown."""
    metrics = (
        "\n".join(f"- **{name}:** {value}" for name, value in doc.accuracy_metrics.items())
        or "- _to be measured_"
    )
    limitations = (
        "\n".join(f"- {item}" for item in doc.known_limitations) or "- _none recorded yet_"
    )
    misuse = "\n".join(f"- {item}" for item in doc.foreseeable_misuse) or "- _none recorded yet_"
    generated = datetime.now(UTC).isoformat(timespec="seconds")

    return f"""# Instructions for Use — {doc.system_name} v{doc.version}

_EU AI Act Article 13(2)-(3). Generated {generated}. Give this document to
every deployer before they operate the system; update it every release._

## 1. Provider identity

{doc.provider}

## 2. Intended purpose

{doc.intended_purpose}

## 3. Accuracy, robustness, and cybersecurity (see Art. 15)

{metrics}

## 4. Known and foreseeable limitations

{limitations}

## 5. Foreseeable misuse

{misuse}

## 6. Human oversight measures (see Art. 14)

{doc.human_oversight_measures or "_to be documented_"}

## 7. Input data requirements

{doc.input_data_requirements or "_to be documented_"}

## 8. How to interpret outputs

{doc.output_interpretation_guidance or "_to be documented_"}

## 9. Expected lifetime and maintenance

- **Expected lifetime:** {doc.expected_lifetime or "_to be documented_"}
- **Maintenance measures:** {doc.maintenance_measures or "_to be documented_"}
"""


def write_instructions(
    doc: InstructionsForUse, output: str | Path = "docs/instructions.md"
) -> Path:
    """Generate and write the instructions-for-use file. Returns the path."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_markdown(doc), encoding="utf-8")
    return path


if __name__ == "__main__":
    demo = InstructionsForUse(
        system_name="Resume Screener",
        version="2.1.0",
        provider="Example GmbH, compliance@example.com",
        intended_purpose=(
            "Ranks incoming job applications by fit against a role's stated "
            "requirements. Output is a recommendation, not a hiring decision."
        ),
        accuracy_metrics={"precision@10": "0.71", "measured on": "held-out 2025 hires"},
        known_limitations=[
            "Underperforms on non-English resumes",
            "Not validated for executive-level roles",
        ],
        foreseeable_misuse=["Using the score as the sole basis for rejection"],
        human_oversight_measures=(
            "A recruiter reviews and can override every ranking before rejection."
        ),
        input_data_requirements="Resume must be plain text or PDF, under 10 pages.",
        output_interpretation_guidance="Score is 0-100 relative fit, not a probability of success.",
        expected_lifetime="Re-validate accuracy every 6 months or after a model change.",
        maintenance_measures="Retraining triggers a new version and a new instructions document.",
    )
    print(generate_markdown(demo)[:400] + "...")
