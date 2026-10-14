# MarketPilot AI — Project Progress

## Git workflow

After each phase, run the relevant checks and update this progress file. Commit
and push only when the user explicitly requests it. Never include API keys, local environment
files, virtual environments, or generated databases. If a phase still has a
blocked validation step, record that limitation accurately in the checkpoint.

## Phase 1 — Setup and First Agent

Status: complete; locally tested and live API response verified in the user's terminal.

- Python 3.12 virtual environment created; project supports Python 3.11+.
- Basic Python package, console entry point, and single-request CLI implemented.
- OpenAI Agents SDK Agent and Runner configured with marketing instructions.
- Uses OPENAI_API_KEY exclusively for project API authentication.
- Model configurable through MARKETPILOT_MODEL or --model.
- Email and social content remain drafts. No external action tools exist.
- Credentials and virtual environment excluded from Git.
- Basic offline tests cover validation, runner wiring, and CLI errors.

Validation:
- Installed openai-agents 0.23.1 and pytest 9.1.1 in the project virtual environment.
- Editable project installation succeeded; SDK version pinned in pyproject.toml.
- `python -m pytest -q`: 4 passed.
- `python -m pip check`: no broken requirements.
- CLI help runs successfully.
- Missing-key check in Codex's shell exits with code 2 and an actionable message.
- User verified the live CLI in their own terminal with:
  `python -m marketpilot "Write one headline for a student productivity app."`
  It returned: "Boost Your Study Efficiency: Master More, Stress Less with [App Name]".

Live verification is based on the user's provided terminal output. The key is
available in their terminal, but not inherited by Codex's shell. Project API
authentication remains separate from Codex login.

## Phase 2 — Tools and Marketing Features

Status: implemented and offline validated; live API verification pending the user's terminal run.

- Added research_market, generate_content, create_social_posts, and draft_email
  as real SDK function tools. The main LLM chooses tool arguments and calls.
- Research requires hosted web search and preserves actual API search actions
  and URL citations; there is no fallback to mock research.
- Drafting tools call the Responses API with focused prompts and structured
  Pydantic output. All emails/posts remain drafts; no sending/publishing exists.
- Tool execution produces terminal running/completed/failed messages and local
  JSON logs under data/runs, excluded from Git. Logs preserve inputs, outputs,
  timestamps, durations, errors, and run/step IDs for the Phase 6 visualizer.
- Main runner limit increased to 8 turns; tool calls configured as sequential.
- SDK failures and log filesystem errors now produce CLI error messages.
- No new dependencies, subagents, MCP, RAG, analytics, SQLite, or UI added.

Validation:
- `python -m pytest -q`: 14 passed (4 existing tests and 10 Phase 2 cases).
- An offline integration test exercised the real SDK tool dispatch and result
  feedback loop with a scripted test model. This is explicitly a test simulation,
  not evidence of a live model choosing a tool.
- Tests cover tool limits, draft parsing/count validation, cited research checks,
  failure recording, credential redaction, and terminal progress callbacks.
- `python -m pip check`: no broken requirements; CLI help works.
- OPENAI_API_KEY is not available in Codex's shell. No live Phase 2 API run has
  been verified yet. Run the Phase 2 example in README.md from the user's terminal.

Limitations: research summaries still require source review; custom models must
support Responses API structured outputs and hosted web search. Drafting tools
make additional paid API calls. Hosted search actions have no per-action timing;
the research tool duration covers the whole API operation. Invalid SDK argument
schemas fail the run before a Python tool step exists. Logs do not provide memory.

## Phase 3 — Knowledge Base and RAG

Status: implemented and offline validated; local keyword retrieval verified.
Live embedding/index generation and a live model-generated RAG answer remain
pending an API-enabled terminal. The user authorized the Phase 3 checkpoint
with the commit message `phase 3 completed`.

- Added three fictional StudySprint Markdown documents with title, tags, status,
  and date metadata. This is a simple bundle-style demonstration, not a formal
  OKF implementation or general-purpose YAML parser.
- Added heading-aware chunks with source lines, metadata, stable IDs, and overlap
  in long sections. The shipped corpus produces 9 chunks from 3 documents.
- Added real text-embedding-3-small API requests and a cached local JSON vector
  index. Unchanged indexes are reused; stale source fingerprints are rejected.
- Added keyword, cosine-based semantic, and weighted hybrid retrieval. Returned
  evidence includes citations and demo labels, without sending vectors to the LLM.
- Added a knowledge CLI for explicit indexing and direct evidence inspection.
- Added search_knowledge as the fifth logged agent tool, plus grounding/citation
  instructions. The existing execution logger supports retrieval without changes.
- No new dependencies, SQLite, MCP, subagents, dashboard, or later-phase code.

Validation:
- `python -m pytest -q`: 28 passed, including 14 new Phase 3 cases.
- Real local keyword search found product.md's Supported features passage and
  preserved its source line 11 and fictional_demo metadata.
- An SDK integration test passed real local passages back to a scripted model;
  this verifies tool plumbing, not a live model's behavior.
- Tests cover metadata, chunk boundaries/overlap, no-match keyword queries,
  embedding batch ordering, cache reuse, stale documents, invalid vectors,
  semantic/hybrid ranking with explicit fixture vectors, and error messages.
- `python -m pip check`: no broken requirements; knowledge CLI help works.
- OPENAI_API_KEY is absent from Codex's shell. No real embedding index was built,
  no mock vectors were saved as a production index, and no live RAG answer claimed.

