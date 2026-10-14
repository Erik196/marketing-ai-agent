"""Graphviz diagrams from implemented connections and real execution records."""

from graphviz import Digraph, escape

STATUS_COLORS = {"running": "#DBEAFE", "completed": "#D1FAE5", "failed": "#FEE2E2"}
TOOL_LABELS = {"research_market": "Market research", "generate_content": "Marketing content",
               "create_social_posts": "Social calendar", "draft_email": "Email draft",
               "search_knowledge": "Knowledge retrieval", "analyze_campaign": "CSV analytics",
               "read_saved_report": "Saved report retrieval",
               "mcp.mcp_campaign_metrics": "CSV analytics through MCP",
               "mcp.mcp_keyword_knowledge": "Knowledge retrieval through MCP"}


def new_diagram(name: str, presentation: bool = False) -> Digraph:
    graph = Digraph(name)
    graph.attr(rankdir="LR", bgcolor="transparent", pad="0.25", nodesep="0.45", ranksep="0.65")
    graph.attr("node", shape="box", style="rounded,filled", fillcolor="#E8EEF8", color="#A6B4CC",
               fontname="Arial", fontsize="17" if presentation else "13", margin="0.18,0.12")
    graph.attr("edge", color="#64748B", fontname="Arial", fontsize="11", arrowsize="0.8")
    return graph


def architecture_diagram(record: dict | None = None, presentation: bool = False) -> Digraph:
    graph = new_diagram("MarketPilot architecture", presentation)
    configuration = (record or {}).get("configuration") or {}
    offline = configuration.get("mode") == "offline_local_demo"
    names = {step["tool"] for step in (record or {}).get("steps", [])}
    generic = record is None
    mcp = configuration.get("mcp_enabled", False)
    knowledge = generic or bool(names & {"search_knowledge", "mcp.mcp_keyword_knowledge"})
    analytics = generic or bool(names & {"analyze_campaign", "mcp.mcp_campaign_metrics"})

    def node(key, label, active=True):
        graph.node(key, escape(label), style="rounded,filled" if active else "rounded,dashed,filled",
                   fillcolor="#E8EEF8" if active else "#F1F5F9", color="#A6B4CC" if active else "#CBD5E1")

    node("request", "User request")
    node("agent", "Marketing agent + SDK\nImplemented" + ("; bypassed in local demo" if offline else ""), not offline)
    node("llm", "OpenAI model\nImplemented" + ("; not called in local demo" if offline else ""), not offline)
    node("tools", "Python tools\nImplemented")
    node("kb", "Knowledge / RAG\nMarkdown + optional vector index", knowledge)
    node("analytics", "CSV analytics\nDeterministic pandas", analytics)
    node("mcp", "Local MCP server\nImplemented; " + ("connected" if mcp else "optional / inactive"), mcp)
    node("logs", "Execution records\nJSON + SQLite")
    node("output", "Final output\nDrafts / report / evidence")
    node("future", "Optional, not implemented\nSubagents / plugin packaging", False)
    if offline:
        graph.edge("request", "tools", "explicit local demo operations")
        graph.edge("tools", "output", "deterministic summary")
    else:
        graph.edge("request", "agent")
        graph.edge("agent", "llm", "instructions + history")
        graph.edge("llm", "agent", "tool request / final answer")
        graph.edge("agent", "tools", "SDK invokes function")
        graph.edge("tools", "agent", "tool results → model history")
        graph.edge("agent", "output", "final answer")
    if knowledge:
        owner = "mcp" if names and "search_knowledge" not in names else "tools"
        graph.edge(owner, "kb", "retrieve")
        graph.edge("kb", owner, "passages + citations")
    if analytics:
        if generic or "analyze_campaign" in names:
            graph.edge("tools", "analytics", "CSV")
            graph.edge("analytics", "tools", "calculated metrics")
        if "mcp.mcp_campaign_metrics" in names:
            graph.edge("mcp", "analytics", "CSV")
            graph.edge("analytics", "mcp", "calculated metrics")
    if mcp:
        graph.edge("tools" if offline else "agent", "mcp", "stdio client calls")
        graph.edge("mcp", "tools" if offline else "agent", "protocol results")
    if not offline and (generic or names & {"research_market", "generate_content", "create_social_posts", "draft_email"}):
        graph.edge("tools", "llm", "separate focused API requests", style="dotted")
        graph.edge("llm", "tools", "research / structured draft", style="dotted")
    graph.edge("tools", "logs", "actual operation events")
    if "read_saved_report" in names:
        graph.edge("logs", "tools", "explicit saved-report query")
    if not offline:
        graph.edge("agent", "logs", "model hooks + final result")
    graph.edge("logs", "output", "saved for inspection", style="dotted")
    return graph


def execution_diagram(record: dict, presentation: bool = False) -> Digraph:
    """Only add steps that exist in the record; never infer a plan from the prompt."""
    graph = new_diagram("MarketPilot execution", presentation)
    graph.node("start", "Request received", fillcolor="#E8EEF8")
    previous = "start"
    for index, step in enumerate(record.get("steps", [])):
        key = f"step_{index}"
        duration = step.get("duration_seconds")
        timing = f"{duration:.3f}s" if duration is not None else "duration unavailable"
        label = TOOL_LABELS.get(step["tool"], step["tool"])
        graph.node(key, escape(f"{step['sequence']}. {label}\n{step['status'].upper()} · {timing}"),
                   fillcolor=STATUS_COLORS.get(step["status"], "#F1F5F9"))
        graph.edge(previous, key)
        previous = key
    status = record["status"]
    graph.node("end", escape(f"Workflow {status}"), fillcolor=STATUS_COLORS.get(status, "#F1F5F9"))
    graph.edge(previous, "end")
    return graph
