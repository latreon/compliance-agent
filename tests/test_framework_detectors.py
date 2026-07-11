"""Tests for framework-specific detectors (LangChain, CrewAI, AutoGen, LangGraph)."""

from pathlib import Path

from compliance_agent.recommender.engine import FixRecommender
from compliance_agent.recommender.rules import FIX_RULES, TRIGGER_TO_RULE
from compliance_agent.reporter.markdown import render_markdown
from compliance_agent.reporter.pdf_report import PDFReporter
from compliance_agent.scanner.detectors.frameworks import (
    ALL_FRAMEWORK_DETECTORS,
    AutoGenDetector,
    CrewAIDetector,
    LangChainDetector,
    LangGraphDetector,
    VercelAIDetector,
)
from compliance_agent.scanner.engine import ScannerEngine

LANGCHAIN_APP = """
from langchain.chat_models import ChatOpenAI
from langchain.agents import AgentExecutor
from langchain.memory import ConversationBufferMemory

llm = ChatOpenAI(model="gpt-4")
agent = create_openai_functions_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)
memory = ConversationBufferMemory()
"""

CREWAI_APP = """
from crewai import Agent, Task, Crew, Process

researcher = Agent(role="researcher", goal="Research", tools=[search])
task = Task(description="Find info", agent=researcher)
crew = Crew(agents=[researcher], tasks=[task], process=Process.sequential)
result = crew.kickoff()
"""

AUTOGEN_APP = """
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

assistant = AssistantAgent(name="assistant", llm_config=config)
user_proxy = UserProxyAgent(name="user", human_input_mode="TERMINATE")
groupchat = GroupChat(agents=[assistant, user_proxy], messages=[])
user_proxy.initiate_chat(assistant, message="Hello")
"""

LANGGRAPH_APP = """
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver

graph = StateGraph(State)
graph.add_node("agent", call_model)
graph.add_conditional_edges("agent", should_continue, {"continue": "tools", "end": END})
app = graph.compile(checkpointer=SqliteSaver.from_conn_string(":memory:"))
"""

LANGCHAIN_JS_APP = """
import { ChatOpenAI } from "@langchain/openai";
import { AgentExecutor, createToolCallingAgent } from "langchain/agents";
import { BufferMemory } from "langchain/memory";

const llm = new ChatOpenAI({ model: "gpt-4o" });
const agent = createToolCallingAgent(llm, tools, prompt);
const executor = new AgentExecutor({ agent, tools });
const memory = new BufferMemory();
"""

LANGGRAPH_JS_APP = """
import { StateGraph, END } from "@langchain/langgraph";
import { ToolNode } from "@langchain/langgraph/prebuilt";

const graph = new StateGraph(State);
graph.addNode("agent", callModel);
graph.addConditionalEdges("agent", shouldContinue, { continue: "tools", end: END });
const app = graph.compile();
"""

VERCEL_AI_APP = """
import { generateText, streamText } from "ai";
import { openai } from "@ai-sdk/openai";

export async function chat(userInput) {
  const result = await generateText({
    model: openai("gpt-4o"),
    prompt: userInput,
    tools: {
      search: tool({ description: "search the web" }),
    },
    maxSteps: 5,
  });
  return result.text;
}
"""


# --- individual detectors ---------------------------------------------------------


def test_langchain_detection() -> None:
    findings = LangChainDetector().analyze(Path("app.py"), LANGCHAIN_APP)
    assert len(findings) >= 2  # agent + executor
    assert any(f.category == "langchain_agent" for f in findings)
    assert any(f.category == "langchain_memory" for f in findings)
    assert all(f.detector == "frameworks:langchain" for f in findings)


def test_crewai_detection() -> None:
    findings = CrewAIDetector().analyze(Path("app.py"), CREWAI_APP)
    assert any(f.category == "crewai_crew" for f in findings)
    assert any(f.category == "crewai_agent" for f in findings)
    assert any(f.category == "crewai_process" for f in findings)


def test_autogen_detection() -> None:
    findings = AutoGenDetector().analyze(Path("app.py"), AUTOGEN_APP)
    assert any(f.category == "autogen_groupchat" for f in findings)
    assert any(f.category == "autogen_userproxy" for f in findings)
    assert any(f.category == "autogen_chat" for f in findings)


def test_langgraph_detection() -> None:
    findings = LangGraphDetector().analyze(Path("app.py"), LANGGRAPH_APP)
    assert any(f.category == "langgraph_graph" for f in findings)
    assert any(f.category == "langgraph_conditional" for f in findings)
    assert any(f.category == "langgraph_checkpoint" for f in findings)


def test_langchain_js_detection() -> None:
    findings = LangChainDetector().analyze(Path("app.ts"), LANGCHAIN_JS_APP)
    assert any(f.category == "langchain_agent" for f in findings)
    assert any(f.category == "langchain_memory" for f in findings)
    assert all(f.detector == "frameworks:langchain" for f in findings)


def test_langgraph_js_detection() -> None:
    findings = LangGraphDetector().analyze(Path("app.ts"), LANGGRAPH_JS_APP)
    assert any(f.category == "langgraph_graph" for f in findings)
    assert any(f.category == "langgraph_conditional" for f in findings)


