import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from marketpilot import agent, cli


def test_missing_key_prevents_api_call(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runner = AsyncMock()
    monkeypatch.setattr(agent.Runner, "run", runner)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        asyncio.run(agent.run_marketing_agent("Draft a campaign"))
    runner.assert_not_called()


def test_empty_request_prevents_api_call():
    with pytest.raises(ValueError, match="nonempty"):
        asyncio.run(agent.run_marketing_agent("  "))


def test_sdk_wiring_and_model_override(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("MARKETPILOT_MODEL", "environment-model")
    runner = AsyncMock(return_value=SimpleNamespace(final_output="Draft campaign"))
    monkeypatch.setattr(agent.Runner, "run", runner)
    assert asyncio.run(agent.run_marketing_agent("  Write a headline  ", "chosen-model")) == "Draft campaign"
    called_agent = runner.call_args.args[0]
    assert called_agent.model == "chosen-model"
    assert called_agent.tools == []
    assert runner.call_args.kwargs["input"] == "Write a headline"
    assert runner.call_args.kwargs["run_config"].tracing_disabled


def test_cli_missing_key_is_actionable(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert cli.main(["Draft a campaign"]) == 2
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.err
    assert not captured.out

