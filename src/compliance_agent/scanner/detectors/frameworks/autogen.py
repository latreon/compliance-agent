"""AutoGen framework detector: agents, group chats, function registration."""

from compliance_agent.models.findings import Severity
from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule


class AutoGenDetector(FrameworkDetector):
    framework_name = "autogen"
    import_modules = frozenset({"autogen", "autogen_agentchat", "autogen_core"})
    rules = (
        FrameworkRule(
            category="autogen_assistant",
            patterns=(r"\bAssistantAgent\s*\(",),
            message="AutoGen assistant agent detected",
            description=(
                "Users interact with an AI assistant. They must be informed "
                "they are talking to an AI system."
            ),
            article="Art. 50",
            suggestion="Add an AI disclosure notice to assistant conversations",
        ),
        FrameworkRule(
            category="autogen_userproxy",
            patterns=(r"\bUserProxyAgent\s*\(", r"\bhuman_input_mode\b"),
            message="AutoGen user proxy with human input mode detected",
            description=(
                "human_input_mode controls when humans intervene. 'NEVER' "
                "removes oversight; 'TERMINATE' defers it to the end."
            ),
            article="Art. 14",
            suggestion="Prefer human_input_mode='ALWAYS' for high-stakes flows",
            severity=Severity.WARNING,
        ),
        FrameworkRule(
            category="autogen_groupchat",
            patterns=(
                r"\bGroupChat\s*\(",
                r"\bGroupChatManager\s*\(",
            ),
            message="AutoGen GroupChat with multiple agents detected",
            description="Multi-agent conversation requires logging for traceability.",
            article="Art. 12",
            suggestion="Enable conversation logging for an audit trail",
            severity=Severity.WARNING,
        ),
        FrameworkRule(
            category="autogen_tools",
            patterns=(
                r"\bregister_function\s*\(",
                r"\bregister_for_llm\b",
                r"\bregister_for_execution\b",
                r"\bcode_execution_config\b",
            ),
            message="AutoGen function/code execution detected",
            description=(
                "Registered functions and code execution give agents access to "
                "external systems — a significant risk surface."
            ),
            article="Art. 9",
            suggestion="Sandbox code execution and register each function as a risk",
            severity=Severity.WARNING,
        ),
        FrameworkRule(
            category="autogen_chat",
            patterns=(r"\binitiate_chat\s*\(",),
            message="AutoGen conversation initiation detected",
            description="Agent conversations should be recorded for traceability.",
            article="Art. 12",
            suggestion="Persist chat transcripts with retention metadata",
        ),
    )
