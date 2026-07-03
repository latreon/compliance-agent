"""Detectors for AI usage patterns in codebases."""

from compliance_agent.scanner.detectors.agents import AgentDetector
from compliance_agent.scanner.detectors.base import BaseDetector
from compliance_agent.scanner.detectors.frameworks import ALL_FRAMEWORK_DETECTORS
from compliance_agent.scanner.detectors.patterns import PatternDetector
from compliance_agent.scanner.detectors.providers import ProviderDetector

ALL_DETECTORS: list[type[BaseDetector]] = [
    ProviderDetector,
    AgentDetector,
    PatternDetector,
    *ALL_FRAMEWORK_DETECTORS,
]

__all__ = [
    "ALL_DETECTORS",
    "AgentDetector",
    "BaseDetector",
    "PatternDetector",
    "ProviderDetector",
]
