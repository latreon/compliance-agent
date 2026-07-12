"""LlamaIndex framework detector: RAG indexing, retrieval, and agents.

LlamaIndex is a leading RAG framework with both Python (``llama_index``) and
JS/TS (``@llamaindex/*``) SDKs. RAG systems ingest and index documents, then
retrieve and synthesize answers — each stage carries distinct EU AI Act
obligations (data governance for what is indexed, robustness/grounding for
retrieval, oversight for agentic query loops).
"""

from compliance_agent.models.findings import Severity
from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule


class LlamaIndexDetector(FrameworkDetector):
    framework_name = "llamaindex"
    import_modules = frozenset(
        {
            # Python: top_level_modules() reduces llama_index.core.* -> llama_index.
            "llama_index",
            # JS/TS: the umbrella package and the scoped packages.
            "llamaindex",
            "@llamaindex/core",
            "@llamaindex/openai",
            "@llamaindex/anthropic",
        }
    )
    rules = (
        FrameworkRule(
            category="llamaindex_indexing",
            patterns=(
                r"\bVectorStoreIndex\b",
                r"\bSummaryIndex\b",
                r"\bKnowledgeGraphIndex\b",
                r"\bSimpleDirectoryReader\b",
                r"\bIngestionPipeline\b",
                r"\bfrom_documents\b",
                r"\bfromDocuments\b",
            ),
            message="LlamaIndex document indexing detected",
            description=(
                "Documents are ingested into a knowledge base. The indexed data "
                "falls under data governance: document provenance, PII handling, "
                "and bias in the source corpus must be examined."
            ),
            article="Art. 10",
            suggestion="Document the indexed data sources, their provenance, and any PII controls",
        ),
        FrameworkRule(
            category="llamaindex_query",
            patterns=(
                r"\bas_query_engine\s*\(",
                r"\bas_retriever\s*\(",
                r"\basQueryEngine\s*\(",
                r"\basRetriever\s*\(",
                r"\bRetrieverQueryEngine\b",
                r"\bQueryEngineTool\b",
            ),
            message="LlamaIndex query/retrieval pipeline detected",
            description=(
                "A retrieval pipeline grounds model output in indexed documents. "
                "Retrieval accuracy and grounding directly affect output "
                "reliability and must be validated."
            ),
            article="Art. 15",
            suggestion="Validate retrieval accuracy/grounding and record it in your technical file",
        ),
        FrameworkRule(
            category="llamaindex_agent",
            patterns=(
                r"\bReActAgent\b",
                r"\bFunctionAgent\b",
                r"\bAgentWorkflow\b",
                r"\bAgentRunner\b",
                r"\bOpenAIAgent\b",
            ),
            message="LlamaIndex agent detected",
            description=(
                "Agentic query loops let the model choose tools and take actions "
                "autonomously. High-stakes actions need a human oversight point."
            ),
            article="Art. 14",
            suggestion="Add a human oversight checkpoint before high-stakes agent actions",
            severity=Severity.WARNING,
        ),
    )
