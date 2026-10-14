# MarketPilot AI

MarketPilot AI is a command-line marketing agent that chooses tools, uses their
results, and produces marketing drafts or answers grounded in retrieved evidence.

## What it can do

- Research competitors, audiences, and trends using web search with citations.
- Draft advertising copy, headlines, blog outlines, social posts/calendars, and promotional emails.
- Retrieve product facts and brand guidance from a local Markdown knowledge base
  using keyword, semantic, or hybrid search.
- Combine retrieval/research and drafting in one request, with actual tool progress
  and inspectable JSON execution logs.

**Current scope:** phases 1–3 are implemented. Email and social content are draft-only.
There is no CSV analytics, conversation memory, MCP, dashboard, or workflow
visualizer yet. The sample knowledge describes **StudySprint, a fictional demo
product**. Research and retrieval results still need source review.

## Setup

Use Python 3.11+; the commands below use Python 3.12 and zsh on macOS.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

# Enter your key privately; do not commit it or paste it into chat.
read -rs 'OPENAI_API_KEY?OpenAI API key: '
export OPENAI_API_KEY
```

The application reads your shell's environment; it does not load `.env` files or
use your Codex login. Model, research, and embedding requests use API credits.

## Run and example prompts

Put any request in quotes:

```sh
python -m marketpilot "Draft three headlines for a productivity app targeting university students."
```

| Task | Example prompt |
| --- | --- |
| Research | Research two current competitors for student productivity apps and cite sources. |
| Ads or blog outlines | Draft two ads and one blog outline for a student productivity app. State assumptions. |
| Social calendar | Create a 3-day Instagram content calendar for a student productivity app. |
| Email | Draft a friendly promotional email for a student productivity app. Use placeholders for unknown offers. |
| Local knowledge | Use search_knowledge in keyword mode to list StudySprint's supported features. Cite sources and label it fictional. |
| Combined request | Research competitors, create a 3-day Instagram calendar, and draft a promotional email for a student productivity app. |

The model chooses tools based on the request; these are examples, not fixed
commands. Each invocation starts independently. `--model` overrides
`MARKETPILOT_MODEL` and the default `gpt-4.1-mini`; `--quiet-tools` hides progress
messages without disabling tools or logs. Use `python -m marketpilot --help` for options.

Tool status and the log path appear in the terminal. Open `data/runs/<run-id>.json`
to inspect tool inputs, outputs, statuses, and durations. Generated logs are excluded from Git.

## Knowledge search

Inspect local passages without running the marketing agent:

```sh
# Keyword search needs no API key or index.
python -m marketpilot.knowledge_cli search "StudySprint supported features" --mode keyword

