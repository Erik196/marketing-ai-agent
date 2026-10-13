# MarketPilot AI — Project Requirements

## Agent Workflow Visualizer

Status: required for the final project; implementation deferred to the dashboard phase. Do not implement the visualizer before that phase.

Purpose: provide a professional, meeting-ready explanation of the AI agent's architecture and demonstrate how real marketing workflows execute. The visualizer must be understandable to nontechnical audiences and suitable for screen sharing.

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

### Presentation

- Use a clean, professional visual design with clear labels.
- Include a presentation-friendly view.
- Support diagram export if feasible within the project time budget.
- Prioritize a working diagram over advanced animations or complex frontend libraries.

### Implementation and phase dependencies

- Prefer Streamlit and Graphviz to minimize development time.
- During the tool-calling implementation phase, begin collecting structured execution logs so the dashboard visualizer can reuse them later.
- Execution records should associate steps with a workflow run and preserve their order, tool name, status, inputs, outputs, and available timing information. Record failures as actual execution events as well.
- Integrate both visualization modes during the dashboard phase, using the implemented architecture and captured execution logs.
- Do not implement the visualizer now; retain this requirement until the relevant phase.

### Time budget and priority

The entire project must remain within approximately five hours. The visualizer is an important final-project deliverable. Simplify less important UI features as needed to prioritize a working architecture diagram and inspectable execution view; keep export and presentation enhancements lightweight.
