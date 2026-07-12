"""CrewAI framework detector: crews, agents, tasks, memory, processes."""

from compliance_agent.models.findings import Severity
from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule


class CrewAIDetector(FrameworkDetector):
    framework_name = "crewai"
    import_modules = frozenset({"crewai"})
    rules = (
        FrameworkRule(
            category="crewai_crew",
            patterns=(r"\bCrew\s*\(", r"\.kickoff\s*\("),
            message="CrewAI multi-agent crew detected",
            description=(
                "Multiple agents collaborating autonomously. Requires an "
                "oversight mechanism before execution."
            ),
            article="Art. 14",
            suggestion="Implement human approval before crew.kickoff()",
            severity=Severity.WARNING,
        ),
        FrameworkRule(
            category="crewai_agent",
            patterns=(r"\bAgent\s*\(",),
            message="CrewAI agent definition detected",
            description=(
                "Each agent has a role and tool access. Agent capabilities "
                "define the system's risk surface."
            ),
            article="Art. 9",
            suggestion="Document each agent's role and tools in the risk register",
        ),
        FrameworkRule(
            category="crewai_task",
            patterns=(r"\bTask\s*\(",),
            message="CrewAI task definition detected",
            description="Task execution should be logged for traceability.",
            article="Art. 12",
            suggestion="Log task inputs, outputs, and the executing agent",
        ),
        FrameworkRule(
            category="crewai_memory",
            # Explicit CrewAI memory classes are unambiguous signals. The
            # `memory=True` kwarg carries a trailing \b so it can't match an
            # unrelated `memory=Trueish`, narrowing the one broad pattern.
            patterns=(
                r"\bLongTermMemory\b",
                r"\bShortTermMemory\b",
                r"\bEntityMemory\b",
                r"\bUserMemory\b",
                r"\bExternalMemory\b",
                r"\bmemory\s*=\s*True\b",
            ),
            message="CrewAI memory detected",
            description=(
                "Crew memory persists interaction history and falls under "
                "record-keeping and retention duties."
            ),
            article="Art. 12",
            suggestion="Ensure crew memory storage meets retention requirements",
        ),
        FrameworkRule(
            category="crewai_process",
            patterns=(r"\bProcess\.(sequential|hierarchical)\b",),
            message="CrewAI process workflow detected",
            description="The crew workflow should be documented for audits.",
            article="Art. 11",
            suggestion="Document the crew workflow in your technical documentation",
        ),
    )
