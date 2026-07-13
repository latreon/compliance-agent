"""DSPy framework detector: modules, signatures, and ReAct agents."""

from compliance_agent.models.findings import Severity
from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule


class DSPyDetector(FrameworkDetector):
    framework_name = "dspy"
    import_modules = frozenset({"dspy"})
    rules = (
        FrameworkRule(
            category="dspy_agent",
            patterns=(r"\bdspy\.ReAct\b", r"\bReAct\s*\("),
            message="DSPy ReAct agent detected",
            description=(
                "A ReAct module lets the model choose and call tools iteratively "
                "to answer a query. High-stakes tool actions need a human "
                "oversight point."
            ),
            article="Art. 14",
            suggestion="Add a human oversight checkpoint before high-stakes tool actions",
            severity=Severity.WARNING,
        ),
        FrameworkRule(
            category="dspy_module",
            patterns=(
                r"\bdspy\.Predict\b",
                r"\bdspy\.ChainOfThought\b",
                r"\bdspy\.Module\b",
                r"\bdspy\.Signature\b",
            ),
            message="DSPy module/signature detected",
            description=(
                "DSPy programs compile prompts from declared signatures. The "
                "compiled program's behavior should be documented for audits."
            ),
            article="Art. 11",
            suggestion=(
                "Document the DSPy signatures and compiled prompt strategy "
                "in your technical documentation"
            ),
        ),
        FrameworkRule(
            category="dspy_optimizer",
            patterns=(
                r"\bBootstrapFewShot\b",
                r"\bMIPROv2\b",
                r"\bteleprompt\b",
            ),
            message="DSPy prompt optimizer detected",
            description=(
                "An automated prompt/example optimizer changes model behavior "
                "based on training data — this affects robustness and must be "
                "evaluated like any other model change."
            ),
            article="Art. 15",
            suggestion="Evaluate and record the optimizer's impact on output accuracy/robustness",
        ),
    )
