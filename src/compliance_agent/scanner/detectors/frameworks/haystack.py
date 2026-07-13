"""Haystack framework detector: pipelines, retrieval, and agents."""

from compliance_agent.models.findings import Severity
from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule


class HaystackDetector(FrameworkDetector):
    framework_name = "haystack"
    import_modules = frozenset({"haystack"})
    rules = (
        FrameworkRule(
            category="haystack_agent",
            patterns=(
                r"\bfrom\s+haystack\.components\.agents\b",
                r"\bAgent\s*\(",
            ),
            message="Haystack agent detected",
            description=(
                "A tool-using agent that iterates over LLM calls to solve a query "
                "autonomously. High-stakes tool actions need a human oversight point."
            ),
            article="Art. 14",
            suggestion="Add a human oversight checkpoint before high-stakes agent actions",
            severity=Severity.WARNING,
        ),
        FrameworkRule(
            category="haystack_pipeline",
            patterns=(r"\bPipeline\s*\(",),
            message="Haystack pipeline detected",
            description="The retrieval/generation pipeline should be documented for audits.",
            article="Art. 11",
            suggestion=(
                "Document the pipeline's components and data flow "
                "in your technical documentation"
            ),
        ),
        FrameworkRule(
            category="haystack_indexing",
            patterns=(
                r"\bDocumentStore\b",
                r"\bInMemoryDocumentStore\b",
                r"\bDocumentWriter\b",
            ),
            message="Haystack document indexing detected",
            description=(
                "Documents are ingested into a document store. Indexed data falls "
                "under data governance: provenance, PII handling, and bias in the "
                "source corpus must be examined."
            ),
            article="Art. 10",
            suggestion="Document the indexed data sources, their provenance, and any PII controls",
        ),
        FrameworkRule(
            category="haystack_retrieval",
            patterns=(
                r"\bRetriever\b",
                r"\bBM25Retriever\b",
                r"\bEmbeddingRetriever\b",
            ),
            message="Haystack retrieval component detected",
            description=(
                "A retrieval component grounds model output in indexed documents. "
                "Retrieval accuracy and grounding directly affect output reliability."
            ),
            article="Art. 15",
            suggestion="Validate retrieval accuracy/grounding and record it in your technical file",
        ),
    )
