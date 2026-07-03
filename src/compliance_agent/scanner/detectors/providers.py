"""Detect AI model provider usage via AST analysis of Python files.

Only actual import statements, constructor calls, and API attribute access
count as evidence — provider names in comments, docstrings, string literals,
URLs, or Markdown files are ignored.
"""

import ast
import re
from pathlib import Path

from compliance_agent.models.findings import Finding, Severity
from compliance_agent.scanner.detectors.base import BaseDetector

# Top-level module -> provider key
PROVIDER_MODULES: dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "mistralai": "mistral",
    "transformers": "local",
    "ollama": "local",
    "vllm": "local",
    "torch": "local",
    "llama_cpp": "local",
}

# Constructor class name -> provider key
CONSTRUCTOR_PROVIDERS: dict[str, str] = {
    "OpenAI": "openai",
    "AsyncOpenAI": "openai",
    "Anthropic": "anthropic",
    "AsyncAnthropic": "anthropic",
    "Mistral": "mistral",
    "MistralClient": "mistral",
}

# Dotted attribute fragment -> provider key (client.method() API patterns)
ATTRIBUTE_PROVIDERS: list[tuple[str, str]] = [
    ("chat.completions", "openai"),
    ("ChatCompletion", "openai"),
    ("messages.create", "anthropic"),
    ("messages.stream", "anthropic"),
]

PROVIDER_LABELS: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "local": "Local model stack",
    "google": "Google Generative AI",
    "mistral": "Mistral AI",
}

# Fallback for Python files that fail to parse: import lines only.
FALLBACK_IMPORT_REGEX = re.compile(
    r"^\s*(?:import|from)\s+(openai|anthropic|mistralai|transformers|ollama|vllm|torch"
    r"|llama_cpp|google\.generativeai)\b"
)


def _dotted_name(node: ast.expr) -> str | None:
    """Reconstruct a dotted name from Attribute/Name chains, else None."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _module_provider(module_name: str) -> str | None:
    if module_name == "google.generativeai" or module_name.startswith("google.generativeai."):
        return "google"
    return PROVIDER_MODULES.get(module_name.split(".")[0])


class ProviderDetector(BaseDetector):
    """Detects real usage of AI model providers in Python source files."""

    name = "providers"

    def analyze(self, file_path: Path, content: str) -> list[Finding]:
        if file_path.suffix != ".py":
            return []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            hits = self._fallback_hits(content)
        else:
            hits = self._ast_hits(tree)
        return [
            self._build_finding(file_path, provider, line_no)
            for provider, line_no in sorted(hits, key=lambda h: (h[0], h[1]))
        ]

    def _ast_hits(self, tree: ast.AST) -> set[tuple[str, int]]:
        hits: set[tuple[str, int]] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    provider = _module_provider(alias.name)
                    if provider:
                        hits.add((provider, node.lineno))
            elif isinstance(node, ast.ImportFrom) and node.module:
                provider = _module_provider(node.module)
                if provider:
                    hits.add((provider, node.lineno))
            elif isinstance(node, ast.Call):
                dotted = _dotted_name(node.func)
                if dotted:
                    class_name = dotted.split(".")[-1]
                    provider = CONSTRUCTOR_PROVIDERS.get(class_name)
                    if provider:
                        hits.add((provider, node.lineno))
            elif isinstance(node, ast.Attribute):
                dotted = _dotted_name(node)
                if dotted:
                    for fragment, provider in ATTRIBUTE_PROVIDERS:
                        if fragment in dotted:
                            hits.add((provider, node.lineno))
        return hits

    def _fallback_hits(self, content: str) -> set[tuple[str, int]]:
        """Regex over import lines only, for files with syntax errors."""
        hits: set[tuple[str, int]] = set()
        for line_no, line in enumerate(content.splitlines(), start=1):
            match = FALLBACK_IMPORT_REGEX.match(line)
            if match:
                provider = _module_provider(match.group(1))
                if provider:
                    hits.add((provider, line_no))
        return hits

    def _build_finding(self, file_path: Path, provider: str, line_no: int) -> Finding:
        label = PROVIDER_LABELS[provider]
        return self._make_finding(
            file_path=file_path,
            line_number=line_no,
            severity=Severity.INFO,
            category=f"provider:{provider}",
            message=f"{label} usage detected",
            description=(
                f"{label} import or API call found at line {line_no}. "
                "AI system usage means the project may fall under EU AI Act obligations."
            ),
            article="Art. 3 (definitions), Art. 6 (classification)",
            suggestion=(
                "Document the AI system's intended purpose and provider "
                "in your technical documentation."
            ),
        )
