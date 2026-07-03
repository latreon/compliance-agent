"""Article-specific gap analyzers."""

from compliance_agent.analyzer.articles.art6 import Art6Analyzer
from compliance_agent.analyzer.articles.art7 import Art7Analyzer
from compliance_agent.analyzer.articles.art9 import Art9Analyzer
from compliance_agent.analyzer.articles.art10 import Art10Analyzer
from compliance_agent.analyzer.articles.art11 import Art11Analyzer
from compliance_agent.analyzer.articles.art12 import Art12Analyzer
from compliance_agent.analyzer.articles.art13 import Art13Analyzer
from compliance_agent.analyzer.articles.art14 import Art14Analyzer
from compliance_agent.analyzer.articles.art15 import Art15Analyzer
from compliance_agent.analyzer.articles.art26 import Art26Analyzer
from compliance_agent.analyzer.articles.art28 import Art28Analyzer
from compliance_agent.analyzer.articles.art50 import Art50Analyzer
from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
)

ALL_ARTICLE_ANALYZERS: list[type[ArticleAnalyzer]] = [
    Art6Analyzer,
    Art7Analyzer,
    Art9Analyzer,
    Art10Analyzer,
    Art11Analyzer,
    Art12Analyzer,
    Art13Analyzer,
    Art14Analyzer,
    Art15Analyzer,
    Art26Analyzer,
    Art28Analyzer,
    Art50Analyzer,
]

__all__ = [
    "ALL_ARTICLE_ANALYZERS",
    "ArticleAnalyzer",
    "ProjectProbe",
    "Requirement",
    "Art6Analyzer",
    "Art7Analyzer",
    "Art9Analyzer",
    "Art10Analyzer",
    "Art11Analyzer",
    "Art12Analyzer",
    "Art13Analyzer",
    "Art14Analyzer",
    "Art15Analyzer",
    "Art26Analyzer",
    "Art28Analyzer",
    "Art50Analyzer",
]
