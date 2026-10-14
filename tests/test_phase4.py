"""Deterministic analytics/persistence and a real SDK workflow with a test-only model."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agents import Model, ModelResponse, RunConfig, Runner, Usage
from agents.tool_context import ToolContext
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage

from marketpilot import agent, analytics, tools, workflow_cli
from marketpilot.execution import ExecutionLog
from marketpilot.reports import CampaignReport
from marketpilot.storage import WorkflowStore


def write_csv(directory, text):
    path = directory / "campaign.csv"
    path.write_text(text, encoding="utf-8")
    return path.name


def test_sample_totals_and_weighted_channel_rates():
    result = analytics.analyze_csv("sample_campaign.csv")
    assert result["data_status"] == "fictional_demo"
    assert result["currency"] == "EUR"
    assert result["totals"]["impressions"] == 25_000
    assert result["totals"]["conversions"] == 85
    assert result["totals"]["ctr_percent"] == 5.6
    assert result["totals"]["cost_per_conversion"] == pytest.approx(600 / 85, abs=0.0001)
    instagram = next(item for item in result["channels"] if item["channel"] == "Instagram")
    assert instagram["ctr_percent"] == pytest.approx(700 / 15_000 * 100, abs=0.0001)
    assert instagram["ctr_percent"] != 4.5  # Do not average the two row CTRs (5% and 4%).


def test_zero_denominators_and_optional_revenue(tmp_path):
    filename = write_csv(tmp_path, "channel,impressions,clicks,conversions,spend\nEmail,0,0,0,10\n")
    result = analytics.analyze_csv(filename, tmp_path)
    assert result["totals"]["ctr_percent"] is None
    assert result["totals"]["cost_per_click"] is None
    assert result["totals"]["cost_per_conversion"] is None
    assert result["totals"]["roas"] is None
    assert result["currency"] is None
    assert any("Revenue" in warning for warning in result["warnings"])
    with pytest.raises(ValueError, match="numeric range"):
        analytics.calculate_metrics({"impressions": 1, "clicks": 1, "conversions": 1, "spend": float("inf")})


@pytest.mark.parametrize("text,error", [
    ("channel,clicks\nEmail,5\n", "missing required"),
    ("channel,impressions,clicks,conversions,spend\nEmail,10,5,1,-2\n", "nonnegative"),
    ("channel,impressions,clicks,conversions,spend\nEmail,10,5,1,NaN\n", "no blanks"),
    ("channel,impressions,clicks,conversions,spend\nEmail,10,5,1,inf\n", "finite"),
    ("channel,impressions,clicks,conversions,spend\nEmail,10,5.5,1,2\n", "whole-number"),
    ("channel,impressions,clicks,conversions,spend\nEmail,10,11,1,2\n", "conversions <= clicks"),
    ("channel,impressions,clicks,conversions,spend\n,10,5,1,2\n", "nonempty channel"),
    ("channel,impressions,clicks,conversions,spend,currency\nEmail,10,5,1,2,EUR\nSearch,10,5,1,2,USD\n", "one nonempty currency"),
    ("channel,impressions,clicks,conversions,spend,spend\nEmail,10,5,1,2,3\n", "duplicate"),
])
def test_invalid_csv_is_rejected(tmp_path, text, error):
    with pytest.raises(ValueError, match=error):
        analytics.analyze_csv(write_csv(tmp_path, text), tmp_path)


def test_csv_path_escape_is_rejected(tmp_path):
    outside = tmp_path / "outside.csv"
    outside.write_text("private data")
    directory = tmp_path / "campaigns"
    directory.mkdir()
    for filename in ["../outside.csv", str(outside), "https://example.com/data.csv"]:
        with pytest.raises(ValueError):
            analytics.resolve_csv(filename, directory)
    (directory / "link.csv").symlink_to(outside)
    with pytest.raises(ValueError):
        analytics.resolve_csv("link.csv", directory)


def test_sqlite_tracks_transitions_reopens_and_redacts(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-offline-secret")
    store = WorkflowStore(tmp_path / "workflows.db")
    log = ExecutionLog("request sk-offline-secret", "test-model", directory=tmp_path / "logs", store=store)
    assert store.get_run(log.path.stem)["status"] == "running"

    async def operation():
        assert store.get_run(log.path.stem)["steps"][0]["status"] == "running"
        return {"result": "calculated"}

    asyncio.run(log.execute("test-tool", {"value": 1}, operation))
    log.finish(output="answer", report={"title": "saved report"})
    reopened = WorkflowStore(store.path)
    run = reopened.get_run(log.path.stem)
    assert run["status"] == "completed"
    assert run["steps"][0]["outputs"] == {"result": "calculated"}
    assert run["final_report"]["title"] == "saved report"
    assert "sk-offline-secret" not in json.dumps(run)
    assert reopened.list_runs()[0]["run_id"] == log.path.stem
    # Parameterized SQL treats this as an ID, never as executable SQL.
    with pytest.raises(ValueError, match="not found"):
        reopened.get_run("' OR 1=1 --")


def test_failed_tool_and_run_survive_in_sqlite(tmp_path):
    store = WorkflowStore(tmp_path / "workflows.db")
    log = ExecutionLog("test", "test-model", directory=tmp_path / "logs", store=store)
    with pytest.raises(RuntimeError):
        asyncio.run(log.execute("broken", {}, AsyncMock(side_effect=RuntimeError("test error"))))
    log.finish(error=RuntimeError("test error"))
    saved = store.get_run(log.path.stem)
    assert saved["status"] == "failed"
    assert saved["steps"][0]["status"] == "failed"
    assert saved["error"]["type"] == "RuntimeError"


def report_fixture():
    return CampaignReport(title="Demo campaign", summary="Based on fictional evidence.",
                          knowledge=["Fictional StudySprint product facts."], research=[],
                          analytics=["Demo campaign CTR is 5.6%."],
                          drafts=[{"kind": "email", "content": "Test draft email"}],
                          recommendations=["Review the draft."], limitations=["Fictional demo, no causal conclusion."])


def test_agent_campaign_mode_saves_structured_report(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
    store = WorkflowStore(tmp_path / "workflows.db")
    monkeypatch.setattr(agent, "WorkflowStore", lambda: store)
    real_log = ExecutionLog
    monkeypatch.setattr(agent, "ExecutionLog", lambda *args, **kwargs: real_log(*args, directory=tmp_path / "logs", **kwargs))
    monkeypatch.setattr(agent.Runner, "run", AsyncMock(return_value=SimpleNamespace(final_output=report_fixture())))
    output = asyncio.run(agent.run_marketing_agent("Create a campaign", campaign=True))
    assert "## Analytics" in output
    assert "Drafts — for human review" in output
    assert store.get_run(store.list_runs()[0]["run_id"])["final_report"]["title"] == "Demo campaign"
    assert agent.Runner.run.call_args.args[0].output_type is CampaignReport
    assert agent.create_marketing_agent().output_type is None


def test_saved_report_tool_uses_explicit_sql_retrieval(tmp_path):
    store = WorkflowStore(tmp_path / "workflows.db")
    earlier = ExecutionLog("previous", "test-model", directory=tmp_path / "logs", store=store)
    earlier.finish(output="Earlier result")
    current = ExecutionLog("follow-up", "test-model", directory=tmp_path / "logs", store=store)
    arguments = json.dumps({"run_id": earlier.path.stem})
    context = ToolContext(context=current, tool_name="read_saved_report", tool_call_id="saved-report-test",
                          tool_arguments=arguments)
    result = asyncio.run(tools.read_saved_report.on_invoke_tool(context, arguments))
    assert result["final_output"] == "Earlier result"
    assert store.get_run(current.path.stem)["steps"][0]["tool"] == "read_saved_report"


class WorkflowModel(Model):
    """Test-only planner: real retrieval + analytics, mocked drafting API, structured final output."""
    def __init__(self):
        self.calls = 0
        self.received_results = []

    async def get_response(self, *args, **kwargs):
        self.calls += 1
        history = kwargs.get("input", args[1] if len(args) > 1 else [])
        self.received_results = [item for item in history if item.get("type") == "function_call_output"]
        calls = [
            ("search_knowledge", {"query": "supported features", "mode": "keyword", "top_k": 1}),
            ("analyze_campaign", {"filename": "sample_campaign.csv"}),
            ("draft_email", {"brief": "Fictional StudySprint demo; improve email using demo results.",
                             "audience": "University students", "tone": "friendly"}),
        ]
        if self.calls <= len(calls):
            name, arguments = calls[self.calls - 1]
            output = [ResponseFunctionToolCall(type="function_call", name=name,
                        call_id=f"workflow-test-{self.calls}", arguments=json.dumps(arguments))]
        else:
            output = [ResponseOutputMessage.model_validate({
                "id": "workflow-final", "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": report_fixture().model_dump_json(), "annotations": []}],
            })]
        return ModelResponse(output=output, usage=Usage(), response_id=None)

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError("Nonstreaming test only")
        yield


def test_real_sdk_multistep_workflow_and_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "generate_draft", AsyncMock(return_value={"draft_only": True, "items": []}))
    model = WorkflowModel()
    marketing_agent = agent.create_marketing_agent(campaign=True)
    marketing_agent.model = model
    store = WorkflowStore(tmp_path / "workflows.db")
    log = ExecutionLog("offline workflow", "scripted-model", directory=tmp_path / "logs", store=store)
    result = asyncio.run(Runner.run(marketing_agent, "Make a campaign", context=log, max_turns=8,
                                    run_config=RunConfig(tracing_disabled=True)))
    assert isinstance(result.final_output, CampaignReport)
    log.finish(output=result.final_output.to_markdown(), report=result.final_output.model_dump())
    saved = WorkflowStore(store.path).get_run(log.path.stem)
    assert [step["tool"] for step in saved["steps"]] == ["search_knowledge", "analyze_campaign", "draft_email"]
    assert all(step["status"] == "completed" for step in saved["steps"])
    assert len(model.received_results) == 3
    assert saved["steps"][1]["outputs"]["totals"]["ctr_percent"] == 5.6
    assert saved["final_report"]["title"] == "Demo campaign"


def test_workflow_cli_local_analysis_and_missing_run(capsys, monkeypatch, tmp_path):
    assert workflow_cli.main(["analyze", "sample_campaign.csv"]) == 0
    assert json.loads(capsys.readouterr().out)["totals"]["conversions"] == 85
    monkeypatch.setattr(workflow_cli, "WorkflowStore", lambda: WorkflowStore(tmp_path / "workflows.db"))
    assert workflow_cli.main(["show", "not-a-run"]) == 2
    assert "not found" in capsys.readouterr().err
