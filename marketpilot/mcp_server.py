"""Real MCP server: tools, a resource, and a prompt over stdio."""

from mcp.server import MCPServer

from marketpilot.analytics import analyze_csv
from marketpilot.retrieval import KNOWLEDGE_DIRECTORY, retrieve_knowledge

server = MCPServer("MarketPilot local marketing", version="0.1.0")


@server.tool()
def mcp_campaign_metrics(filename: str) -> dict:
    """Calculate campaign CSV metrics through the local MCP server; filename is inside data/campaigns/."""
    return {"transport": "local_mcp_stdio", **analyze_csv(filename)}


@server.tool()
async def mcp_keyword_knowledge(query: str, top_k: int = 3) -> dict:
    """Retrieve local Markdown passages by keyword without requiring an embedding API key."""
    return await retrieve_knowledge(query, mode="keyword", top_k=top_k)


@server.resource("marketpilot://brand-guide", mime_type="text/markdown")
def brand_guide() -> str:
    """Read the fictional StudySprint brand guide as an MCP resource."""
    return (KNOWLEDGE_DIRECTORY / "brand.md").read_text(encoding="utf-8")


@server.prompt()
def campaign_brief(goal: str) -> str:
    """Render a reusable campaign request selected by the user, not automatically by the model."""
    return (f"Create a draft-only campaign for this goal: {goal}. Retrieve relevant product evidence, "
            "analyze any supplied CSV, cite sources, and label fictional demo inputs.")


if __name__ == "__main__":
    # stdout is the protocol wire; use stderr for human-readable server diagnostics.
    server.run(transport="stdio")
