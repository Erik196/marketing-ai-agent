# MarketPilot workflow guide

Technical notes for inspecting the local application, tracing tool results, and
understanding implementation decisions.

## Inspect a local workflow

1. Start `python -m streamlit run app.py` from the terminal with your API key.
2. Run a request using local knowledge, sample CSV analytics, and an email draft.
3. Open Execution view to inspect the recorded inputs, outputs, status, and duration.
4. Check the saved report and compare its claims with the original tool results.
5. Enable MCP when needed and inspect the separate server's recorded operations.

Without an API key, “Run local demo — no LLM” executes actual retrieval, analytics,
and MCP calls. It does not perform autonomous model planning or generate content.

## Trace one request through the code

```text
app.py (or cli.py)
  → agent.py · run_marketing_agent()
      → create_marketing_agent(): instructions, tools, optional report schema
      → ExecutionLog + WorkflowStore: initial running record
      → optional LoggedMCPServer: start/connect server
      → Runner.run(): bounded model/tool loop
          → model chooses tool name + JSON arguments
          → SDK validates and invokes the tool
          → tools.py · search_knowledge()
              → execution.py · execute(): save running
              → retrieval.py · retrieve_knowledge(): return passages
              → execute(): save completed/output/timing
          → SDK adds function_call_output with matching call ID to history
          → next model call consumes that evidence
          → analytics/drafting tools when requested
      → CampaignReport parsed in --campaign mode
      → to_markdown(), log.finish(), SQLite final snapshot
  → display report and diagrams
```

`context=log` is local Python state. It does not put the logger in the model's
prompt. The model sees tool results because the SDK adds them to conversation
history. Separate drafting API calls receive their focused instructions and brief;
they do not automatically share the main model's history.

## Architecture decisions and limitations

| Decision | Reason and limitation |
| --- | --- |
| One main agent | Simple orchestration; separate drafting calls are not subagents. |
| Function tools | Typed schemas expose capabilities while Python performs the work. |
| Eight main-model turns | Bounds the runner; helper API calls and retries are separate. Stops earlier on a final answer. |
| Sequential calls | Easier evidence dependencies and understandable execution records. |
| Python/pandas metrics | Deterministic arithmetic instead of relying on generated numbers. Aggregate before calculating rates. |
| Markdown + local vectors | Easy to inspect and small enough for a local index. Not a dedicated vector database. |
| Hybrid retrieval | Combines exact words and related meaning. Weights are heuristic; ranks are not confidence. |
| Cached embeddings | Reuse document vectors; re-embed queries and reject stale source indexes. No model training happens. |
| SQLite + JSON | Queryable persistent state plus readable logs. Separate writes; not an automatic resume system. |
| Structured final report | Validates shape, not truth. Check original evidence and recorded tool calls. |
| MCP | Standard protocol for a separate server's capabilities, rather than a Python-only import. |
| Rules/skills | Explicit Markdown instructions. They are application conventions, not a native plugin/skill registry. |
| Hooks | Actual SDK callbacks observe main-model calls; Python wrappers observe tool operations. |
| Graphviz visualizer | Clear, inspectable diagrams using stored events. No invented execution steps or advanced frontend machinery. |

## Read the code in this order

1. `agent.py` and `cli.py`: understand the main entry point and loop configuration.
2. One tool in `tools.py`, then `execution.py`: follow its execution and result.
3. `retrieval.py`: loading/chunking → indexing → keyword/semantic/hybrid retrieval.
4. `analytics.py`: validate input → aggregate → calculate metrics.
5. `storage.py` and `reports.py`: persisted state and final output shape.
6. `mcp_server.py`, `mcp_client.py`: host/client/server and protocol primitives.
7. `customization.py`, rules/skills Markdown, `hooks.py`: customization and observation.
8. `app.py`, `visualizer.py`: UI and diagrams reuse the existing core.
9. Tests: identify what is real, what is mocked, and what each test proves.

You need to explain responsibility, data flow, and failure behavior. You do not
need to memorize every regex, SQL statement, or helper implementation.

## Implementation FAQ

1. **What makes this an agent rather than a single LLM request?** The model can
   choose tools, observe their results, and choose another action before answering.
2. **Who executes the tools?** The SDK invokes our Python functions or its MCP
   client; the model requests actions but does not execute Python itself.
3. **How do results reach the model?** The runtime adds tool-result messages with
   call IDs to history, then makes the next model request.
4. **What if retrieval finds nothing useful?** A rank does not establish relevance;
   acknowledge missing evidence rather than fabricate facts.
5. **What happens after editing Markdown?** Keyword search reads current files;
   semantic/hybrid search rejects a stale index until indexing is rerun.
6. **What if conversions are zero?** CPA is unavailable (`null`), not zero. No
   causal or statistical claim follows from a small observational dataset.
7. **How are MCP tools different from resources/prompts?** Tools are actions the
   model can request; resources are host-loaded data; prompts are user-selected templates.
8. **Are previous reports automatically remembered?** No. A run ID explicitly
   retrieves a saved report; new invocations do not inherit conversation history.
9. **How do you prove a tool ran?** Inspect its logged inputs, outputs, status,
   timing, and saved record; do not rely on the model's narrative alone.
10. **What do offline tests prove?** Python logic and real SDK/protocol plumbing
    under controlled responses. They do not prove live API access or model quality.
11. **What happens when the loop exceeds eight turns?** The SDK raises a limit
    error; the run is recorded as failed. It does not force exactly eight calls.
12. **What has not been built?** Automatic conversation memory/resume, subagents,
    plugin packaging, real publishing, comprehensive evaluations, and production deployment.

## Local checks

Trace a tool result back to the next model call. Check how a missing API key,
stale index, or invalid CSV is handled using the CLI and tests.
