"""
EU AI Act Article 17 — Quality Management System
Requirement: Providers of high-risk AI systems must put a documented quality
management system in place, covering regulatory-compliance strategy, design
and QA procedures, testing/validation procedures, data management, and an
accountability framework.

Usage: Fill in QMSDocument, call generate_markdown(), commit the result, and
review it every release.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class QMSDocument:
    """Inputs for the Art. 17(1) quality management system skeleton."""

    system_name: str
    compliance_strategy: str  # Art. 17(1)(a): regulatory compliance strategy
    design_and_qa_techniques: str  # Art. 17(1)(c): design control/verification
    testing_procedures: str  # Art. 17(1)(d)-(g): examination, testing, validation
    data_management_procedures: str  # Art. 17(1)(f): data management
    post_market_monitoring_ref: str  # Art. 17(1)(h): cross-ref to Art. 72 plan
    incident_reporting_ref: str  # Art. 17(1)(i): cross-ref to Art. 73 procedure
    accountability_framework: str  # Art. 17(1)(n): management responsibilities
    resource_management: str = ""  # Art. 17(1)(l)
    reviewed_by: list[str] = field(default_factory=list)


def generate_markdown(doc: QMSDocument) -> str:
    """Render an Art. 17(1)-style QMS skeleton in Markdown."""
    generated = datetime.now(UTC).isoformat(timespec="seconds")
    reviewers = ", ".join(doc.reviewed_by) or "_not yet reviewed_"

    return f"""# Quality Management System — {doc.system_name}

_EU AI Act Article 17(1). Generated {generated}. Review this document every
release and record who reviewed it._

## 1. Regulatory compliance strategy (17(1)(a))

{doc.compliance_strategy}

## 2. Design, QC and QA techniques (17(1)(c))

{doc.design_and_qa_techniques}

## 3. Examination, testing, and validation procedures (17(1)(d)-(g))

{doc.testing_procedures}

## 4. Data management procedures (17(1)(f))

{doc.data_management_procedures}

## 5. Post-market monitoring (17(1)(h), see Art. 72)

{doc.post_market_monitoring_ref}

## 6. Incident reporting (17(1)(i), see Art. 73)

{doc.incident_reporting_ref}

## 7. Resource management (17(1)(l))

{doc.resource_management or "_to be documented_"}

## 8. Accountability framework (17(1)(n))

{doc.accountability_framework}

## Review log

Reviewed by: {reviewers}
"""


def write_documentation(
    doc: QMSDocument, output: str | Path = "docs/quality-management.md"
) -> Path:
    """Generate and write the QMS document. Returns the path."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_markdown(doc), encoding="utf-8")
    return path


if __name__ == "__main__":
    demo = QMSDocument(
        system_name="Credit Risk Copilot",
        compliance_strategy="Annual internal audit against Art. 9-17 obligations.",
        design_and_qa_techniques="Design review + code review required before release.",
        testing_procedures="Unit, integration, and bias-evaluation suites run in CI.",
        data_management_procedures="See docs/data-governance.md for dataset provenance.",
        post_market_monitoring_ref="See docs/post-market-monitoring.md.",
        incident_reporting_ref="See docs/incident-reporting.md.",
        accountability_framework="Head of ML Platform is accountable for the QMS.",
        reviewed_by=["ml-platform-lead"],
    )
    print(generate_markdown(demo)[:400] + "...")
