"""No-key demo that executes real local operations; there is no simulated agent planning."""

import asyncio

from marketpilot.analytics import analyze_csv
from marketpilot.execution import ExecutionLog
from marketpilot.mcp_client import LoggedMCPServer
from marketpilot.retrieval import retrieve_knowledge
from marketpilot.storage import WorkflowStore


async def run_local_demo(store: WorkflowStore | None = None, notify=None, on_run_created=None,
                         directory=None) -> str:
    store = store or WorkflowStore()
    kwargs = {"directory": directory} if directory is not None else {}
    log = ExecutionLog("Explicit local demo: retrieve fictional product evidence, calculate sample metrics, "
                       "and repeat analytics over real MCP. No LLM planning or content generation.",
                       "not_called", notify, store=store,
                       configuration={"mode": "offline_local_demo", "mcp_enabled": False}, **kwargs)
    try:
        if on_run_created:
            on_run_created(log.path.stem)
        await log.execute("search_knowledge", {"query": "supported features", "mode": "keyword"},
                          lambda: retrieve_knowledge("supported features", mode="keyword", top_k=1))

        async def analytics():
            return analyze_csv("sample_campaign.csv")

        metrics = await log.execute("analyze_campaign", {"filename": "sample_campaign.csv"}, analytics)
        async with LoggedMCPServer(log) as connection:
            log.record["configuration"]["mcp_enabled"] = True
            log.save()
            await connection.call_tool("mcp_campaign_metrics", {"filename": "sample_campaign.csv"})
        output = ("# Local execution demonstration\n\nNo LLM was called. All recorded steps executed locally; "
                  "MCP used a real subprocess. The input product and CSV are fictional demo data.\n\n"
                  f"- Sample CTR: {metrics['totals']['ctr_percent']}%\n"
                  f"- Sample conversions: {metrics['totals']['conversions']}\n"
                  "- This is not a demonstration of autonomous model planning or generated campaign content.")
        log.finish(output=output)
        return log.path.stem
    except BaseException as exc:
        log.finish(error=exc)
        raise


if __name__ == "__main__":
    print(asyncio.run(run_local_demo(notify=print)))
