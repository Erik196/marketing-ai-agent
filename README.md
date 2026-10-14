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

To exercise the Phase 2 tools:

```sh
python -m marketpilot "Research two current competitors for a student productivity app, then create a 3-day Instagram calendar and draft a promotional email. Use placeholders for unknown product features and offers."
```

Tool progress appears on stderr, followed by the final answer on stdout:

```text
[Log] .../data/runs/<run-id>.json
[Running] research_market
[Completed] research_market — <measured duration>s
```

These are illustrative messages, not a claim that a live run has been verified.
The log path points to the actual JSON record, which you can open in VS Code to
inspect inputs, outputs, status, and timing. Use `--quiet-tools` to hide terminal
progress while retaining the log. Logs stay local and are excluded from Git.

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
