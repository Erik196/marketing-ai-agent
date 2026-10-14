"""Real subprocess MCP and real SDK hooks; only model planning is scripted."""

import asyncio
import json
import sqlite3

import pytest
from agents import Model, ModelResponse, RunConfig, Runner, Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage

from marketpilot.agent import create_marketing_agent
from marketpilot.customization import load_custom_instructions
from marketpilot.execution import ExecutionLog
from marketpilot.hooks import RuntimeHooks
from marketpilot.mcp_client import LoggedMCPServer, inspect_mcp
from marketpilot.storage import WorkflowStore


def test_rules_and_explicit_skill_loading():
    assert "Produce drafts only" in load_custom_instructions()
    assert "Selected procedure" not in load_custom_instructions()
    assert "Campaign review procedure" in load_custom_instructions("campaign-review")
    with pytest.raises(ValueError, match="Unknown skill"):
        load_custom_instructions("../../private")


def test_real_mcp_tools_resource_and_prompt():
    result = asyncio.run(inspect_mcp())
    assert result["transport"] == "real_local_stdio"
    assert "mcp_campaign_metrics" in result["tools"]
    assert "marketpilot://brand-guide" in result["resources"]
    assert "campaign_brief" in result["prompts"]
    metrics = json.loads(result["metrics"]["content"][0]["text"])
    assert metrics["totals"]["ctr_percent"] == 5.6
    assert "fictional" in result["resource_read"]["contents"][0]["text"]
    assert "Reach university students" in result["rendered_prompt"]["messages"][0]["content"]["text"]


class MCPModel(Model):
    def __init__(self):
        self.calls = 0
        self.saw_result = False

    async def get_response(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            output = [ResponseFunctionToolCall(type="function_call", name="mcp_campaign_metrics",
                        call_id="mcp-test-call", arguments='{"filename":"sample_campaign.csv"}')]
        else:
            history = kwargs.get("input", args[1] if len(args) > 1 else [])
            self.saw_result = any(item.get("type") == "function_call_output" and
                                 "5.6" in str(item.get("output")) for item in history)
            output = [ResponseOutputMessage.model_validate({
                "id": "mcp-final", "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": "Offline test: MCP result received.", "annotations": []}],
            })]
        return ModelResponse(output=output, usage=Usage(input_tokens=10, output_tokens=5), response_id=None)

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError()
        yield


def test_native_sdk_mcp_call_and_hooks_are_logged(tmp_path):
    store = WorkflowStore(tmp_path / "runs.db")
    log = ExecutionLog("offline MCP test", "scripted-model", directory=tmp_path / "logs", store=store,
                       configuration={"mcp_enabled": True})
    model = MCPModel()

    async def run():
        async with LoggedMCPServer(log) as connection:
            agent = create_marketing_agent(skill="campaign-review")
            agent.model = model
            agent.mcp_servers = [connection]
            result = await Runner.run(agent, "Use MCP analytics", context=log,
                                      hooks=RuntimeHooks(), run_config=RunConfig(tracing_disabled=True))
            log.finish(output=result.final_output)

    asyncio.run(run())
    saved = store.get_run(log.path.stem)
    assert model.saw_result
    assert saved["steps"][0]["tool"] == "mcp.mcp_campaign_metrics"
    assert saved["steps"][0]["status"] == "completed"
    assert len(saved["model_calls"]) == 2
    assert all(call["status"] == "completed" for call in saved["model_calls"])
    assert saved["model_calls"][0]["input_tokens"] == 10
    assert saved["configuration"]["mcp_enabled"]


def test_mcp_failure_is_recorded(tmp_path):
    log = ExecutionLog("failure test", "offline", directory=tmp_path)

    async def run():
        async with LoggedMCPServer(log) as connection:
            await connection.call_tool("mcp_campaign_metrics", {"filename": "missing.csv"})

    with pytest.raises(ValueError, match="MCP tool"):
        asyncio.run(run())
    assert log.record["steps"][0]["status"] == "failed"


def test_sqlite_additive_migration_preserves_old_runs(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, model TEXT, prompt TEXT, status TEXT, "
                   "started_at TEXT, ended_at TEXT, duration_seconds REAL, final_output TEXT, "
                   "final_report_json TEXT, error_json TEXT)")
        db.execute("INSERT INTO runs VALUES ('old', 'model', 'prompt', 'completed', 'date', NULL, 1, 'answer', NULL, NULL)")
    store = WorkflowStore(path)
    assert store.get_run("old")["final_output"] == "answer"
    assert store.get_run("old")["model_calls"] is None
