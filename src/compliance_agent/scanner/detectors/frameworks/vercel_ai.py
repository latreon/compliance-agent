"""Vercel AI SDK framework detector: generation calls, tool calling, agent loops."""

from compliance_agent.models.findings import Severity
from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule


class VercelAIDetector(FrameworkDetector):
    framework_name = "vercel-ai-sdk"
    # The bare "ai" package is the SDK core; each "@ai-sdk/*" package is a
    # provider adapter (openai, anthropic, ...) — importing either is
    # sufficient evidence the SDK is in use.
    import_modules = frozenset(
        {
            "ai",
            "@ai-sdk/openai",
            "@ai-sdk/anthropic",
            "@ai-sdk/google",
            "@ai-sdk/mistral",
            "@ai-sdk/cohere",
            "@ai-sdk/groq",
            "@ai-sdk/amazon-bedrock",
            "@ai-sdk/azure",
            "@ai-sdk/togetherai",
        }
    )
    rules = (
        FrameworkRule(
            category="vercel_generation",
            patterns=(
                r"\bgenerateText\s*\(",
                r"\bstreamText\s*\(",
                r"\buseChat\s*\(",
                r"\buseCompletion\s*\(",
            ),
            message="Vercel AI SDK generation call detected",
            description=(
                "Model output is generated or streamed to users. Users must be "
                "informed they are interacting with an AI system."
            ),
            article="Art. 50",
            suggestion="Add an AI disclosure notice where generated output reaches users",
        ),
        FrameworkRule(
            category="vercel_tools",
            patterns=(
                r"\btool\s*\(\s*\{",
                r"\btools\s*:\s*\{",
                r"\bexperimental_activeTools\b",
            ),
            message="Vercel AI SDK tool-calling detected",
            description=(
                "Tools give the model access to external systems. Each tool "
                "expands the risk surface."
            ),
            article="Art. 9",
            suggestion="Register each tool in your risk register with a mitigation",
        ),
        FrameworkRule(
            category="vercel_agent_loop",
            patterns=(r"\bmaxSteps\s*:", r"\bstopWhen\s*:", r"\bexperimental_continueSteps\b"),
            message="Vercel AI SDK multi-step agent loop detected",
            description=(
                "Multi-step tool-calling loops let the model take autonomous "
                "actions across several turns. Consider human-in-the-loop for "
                "high-stakes decisions."
            ),
            article="Art. 14",
            suggestion="Add a human oversight checkpoint before high-stakes tool calls",
            severity=Severity.WARNING,
        ),
        FrameworkRule(
            category="vercel_structured_output",
            patterns=(
                r"\bgenerateObject\s*\(",
                r"\bstreamObject\s*\(",
                r"\bexperimental_generateObject\s*\(",
                r"\bexperimental_streamObject\s*\(",
            ),
            message="Vercel AI SDK structured generation detected",
            description=(
                "Structured (schema-validated) model output should be "
                "documented as part of the system's technical documentation."
            ),
            article="Art. 11",
            suggestion="Document the output schema and its validation in your technical file",
        ),
    )
