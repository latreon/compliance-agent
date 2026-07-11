"""Sample multi-framework research pipeline for demonstration.

Real agent projects rarely stick to one framework — a team migrating from
CrewAI to LangGraph, or bolting a LangChain retrieval chain onto a new
orchestrator, ends up with several frameworks live in the same codebase at
once. This project combines three on purpose:

  - LangChain: a summarization chain and a web-search tool
  - CrewAI: a two-agent crew (researcher + writer) for a sub-task
  - LangGraph: the top-level state graph that orchestrates both

It is INTENTIONALLY missing compliance measures, same as the other examples.
Run `compliance-agent scan examples/sample-multi-framework` from the repo
root to see findings surface across all three frameworks in one pass —
nothing from CrewAI or LangGraph shadows what LangChain triggered, and vice
versa.
"""

from crewai import Agent, Crew, Process, Task
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

memory = ConversationBufferMemory()


@tool
def web_search(query: str) -> str:
    """Search the web for background material on the research topic."""
    return f"search results for: {query}"


def build_summarizer_chain(llm) -> LLMChain:
    """LangChain chain that condenses raw research notes for the crew."""
    chain = LLMChain(llm=llm, prompt=SUMMARY_PROMPT)
    return chain


def run_summarizer(chain: LLMChain, notes: str) -> str:
    summary = chain.invoke({"notes": notes})
    memory.save_context({"notes": notes}, {"summary": summary})
    return summary


def build_research_crew(llm) -> Crew:
    """CrewAI crew: one agent researches, another writes the final report."""
    researcher = Agent(
        role="Researcher",
        goal="Gather accurate background facts on the topic",
        tools=[web_search],
        llm=llm,
    )
    writer = Agent(
        role="Writer",
        goal="Turn research notes into a polished report",
        llm=llm,
    )
    research_task = Task(description="Research the topic thoroughly", agent=researcher)
    writing_task = Task(description="Write the final report", agent=writer)
    return Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
        process=Process.sequential,
    )


def run_crew_node(state: dict, llm) -> dict:
    """LangGraph node: hands the summarized notes to the CrewAI crew."""
    crew = build_research_crew(llm)
    result = crew.kickoff(inputs={"notes": state["summary"]})
    return {**state, "report": result}


def route_after_summary(state: dict) -> str:
    """LangGraph conditional edge: skip the crew for very short notes."""
    return "crew" if len(state.get("summary", "")) > 200 else "done"


def build_pipeline_graph(llm):
    """LangGraph state graph orchestrating the LangChain chain + CrewAI crew."""
    graph = StateGraph(dict)
    graph.add_node("summarize", lambda state: run_summarizer(state["chain"], state["notes"]))
    graph.add_node("crew", lambda state: run_crew_node(state, llm))
    graph.add_node("tools", ToolNode([web_search]))
    graph.add_conditional_edges("summarize", route_after_summary, {"crew": "crew", "done": "tools"})
    return graph.compile(checkpointer=MemorySaver())


SUMMARY_PROMPT = "Summarize the following research notes:\n{notes}"
