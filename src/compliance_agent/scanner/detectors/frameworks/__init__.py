"""Framework-specific detectors with per-pattern compliance mapping."""

from compliance_agent.scanner.detectors.frameworks.autogen import AutoGenDetector
from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule
from compliance_agent.scanner.detectors.frameworks.crewai import CrewAIDetector
from compliance_agent.scanner.detectors.frameworks.langchain import LangChainDetector
from compliance_agent.scanner.detectors.frameworks.langgraph import LangGraphDetector

ALL_FRAMEWORK_DETECTORS: list[type[FrameworkDetector]] = [
    LangChainDetector,
    CrewAIDetector,
    AutoGenDetector,
    LangGraphDetector,
]

__all__ = [
    "ALL_FRAMEWORK_DETECTORS",
    "AutoGenDetector",
    "CrewAIDetector",
    "FrameworkDetector",
    "FrameworkRule",
    "LangChainDetector",
    "LangGraphDetector",
]
