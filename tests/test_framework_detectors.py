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


def test_framework_version_populated_from_requirements(tmp_path: Path) -> None:
    """A detected framework reports the version declared in requirements.txt."""
    (tmp_path / "crew.py").write_text(CREWAI_APP)
    (tmp_path / "requirements.txt").write_text("crewai==0.30.1\nopenai>=1.0\n")

    result = ScannerEngine(tmp_path).scan()

    crewai = next(f for f in result.frameworks_detected if f.name == "crewai")
    assert crewai.version == "0.30.1"


def test_framework_version_none_without_manifest(tmp_path: Path) -> None:
    """Version stays None when no manifest declares the framework."""
    (tmp_path / "crew.py").write_text(CREWAI_APP)

    result = ScannerEngine(tmp_path).scan()

    crewai = next(f for f in result.frameworks_detected if f.name == "crewai")
    assert crewai.version is None


# --- provider / framework gap fixes ---------------------------------------------

VERCEL_EXPERIMENTAL_APP = """
import { experimental_generateObject, experimental_streamObject } from "ai";
import { azure } from "@ai-sdk/azure";

export async function extract(input) {
  return await experimental_generateObject({ model: azure("gpt-4o"), schema });
}
"""

LLAMAINDEX_PY_APP = """
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.agent import ReActAgent

documents = SimpleDirectoryReader("data").load_data()
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()
agent = ReActAgent.from_tools(tools)
"""

LLAMAINDEX_JS_APP = """
import { VectorStoreIndex, Document } from "@llamaindex/core";
import { OpenAI } from "@llamaindex/openai";

const index = await VectorStoreIndex.fromDocuments(documents);
const queryEngine = index.asQueryEngine();
"""


def test_vercel_experimental_structured_output_detected() -> None:
    findings = VercelAIDetector().analyze(Path("app.ts"), VERCEL_EXPERIMENTAL_APP)
    assert any(f.category == "vercel_structured_output" for f in findings)


def test_ai_sdk_azure_maps_to_openai_provider() -> None:
    from compliance_agent.scanner.detectors.providers import _module_provider

    assert _module_provider("@ai-sdk/azure") == "openai"


def test_langchain_textsplitters_import_recognized() -> None:
    content = 'import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";\n'
    assert LangChainDetector().uses_framework(Path("split.ts"), content)


def test_crewai_entity_memory_detected() -> None:
    content = (
        "from crewai import Crew\nfrom crewai.memory import EntityMemory\nm = EntityMemory()\n"
    )
    findings = CrewAIDetector().analyze(Path("app.py"), content)
    assert any(f.category == "crewai_memory" for f in findings)


def test_crewai_memory_true_requires_word_boundary() -> None:
    # `memory=Trueish` is not the CrewAI memory kwarg and must not match.
    content = "from crewai import Crew\nc = SomeConfig(memory=Trueish)\n"
    findings = CrewAIDetector().analyze(Path("app.py"), content)
    assert not any(f.category == "crewai_memory" for f in findings)


def test_crewai_memory_true_still_detected() -> None:
    content = "from crewai import Crew\ncrew = Crew(agents=[a], memory=True)\n"
    findings = CrewAIDetector().analyze(Path("app.py"), content)
    assert any(f.category == "crewai_memory" for f in findings)


def test_llamaindex_python_detection() -> None:
    from compliance_agent.scanner.detectors.frameworks import LlamaIndexDetector

    findings = LlamaIndexDetector().analyze(Path("rag.py"), LLAMAINDEX_PY_APP)
    cats = {f.category for f in findings}
    assert "llamaindex_indexing" in cats
    assert "llamaindex_query" in cats
    assert "llamaindex_agent" in cats
    assert all(f.detector == "frameworks:llamaindex" for f in findings)


def test_llamaindex_js_detection() -> None:
    from compliance_agent.scanner.detectors.frameworks import LlamaIndexDetector

    findings = LlamaIndexDetector().analyze(Path("rag.ts"), LLAMAINDEX_JS_APP)
    cats = {f.category for f in findings}
    assert "llamaindex_indexing" in cats
    assert "llamaindex_query" in cats


