# Detectors — Full Reference

This is the exhaustive reference for what the scanner actually looks for in
your code: every AI provider, framework, and generic pattern it recognizes,
and the precise import/construct that triggers each one. For what happens
*after* a finding is emitted (how it becomes a compliance status), see
[ARTICLES.md](ARTICLES.md). For the pipeline overview, see
[ARCHITECTURE.md](ARCHITECTURE.md).

## Python vs. JS/TS: a key distinction

**Python files are parsed with a real AST** (`ast.parse`). This means a
provider name sitting in a comment, a docstring, or a string literal never
falsely triggers a finding — only an actual `import` statement or
constructor call does. If a Python file fails to parse (a syntax error), the
scanner falls back to a regex over import lines only.

**JS/TS files have no AST parser** — detection is regex/string-based, over
comment-stripped source. Comments are stripped first, so a commented-out
`// new OpenAI(...)` won't match, but a string literal that happens to
contain matching text theoretically could — there's no bundled JS/TS parser
to make findings AST-precise the way Python's are. In practice this rarely
causes false positives because the patterns matched are specific constructor
names and import specifiers, not generic words.

## `providers.py` — AI Provider Detection

Detection has a **strong vs. weak** split. Strong signals: a matching import
plus a constructor call (e.g. `import openai` + `OpenAI(...)`), or a
provider-specific API shape like `boto3.client("bedrock-runtime")`. Weak
signals: a dotted-attribute API fragment alone (`chat.completions`,
`ChatCompletion`, `messages.create`, `messages.stream`) — these only count
when no strong provider was already found, or when they agree with one
already proven (this is what stops Groq's OpenAI-compatible
`.chat.completions` call from being mislabeled as the `openai` provider).

Every provider finding is `Severity.INFO`, category `provider:<key>`, and
maps to **Art. 3** (definitions) and **Art. 6** (classification) — provider
usage on its own is informational; it's what article coverage does with it
(combined with risk-tier signals) that determines real obligations.

| Provider | Python trigger | JS/TS trigger |
|---|---|---|
| **OpenAI** | `import openai`; constructors `OpenAI`, `AsyncOpenAI`, `AzureOpenAI`, `AsyncAzureOpenAI`, `ChatOpenAI`; weak: `chat.completions`, `ChatCompletion` | `"openai"`; `@langchain/openai`; `@ai-sdk/openai`; `@ai-sdk/azure` (Azure-hosted, still labeled `openai`) |
| **Anthropic** | `import anthropic`; `Anthropic`, `AsyncAnthropic`, `ChatAnthropic`; `AnthropicBedrock` → labeled `bedrock` instead; weak: `messages.create`, `messages.stream` | `@anthropic-ai/sdk`; `@langchain/anthropic`; `@ai-sdk/anthropic` |
| **Mistral** | `import mistralai`; `Mistral`, `MistralClient`, `ChatMistralAI` | `@mistralai/mistralai`; `@langchain/mistralai`; `@ai-sdk/mistral` |
| **Cohere** | `import cohere` (module import only — no dedicated constructor pattern) | `cohere-ai`; `@langchain/cohere`; `@ai-sdk/cohere` |
| **Groq** | `import groq`; `Groq`, `ChatGroq` | `groq-sdk`; `@langchain/groq`; `@ai-sdk/groq` |
| **Together** | `import together`; `Together`, `ChatTogether` | `together-ai`; `@ai-sdk/togetherai` |
| **Replicate** | `import replicate`; `Replicate` | `replicate` (same package name on npm) |
| **Hugging Face** | `import huggingface_hub`; `InferenceClient`, `ChatHuggingFace`; also `langchain_huggingface` | `@huggingface/inference` |
| **Google (Generative AI)** | `google.generativeai` or `google.genai` (both normalize to `google`); `ChatGoogleGenerativeAI` | `@google/generative-ai`; `@google/genai`; `@langchain/google-genai`; `@ai-sdk/google` |
| **Google Vertex AI** | `langchain_google_vertexai`; `ChatVertexAI` | `@google-cloud/vertexai`; `@langchain/google-vertexai` |
| **AWS Bedrock** | `langchain_aws`; `ChatBedrock`/`BedrockChat`; `AnthropicBedrock`; **or** any `boto3.client(...)`/`boto3.resource(...)` call whose string argument starts with `"bedrock"` (case-insensitive) | `@aws-sdk/client-bedrock-runtime`; `@langchain/aws`; `@ai-sdk/amazon-bedrock` |
| **DeepSeek** | `deepseek`, `deepseek_sdk`, `langchain_deepseek`; `ChatDeepSeek` | `@ai-sdk/deepseek` |
| **Fireworks AI** | `fireworks`, `langchain_fireworks`; `Fireworks`, `AsyncFireworks`, `ChatFireworks` | `@ai-sdk/fireworks` |
| **xAI (Grok)** | `xai_sdk`, `langchain_xai`; `ChatXAI` | `@ai-sdk/xai` |
| **LiteLLM** | `import litellm`; `ChatLiteLLM` | — |
| **Local runtimes** (transformers, ollama, vLLM, torch, llama.cpp) | `transformers`, `ollama`, `vllm`, `torch`, `llama_cpp`, `langchain_ollama` (all normalize to `local`); `ChatOllama` | `ollama`; `node-llama-cpp`; `@xenova/transformers`; `@langchain/ollama` |

