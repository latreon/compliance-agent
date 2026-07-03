"""Detect AI model provider usage (OpenAI, Anthropic, local models, etc.)."""

import re
from pathlib import Path

from compliance_agent.models.findings import Finding, Severity
from compliance_agent.scanner.detectors.base import BaseDetector

PROVIDER_PATTERNS: dict[str, list[str]] = {
    "openai": [
        r"\bimport\s+openai\b",
        r"\bfrom\s+openai\b",
        r"\bOpenAI\s*\(",
        r"\bopenai\.ChatCompletion\b",
        r"\bclient\.chat\.completions\b",
    ],
    "anthropic": [
        r"\bimport\s+anthropic\b",
        r"\bfrom\s+anthropic\b",
        r"\bAnthropic\s*\(",
        r"\bclient\.messages\b",
    ],
    "local": [
        r"\btransformers\b",
        r"\bollama\b",
        r"llama\.cpp",
        r"\bvllm\b",
        r"\bimport\s+torch\b",
        r"\bfrom\s+torch\b",
    ],
    "google": [
        r"\bfrom\s+google\.generativeai\b",
        r"\bimport\s+google\.generativeai\b",
        r"\bgenai\b",
    ],
    "mistral": [
        r"\bimport\s+mistralai\b",
        r"\bfrom\s+mistralai\b",
    ],
}

PROVIDER_LABELS: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "local": "Local model stack",
    "google": "Google Generative AI",
    "mistral": "Mistral AI",
}


class ProviderDetector(BaseDetector):
    """Detects usage of AI model providers in source files."""

    name = "providers"

    def __init__(self) -> None:
        self._compiled: dict[str, list[re.Pattern[str]]] = {
            provider: [re.compile(p) for p in patterns]
            for provider, patterns in PROVIDER_PATTERNS.items()
        }

    def analyze(self, file_path: Path, content: str) -> list[Finding]:
        findings: list[Finding] = []
        for provider, patterns in self._compiled.items():
            seen_lines: set[int] = set()
            for pattern in patterns:
                for line_no, line in self._match_lines(content, pattern):
                    if line_no in seen_lines:
                        continue
                    seen_lines.add(line_no)
                    label = PROVIDER_LABELS[provider]
                    findings.append(
                        self._make_finding(
                            file_path=file_path,
                            line_number=line_no,
                            severity=Severity.INFO,
                            category=f"provider:{provider}",
                            message=f"{label} usage detected",
                            description=(
                                f"{label} API/library usage found: `{line.strip()[:120]}`. "
                                "AI system usage means the project may fall under "
                                "EU AI Act obligations."
                            ),
                            article="Art. 3 (definitions), Art. 6 (classification)",
                            suggestion=(
                                "Document the AI system's intended purpose and provider "
                                "in your technical documentation."
                            ),
                        )
                    )
        return findings
