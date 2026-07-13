"""Semantic Kernel framework detector: kernel setup, plugins, and agents.

Only LangChain/CrewAI/AutoGen/LangGraph were recognized as agent frameworks
previously — a Semantic Kernel-based agent (``ChatCompletionAgent``,
``AgentGroupChat``) triggered no Art. 14 oversight check at all.
"""

from compliance_agent.models.findings import Severity
from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule


class SemanticKernelDetector(FrameworkDetector):
    framework_name = "semantic_kernel"
    import_modules = frozenset({"semantic_kernel"})
    rules = (
        FrameworkRule(
            category="semantic_kernel_agent",
            patterns=(
                r"\bChatCompletionAgent\b",
                r"\bAgentGroupChat\b",
                r"\bOpenAIAssistantAgent\b",
                r"\bAzureAssistantAgent\b",
            ),
            message="Semantic Kernel agent detected",
            description=(
                "An autonomous agent (or multi-agent group chat) that can choose "
                "actions and call functions on its own. Requires an oversight "
                "mechanism before high-stakes actions execute."
            ),
            article="Art. 14",
            suggestion="Add a human oversight checkpoint before autonomous agent actions",
            severity=Severity.WARNING,
        ),
        FrameworkRule(
            category="semantic_kernel_kernel",
            patterns=(r"\bKernel\s*\(",),
            message="Semantic Kernel instance detected",
            description=(
                "The kernel orchestrates model calls, plugins, and memory — the "
                "system's core AI orchestration layer should be documented."
            ),
            article="Art. 11",
            suggestion=(
                "Document the kernel's configured services and plugins "
                "in your technical documentation"
            ),
        ),
        FrameworkRule(
            category="semantic_kernel_plugin",
            patterns=(
                r"\badd_plugin\s*\(",
                r"\bKernelFunction\b",
                r"@kernel_function\b",
            ),
            message="Semantic Kernel plugin/function detected",
            description=(
                "Plugins expose callable functions (including external actions) "
                "to the model. Plugin capabilities define the system's risk surface."
            ),
            article="Art. 9",
            suggestion="Document each plugin's capabilities and access scope in the risk register",
        ),
    )
