# MarketPilot AI — Project Progress

## Git workflow

After each phase, run the relevant checks, update this progress file, commit the
phase's changes, and push to origin. Never include API keys, local environment
files, virtual environments, or generated databases. If a phase still has a
blocked validation step, record that limitation accurately in the checkpoint.

## Phase 1 — Setup and First Agent

Status: implemented and locally validated; live API verification pending credentials.

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
- Live smoke-test command exits with code 2 and an actionable missing-key message;
  no API request was made because OPENAI_API_KEY is not set.

Live API verification is pending: OPENAI_API_KEY was not available in the agent's
shell at setup. No successful live response has been claimed.

## Remaining phases — not implemented

2. Tools and marketing features: real tool calling and structured execution events.
3. Knowledge base and RAG: Markdown, chunking, embeddings, retrieval.
4. Workflows and analytics: multi-step execution, pandas, SQLite state.
5. MCP and customization: real MCP demo, rules, skills, optional hooks/subagents.
6. Dashboard: Streamlit and required architecture/execution visualizer; export if feasible.
7. Testing and demo: end-to-end verification and presentation documentation.

The original phase budget totals 300 minutes. Keep optional additions small and
protect the required visualizer. Do not begin a new phase without user instruction.