def test_llamaindex_registered_in_all_detectors() -> None:
    from compliance_agent.scanner.detectors.frameworks import (
        ALL_FRAMEWORK_DETECTORS,
        LlamaIndexDetector,
    )

    assert LlamaIndexDetector in ALL_FRAMEWORK_DETECTORS


SEMANTIC_KERNEL_APP = """
from semantic_kernel import Kernel
from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent

kernel = Kernel()
kernel.add_plugin(my_plugin, plugin_name="tools")
agent = ChatCompletionAgent(kernel=kernel, name="assistant")
chat = AgentGroupChat(agents=[agent])
"""

HAYSTACK_APP = """
from haystack import Pipeline
from haystack.components.agents import Agent
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever

store = InMemoryDocumentStore()
pipeline = Pipeline()
agent = Agent(chat_generator=generator, tools=[my_tool])
retriever = InMemoryBM25Retriever(document_store=store)
"""

DSPY_APP = """
import dspy
from dspy.teleprompt import BootstrapFewShot

qa = dspy.Predict("question -> answer")
cot = dspy.ChainOfThought("question -> answer")
agent = dspy.ReAct("question -> answer", tools=[search, calc])
optimizer = BootstrapFewShot(metric=validate_answer)
"""

INSTRUCTOR_APP = """
import instructor
from pydantic import BaseModel

class User(BaseModel):
    name: str

client = instructor.from_openai(openai.OpenAI())
user = client.chat.completions.create(response_model=User, messages=[])
"""


def test_semantic_kernel_detection() -> None:
    from compliance_agent.scanner.detectors.frameworks import SemanticKernelDetector

    findings = SemanticKernelDetector().analyze(Path("assistant.py"), SEMANTIC_KERNEL_APP)
    cats = {f.category for f in findings}
    assert "semantic_kernel_agent" in cats
    assert "semantic_kernel_kernel" in cats
    assert "semantic_kernel_plugin" in cats
    assert all(f.detector == "frameworks:semantic_kernel" for f in findings)


def test_haystack_detection() -> None:
    from compliance_agent.scanner.detectors.frameworks import HaystackDetector

    findings = HaystackDetector().analyze(Path("rag.py"), HAYSTACK_APP)
    cats = {f.category for f in findings}
    assert "haystack_agent" in cats
    assert "haystack_pipeline" in cats
    assert "haystack_indexing" in cats
    assert "haystack_retrieval" in cats
    assert all(f.detector == "frameworks:haystack" for f in findings)


def test_dspy_detection() -> None:
    from compliance_agent.scanner.detectors.frameworks import DSPyDetector

    findings = DSPyDetector().analyze(Path("program.py"), DSPY_APP)
    cats = {f.category for f in findings}
    assert "dspy_agent" in cats
    assert "dspy_module" in cats
    assert "dspy_optimizer" in cats
    assert all(f.detector == "frameworks:dspy" for f in findings)


def test_instructor_detection() -> None:
    from compliance_agent.scanner.detectors.frameworks import InstructorDetector

    findings = InstructorDetector().analyze(Path("extract.py"), INSTRUCTOR_APP)
    cats = {f.category for f in findings}
    assert "instructor_structured_output" in cats
    assert all(f.detector == "frameworks:instructor" for f in findings)


def test_new_framework_detectors_registered_in_all_detectors() -> None:
    from compliance_agent.scanner.detectors.frameworks import (
        ALL_FRAMEWORK_DETECTORS,
        DSPyDetector,
        HaystackDetector,
        InstructorDetector,
        SemanticKernelDetector,
    )

    assert DSPyDetector in ALL_FRAMEWORK_DETECTORS
    assert HaystackDetector in ALL_FRAMEWORK_DETECTORS
    assert InstructorDetector in ALL_FRAMEWORK_DETECTORS
    assert SemanticKernelDetector in ALL_FRAMEWORK_DETECTORS
