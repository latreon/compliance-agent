"""
EU AI Act Article 11 / Annex IV — Technical Documentation
Requirement: High-risk AI systems must have technical documentation prepared
before market placement and kept up to date.

Usage: Fill in SystemDescription, call generate_markdown(), commit the result.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class SystemDescription:
    """Inputs for the Annex IV technical documentation skeleton."""

    system_name: str
    version: str
    provider: str  # legal entity responsible for the system
    intended_purpose: str  # what the system is for, and for whom
    ai_models: list[str]  # e.g. ["gpt-4o (OpenAI API)", "in-house ranker v3"]
    architecture_summary: str  # components and how data flows through them
    data_sources: list[str]  # training/reference data provenance
    human_oversight_measures: str  # Art. 14 measures in place
    performance_metrics: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


SECTION_ORDER = [
    "General description",
    "Intended purpose",
    "Models and components",
    "System architecture",
    "Data and data governance",
    "Human oversight",
    "Performance and metrics",
    "Known limitations",
]


def generate_markdown(desc: SystemDescription) -> str:
    """Render an Annex IV-style technical documentation skeleton in Markdown."""
    metrics = (
        "\n".join(f"- **{name}:** {value}" for name, value in desc.performance_metrics.items())
        or "- _to be measured_"
    )
    limitations = "\n".join(f"- {item}" for item in desc.limitations) or "- _none recorded yet_"
    models = "\n".join(f"- {model}" for model in desc.ai_models)
    sources = "\n".join(f"- {src}" for src in desc.data_sources)
    generated = datetime.now(UTC).isoformat(timespec="seconds")

    return f"""# Technical Documentation — {desc.system_name} v{desc.version}

_EU AI Act Article 11 / Annex IV. Generated {generated}. Keep this document
in version control and update it with every release._

## 1. General description

- **Provider:** {desc.provider}
- **System:** {desc.system_name}
- **Version:** {desc.version}

## 2. Intended purpose

{desc.intended_purpose}

## 3. Models and components

{models}

## 4. System architecture

{desc.architecture_summary}

## 5. Data and data governance (see Art. 10)

{sources}

## 6. Human oversight (see Art. 14)

{desc.human_oversight_measures}

## 7. Performance and metrics

{metrics}

## 8. Known limitations

{limitations}
"""


def write_documentation(desc: SystemDescription, output: str | Path = "TECHNICAL_DOC.md") -> Path:
    """Generate and write the documentation file. Returns the path."""
    path = Path(output)
    path.write_text(generate_markdown(desc), encoding="utf-8")
    return path


if __name__ == "__main__":
    demo = SystemDescription(
        system_name="Support Copilot",
        version="1.4.0",
        provider="Example GmbH",
        intended_purpose="Drafts replies for support staff; staff review before sending.",
        ai_models=["claude-sonnet-5 (Anthropic API)"],
        architecture_summary="FastAPI -> retrieval layer -> LLM -> human review queue.",
        data_sources=["internal knowledge base (curated, no personal data)"],
        human_oversight_measures="Every draft requires explicit agent approval before sending.",
        performance_metrics={"draft acceptance rate": "78%"},
        limitations=["No support for right-to-left languages yet"],
    )
    print(generate_markdown(demo)[:400] + "...")
