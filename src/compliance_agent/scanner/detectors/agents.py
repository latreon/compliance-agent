"""Detect agent-specific patterns: MCP servers, tool calls, multi-agent frameworks.

Precision rules:
- MCP requires concrete MCP usage (``mcp.server``, ``@server.tool``,
  ``.mcp.json``, an actual ``import mcp``) — never the bare word "mcp".
- Tool-call patterns only count in files that actually import an AI library.
- The word "agent" alone is never a finding; it needs AI context on the same
  line plus an AI import, or an AI import in a file whose path mentions agents.
"""

import re
from pathlib import Path

from compliance_agent.models.findings import Finding, Severity
from compliance_agent.scanner.detectors.base import BaseDetector, detect_ai_imports

MCP_PATTERNS = [
    r"\bmcp\.server\b",
    r"\bMcpServer\b",
    r"@server\.tool\b",
    r"@server\.prompt\b",
    r"\.mcp\.json\b",
    r"^\s*(?:from|import)\s+mcp\b",
]

TOOL_CALL_PATTERNS = [
    r"tools\s*=\s*\[",
    r"\btool_choice\b",
    r"\bfunction_call\b",
]

MULTI_AGENT_MODULES = {"crewai", "autogen", "langgraph"}
MULTI_AGENT_IMPORT_REGEX = re.compile(r"^\s*(?:from|import)\s+(crewai|autogen|langgraph)\b")

AGENT_WORD_REGEX = re.compile(r"\bagents?\b", re.IGNORECASE)
# Applied to a file *stem*, where words are joined by _ or - (snake/kebab case).
# ``\b`` treats ``_`` as a word char, so ``\bagents?\b`` never matched
# ``sales_agent`` / ``my_agents`` — the dominant Python filename convention.
AGENT_STEM_REGEX = re.compile(r"(?:^|[_-])agents?(?:[_-]|$)", re.IGNORECASE)
AGENT_CONTEXT_REGEX = re.compile(
    r"\b(tools?|llm|model|prompt|chain|workflow|autonomous)\b", re.IGNORECASE
)

# Specific framework classes are strong signals on their own.
PROMPT_TEMPLATE_PATTERNS = [
    r"\bChatPromptTemplate\b",
    r"\bPromptTemplate\b",
    r"\bSystemMessage\b",
]
# Generic snake_case name needs an AI import to count.
GATED_PROMPT_PATTERNS = [r"\bsystem_message\b"]


class AgentDetector(BaseDetector):
    """Detects agentic AI patterns that raise autonomy/oversight concerns."""

    name = "agents"

    def __init__(self) -> None:
        self._mcp = [re.compile(p) for p in MCP_PATTERNS]
        self._tool_calls = [re.compile(p) for p in TOOL_CALL_PATTERNS]
        self._prompt_templates = [re.compile(p) for p in PROMPT_TEMPLATE_PATTERNS]
        self._gated_prompt_templates = [re.compile(p) for p in GATED_PROMPT_PATTERNS]

    def analyze(self, file_path: Path, content: str) -> list[Finding]:
        findings: list[Finding] = []
        ai_imports = detect_ai_imports(file_path, content)

        findings.extend(self._detect_mcp(file_path, content))
        if ai_imports:
            findings.extend(self._detect_tool_calls(file_path, content))
            findings.extend(self._detect_multi_agent(file_path, content))
        findings.extend(self._detect_prompt_templates(file_path, content, ai_imports))
        return findings

    def _detect_mcp(self, file_path: Path, content: str) -> list[Finding]:
        findings: list[Finding] = []
        if file_path.name == ".mcp.json":
            findings.append(
                self._agent_finding(file_path, None, "mcp", "MCP configuration file detected")
            )
        # Concrete MCP code signals (`import mcp`, `mcp.server`, `.mcp.json`
        # references) only count in Python source. A README or YAML that merely
        # *documents* MCP setup is prose, not behaviour — matching it there
        # produced findings for projects that never actually use MCP.
        if file_path.suffix == ".py":
            for pattern in self._mcp:
                for line_no, _line in self._match_lines(content, pattern):
                    findings.append(
                        self._agent_finding(
                            file_path, line_no, "mcp", "MCP server/tooling detected"
                        )
                    )
        return findings

    def _detect_tool_calls(self, file_path: Path, content: str) -> list[Finding]:
        findings: list[Finding] = []
        for pattern in self._tool_calls:
            for line_no, _line in self._match_lines(content, pattern):
                findings.append(
                    self._agent_finding(
                        file_path,
                        line_no,
                        "tool-calls",
                        "LLM tool-calling detected",
                        severity=Severity.WARNING,
                    )
                )
        return findings

    def _detect_multi_agent(self, file_path: Path, content: str) -> list[Finding]:
        # Called only when the file already imports an AI library (gated by the
        # caller), so the "agent" word here is in a genuine AI context.
        findings: list[Finding] = []
        lines = self._lines(content)
        # 1. Direct import of a multi-agent framework.
        for line_no, line in enumerate(lines, start=1):
            if MULTI_AGENT_IMPORT_REGEX.match(line):
                findings.append(
                    self._agent_finding(
                        file_path,
                        line_no,
                        "multi-agent",
                        "Multi-agent framework import detected",
                        severity=Severity.WARNING,
                    )
                )
        # 2. "agent" word with AI context on the same line (file already imports AI).
        for line_no, line in enumerate(lines, start=1):
            if AGENT_WORD_REGEX.search(line) and AGENT_CONTEXT_REGEX.search(line):
                findings.append(
                    self._agent_finding(
                        file_path,
                        line_no,
                        "multi-agent",
                        "Agent pattern with AI context detected",
                        severity=Severity.WARNING,
                    )
                )
        # 3. File path mentions agents and the file imports an AI library.
        if not findings and AGENT_STEM_REGEX.search(file_path.stem):
            findings.append(
                self._agent_finding(
                    file_path,
                    None,
                    "multi-agent",
                    "Agent module using AI libraries detected",
                    severity=Severity.WARNING,
                )
            )
        return findings

    def _detect_prompt_templates(
        self, file_path: Path, content: str, ai_imports: set[str]
    ) -> list[Finding]:
        findings: list[Finding] = []
        patterns = list(self._prompt_templates)
        if ai_imports:
            patterns.extend(self._gated_prompt_templates)
        for pattern in patterns:
            for line_no, _line in self._match_lines(content, pattern):
                findings.append(
                    self._agent_finding(
                        file_path, line_no, "prompt-templates", "Prompt template usage detected"
                    )
                )
        return findings

    def _agent_finding(
        self,
        file_path: Path,
        line_no: int | None,
        category: str,
        message: str,
        severity: Severity = Severity.INFO,
    ) -> Finding:
        return self._make_finding(
            file_path=file_path,
            line_number=line_no,
            severity=severity,
            category=f"agent:{category}",
            message=message,
            description=(
                f"Agentic pattern `{category}` found. Autonomous tool execution "
                "requires human oversight measures under the EU AI Act."
            ),
            article="Art. 14 (human oversight)",
            suggestion=(
                "Ensure human oversight controls exist for autonomous actions "
                "(approval gates, logging, kill switches)."
            ),
        )
