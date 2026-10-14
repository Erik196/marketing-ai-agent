# MarketPilot AI — Project Requirements

## Agent Workflow Visualizer

Status: implemented in the dashboard phase; see PROJECT_PROGRESS.md for verification status.

Purpose: inspect the AI agent's architecture and actual marketing workflow execution locally, with clear connections and recorded events.

### Architecture View

- Show the user request, main marketing agent, LLM, tools, knowledge base/RAG, MCP server, and final output.
- Use directed arrows to represent actual connections and data flow.
- Clearly label implemented components separately from optional or simulated components. Do not imply that an optional integration is active.

### Execution View

- Show the actual sequence of tool calls for a completed marketing workflow.
- Capture and display real execution events; do not invent workflow steps.
- Display running, completed, and failed statuses.
- Show tool inputs, outputs, and execution durations when available.
- Allow users to inspect individual execution steps.

### Inspection interface

- Use a clean, professional visual design with clear labels.
- Include a focus view with more room for inspecting diagrams.
- Support diagram export if feasible within the project time budget.
- Prioritize a working diagram over advanced animations or complex frontend libraries.

### Implementation and phase dependencies

- Prefer Streamlit and Graphviz to minimize development time.
- During the tool-calling implementation phase, begin collecting structured execution logs so the dashboard visualizer can reuse them later.
- Execution records should associate steps with a workflow run and preserve their order, tool name, status, inputs, outputs, and available timing information. Record failures as actual execution events as well.
- Integrate both visualization modes during the dashboard phase, using the implemented architecture and captured execution logs.