"""Offline tests: real SDK tool dispatch with explicitly simulated API responses."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from agents import Model, ModelResponse, RunConfig, Runner, Usage
from agents.tool_context import ToolContext
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage

from marketpilot import agent, tools
from marketpilot.execution import ExecutionLog


def test_execution_records_success_failure_and_redacts_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    messages = []
    log = ExecutionLog("prompt sk-test-secret", "offline-model", messages.append, tmp_path)
    assert asyncio.run(log.execute("example", {"x": 1}, AsyncMock(return_value={"result": "ok"}))) == {"result": "ok"}
    with pytest.raises(RuntimeError):
        asyncio.run(log.execute("broken", {}, AsyncMock(side_effect=RuntimeError("sk-test-secret"))))
    log.finish(error=RuntimeError("tool failed"))
    record = json.loads(log.path.read_text())
    assert record["status"] == "failed"
    assert [step["status"] for step in record["steps"]] == ["completed", "failed"]
    assert [step["sequence"] for step in record["steps"]] == [1, 2]
    assert all(step["duration_seconds"] >= 0 for step in record["steps"])
    assert "sk-test-secret" not in log.path.read_text()
    assert messages[1] == "[Running] example"
    assert messages[-1].startswith("[Failed] broken")


@pytest.mark.parametrize("tool,arguments", [
    (tools.generate_content, {"brief": "App", "content_type": "headlines", "count": 0}),
    (tools.create_social_posts, {"brief": "App", "platform": "Instagram", "days": 8}),
])
def test_invalid_limits_are_logged_without_api_calls(tool, arguments, tmp_path, monkeypatch):
    backend = AsyncMock()
    monkeypatch.setattr(tools, "generate_draft", backend)
    log = ExecutionLog("test", "offline-model", directory=tmp_path)
    with pytest.raises(ValueError):
        context = ToolContext(context=log, tool_name=tool.name, tool_call_id="test-call", tool_arguments=json.dumps(arguments))
        asyncio.run(tool.on_invoke_tool(context, json.dumps(arguments)))
    backend.assert_not_called()
    assert log.record["steps"][0]["status"] == "failed"


@pytest.mark.parametrize("tool,arguments,expected_count", [
    (tools.generate_content, {"brief": "App", "content_type": "headlines", "count": 2}, 2),
    (tools.create_social_posts, {"brief": "App", "platform": "Instagram", "days": 3}, 3),
    (tools.draft_email, {"brief": "App", "audience": "Students", "tone": "friendly"}, 4),
])
def test_drafting_tools_dispatch_and_log(tool, arguments, expected_count, tmp_path, monkeypatch):
    backend = AsyncMock(return_value={"draft_only": True, "items": []})
    monkeypatch.setattr(tools, "generate_draft", backend)
    log = ExecutionLog("test", "offline-model", directory=tmp_path)
    context = ToolContext(context=log, tool_name=tool.name, tool_call_id="test-call", tool_arguments=json.dumps(arguments))
    result = asyncio.run(tool.on_invoke_tool(context, json.dumps(arguments)))
    assert result["draft_only"]
    assert backend.call_args.args[0] == "offline-model"
    assert backend.call_args.args[2] == arguments
    assert backend.call_args.args[3] == expected_count
    assert log.record["steps"][0]["tool"] == tool.name
    assert log.record["steps"][0]["status"] == "completed"


def mock_api(monkeypatch, response):
    """No network requests: return the supplied fake response from the API client."""
    responses = SimpleNamespace(create=AsyncMock(return_value=response), parse=AsyncMock(return_value=response))
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=SimpleNamespace(responses=responses))
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(tools, "AsyncOpenAI", MagicMock(return_value=client))
    return responses


def test_research_requires_actual_search_evidence_and_preserves_citations(monkeypatch):
    search = SimpleNamespace(type="web_search_call", model_dump=lambda **kwargs: {
        "type": "web_search_call", "status": "completed", "action": {"query": "test"},
    })
    citation = SimpleNamespace(type="url_citation", model_dump=lambda **kwargs: {
        "type": "url_citation", "url": "https://example.com", "title": "Offline fixture",
    })
    message = SimpleNamespace(type="message", content=[SimpleNamespace(type="output_text", annotations=[citation])])
    response = SimpleNamespace(output=[search, message], output_text="Offline cited summary")
    responses = mock_api(monkeypatch, response)
    result = asyncio.run(tools.search_market("offline-model", "question"))
    assert responses.create.call_args.kwargs["tool_choice"] == "required"
    assert result["citations"][0]["url"] == "https://example.com"
    assert result["search_calls"][0]["status"] == "completed"
    response.output = [message]
    with pytest.raises(ValueError, match="did not complete"):
        asyncio.run(tools.search_market("offline-model", "question"))
    response.output = [search]
    with pytest.raises(ValueError, match="no cited summary"):
        asyncio.run(tools.search_market("offline-model", "question"))


def test_structured_draft_validation(monkeypatch):
    response = SimpleNamespace(output_parsed=tools.DraftOutput(
        title="Draft", items=[tools.DraftItem(label="Headline", text="Study with focus")], assumptions=[],
    ))
    responses = mock_api(monkeypatch, response)
    result = asyncio.run(tools.generate_draft("offline-model", "task", {}, 1))
    assert result["draft_only"]
    assert responses.parse.call_args.kwargs["text_format"] is tools.DraftOutput
    with pytest.raises(ValueError, match="number of items"):
        asyncio.run(tools.generate_draft("offline-model", "task", {}, 2))
    response.output_parsed = None
    with pytest.raises(ValueError, match="usable structured draft"):
        asyncio.run(tools.generate_draft("offline-model", "task", {}, 1))


class ScriptedModel(Model):
    """Test-only model: request a tool, then confirm its result reached the SDK loop."""
    def __init__(self):
        self.calls = 0
        self.saw_tool_result = False

    async def get_response(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            output = [ResponseFunctionToolCall(
                type="function_call", name="generate_content", call_id="test-call-1",
                arguments=json.dumps({"brief": "Student app", "content_type": "headlines", "count": 1}),
            )]
        else:
            history = kwargs.get("input", args[1] if len(args) > 1 else [])
            self.saw_tool_result = any(item.get("type") == "function_call_output" for item in history)
            output = [ResponseOutputMessage.model_validate({
                "id": "test-message", "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": "Final answer from tool result", "annotations": []}],
            })]
        return ModelResponse(output=output, usage=Usage(), response_id=None)

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError("This test only covers nonstreaming execution.")
        yield


def test_real_sdk_agent_tool_agent_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "generate_draft", AsyncMock(return_value={"draft_only": True, "items": []}))
    model = ScriptedModel()
    marketing_agent = agent.create_marketing_agent()
    marketing_agent.model = model
    log = ExecutionLog("offline test", "scripted-model", directory=tmp_path)
    result = asyncio.run(Runner.run(marketing_agent, "Write a headline", context=log,
                                    run_config=RunConfig(tracing_disabled=True)))
    log.finish(output=result.final_output)
    assert model.calls == 2
    assert model.saw_tool_result
    assert result.final_output == "Final answer from tool result"
    assert [step["tool"] for step in log.record["steps"]] == ["generate_content"]
    assert log.record["status"] == "completed"


def test_agent_run_failure_is_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
    real_log = ExecutionLog
    monkeypatch.setattr(agent, "WorkflowStore", lambda: None)
    monkeypatch.setattr(agent, "ExecutionLog", lambda *args, **kwargs: real_log(*args, directory=tmp_path, **kwargs))
    monkeypatch.setattr(agent.Runner, "run", AsyncMock(side_effect=RuntimeError("test failure")))
    with pytest.raises(RuntimeError):
        asyncio.run(agent.run_marketing_agent("test"))
    record = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert record["status"] == "failed"
    assert record["steps"] == []  # No tools ran, so do not invent a failed tool step.