def test_vercel_ai_detection() -> None:
    findings = VercelAIDetector().analyze(Path("app.ts"), VERCEL_AI_APP)
    assert any(f.category == "vercel_generation" for f in findings)
    assert any(f.category == "vercel_tools" for f in findings)
    assert any(f.category == "vercel_agent_loop" for f in findings)
    assert all(f.detector == "frameworks:vercel-ai-sdk" for f in findings)


def test_vercel_ai_no_findings_without_import() -> None:
    content = "const result = generateText({ model, prompt });\n"
    assert VercelAIDetector().analyze(Path("app.ts"), content) == []


def test_vercel_ai_no_findings_in_python_files() -> None:
    assert VercelAIDetector().analyze(Path("app.py"), VERCEL_AI_APP) == []


def test_langchain_agenttype_detected() -> None:
    # Regression: AgentType (the enum selecting an agent strategy) was not in the
    # langchain_agent pattern set.
    content = (
        "import langchain\n"
        "from langchain.agents import AgentType\n"
        "strategy = AgentType.ZERO_SHOT_REACT_DESCRIPTION\n"
    )
    findings = LangChainDetector().analyze(Path("app.py"), content)
    assert any(f.category == "langchain_agent" for f in findings)


def test_langgraph_tools_kwarg_detected() -> None:
    # Regression: langgraph_tools only matched ToolNode/ToolExecutor, missing the
    # common `tools=[...]` binding.
    content = (
        "import langgraph\n"
        "from langgraph.graph import StateGraph\n"
        "node = make_node(tools=[search, calc])\n"
    )
    findings = LangGraphDetector().analyze(Path("app.py"), content)
    assert any(f.category == "langgraph_tools" for f in findings)


def test_findings_carry_article_and_suggestion() -> None:
    findings = LangChainDetector().analyze(Path("app.py"), LANGCHAIN_APP)
    agent_finding = next(f for f in findings if f.category == "langchain_agent")
    assert agent_finding.article == "Art. 14"
    assert agent_finding.suggestion


# --- precision: import gating -------------------------------------------------------


def test_no_findings_without_framework_import() -> None:
    # Mentions framework class names but never imports the framework.
    content = 'DOCS = "Use AgentExecutor and Crew for orchestration"\nimport os\n'
    for detector_cls in ALL_FRAMEWORK_DETECTORS:
        assert detector_cls().analyze(Path("app.py"), content) == []


def test_no_findings_in_non_python_files() -> None:
    content = "from crewai import Crew\ncrew = Crew()\n"
    assert CrewAIDetector().analyze(Path("notes.md"), content) == []


def test_framework_dedup_via_engine(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(LANGCHAIN_APP)
    result = ScannerEngine(tmp_path).scan()
    langchain = [f for f in result.findings if f.detector == "frameworks:langchain"]
    categories = [f.category for f in langchain]
    assert len(categories) == len(set(categories))  # one finding per category per file


# --- framework summary ---------------------------------------------------------------


def test_framework_summary_populated(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(LANGCHAIN_APP)
    (tmp_path / "crew.py").write_text(CREWAI_APP)
    result = ScannerEngine(tmp_path).scan()

    names = {fw.name for fw in result.frameworks_detected}
    assert names == {"langchain", "crewai"}
    langchain = next(fw for fw in result.frameworks_detected if fw.name == "langchain")
    assert "agent" in langchain.patterns
    assert "memory" in langchain.patterns
    assert langchain.risk_notes


def test_framework_summary_empty_without_frameworks(clean_project: Path) -> None:
    result = ScannerEngine(clean_project).scan()
    assert result.frameworks_detected == []


def test_vercel_ai_detected_via_scanner_engine(tmp_path: Path) -> None:
    (tmp_path / "chat.ts").write_text(VERCEL_AI_APP)
    result = ScannerEngine(tmp_path).scan()
    names = {fw.name for fw in result.frameworks_detected}
    assert "vercel-ai-sdk" in names
    assert any(f.category == "provider:openai" for f in result.findings)


def test_langchain_js_detected_via_scanner_engine(tmp_path: Path) -> None:
    (tmp_path / "agent.ts").write_text(LANGCHAIN_JS_APP)
    result = ScannerEngine(tmp_path).scan()
    names = {fw.name for fw in result.frameworks_detected}
    assert "langchain" in names


def test_markdown_report_includes_frameworks(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(CREWAI_APP)
    result = ScannerEngine(tmp_path).scan()
    report = render_markdown(result)
    assert "## Frameworks Detected" in report
    assert "crewai" in report
    assert "**Frameworks:** crewai" in report


def test_pdf_html_includes_frameworks(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(AUTOGEN_APP)
    result = ScannerEngine(tmp_path).scan()
    html = PDFReporter()._render_html(result)
    assert "Frameworks Detected" in html
    assert "autogen" in html


# --- recommender integration -----------------------------------------------------------


def test_framework_findings_trigger_recommendations(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(CREWAI_APP)
    result = ScannerEngine(tmp_path).scan()
    recs = FixRecommender().recommend(result)
    rule_keys = {r.rule_key for r in recs}
    assert "art14" in rule_keys  # crewai_crew
    assert "art12" in rule_keys  # crewai_task


def test_all_framework_triggers_map_to_known_rules() -> None:
    framework_triggers = {k for k in TRIGGER_TO_RULE if "_" in k and ":" not in k}
    assert framework_triggers, "expected framework trigger mappings"
    assert {TRIGGER_TO_RULE[k] for k in framework_triggers} <= set(FIX_RULES.keys())
