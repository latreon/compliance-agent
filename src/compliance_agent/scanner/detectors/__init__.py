"""Detectors for AI usage patterns in codebases."""

from compliance_agent.scanner.detectors.agents import AgentDetector
from compliance_agent.scanner.detectors.base import BaseDetector
from compliance_agent.scanner.detectors.patterns import PatternDetector
from compliance_agent.scanner.detectors.providers import ProviderDetector

ALL_DETECTORS: list[type[BaseDetector]] = [
    ProviderDetector,
    AgentDetector,
    PatternDetector,
]

__all__ = [
    "ALL_DETECTORS",
    "AgentDetector",
    "BaseDetector",
    "PatternDetector",
    "ProviderDetector",
]
