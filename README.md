# MarketPilot AI

A five-hour learning project, built one phase at a time. Phase 1 provides a
single-request CLI marketing assistant using the OpenAI Agents SDK.

## Setup

Use Python 3.11+ (this workspace uses Python 3.12).

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Set `OPENAI_API_KEY` in the shell that runs the application. To enter it without
displaying it or putting the value into shell command history, in zsh use:

```sh
read -rs 'OPENAI_API_KEY?OpenAI API key: '
export OPENAI_API_KEY
```

Do not paste your key into chat or commit it. The application reads the environment
variable; it does not use your Codex login, and does not load `.env` files.
API requests use your API account's credits. `.env` files are ignored by Git.

## Run

```sh
python -m marketpilot "Suggest three campaign ideas for a productivity app targeting university students. State your assumptions."
```

The default model is `gpt-4.1-mini`. You can configure a model available to your
API account using `MARKETPILOT_MODEL` or an explicit CLI override:

```sh
python -m marketpilot --model gpt-4.1-mini "Draft one headline for a student productivity app."
marketpilot --help
```

Each invocation is independent. The CLI prints Markdown text; it does not render
a dashboard. Missing credentials, authentication errors, quota errors, and
connection errors produce actionable messages and nonzero exit codes.

## Test

```sh
python -m pytest -q
python -m pip check
```

Unit tests use a mocked SDK runner and do not spend API credits. They do not
prove live API connectivity. Run the marketing request above for a live smoke
test after setting your key.

## How Phase 1 works

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

See [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) for validation and limitations and
[REQUIREMENTS.md](REQUIREMENTS.md) for the visualizer requirements.

Official pattern: [OpenAI Agents SDK quickstart](https://developers.openai.com/api/docs/guides/agents/quickstart).

