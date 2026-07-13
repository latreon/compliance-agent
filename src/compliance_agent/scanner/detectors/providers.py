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
from compliance_agent.scanner.parser import JS_TS_SUFFIXES, iter_js_import_specs, strip_js_comments

# Top-level module -> provider key
PROVIDER_MODULES: dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "mistralai": "mistral",
    "cohere": "cohere",
    "litellm": "litellm",
    "groq": "groq",
    "together": "together",
    "replicate": "replicate",
    "huggingface_hub": "huggingface",
    "transformers": "local",
    "ollama": "local",
    "vllm": "local",
    "torch": "local",
    "llama_cpp": "local",
    "fireworks": "fireworks",
    "xai_sdk": "xai",
    "deepseek": "deepseek",
    "deepseek_sdk": "deepseek",
    "langchain_deepseek": "deepseek",
    "langchain_fireworks": "fireworks",
    "langchain_xai": "xai",
    # LangChain provider-binding packages: importing one is direct evidence of
    # that provider, even before a constructor call is seen.
    "langchain_openai": "openai",
    "langchain_anthropic": "anthropic",
    "langchain_mistralai": "mistral",
    "langchain_cohere": "cohere",
    "langchain_groq": "groq",
    "langchain_together": "together",
    "langchain_aws": "bedrock",
    "langchain_google_vertexai": "vertex",
    "langchain_google_genai": "google",
    "langchain_ollama": "local",
    "langchain_huggingface": "huggingface",
    # npm packages. "openai" and "replicate" are the same package name on both
    # registries and already covered above.
    "@anthropic-ai/sdk": "anthropic",
    "cohere-ai": "cohere",
    "groq-sdk": "groq",
    "together-ai": "together",
    "@huggingface/inference": "huggingface",
    "@google/generative-ai": "google",
    "@google/genai": "google",
    "@google-cloud/vertexai": "vertex",
    "@aws-sdk/client-bedrock-runtime": "bedrock",
    "@mistralai/mistralai": "mistral",
    "@xenova/transformers": "local",
    "node-llama-cpp": "local",
    # LangChain.js provider-binding packages, mirroring the Python ones above.
    "@langchain/openai": "openai",
    "@langchain/anthropic": "anthropic",
    "@langchain/mistralai": "mistral",
    "@langchain/cohere": "cohere",
    "@langchain/groq": "groq",
    "@langchain/aws": "bedrock",
    "@langchain/google-vertexai": "vertex",
    "@langchain/google-genai": "google",
    "@langchain/ollama": "local",
    # Vercel AI SDK provider adapters — the bare "ai" package is provider-
    # agnostic (it is paired with one of these) and is intentionally absent.
    "@ai-sdk/openai": "openai",
    "@ai-sdk/anthropic": "anthropic",
    "@ai-sdk/google": "google",
    "@ai-sdk/mistral": "mistral",
    "@ai-sdk/cohere": "cohere",
    "@ai-sdk/groq": "groq",
    "@ai-sdk/amazon-bedrock": "bedrock",
    "@ai-sdk/togetherai": "together",
    "@ai-sdk/fireworks": "fireworks",
    "@ai-sdk/xai": "xai",
    "@ai-sdk/deepseek": "deepseek",
    # Azure-hosted OpenAI models via the Vercel AI SDK. Treated as "openai" to
    # match the AzureOpenAI/AzureChatOpenAI constructor convention above (it is
    # the OpenAI model family, Azure-hosted).
    "@ai-sdk/azure": "openai",
}

# Constructor class name -> provider key
CONSTRUCTOR_PROVIDERS: dict[str, str] = {
    "OpenAI": "openai",
    "AsyncOpenAI": "openai",
    "AzureOpenAI": "openai",  # still the OpenAI SDK, Azure-hosted
    "AsyncAzureOpenAI": "openai",
    "ChatOpenAI": "openai",  # LangChain wrapper
    "AzureChatOpenAI": "openai",  # LangChain wrapper
    "Anthropic": "anthropic",
    "AsyncAnthropic": "anthropic",
    "AnthropicBedrock": "bedrock",  # Anthropic models served via AWS Bedrock
    "ChatAnthropic": "anthropic",  # LangChain wrapper
    "Mistral": "mistral",
    "MistralClient": "mistral",
    "ChatMistralAI": "mistral",  # LangChain wrapper
    "Groq": "groq",
    "ChatGroq": "groq",  # LangChain wrapper
    "Together": "together",
    "ChatTogether": "together",  # LangChain wrapper
    "Replicate": "replicate",
    "InferenceClient": "huggingface",
    "ChatHuggingFace": "huggingface",  # LangChain wrapper
    "ChatBedrock": "bedrock",  # LangChain wrapper
    "BedrockChat": "bedrock",  # LangChain wrapper (legacy name)
    "ChatVertexAI": "vertex",  # LangChain wrapper
    "ChatGoogleGenerativeAI": "google",  # LangChain wrapper
    "ChatLiteLLM": "litellm",  # LangChain wrapper
    "ChatOllama": "local",  # LangChain wrapper
    "Fireworks": "fireworks",
    "AsyncFireworks": "fireworks",
    "ChatFireworks": "fireworks",  # LangChain wrapper
    "ChatXAI": "xai",  # LangChain wrapper
    "ChatDeepSeek": "deepseek",  # LangChain wrapper
}

