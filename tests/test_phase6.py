"""Visualizer/data tests and Streamlit UI tests without OpenAI requests."""

import asyncio
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from marketpilot import demo, storage
from marketpilot.dashboard_helpers import save_campaign_upload
from marketpilot.storage import WorkflowStore
from marketpilot.visualizer import architecture_diagram, execution_diagram

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_diagrams_only_use_recorded_steps():
    empty = {"status": "failed", "steps": [], "configuration": {}}
    source = execution_diagram(empty).source
    assert "step_0" not in source
    assert "Workflow failed" in source
    record = {"status": "completed", "configuration": {"mode": "offline_local_demo", "mcp_enabled": True},
              "steps": [{"sequence": 1, "tool": "analyze_campaign", "status": "completed", "duration_seconds": 0.1}]}
    source = execution_diagram(record).source
    assert "CSV analytics" in source
    assert "0.100s" in source
    assert "step_1" not in source
    architecture = architecture_diagram(record).source
    assert "not called in local demo" in architecture
    assert "explicit local demo operations" in architecture
    assert "not implemented" in architecture


def test_local_demo_has_real_operations_without_model_calls(tmp_path):
    store = WorkflowStore(tmp_path / "runs.db")
    run_id = asyncio.run(demo.run_local_demo(store=store, directory=tmp_path / "logs"))
    saved = store.get_run(run_id)
    assert saved["status"] == "completed"
    assert saved["configuration"]["mode"] == "offline_local_demo"
    assert saved["model_calls"] == []
    assert [step["tool"] for step in saved["steps"]] == [
        "search_knowledge", "analyze_campaign", "mcp.mcp_campaign_metrics"]
    assert saved["steps"][1]["outputs"]["totals"]["ctr_percent"] == 5.6
    assert "No LLM was called" in saved["final_output"]


def test_upload_validates_before_saving_and_ignores_supplied_path(tmp_path):
    data = b"channel,impressions,clicks,conversions,spend\nEmail,100,10,1,5\n"
    filename = save_campaign_upload("../../customer.csv", data, tmp_path)
    assert filename.startswith("upload_")
    assert (tmp_path / filename).read_bytes() == data
    assert len(list(tmp_path.glob("*.csv"))) == 1
    with pytest.raises(ValueError):
        save_campaign_upload("bad.csv", b"invalid CSV", tmp_path)
    assert len(list(tmp_path.glob("*.csv"))) == 1


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    real_store = WorkflowStore
    monkeypatch.setattr(storage, "WorkflowStore", lambda: real_store(tmp_path / "app.db"))
    real_demo = demo.run_local_demo

    async def isolated_demo(**kwargs):
        return await real_demo(**kwargs, directory=tmp_path / "logs")

    monkeypatch.setattr(demo, "run_local_demo", isolated_demo)
    return AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=20).run()


def test_dashboard_no_key_and_real_keyword_inspection(app):
    assert not app.exception
    run_button = next(button for button in app.button if button.label == "Run agent")
    assert run_button.disabled
    app.radio[0].set_value("Knowledge").run()
    next(button for button in app.button if button.label == "Retrieve evidence").click().run()
    assert not app.exception
    assert any("knowledge/product.md" in str(element.value) for element in app.json)


def test_dashboard_local_demo_execution_inspection_and_presentation(app):
    app.button(key="local_demo").click().run()
    assert not app.exception
    assert app.session_state["selected_run"]
    app.radio[0].set_value("Workflow visualizer").run()
    assert not app.exception
    next(radio for radio in app.radio if radio.label == "Diagram mode").set_value("Execution").run()
    assert not app.exception
    inspector = next(box for box in app.selectbox if box.label == "Inspect an execution step")
    assert len(inspector.options) == 3
    assert any("No LLM" in str(message.value) for message in app.info)
    assert app.get("graphviz_chart")
    app.toggle[0].set_value(True).run()
    assert not app.exception
    assert app.get("graphviz_chart")


def test_dashboard_mcp_inspection_is_real(app):
    app.radio[0].set_value("MCP").run()
    next(button for button in app.button if button.label.startswith("Inspect real MCP")).click().run()
    assert not app.exception
    assert any("real_local_stdio" in str(element.value) for element in app.json)
