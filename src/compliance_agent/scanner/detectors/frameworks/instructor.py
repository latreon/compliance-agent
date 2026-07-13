"""Instructor framework detector: structured/validated LLM output extraction."""

from compliance_agent.models.findings import Severity
from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule


class InstructorDetector(FrameworkDetector):
    framework_name = "instructor"
    import_modules = frozenset({"instructor"})
    rules = (
        FrameworkRule(
            category="instructor_structured_output",
            patterns=(
                r"\binstructor\.from_openai\b",
                r"\binstructor\.from_provider\b",
                r"\bresponse_model\s*=",
            ),
            message="Instructor structured-output extraction detected",
            description=(
                "Model output is parsed into a validated schema. Schema "
                "validation is a concrete robustness mechanism and should be "
                "documented as part of output-accuracy controls."
            ),
            article="Art. 15",
            suggestion=(
                "Document the response schema and retry/validation behavior in your technical file"
            ),
            severity=Severity.INFO,
        ),
    )
