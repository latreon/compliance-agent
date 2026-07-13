"""Framework-specific detectors with per-pattern compliance mapping."""

from compliance_agent.scanner.detectors.frameworks.autogen import AutoGenDetector
from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule
from compliance_agent.scanner.detectors.frameworks.crewai import CrewAIDetector
from compliance_agent.scanner.detectors.frameworks.dspy import DSPyDetector
from compliance_agent.scanner.detectors.frameworks.haystack import HaystackDetector
from compliance_agent.scanner.detectors.frameworks.instructor import InstructorDetector
from compliance_agent.scanner.detectors.frameworks.langchain import LangChainDetector
from compliance_agent.scanner.detectors.frameworks.langgraph import LangGraphDetector
from compliance_agent.scanner.detectors.frameworks.llamaindex import LlamaIndexDetector
from compliance_agent.scanner.detectors.frameworks.semantic_kernel import SemanticKernelDetector
from compliance_agent.scanner.detectors.frameworks.vercel_ai import VercelAIDetector

ALL_FRAMEWORK_DETECTORS: list[type[FrameworkDetector]] = [
    LangChainDetector,
    CrewAIDetector,
    AutoGenDetector,
    LangGraphDetector,
    LlamaIndexDetector,
    VercelAIDetector,
    SemanticKernelDetector,
    HaystackDetector,
    DSPyDetector,
    InstructorDetector,
]

__all__ = [
    "ALL_FRAMEWORK_DETECTORS",
    "AutoGenDetector",
    "CrewAIDetector",
    "DSPyDetector",
    "FrameworkDetector",
    "FrameworkRule",
    "HaystackDetector",
    "InstructorDetector",
    "LangChainDetector",
    "LangGraphDetector",
    "LlamaIndexDetector",
    "SemanticKernelDetector",
    "VercelAIDetector",
]
