# MarketPilot AI — Project Progress

## Git workflow

After each phase, run the relevant checks, update this progress file, commit the
phase's changes, and push to origin. Never include API keys, local environment
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

## Remaining phases — not implemented

3. Knowledge base and RAG: Markdown, chunking, embeddings, retrieval.
4. Workflows and analytics: multi-step execution, pandas, SQLite state.
5. MCP and customization: real MCP demo, rules, skills, optional hooks/subagents.
6. Dashboard: Streamlit and required architecture/execution visualizer; export if feasible.
7. Testing and demo: end-to-end verification and presentation documentation.

The original phase budget totals 300 minutes. Keep optional additions small and
protect the required visualizer. Do not begin a new phase without user instruction.
