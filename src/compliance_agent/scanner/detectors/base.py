"""Base detector interface and shared AI-context helpers."""

import re
from abc import ABC, abstractmethod
from pathlib import Path

from compliance_agent.models.findings import Finding, Severity
from compliance_agent.scanner.parser import JS_TS_SUFFIXES, extract_imports, top_level_modules

# Top-level Python packages whose import marks a file as AI-relevant.
AI_TOP_LEVEL_MODULES_PY = {
    "openai",
    "anthropic",
    "mistralai",
    "cohere",
    "litellm",
    "groq",
    "together",
    "replicate",
    "huggingface_hub",
    "transformers",
    "ollama",
    "vllm",
    "torch",
    "llama_cpp",
    "langchain",
    "langchain_core",
    "langchain_community",
    "langchain_openai",
    "langchain_anthropic",
    "langchain_mistralai",
    "langchain_cohere",
    "langchain_groq",
    "langchain_together",
    "langchain_aws",
    "langchain_google_vertexai",
    "langchain_google_genai",
    "langchain_ollama",
    "langchain_huggingface",
    "crewai",
    "autogen",
    "langgraph",
}

# npm packages (scoped packages keyed as "@scope/name", matching
# top_level_modules' resolution) whose import marks a file as AI-relevant.
AI_TOP_LEVEL_MODULES_JS = {
    "openai",
    "@anthropic-ai/sdk",
    "cohere-ai",
    "groq-sdk",
    "together-ai",
    "replicate",
    "ollama",
    "node-llama-cpp",
    "@xenova/transformers",
    "@huggingface/inference",
    "@google/generative-ai",
    "@google/genai",
    "@google-cloud/vertexai",
    "@aws-sdk/client-bedrock-runtime",
    "@mistralai/mistralai",
    "langchain",
    "@langchain/core",
    "@langchain/community",
    "@langchain/openai",
    "@langchain/anthropic",
    "@langchain/mistralai",
    "@langchain/cohere",
    "@langchain/groq",
    "@langchain/aws",
    "@langchain/google-vertexai",
    "@langchain/google-genai",
    "@langchain/ollama",
    "@langchain/langgraph",
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
    "llamaindex",
}

# Union used by callers that do not need the per-language split.
AI_TOP_LEVEL_MODULES = AI_TOP_LEVEL_MODULES_PY | AI_TOP_LEVEL_MODULES_JS

_ALLOWED_AI_IMPORT_SUFFIXES = frozenset({".py"}) | JS_TS_SUFFIXES


def detect_ai_imports(file_path: Path, content: str) -> set[str]:
    """Return AI-related modules actually imported by a Python or JS/TS file.

    Uses AST-based (Python) or comment-aware regex-based (JS/TS) import
    extraction, so provider names in comments, docstrings, or string literals
    do not count.
    """
    if file_path.suffix not in _ALLOWED_AI_IMPORT_SUFFIXES:
        return set()
    imports = extract_imports(file_path, content)
    found = top_level_modules(imports) & AI_TOP_LEVEL_MODULES
    for name in imports:
        if name == "google.generativeai" or name.startswith("google.generativeai."):
            found.add("google.generativeai")
        elif name == "google.genai" or name.startswith("google.genai."):
            found.add("google.genai")
    return found


class BaseDetector(ABC):
    """Base class for all detectors.

    Subclasses implement `analyze` to inspect a single file's content and
    return zero or more findings.
    """

    name: str = "base"
    # Cache of the last file's split lines, so multiple patterns matched against
    # the same content do not re-split it. Class-level default keeps this safe
    # for subclasses whose __init__ does not call super().
    _lines_cache: tuple[str, list[str]] | None = None

    @abstractmethod
    def analyze(self, file_path: Path, content: str) -> list[Finding]:
        """Analyze a file and return findings."""

    def _lines(self, content: str) -> list[str]:
        """Split content into lines once, reusing the result for the same string.

        The cache holds a *reference* to the content object (not just its id),
        so the cached string stays alive and its identity cannot be reused by a
        later, different file of the same length — an identity check is then
        sound. Detector instances are reused across files, so keying on id alone
        would return stale lines when CPython recycles a freed string's address.
        """
        cache = self._lines_cache
        if cache is not None and cache[0] is content:
            return cache[1]
        lines = content.splitlines()
        self._lines_cache = (content, lines)
        return lines

    def _match_lines(self, content: str, pattern: re.Pattern[str]) -> list[tuple[int, str]]:
        """Return (1-based line number, line) pairs matching the pattern."""
        matches = []
        for line_no, line in enumerate(self._lines(content), start=1):
            if pattern.search(line):
                matches.append((line_no, line))
        return matches

    def _make_finding(
        self,
        *,
        file_path: Path,
        line_number: int | None,
        severity: Severity,
        category: str,
        message: str,
        description: str,
        article: str | None = None,
        suggestion: str | None = None,
    ) -> Finding:
        """Build a Finding with a deterministic ID."""
        finding_id = f"{self.name}:{category}:{file_path}:{line_number or 0}"
        return Finding(
            id=finding_id,
            file_path=str(file_path),
            line_number=line_number,
            detector=self.name,
            severity=severity,
            category=category,
            message=message,
            description=description,
            article=article,
            suggestion=suggestion,
        )