# Dotted attribute fragment -> provider key (client.method() API patterns).
# Applied ONLY as a last resort, when no import/constructor already identified a
# provider in the file — many providers (Groq, Together, Fireworks, local OpenAI
# shims) expose an OpenAI-compatible ``chat.completions`` surface, so this
# fragment alone cannot prove the client is OpenAI.
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
    "vertex": "Google Vertex AI",
    "mistral": "Mistral AI",
    "cohere": "Cohere",
    "litellm": "LiteLLM (multi-provider router)",
    "groq": "Groq",
    "together": "Together AI",
    "replicate": "Replicate",
    "huggingface": "Hugging Face",
    "bedrock": "AWS Bedrock",
    "fireworks": "Fireworks AI",
    "xai": "xAI (Grok)",
    "deepseek": "DeepSeek",
}

# Fallback for Python files that fail to parse: import lines only.
#
# ``from google import genai`` is handled as a special case (not via this
# alternation): the provider lives in module + imported name, not the bare
# `google` package — matching plain ``google`` here would false-positive on
# every unrelated ``google.cloud``/``google.protobuf`` import.
FALLBACK_IMPORT_REGEX = re.compile(
    r"^\s*(?:import|from)\s+(openai|anthropic|mistralai|cohere|litellm|groq|together"
    r"|replicate|huggingface_hub|transformers|ollama|vllm|torch|llama_cpp"
    r"|fireworks|xai_sdk|deepseek|deepseek_sdk"
    r"|google\.generativeai|google\.genai|langchain_openai|langchain_anthropic"
    r"|langchain_mistralai|langchain_cohere|langchain_groq|langchain_together"
    r"|langchain_aws|langchain_google_vertexai|langchain_google_genai"
    r"|langchain_ollama|langchain_huggingface|langchain_deepseek"
    r"|langchain_fireworks|langchain_xai)\b"
)

# ``from google import genai`` / ``from google import generativeai`` — the
# bare ``google`` package is never itself a provider (it also backs
# google-cloud/protobuf/etc), so it is matched only in this two-token form and
# resolved via the imported name, mirroring what the AST path already does in
# ``_ast_hits`` for files that parse cleanly.
FALLBACK_FROM_GOOGLE_IMPORT_REGEX = re.compile(
    r"^\s*from\s+google\s+import\s+(genai|generativeai)\b"
)


# `new ClassName(...)` — reuses CONSTRUCTOR_PROVIDERS, since LangChain.js and
# the native provider SDKs use the same class names as their Python siblings.
JS_CONSTRUCTOR_REGEX = re.compile(r"\bnew\s+([A-Za-z_$][\w$]*)\s*\(")


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
    # Google ships two SDKs: the legacy ``google.generativeai`` and the newer
    # unified ``google.genai``. Both are the Gemini API.
    if module_name == "google.generativeai" or module_name.startswith("google.generativeai."):
        return "google"
    if module_name == "google.genai" or module_name.startswith("google.genai."):
        return "google"
    # Exact match first (covers scoped npm packages like "@langchain/openai",
    # which must not be reduced further — "@langchain" alone is not a
    # provider). Then fall back to the top-level package: Python submodules
    # are dotted ("openai.types" -> "openai"), npm subpaths are slash-
    # separated ("openai/resources" -> "openai").
    if module_name in PROVIDER_MODULES:
        return PROVIDER_MODULES[module_name]
    if "/" in module_name:
        parts = module_name.split("/")
        top = "/".join(parts[:2]) if module_name.startswith("@") else parts[0]
    else:
        top = module_name.split(".")[0]
    return PROVIDER_MODULES.get(top)


def _bedrock_client_call(node: ast.Call) -> bool:
    """True for ``boto3.client('bedrock-runtime')``-style AWS Bedrock clients.

    boto3 is generic AWS glue, so importing it is not evidence of AI. A client
    constructed for a ``bedrock`` service *is* — detected by the string service
    name so a Bedrock-backed app is not reported as containing no AI.
    """
    dotted = _dotted_name(node.func)
    if not dotted or dotted.split(".")[-1] not in ("client", "resource"):
        return False
    for arg in (*node.args, *(kw.value for kw in node.keywords)):
        if (
            isinstance(arg, ast.Constant)
            and isinstance(arg.value, str)
            and arg.value.lower().startswith("bedrock")
        ):
            return True
    return False


