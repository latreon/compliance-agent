"""LangGraph framework detector: state graphs, tool nodes, checkpointing."""

from compliance_agent.scanner.detectors.frameworks.base import FrameworkDetector, FrameworkRule


class LangGraphDetector(FrameworkDetector):
    framework_name = "langgraph"
    # "@langchain/langgraph" is the npm package for LangGraph.js, which mirrors
    # the Python API (StateGraph, add_node, add_conditional_edges, ToolNode).
    import_modules = frozenset({"langgraph", "@langchain/langgraph"})
    rules = (
        FrameworkRule(
            category="langgraph_graph",
            patterns=(
                r"\bStateGraph\s*\(",
                r"\.add_node\s*\(",
                r"\.addNode\s*\(",  # LangGraph.js uses camelCase method names.
                # Deliberately no bare `.compile(` pattern here: it collides
                # with `re.compile(`, Keras/TF `model.compile()`, etc. once
                # the file's import gate is satisfied. `StateGraph(`/
                # `add_node`/`addNode` are specific enough on their own.
            ),
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
            patterns=(r"\.add_conditional_edges\s*\(", r"\.addConditionalEdges\s*\("),
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
            patterns=(
                r"\bToolNode\b",
                r"\bToolExecutor\b",
                r"\btools\s*=\s*\[",  # Python kwarg style.
                r"\btools\s*:\s*\[",  # JS object-literal property style.
            ),
            message="LangGraph tool node detected",
            description="Tool nodes give the graph access to external systems.",
            article="Art. 9",
            suggestion="Register each tool in your risk register with a mitigation",
        ),
        FrameworkRule(
            category="langgraph_checkpoint",
            patterns=(
                r"\bSqliteSaver\b",
                r"\bMemorySaver\b",
                r"\bcheckpointer\s*=",  # Python kwarg style.
                r"\bcheckpointer\s*:",  # JS object-literal property style.
            ),
            message="LangGraph checkpointing detected",
            description=(
                "Checkpointers persist state history — useful for the audit "
                "trail, subject to retention duties."
            ),
            article="Art. 12",
            suggestion="Align checkpoint retention with the 6-month log requirement",
        ),
    )