**Vercel AI SDK** is detected here for *provider identification* only — the
`@ai-sdk/*` adapter packages map to whichever underlying provider they wrap
(the bare `"ai"` package is deliberately excluded from the provider table
since it's provider-agnostic). The SDK's own constructs — `generateText`,
`streamText`, tool calling, `maxSteps` — are a separate detector, covered
under `frameworks/vercel_ai.py` below. Node OpenAI SDK and LangChain.js
imports are also handled directly in `providers.py`'s npm package tables —
there's no separate JS-specific provider detector file.

## `agents.py` — Agent Patterns

Category prefix `agent:`; every finding maps to **Art. 14** (human
oversight).

- **MCP servers** (`agent:mcp-server`) — Python: `mcp.server`, `McpServer`,
  `@server.tool`, `@server.prompt`, `.mcp.json`, `from mcp import ...`/
  `import mcp`. JS: `server.tool(`, `server.prompt(`, `server.resource(`,
  `@modelcontextprotocol/sdk`. A literal `.mcp.json` file in the project
  always triggers a finding on its own. Only `.py`/JS-TS files are scanned
  for code signals — docs/YAML/README content is excluded here.
- **Tool calls** (`agent:tool-calls`, WARNING) — `tools = [`, `tool_choice`,
  `function_call` — but only in files that already have an AI import (see
  "gated on AI imports" below).
- **Multi-agent orchestration** (`agent:multi-agent`, WARNING) — three
  tiers, all gated on the file having an AI import: (1) a direct import of
  `crewai`, `autogen`, `autogen_agentchat`, `autogen_core`, `langgraph`, or
  the npm `@langchain/langgraph`; (2) the word `agent`/`agents` appearing on
  the same line as an AI-context word (`tools`, `llm`, `model`, `prompt`,
  `chain`, `workflow`, `autonomous`); (3) fallback — if nothing else matched,
  a filename like `sales_agent.py` or `my_agents.py` (the word `agent`/
  `agents` as a `_`/`-`-delimited token) on a file that has an AI import.
- **Prompt templates** (`agent:prompt-templates`, INFO) — unconditional:
  `ChatPromptTemplate`, `PromptTemplate`, `SystemMessage`; gated on AI
  imports: the generic snake_case `system_message`.

## `patterns.py` — General AI Application Patterns

Category prefix `pattern:`.

- **User input into AI** (`pattern:user-input`, INFO, → Art. 50) —
  `request.form`/`user_input` gated on AI imports; the bare word `query`
  gated on AI imports *or* an AI-suggestive filename (`llm`, `model`, or
  `prompt` in the `.py` filename). Note: plain `input(` is never flagged on
  its own — it's far too common in ordinary Python to be a useful signal.
- **Chat interface** (`pattern:chat-interface`, INFO, → Art. 50) — three
  tiers: unconditional strong hits (`chatbot`, `chat_interface`,
  `ChatCompletion`); an unconditional chat-UI framework import
  (`streamlit`, `gradio`, `chainlit`); and the bare word `chat`, gated on AI
  imports.
- **Data processing** (`pattern:data-processing`, INFO, → Art. 10) — only
  evaluated on files with an AI import: a `pandas`/`numpy` import, or a call
  to `read_csv(`/`load_dataset(`.
- **Missing logging** (`pattern:missing-logging`, WARNING, → Art. 12) — only
  evaluated on files with an AI import. `__init__.py` files are always
  skipped, as is any file that is "declarative-only" — every `Call` node in
  the file (other than class/function decorators) is a `field(...)`/
  `Field(...)` call, i.e. a pure dataclass/Pydantic schema with no real
  logic to log. Otherwise, the whole file is flagged (no specific line) if
  none of `import logging`, `logger`, `log.`, `structlog` appear anywhere in
  it.
- **Hand-rolled agent loop** (`pattern:custom-agent-loop`, WARNING, →
  Art. 14; Python-only, AST-based) — only evaluated on files with an AI
  import: a `while True:` (or `while 1:`) loop whose body contains a call
  that "names an agent step" — either the bare call is exactly `run_agent`
  (case-insensitive), or an attribute call (`x.y()`) where either the owner
  or the method name contains the substring `agent` (e.g. `agent.step()`,
  `self.agent.run()`, `run_agent_loop()`). Generic verbs alone — `run`,
  `execute`, `chat`, `generate`, `predict` — never trigger this on their
  own, so a bounded retry loop calling `client.chat(...)` is not flagged.

## "Gated on AI imports" — what that means

Several detectors above only look for a pattern *after* confirming the file
already imports something AI-related (`detect_ai_imports()` in
`detectors/base.py`). This two-step design exists because several of the
trigger words on their own are extremely generic — `query`, `chat`, `tools`
— and would produce noisy false positives in any ordinary web app or CLI
tool if matched unconditionally. Requiring a confirmed AI import first (an
OpenAI/Anthropic/etc. import, or a framework import) keeps these detectors
scoped to files that are actually doing something AI-related.

`detect_ai_imports()` checks `.py` and JS/TS files, restricted to a fixed
list of AI-related top-level modules — the same provider/framework module
names used above, plus `langchain`, `langchain_core`, `langchain_community`,
`crewai`, `autogen`, `langgraph`, `llamaindex`, the bare `ai` npm package, and
scoped `@ai-sdk/*`/`@langchain/*` packages.

## `frameworks/*.py` — Agentic Framework Detectors

Every framework detector requires the framework's package to actually be
imported before *any* of its patterns are checked — a bare string like
`Agent(` never fires on its own without a confirmed `crewai`/`autogen`/etc.
import in that file first. Each rule below carries its own EU AI Act article
mapping.

**LangChain** (`langchain`, `langchain_core`, `langchain_community`,
`langchain_openai`, `langchain_anthropic`, `@langchain/*`):
- `langchain_agent` (→ Art. 14, WARNING) — `AgentExecutor`,
  `create_openai_functions_agent`, `create_react_agent`,
  `create_tool_calling_agent`, `initialize_agent`, `AgentType`.
- `langchain_tools` (→ Art. 9) — `@tool` decorator, `Tool(`, `BaseTool`,
  `StructuredTool`, JS `tool(`, `DynamicTool`, `DynamicStructuredTool`.
- `langchain_memory` (→ Art. 12) — `ConversationBufferMemory`,
  `ConversationSummaryMemory`, `ConversationBufferWindowMemory`,
  `.save_context(`, JS `BufferMemory`, `BufferWindowMemory`.
- `langchain_chain` (→ Art. 50) — `LLMChain(`, `ConversationChain(`,
  `SequentialChain(`, `chain.invoke`/`.predict`/`.run`.

**CrewAI** (`crewai`):
- `crewai_crew` (→ Art. 14, WARNING) — `Crew(`, `.kickoff(`.
- `crewai_agent` (→ Art. 9) — `Agent(`.
- `crewai_task` (→ Art. 12) — `Task(`.
- `crewai_memory` (→ Art. 12) — `LongTermMemory`, `ShortTermMemory`,
  `EntityMemory`, `UserMemory`, `ExternalMemory`, `memory=True`.
- `crewai_process` (→ Art. 11) — `Process.sequential`, `Process.hierarchical`.

**AutoGen** (`autogen`, `autogen_agentchat`, `autogen_core`):
- `autogen_assistant` (→ Art. 50) — `AssistantAgent(`.
- `autogen_userproxy` (→ Art. 14, WARNING) — `UserProxyAgent(`,
  `human_input_mode`.
- `autogen_groupchat` (→ Art. 12, WARNING) — `GroupChat(`,
  `GroupChatManager(`.
- `autogen_tools` (→ Art. 9, WARNING) — `register_function(`,
  `register_for_llm`, `register_for_execution`, `code_execution_config`.
- `autogen_chat` (→ Art. 12) — `initiate_chat(`.

**LangGraph** (`langgraph`, `@langchain/langgraph`):
- `langgraph_graph` (→ Art. 11) — `StateGraph(`, `.add_node(`/`.addNode(`,
  `.compile(`.
- `langgraph_conditional` (→ Art. 14) — `.add_conditional_edges(`/
  `.addConditionalEdges(`.
- `langgraph_tools` (→ Art. 9) — `ToolNode`, `ToolExecutor`, `tools = [`/
  `tools: [`.
- `langgraph_checkpoint` (→ Art. 12) — `SqliteSaver`, `MemorySaver`,
  `checkpointer=`/`checkpointer:`.

**LlamaIndex** (`llama_index`, `llamaindex`, `@llamaindex/*`):
- `llamaindex_indexing` (→ Art. 10) — `VectorStoreIndex`, `SummaryIndex`,
  `KnowledgeGraphIndex`, `SimpleDirectoryReader`, `IngestionPipeline`,
  `from_documents`/`fromDocuments`.
- `llamaindex_query` (→ Art. 15) — `as_query_engine(`, `as_retriever(`,
  `asQueryEngine(`, `asRetriever(`, `RetrieverQueryEngine`,
  `QueryEngineTool`.
- `llamaindex_agent` (→ Art. 14, WARNING) — `ReActAgent`, `FunctionAgent`,
  `AgentWorkflow`, `AgentRunner`, `OpenAIAgent`.

**Vercel AI SDK** (`ai`, `@ai-sdk/*`):
- `vercel_generation` (→ Art. 50) — `generateText(`, `streamText(`,
  `useChat(`, `useCompletion(`.
- `vercel_tools` (→ Art. 9) — `tool({`, `tools: {`,
  `experimental_activeTools`.
- `vercel_agent_loop` (→ Art. 14, WARNING) — `maxSteps:`, `stopWhen:`,
  `experimental_continueSteps`.
- `vercel_structured_output` (→ Art. 11) — `generateObject(`,
  `streamObject(`, `experimental_generateObject(`,
  `experimental_streamObject(`.

**Semantic Kernel** (`semantic_kernel`):
- `semantic_kernel_agent` (→ Art. 14, WARNING) — `ChatCompletionAgent`,
  `AgentGroupChat`, `OpenAIAssistantAgent`, `AzureAssistantAgent`.
- `semantic_kernel_kernel` (→ Art. 11) — `Kernel(`.
- `semantic_kernel_plugin` (→ Art. 9) — `add_plugin(`, `KernelFunction`,
  `@kernel_function`.

**Haystack** (`haystack`):
- `haystack_agent` (→ Art. 14, WARNING) — `haystack.components.agents`,
  `Agent(`.
- `haystack_pipeline` (→ Art. 11) — `Pipeline(`.
- `haystack_indexing` (→ Art. 10) — `DocumentStore`,
  `InMemoryDocumentStore`, `DocumentWriter`.
- `haystack_retrieval` (→ Art. 15) — `Retriever(`, `BM25Retriever`,
  `EmbeddingRetriever`.

**DSPy** (`dspy`):
- `dspy_agent` (→ Art. 14, WARNING) — `dspy.ReAct`, `ReAct(`.
- `dspy_module` (→ Art. 11) — `dspy.Predict`, `dspy.ChainOfThought`,
  `dspy.Module`, `dspy.Signature`.
- `dspy_optimizer` (→ Art. 15) — `BootstrapFewShot`, `MIPROv2`,
  `teleprompt`.

**Instructor** (`instructor`):
- `instructor_structured_output` (→ Art. 15, INFO) — `instructor.from_openai`,
  `instructor.from_provider`, `response_model=`.

## Finding shape

Every detector emits a `Finding` (`scanner/detectors/base.py`) with a
deterministic id (`{detector}:{category}:{file_path}:{line_number}` — so the
same finding in the same file always gets the same id across scans, which is
what makes `diff_scans` able to track "resolved" vs. "new" findings) plus
`file_path`, an optional `line_number`, `severity`, `category`, a
human-readable `message`/`description`, the mapped `article`, and an
optional `suggestion`.
