"""Detect agent-specific patterns: MCP servers, tool calls, multi-agent frameworks."""

import re
from pathlib import Path

from compliance_agent.models.findings import Finding, Severity
from compliance_agent.scanner.detectors.base import BaseDetector

AGENT_PATTERNS: dict[str, tuple[list[str], str, Severity]] = {
    "mcp": (
        [
            r"\bMcpServer\b",
            r"@server\.tool\b",
            r"@server\.prompt\b",
            r"\.mcp\.json",
            r"\bmcp_config\b",
            r"\bfrom\s+mcp\b",
            r"\bimport\s+mcp\b",
        ],
        "MCP server/tooling detected",
        Severity.INFO,
    ),
    "tool-calls": (
        [
            r"tools\s*=\s*\[",
            r"\bfunction_call\b",
            r"\btool_choice\b",
            r"@tool\b",
            r"\bdef\s+tool\w*\s*\(",
        ],
        "LLM tool-calling detected",
        Severity.WARNING,
    ),
    "multi-agent": (
        [
            r"\bcrewai\b",
            r"\bautogen\b",
            r"\blanggraph\b",
            r"\bagent\b",
            r"\bswarm\b",
        ],
        "Multi-agent framework/pattern detected",
        Severity.WARNING,
    ),
    "prompt-templates": (
        [
            r"\bChatPromptTemplate\b",
            r"\bPromptTemplate\b",
            r"\bsystem_message\b",
            r"\bSystemMessage\b",
        ],
        "Prompt template usage detected",
        Severity.INFO,
    ),
}


class AgentDetector(BaseDetector):
    """Detects agentic AI patterns that raise autonomy/oversight concerns."""

    name = "agents"

    def __init__(self) -> None:
        self._compiled: dict[str, tuple[list[re.Pattern[str]], str, Severity]] = {
            category: ([re.compile(p, re.IGNORECASE) for p in patterns], message, severity)
            for category, (patterns, message, severity) in AGENT_PATTERNS.items()
        }

    def analyze(self, file_path: Path, content: str) -> list[Finding]:
        findings: list[Finding] = []
        for category, (patterns, message, severity) in self._compiled.items():
            seen_lines: set[int] = set()
            for pattern in patterns:
                for line_no, line in self._match_lines(content, pattern):
                    if line_no in seen_lines:
                        continue
                    seen_lines.add(line_no)
                    findings.append(
                        self._make_finding(
                            file_path=file_path,
                            line_number=line_no,
                            severity=severity,
                            category=f"agent:{category}",
                            message=message,
                            description=(
                                f"Agentic pattern `{category}` found: "
                                f"`{line.strip()[:120]}`. Autonomous tool execution "
                                "requires human oversight measures under the EU AI Act."
                            ),
                            article="Art. 14 (human oversight)",
                            suggestion=(
                                "Ensure human oversight controls exist for autonomous "
                                "actions (approval gates, logging, kill switches)."
                            ),
                        )
                    )
        return findings
