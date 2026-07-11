"""LangChain framework detector: chains, agents, tools, memory."""

from compliance_agent.models.findings import Severity
from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule


class LangChainDetector(FrameworkDetector):
    framework_name = "langchain"
    import_modules = frozenset(
        {
            "langchain",
            "langchain_core",
            "langchain_community",
            "langchain_openai",
            "langchain_anthropic",
            # LangChain.js: same package family, npm-scoped.
            "@langchain/core",
            "@langchain/community",
            "@langchain/openai",
            "@langchain/anthropic",
        }
    )
    rules = (
        FrameworkRule(
            category="langchain_agent",
            patterns=(
                r"\bAgentExecutor\b",
                r"\bcreate_openai_functions_agent\b",
                r"\bcreate_react_agent\b",
                r"\bcreate_tool_calling_agent\b",
                r"\binitialize_agent\b",
                r"\bAgentType\b",
                # LangChain.js: same agent factories, camelCase.
                r"\bcreateOpenAIFunctionsAgent\b",
                r"\bcreateOpenAIToolsAgent\b",
                r"\bcreateReactAgent\b",
                r"\bcreateToolCallingAgent\b",
            ),
            message="LangChain agent detected with tool access",
            description=(
                "Agent can take autonomous actions via tools. Consider "
                "human-in-the-loop for high-stakes decisions."
            ),
            article="Art. 14",
            suggestion="Add HumanOversightCheckpoint for agent decisions",
            severity=Severity.WARNING,
        ),
        FrameworkRule(
            category="langchain_tools",
            patterns=(
                r"^\s*@tool\b",  # Python decorator syntax.
                r"\bTool\s*\(",
                r"\bBaseTool\b",
                r"\bStructuredTool\b",
                # LangChain.js: plain function calls/classes, no decorator syntax.
                r"\btool\s*\(",
                r"\bDynamicTool\b",
                r"\bDynamicStructuredTool\b",
            ),
            message="LangChain tool definition detected",
            description=(
                "Tools give the model access to external systems. Each tool "
                "expands the risk surface."
            ),
            article="Art. 9",
            suggestion="Register each tool in your risk register with a mitigation",
        ),
        FrameworkRule(
            category="langchain_memory",
            patterns=(
                r"\bConversationBufferMemory\b",
                r"\bConversationSummaryMemory\b",
                r"\bConversationBufferWindowMemory\b",
                r"\.save_context\s*\(",
                # LangChain.js drops the "Conversation" prefix on buffer memories.
                r"\bBufferMemory\b",
                r"\bBufferWindowMemory\b",
            ),
            message="LangChain conversation memory detected",
            description=(
                "Memory stores conversation history. Stored interactions fall "
                "under record-keeping and retention duties."
            ),
            article="Art. 12",
            suggestion="Ensure conversation logs meet the 6-month retention requirement",
        ),
        FrameworkRule(
            category="langchain_chain",
            patterns=(
                r"\bLLMChain\s*\(",
                r"\bConversationChain\s*\(",
                r"\bSequentialChain\s*\(",
                r"\bchain\.(invoke|predict|run)\b",
            ),
            message="LangChain chain processing user input detected",
            description=(
                "Chains process user input through the model. Users must be "
                "informed they are interacting with an AI system."
            ),
            article="Art. 50",
            suggestion="Add an AI disclosure notice where chain output reaches users",
        ),
    )
