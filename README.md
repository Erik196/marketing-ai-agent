# MarketPilot AI

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

## Completed phases

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
