# Expected Output

Real output from `compliance-agent scan examples/sample-multi-framework` (run
from the repo root; timestamps and absolute paths will differ). The project
is a single file, `research_pipeline.py`, that combines **three** agent
frameworks the way real migrations and integrations do: a LangChain
summarization chain and search tool, a CrewAI researcher/writer crew, and a
LangGraph state graph that orchestrates both.

## Summary

```markdown
## Scan Summary

- **Files scanned:** 1
- **AI providers detected:** none
- **Risk tier:** **LIMITED**
- **Findings:** 4 warning, 11 info
- **Frameworks:** crewai, langchain, langgraph
```

No provider (OpenAI/Anthropic/etc.) is detected because the LLM client is
injected as a parameter (`llm`) rather than constructed in this file — a
realistic pattern for a shared client, and a reminder that the scanner sees
what is actually written, not what is architecturally implied.

## Frameworks detected

This is the section that does not exist for a single-framework project: each
detected framework gets its own group, so you can tell at a glance which
patterns came from where instead of one undifferentiated finding list.

```markdown
## Frameworks Detected

### crewai (agent, crew, process, task)

- → Document each agent's role and tools in the risk register
- → Log task inputs, outputs, and the executing agent
- → Implement human approval before crew.kickoff()
- → Document the crew workflow in your technical documentation

### langchain (chain, memory, tools)

- → Ensure conversation logs meet the 6-month retention requirement
- → Register each tool in your risk register with a mitigation
- → Add an AI disclosure notice where chain output reaches users

### langgraph (checkpoint, conditional, graph, tools)

- → Align checkpoint retention with the 6-month log requirement
- → Register each tool in your risk register with a mitigation
- → Document all possible state transitions
- → Add a human checkpoint node before high-stakes branches
```

## Findings

Every construct across all three frameworks is picked up in one pass — a
CrewAI `Crew(...)` on line 63 does not suppress or get suppressed by the
LangGraph `StateGraph(...)` on line 84:

```markdown
### `research_pipeline.py`

- 🟡 **warning** `pattern:missing-logging` (file-level): AI usage without logging
- 🟡 **warning** `agent:multi-agent` (line 19, ×4): Multi-agent framework import detected
- 🔵 **info** `langchain_memory` (line 21, ×3): LangChain conversation memory detected
- 🔵 **info** `langgraph_checkpoint` (line 23, ×2): LangGraph checkpointing detected
- 🔵 **info** `langgraph_tools` (line 25, ×3): LangGraph tool node detected
- 🔵 **info** `langchain_tools` (line 30): LangChain tool definition detected
- 🔵 **info** `pattern:user-input` (line 31, ×2): Query handling in AI context detected
- 🔵 **info** `langchain_chain` (line 38, ×2): LangChain chain processing user input detected
- 🔵 **info** `crewai_agent` (line 50, ×2): CrewAI agent definition detected
- 🟡 **warning** `agent:tool-calls` (line 53): LLM tool-calling detected
- 🔵 **info** `crewai_task` (line 61, ×2): CrewAI task definition detected
- 🟡 **warning** `crewai_crew` (line 63, ×2): CrewAI multi-agent crew detected
- 🔵 **info** `crewai_process` (line 66): CrewAI process workflow detected
- 🔵 **info** `langgraph_graph` (line 84, ×5): LangGraph state machine detected
- 🔵 **info** `langgraph_conditional` (line 88): LangGraph conditional routing detected
```

## Gaps

Art. 11 (technical documentation), Art. 12 (record-keeping), Art. 14 (human
oversight, ×2), and Art. 50 (AI disclosure) — the same fix templates apply
regardless of which framework triggered the underlying finding. A `Task(...)`
from CrewAI and a checkpointed `StateGraph` from LangGraph both point at the
Art. 12 logging template; a `Crew(...).kickoff()` and a LangGraph conditional
edge both point at the Art. 14 oversight template.

## Fixing it

```bash
compliance-agent recommend examples/sample-multi-framework --output ./fixes
```

produces one deduplicated recommendation per article, not one per framework —
so a project using all three frameworks does not get three redundant copies
of the same Art. 14 fix.