# Build real embeddings before semantic/hybrid search or default agent retrieval.
python -m marketpilot.knowledge_cli index
python -m marketpilot.knowledge_cli search "help students organize coursework" --mode semantic
python -m marketpilot.knowledge_cli search "StudySprint brand voice" --mode hybrid
```

Indexing uses `text-embedding-3-small` and saves `data/knowledge_index.json` locally.
Rerun `index` after changing documents; unchanged indexes are reused. Semantic and
hybrid searches embed each query. Their default is hybrid; keyword searches use
current Markdown directly. The knowledge CLI prints evidence, while an agent
request generates an answer from that evidence.

## Test and validation

```sh
python -m pytest -q
python -m pip check
```

All 28 offline tests passed. Tests use mocked API/model responses and do not spend
credits. Phase 1 has a verified live response; Phase 2 live tool calls and Phase 3
live embeddings/RAG still need verification from an API-enabled terminal.
See [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) for status and
[REQUIREMENTS.md](REQUIREMENTS.md) for the planned visualizer.

## Build walkthrough by phase

### Phase 1 — Setup and First Agent

- Created a Python package and an isolated Python 3.12 virtual environment.
- Installed and configured the OpenAI Agents SDK.
- Defined the first Marketing Agent with marketing instructions and
  `gpt-4.1-mini` as its default model.
- Built a CLI that accepts a request and an optional model override, runs the
  agent, and prints its response.
- Configured API authentication through `OPENAI_API_KEY`.
- Added input validation and clear messages for common API errors.
- Added four offline tests; all passed, and the dependency check passed.
- Verified a real API request in the local terminal: a request for a student
  productivity app headline returned a generated headline.
- Added `.gitignore`, project requirements, and progress documentation; committed
  and pushed the Phase 1 checkpoint to GitHub.

The request flow is:

1. `marketpilot/cli.py` reads your request and optional model override.
2. `marketpilot/agent.py` validates the request and checks that a key is present.
3. `Agent` describes the assistant: name, instructions, and model.
4. `Runner.run()` sends the request and instructions to the model through the SDK.
5. The LLM creates a marketing response; Python prints `result.final_output`.

The SDK is the runtime/harness: it manages model interactions and, once we add
tools, the repeated model → tool → model loop. System instructions guide the
model's behavior; they are not executable Python or a hard security boundary.
There are no publishing tools, so this application cannot send emails or post.
Remote SDK tracing is disabled for this first exercise.

Phase 1 has no tools, live research, retrieval, CSV analysis, persistence, MCP,
subagents, or dashboard. General marketing suggestions are not verified market
research. We will collect actual tool execution events in Phase 2 and build the
workflow visualizer in Phase 6.

### Why the interface and agent logic are separate

`cli.main()` reads terminal arguments and prints the answer in the terminal.
The future Streamlit dashboard will read a web textbox and display the answer
on a webpage. It should call `run_marketing_agent()` directly rather than call
`cli.main()`, because terminal argument parsing does not belong in the dashboard.

Both interfaces can reuse the same agent logic:

```text
Terminal → cli.py ───────┐
                        ├→ run_marketing_agent() → SDK → LLM
