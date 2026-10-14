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

## Remaining phases — not implemented

4. Workflows and analytics: multi-step execution, pandas, SQLite state.
5. MCP and customization: real MCP demo, rules, skills, optional hooks/subagents.
6. Dashboard: Streamlit and required architecture/execution visualizer; export if feasible.
7. Testing and demo: end-to-end verification and presentation documentation.

The original phase budget totals 300 minutes. Keep optional additions small and
protect the required visualizer. Do not begin a new phase without user instruction.
