"""The host starts a local server; the Agents SDK provides the MCP client."""

import asyncio
import json
import sys

from agents.mcp import MCPServerStdio

from marketpilot.execution import ExecutionLog
from marketpilot.retrieval import PROJECT_ROOT


class LoggedMCPServer(MCPServerStdio):
    def __init__(self, log: ExecutionLog | None = None):
        self.log = log
        super().__init__(
            params={"command": sys.executable, "args": ["-m", "marketpilot.mcp_server"],
                    "cwd": str(PROJECT_ROOT)},
            name="MarketPilot local MCP", cache_tools_list=True,
            client_session_timeout_seconds=30, use_structured_content=True,
            failure_error_function=None,
        )

    async def call_tool(self, tool_name, arguments=None, meta=None):
        if self.log is None:
            return await super().call_tool(tool_name, arguments, meta)
        result = None

        async def operation():
            nonlocal result
            result = await super(LoggedMCPServer, self).call_tool(tool_name, arguments, meta)
            if result.is_error:
                raise ValueError(f"MCP tool {tool_name} failed; inspect the server diagnostics.")
            return result.model_dump(mode="json")

        # Preserve the SDK result object while recording a JSON-safe representation.
        await self.log.execute(f"mcp.{tool_name}", arguments or {}, operation)
        return result


async def inspect_mcp() -> dict:
    """Exercise the real subprocess protocol without an LLM or API key."""
    async with LoggedMCPServer() as connection:
        tools = await connection.list_tools()
        resources = await connection.list_resources()
        prompts = await connection.list_prompts()
        metrics = await connection.call_tool("mcp_campaign_metrics", {"filename": "sample_campaign.csv"})
        guide = await connection.read_resource("marketpilot://brand-guide")
        prompt = await connection.get_prompt("campaign_brief", {"goal": "Reach university students"})
        return {"transport": "real_local_stdio", "tools": [tool.name for tool in tools],
                "resources": [str(resource.uri) for resource in resources.resources],
                "prompts": [item.name for item in prompts.prompts],
                "metrics": metrics.model_dump(mode="json"),
                "resource_read": guide.model_dump(mode="json"),
                "rendered_prompt": prompt.model_dump(mode="json")}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(inspect_mcp()), ensure_ascii=False, indent=2))