class ProviderDetector(BaseDetector):
    """Detects real usage of AI model providers in Python and JS/TS source files."""

    name = "providers"

    def analyze(self, file_path: Path, content: str) -> list[Finding]:
        if file_path.suffix in JS_TS_SUFFIXES:
            hits = self._js_hits(content)
            return [
                self._build_finding(file_path, provider, line_no)
                for provider, line_no in sorted(hits, key=lambda h: (h[0], h[1]))
            ]
        if file_path.suffix != ".py":
            return []
        # Strip a leading BOM so a BOM-prefixed file (common Windows/editor
        # output) still parses via AST instead of degrading to import-line-only
        # regex, which misses constructors and client.method() API calls.
        content = content.lstrip("\ufeff")
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

    def _js_hits(self, content: str) -> set[tuple[str, int]]:
        """Regex-based provider detection for JS/TS (no JS AST parser bundled).

        Mirrors ``_ast_hits``'s strong/weak split: imports and `new X(...)`
        constructor calls name the provider unambiguously (strong); an
        OpenAI-compatible API-surface fragment (`.chat.completions.create`)
        only counts on its own when nothing stronger was found in the file.
        """
        content = content.lstrip("\ufeff")
        strong: set[tuple[str, int]] = set()
        weak: set[tuple[str, int]] = set()
        for spec, line_no in iter_js_import_specs(content):
            provider = _module_provider(spec)
            if provider:
                strong.add((provider, line_no))
        stripped = strip_js_comments(content)
        for line_no, line in enumerate(stripped.splitlines(), start=1):
            for ctor_match in JS_CONSTRUCTOR_REGEX.finditer(line):
                provider = CONSTRUCTOR_PROVIDERS.get(ctor_match.group(1))
                if provider:
                    strong.add((provider, line_no))
            for fragment, provider in ATTRIBUTE_PROVIDERS:
                if fragment in line:
                    weak.add((provider, line_no))
        if not strong:
            return weak
        strong_providers = {provider for provider, _ in strong}
        return strong | {hit for hit in weak if hit[0] in strong_providers}

    def _ast_hits(self, tree: ast.AST) -> set[tuple[str, int]]:
        # Strong signals: imports and constructor/client calls name the provider
        # unambiguously.
        strong: set[tuple[str, int]] = set()
        # Weak signals: OpenAI-compatible API-surface fragments, kept only if no
        # strong signal identified a provider in this file (see ATTRIBUTE_PROVIDERS).
        weak: set[tuple[str, int]] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    provider = _module_provider(alias.name)
                    if provider:
                        strong.add((provider, node.lineno))
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                # Skip relative imports (node.level > 0): ``from .openai import x``
                # is a local sibling module, not the real provider SDK.
                provider = _module_provider(node.module)
                if provider:
                    strong.add((provider, node.lineno))
                else:
                    # ``from google import genai`` imports the ``google.genai``
                    # submodule — the provider lives in module + imported name,
                    # not the bare package.
                    for alias in node.names:
                        sub = _module_provider(f"{node.module}.{alias.name}")
                        if sub:
                            strong.add((sub, node.lineno))
            elif isinstance(node, ast.Call):
                dotted = _dotted_name(node.func)
                if dotted:
                    provider = CONSTRUCTOR_PROVIDERS.get(dotted.split(".")[-1])
                    if provider:
                        strong.add((provider, node.lineno))
                if _bedrock_client_call(node):
                    strong.add(("bedrock", node.lineno))
            elif isinstance(node, ast.Attribute):
                dotted = _dotted_name(node)
                if dotted:
                    for fragment, provider in ATTRIBUTE_PROVIDERS:
                        if fragment in dotted:
                            weak.add((provider, node.lineno))
        # Keep an ambiguous OpenAI-compatible fragment only when it agrees with a
        # provider already proven in this file, or when nothing stronger was found
        # at all. So ``import openai; client.chat.completions...`` still counts the
        # API-call line as OpenAI, while ``from groq import Groq; c.chat.completions...``
        # is labelled Groq (the strong signal) and not also mislabelled OpenAI.
        if not strong:
            return weak
        strong_providers = {provider for provider, _ in strong}
        return strong | {hit for hit in weak if hit[0] in strong_providers}

    def _fallback_hits(self, content: str) -> set[tuple[str, int]]:
        """Regex over import lines only, for files with syntax errors."""
        hits: set[tuple[str, int]] = set()
        for line_no, line in enumerate(content.splitlines(), start=1):
            match = FALLBACK_IMPORT_REGEX.match(line)
            if match:
                provider = _module_provider(match.group(1))
                if provider:
                    hits.add((provider, line_no))
                continue
            google_match = FALLBACK_FROM_GOOGLE_IMPORT_REGEX.match(line)
            if google_match:
                provider = _module_provider(f"google.{google_match.group(1)}")
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
