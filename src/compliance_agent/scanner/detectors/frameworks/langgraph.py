"""LangGraph framework detector: state graphs, tool nodes, checkpointing."""

from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule


class LangGraphDetector(FrameworkDetector):
    framework_name = "langgraph"
    import_modules = frozenset({"langgraph"})
    rules = (
        FrameworkRule(
            category="langgraph_graph",
            patterns=(r"\bStateGraph\s*\(", r"\.add_node\s*\(", r"\.compile\s*\("),
            message="LangGraph state machine detected",
            description=(
                "Complex workflow with graph-based routing. All state "
                "transitions should be documented."
            ),
            article="Art. 11",
            suggestion="Document all possible state transitions",
        ),
        FrameworkRule(
            category="langgraph_conditional",
            patterns=(r"\.add_conditional_edges\s*\(",),
            message="LangGraph conditional routing detected",
            description=(
                "Branching decisions steer the workflow autonomously. "
                "High-stakes branches need human oversight."
            ),
            article="Art. 14",
            suggestion="Add a human checkpoint node before high-stakes branches",
        ),
        FrameworkRule(
            category="langgraph_tools",
            patterns=(r"\bToolNode\b", r"\bToolExecutor\b", r"\btools\s*=\s*\["),
            message="LangGraph tool node detected",
            description="Tool nodes give the graph access to external systems.",
            article="Art. 9",
            suggestion="Register each tool in your risk register with a mitigation",
        ),
        FrameworkRule(
            category="langgraph_checkpoint",
            patterns=(r"\bSqliteSaver\b", r"\bMemorySaver\b", r"\bcheckpointer\s*="),
            message="LangGraph checkpointing detected",
            description=(
                "Checkpointers persist state history — useful for the audit "
                "trail, subject to retention duties."
            ),
            article="Art. 12",
            suggestion="Align checkpoint retention with the 6-month log requirement",
        ),
    )
