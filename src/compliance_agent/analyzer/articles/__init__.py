"""Article-specific gap analyzers."""

from compliance_agent.analyzer.articles.art5 import Art5Analyzer
from compliance_agent.analyzer.articles.art6 import Art6Analyzer
from compliance_agent.analyzer.articles.art9 import Art9Analyzer
from compliance_agent.analyzer.articles.art10 import Art10Analyzer
from compliance_agent.analyzer.articles.art11 import Art11Analyzer
from compliance_agent.analyzer.articles.art12 import Art12Analyzer
from compliance_agent.analyzer.articles.art13 import Art13Analyzer
from compliance_agent.analyzer.articles.art14 import Art14Analyzer
from compliance_agent.analyzer.articles.art15 import Art15Analyzer
from compliance_agent.analyzer.articles.art16 import Art16Analyzer
from compliance_agent.analyzer.articles.art17 import Art17Analyzer
from compliance_agent.analyzer.articles.art24 import Art24Analyzer
from compliance_agent.analyzer.articles.art26 import Art26Analyzer
from compliance_agent.analyzer.articles.art27 import Art27Analyzer
from compliance_agent.analyzer.articles.art43 import Art43Analyzer
from compliance_agent.analyzer.articles.art50 import Art50Analyzer
from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
)

# Ordered by article number for a readable coverage table.
ALL_ARTICLE_ANALYZERS: list[type[ArticleAnalyzer]] = [
    Art5Analyzer,
    Art6Analyzer,
    Art9Analyzer,
    Art10Analyzer,
    Art11Analyzer,
    Art12Analyzer,
    Art13Analyzer,
    Art14Analyzer,
    Art15Analyzer,
    Art16Analyzer,
    Art17Analyzer,
    Art24Analyzer,
    Art26Analyzer,
    Art27Analyzer,
    Art43Analyzer,
    Art50Analyzer,
]

__all__ = [
    "ALL_ARTICLE_ANALYZERS",
    "ArticleAnalyzer",
    "ProjectProbe",
    "Requirement",
    "Art5Analyzer",
    "Art6Analyzer",
    "Art9Analyzer",
    "Art10Analyzer",
    "Art11Analyzer",
    "Art12Analyzer",
    "Art13Analyzer",
    "Art14Analyzer",
    "Art15Analyzer",
    "Art16Analyzer",
    "Art17Analyzer",
    "Art24Analyzer",
    "Art26Analyzer",
    "Art27Analyzer",
    "Art43Analyzer",
    "Art50Analyzer",
]