Web page → Streamlit ───┘
```

The Streamlit path is planned for Phase 6; only the terminal interface exists now.

### Phase 2 — Tools and Marketing Features

- Added four real SDK function tools: `research_market`, `generate_content`,
  `create_social_posts`, and `draft_email`.
- Added live web research through OpenAI's hosted web search, requiring a
  completed search and cited summary. API-provided citations and search actions
  are preserved in the tool output.
- Added focused drafting prompts and a Pydantic output schema. Content variants
  are limited to 1–5 and social calendars to 1–7 days. All content stays draft-only.
- Connected tools to the main agent so the model can choose calls and consume
  their results; tool calls are configured to run sequentially.
- Added terminal status messages and JSON execution records for the future visualizer.
- Increased the main runner limit from 3 to 8 model turns and added SDK error handling.
- Passed 14 offline tests, including the real SDK model → tool → model loop with
  an explicitly scripted test model. Live Phase 2 API verification remains pending.

#### How a tool request works

1. The main LLM sees your request, instructions, and tool schemas.
2. It chooses a tool and produces JSON arguments. `@function_tool` derives the
   tool schema from the Python signature and docstring; the SDK validates arguments.
3. The SDK invokes the Python function. Its local context contains the run log
   and model name; the LLM does not supply this context.
4. Python records the running state and calls the relevant API operation.
5. Python records the result or failure and measured duration.
6. The SDK sends the tool result back to the main LLM, which can request another
   tool or compose a final answer. The runner stops when it receives a final answer.

The drafting tools use focused model calls to produce reusable structured drafts.
They are not separate agents or handoffs. Each drafting tool adds an API request;
web research also uses hosted search and its associated API charges. Research
is a web-sourced synthesis, not a guarantee that every claim is correct.
The 8-turn limit counts calls made by the main agent's runner; the focused API
calls inside tools are separate and do not count toward that limit.

#### Phase 2 code guide

| File | Functions or classes | Purpose |
| --- | --- | --- |
| `marketpilot/tools.py` | `DraftItem`, `DraftOutput` | Define the structured draft fields: title, labeled text items, and assumptions. |
| `marketpilot/tools.py` | `generate_draft()` | Call the Responses API with a focused prompt, parse the schema, and validate the item count. |
| `marketpilot/tools.py` | `search_market()` | Require hosted search and return its summary, citations, and search actions. |
| `marketpilot/tools.py` | `research_market()` | Expose and log the research operation as a function tool. |
| `marketpilot/tools.py` | `generate_content()` | Validate the variant count and draft ads, headlines, or blog outlines. |
| `marketpilot/tools.py` | `create_social_posts()` | Validate the calendar length and draft one post per day for a platform. |
| `marketpilot/tools.py` | `draft_email()` | Draft subject, preview text, body, and call to action. |
| `marketpilot/execution.py` | `utc_now()`, `redact()` | Produce UTC timestamps and mask API keys in saved text. |
| `marketpilot/execution.py` | `ExecutionLog.__init__()` | Create a unique run record and save its initial state. |
| `marketpilot/execution.py` | `emit()`, `save()` | Send progress to the interface and atomically save JSON. |
| `marketpilot/execution.py` | `execute()` | Wrap an actual tool operation with running/completed/failed events and timing. |
| `marketpilot/execution.py` | `finish()` | Save the final response or run failure and total duration. |
| `marketpilot/agent.py` | `create_marketing_agent()`, `run_marketing_agent()` | Attach tools, supply local context, and finalize the execution log. |
| `marketpilot/cli.py` | `main()` | Print progress to stderr, support `--quiet-tools`, and handle SDK/logging errors. |

The small inner `operation()` functions in content and social tools keep validation
inside the logged operation, so invalid limits are recorded as failed steps.
The lambdas defer API execution until `execute()` has saved the running event.

Run records contain a run ID, model, prompt, final output, overall status and timing,
and an ordered list of tool steps. Each step contains its own ID, tool name, inputs,
outputs, status, timestamps, duration, and error if one occurred. Ordering reflects
when operations start. Only operations entered in Python become tool steps; SDK
argument-validation failures are recorded as run failures. Hosted search actions
are preserved within research output; their individual durations are unavailable.

### Phase 3 — Knowledge Base and RAG

- Added a Markdown knowledge bundle containing fictional product facts, brand
  guidance, and audience hypotheses, each with title, status, tags, and date metadata.
- Added heading-aware chunking with 1,000-character windows and 150-character
  overlap inside long sections. Chunks retain source paths, line ranges, metadata,
  and stable IDs. Character windows keep this demonstration simple; they may split words.
- Added real OpenAI embeddings and a cached JSON vector index with stale-source detection.
- Added keyword search, semantic search using cosine similarity, and weighted
  hybrid search: 70% nonnegative semantic score plus 30% keyword score.
- Added `search_knowledge` as a logged SDK function tool. The agent can choose
  retrieval, consume passages, and cite source references before answering or drafting.
- Passed 28 offline tests in total, including a real SDK retrieval loop with a
  scripted test model. Real keyword search was verified against the sample documents.
- Live embedding requests and a live model-generated RAG answer remain unverified
  in Codex's shell because its API key is unavailable. No fake index is substituted.

#### The concepts in this implementation

**RAG** means retrieve relevant information, add it to the model's input, and
generate an answer from it. It does not train or change the model's weights.
**Embeddings** represent text as numeric vectors; cosine similarity compares
their directions. **Keyword search** matches exact words, while **semantic search**
can find related meaning with different wording. Hybrid search combines both.
Scores are ranking signals, not accuracy percentages, and top results can still
be irrelevant; the agent is instructed to acknowledge missing evidence.

This is a lightweight **agentic RAG** pattern: retrieval is a tool the agent can
choose and repeat with a more focused query. It is not an autonomous research
planner, reranker, or production retrieval system. The JSON file is a local vector
index, not a dedicated vector database. SQL retrieval belongs to a later phase.

The Markdown bundle uses a simple `---` metadata header containing single-line
`key: value` strings; tags are comma-separated text. This is a small bundle-style
demonstration, not a complete YAML parser or a claimed OKF-format implementation.
Keep source content in the body under Markdown headings. Every returned passage
includes its metadata so fictional examples remain distinguishable from real data.

#### Phase 3 files and reading order

1. `knowledge/product.md`, `brand.md`, and `audience.md`: inspect the source text
   and metadata before studying retrieval.
2. `marketpilot/retrieval.py`: follow loading → chunking → indexing → searching.
3. `marketpilot/knowledge_cli.py`: see how indexing and standalone search are invoked.
4. `marketpilot/tools.py`: read the new `search_knowledge()` wrapper.
5. `marketpilot/agent.py`: inspect the added retrieval instructions and citations policy.
6. `tests/test_phase3.py`: read the keyword test, then the index/ranking tests and SDK loop test.
7. This README and `PROJECT_PROGRESS.md`: review run commands, limitations, and validation.

| Function/class | Responsibility |
| --- | --- |
| `Document` | Hold a document's source, body, starting line, and metadata. |
| `load_documents()` | Read Markdown and its simple metadata header. |
| `chunk_document()` | Split heading sections into bounded, overlapping passages. |
| `collect_chunks()` | Load the whole knowledge directory and collect its chunks. |
| `corpus_fingerprint()` | Hash chunk content and metadata to detect changes. |
| `searchable_text()` | Combine title, tags, heading, and passage for search. |
| `embed_texts()` | Batch real embedding requests and restore input order. |
| `build_index()` | Reuse a current index or embed and atomically save a new one. |
| `validate_vectors()` | Reject empty, zero, nonfinite, or dimensionally inconsistent vectors. |
| `load_index()` | Reject missing, stale, malformed, or inconsistent cached indexes. |
| `keyword_score()` | Measure the fraction of query words present in a passage. |
| `cosine_similarity()` | Compare the query vector with a passage vector. |
| `retrieve_knowledge()` | Rank passages in the selected mode and return the top results with citations. |
| `knowledge_cli.main()` | Parse index/search commands and display results or errors. |
| `tools.search_knowledge()` | Expose retrieval to the agent and log its actual execution. |

No Phase 3 changes are needed in `execution.py`, `cli.py`, or `__main__.py`: the
existing tool logger and main runner already support another function tool.
The existing tool-registration test was updated to expect the fifth tool.
No files were deleted or dependencies added. No Phase 4–7 code was implemented.

#### File flow

This is a learning diagram, not the Phase 6 dashboard visualizer.

```mermaid
flowchart TD
    Docs["knowledge/*.md<br/>product, brand, audience"] --> Collect["retrieval.py<br/>load_documents → collect_chunks"]
    KBCLI["knowledge_cli.py · main<br/>index command"] --> Build["retrieval.py · build_index"]
    Collect --> Build
    Build --> Embed["retrieval.py · embed_texts<br/>Embed document passages via OpenAI"]
    Embed --> Index["data/knowledge_index.json<br/>text, metadata, vectors"]
    KBCLI -->|search command| Retrieve["retrieval.py · retrieve_knowledge"]
    Entry["__main__.py"] --> CLI["cli.py · main"]
    CLI --> Agent["agent.py · run_marketing_agent<br/>create_marketing_agent"]
    Agent --> SDK["SDK Runner + main model"]
    SDK -->|tool call| Tool["tools.py · search_knowledge"]
    Tool --> Log["execution.py · execute<br/>record running, then perform retrieval"]
    Log --> Retrieve
    Collect -->|current passages| Retrieve
    Index -->|semantic / hybrid only| Retrieve
    Retrieve -->|semantic / hybrid only| QueryEmbed["retrieval.py · embed_texts<br/>Embed query via OpenAI"]
    QueryEmbed -->|query vector| Retrieve
    Retrieve --> Evidence["Top passages + metadata + citations"]
    Evidence -->|record tool result| Log
    Log --> Runs["data/runs/*.json"]
    Log -->|return tool result| SDK
    SDK -->|final answer| Agent
    Agent -->|finish run log| Runs
    Agent -->|answer| CLI
    Tests["tests/test_phase3.py"] -.->|verify| Retrieve
    Tests -.->|verify| SDK
```