Limitations: JSON is a small local vector index, not a dedicated vector database.
Character chunking can split words. Keyword scoring is simple word overlap, not
BM25; hybrid weights are heuristic, not tuned. Rankings are not confidence scores
and can return irrelevant passages. Demo audience notes are hypotheses, not research.
Semantic/hybrid search needs an up-to-date index and paid query embeddings.
Conversation memory, SQL retrieval, and a dashboard are still unimplemented.

## Phase 4 — Workflows and Analytics

Status: implemented and offline validated. Deterministic sample analytics and
SQLite persistence are verified; live LLM orchestration and report generation
remain pending the user's API-enabled terminal. The user authorized sequential phase-end commits and pushes.

- Added pandas CSV analysis with schema/value validation and aggregate/channel
  CTR, conversion rate, CPC, CPA, and optional ROAS. Null represents undefined metrics.
- Added a fictional sample CSV: 25,000 impressions, 1,400 clicks, 85 conversions,
  EUR 600 spend, and EUR 1,700 revenue. Computed CTR is 5.6% and CPA EUR 7.0588.
- Added analyze_campaign and read_saved_report tools; seven tools now share the
  existing sequential SDK loop with an eight-turn limit.
- Added optional CampaignReport output schema through --campaign and Markdown
  rendering. Stored reports retain both the structured fields and displayed text.
- Added SQLite runs/tool_steps tables, saving actual execution transitions and
  explicit report retrieval with fixed parameterized queries. This is saved state,
  not automatic memory, model-generated SQL, or resumable execution.
- Added workflow_cli analyze/list/show commands that require no API key.
- Added pandas 3.0.6 to pyproject.toml and generated requirements.txt with pip
  freeze --exclude marketpilot-ai, omitting machine-specific editable paths.
- Phase 4 committed and pushed as b53eb08 after explicit user authorization. No files deleted.

Validation:
- `python -m pytest -q`: 46 passed, including 18 Phase 4 cases.
- Real local sample CSV analysis matches expected weighted totals and channel rates.
- Tests cover invalid/missing numeric data, whole counts, currency consistency,
  duplicate columns, restricted paths, zero denominators, and unavailable revenue.
- SQLite tests verify running/completed/failed snapshots, reopened databases,
  key redaction, ordered steps, saved reports, and parameterized ID queries.
- A real SDK integration test runs local retrieval -> analytics -> mocked email
  drafting -> a structured report using a scripted test model, then reopens SQLite
  and checks results. This does not claim live LLM planning has been verified.
- CLI help works; dependency checks report no broken requirements.
- OPENAI_API_KEY remains unavailable to Codex's shell; no live Phase 4 API run claimed.

Limits: simple CSV schema assumes conversions <= clicks <= impressions and one
currency. Maximum file size is 5 MB and 10,000 rows. Observational metrics do not
establish causality or significance. Structured output validates shape, not facts.
JSON and SQLite writes are separate; forced termination may leave running state.
No automatic resume, sessions, MCP, dashboard, or visualizer has been implemented.

## Phase 5 — MCP and Agent Customization

Status: implemented and tested; real MCP subprocess verified without an API key.
Live LLM MCP selection remains pending an API-enabled terminal.

- Real stdio MCP server exposes two tools, one Markdown resource, and one prompt.
- Optional --mcp attaches the server natively through the Agents SDK and logs calls.
- Fixed rules and explicitly selected --skill campaign-review load Markdown instructions.
- These are application-level conventions; no native skill registry, plugins, or subagents claimed.
- Real RunHooks callbacks record main-model call statuses, timing, and token counts.
- SQLite migration retains older runs and adds configuration/model-call JSON fields.
- mcp 2.3.0 declared explicitly; inspection CLI exercises all three protocol primitives.
- 51 tests passed, including actual subprocess protocol calls and native SDK dispatch
  with a scripted test model. Failure logging and legacy SQLite migration are tested.
- Resources/prompts are not automatically attached to model context. Hooks do not
  instrument the separate model requests inside drafting/research helper functions.

## Phase 6 — Dashboard and Workflow Visualizer

Status: implemented and tested. Live OpenAI workflow remains pending the user's
API-enabled terminal; actual browser appearance awaits user review.

- Streamlit Workspace, Knowledge, MCP, Learn, and Workflow visualizer views reuse
  existing core functions; no second agent runtime introduced.
- Architecture diagram distinguishes implemented, optional/inactive, and unimplemented
  components. A selected local demo clearly bypasses LLM planning.
- Execution diagram uses actual stored tool steps with statuses/durations and an
  input/output/error inspector. Model-call hook records can be inspected separately.
- Presentation mode, DOT export, conditional SVG export, Markdown report export,
  and JSON record export implemented. Native dot is not installed in this environment.
- CSV upload validates before persistence and uses a content-derived local filename.
- Explicit no-key demo executes actual retrieval, pandas, and real MCP operations;
  it makes no model calls and is not presented as autonomous agent planning.
- Added Streamlit 1.65.0, graphviz 0.21, theme config, and refreshed requirements.txt.
- Added an AI-agent interview guide with pitch, demo script, file map, and answer checkpoints.
- 57 tests passed, including Streamlit AppTest for no-key state, knowledge search,
  real local demo, execution inspection, presentation mode, and real MCP inspection.
- Local Streamlit server starts; /_stcore/health responds ok. Browser screenshot
  testing and live OpenAI calls are not claimed as verified.

## Remaining phases — not implemented

7. Testing and demo: end-to-end verification and presentation documentation.

The original phase budget totals 300 minutes. Keep optional additions small and
protect the required visualizer. Do not begin a new phase without user instruction.
