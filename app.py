"""MarketPilot dashboard: interface only; agent logic stays in the Python package."""

import asyncio
import json
import os
import shutil

import streamlit as st
from openai import OpenAIError

from marketpilot.agent import DEFAULT_MODEL, run_marketing_agent
from marketpilot.analytics import CAMPAIGN_DIRECTORY, analyze_csv
from marketpilot.customization import SKILLS
from marketpilot.dashboard_helpers import save_campaign_upload
from marketpilot.demo import run_local_demo
from marketpilot.execution import redact
from marketpilot.mcp_client import inspect_mcp
from marketpilot.retrieval import build_index, load_documents, retrieve_knowledge
from marketpilot.storage import WorkflowStore
from marketpilot.visualizer import TOOL_LABELS, architecture_diagram, execution_diagram

st.set_page_config(page_title="MarketPilot AI", page_icon="📈", layout="wide")
st.title("MarketPilot AI")
st.caption("Marketing drafts · grounded knowledge · measurable execution")
store = WorkflowStore()
has_key = bool(os.environ.get("OPENAI_API_KEY", "").strip())
presentation = st.toggle("Presentation mode", key="presentation")
if presentation:
    st.markdown("<style>[data-testid='stSidebar']{display:none}</style>", unsafe_allow_html=True)

with st.sidebar:
    st.header("Run settings")
    model = st.text_input("Model", value=os.environ.get("MARKETPILOT_MODEL") or DEFAULT_MODEL)
    campaign = st.checkbox("Structured campaign report", value=True)
    use_mcp = st.checkbox("Connect local MCP server", value=False)
    skill = st.selectbox("Application procedure", ["None", *SKILLS])
    st.caption("API key available" if has_key else "No API key in this process. Local tools and the local demo still work.")
    st.caption("All emails and social content remain drafts. Sample knowledge and campaign data are fictional.")

view = "Workflow visualizer" if presentation else st.radio(
    "View", ["Workspace", "Workflow visualizer", "Knowledge", "MCP", "Learn"], horizontal=True)


def show_error(exc):
    if isinstance(exc, OpenAIError):
        st.error(f"OpenAI request failed ({type(exc).__name__}). Check credentials, API credits, model access, and network.")
    else:
        st.error(redact(str(exc)))


def show_diagram(graph, filename):
    st.graphviz_chart(graph, width="stretch", alt="MarketPilot workflow diagram")
    st.download_button("Download diagram (.dot)", graph.source, file_name=f"{filename}.dot",
                       mime="text/vnd.graphviz", key=f"dot_{filename}")
    # Browser diagrams need no native Graphviz binary; server-side SVG export does.
    if shutil.which("dot"):
        try:
            st.download_button("Download SVG", graph.pipe(format="svg"), file_name=f"{filename}.svg",
                               mime="image/svg+xml", key=f"svg_{filename}")
        except Exception:
            st.caption("SVG export is unavailable; the DOT download is still available.")


def created(run_id):
    st.session_state["selected_run"] = run_id


def run_with_progress(local=False, prompt=None):
    with st.status("Executing workflow", expanded=True) as status:
        progress_diagram = st.empty()

        def notify(message):
            status.write(message)
            run_id = st.session_state.get("selected_run")
            if run_id:
                record = store.get_run(run_id)
                progress_diagram.graphviz_chart(execution_diagram(record), width="stretch")

        try:
            if local:
                asyncio.run(run_local_demo(store=store, notify=notify, on_run_created=created))
            else:
                asyncio.run(run_marketing_agent(prompt, model=model, campaign=campaign, use_mcp=use_mcp,
                    skill=None if skill == "None" else skill, notify=notify, on_run_created=created))
            status.update(label="Workflow completed", state="complete", expanded=False)
        except Exception as exc:
            status.update(label="Workflow failed — inspect recorded steps", state="error")
            show_error(exc)
            return
    st.rerun()


if view == "Workspace":
    st.subheader("Create a marketing workflow")
    with st.form("marketing_request"):
        prompt = st.text_area("Marketing request", height=140,
            value="Use StudySprint knowledge in keyword mode, analyze sample_campaign.csv, and draft an improved email. Cite sources and label the data fictional.")
        submitted = st.form_submit_button("Run agent", disabled=not has_key)
    if submitted:
        run_with_progress(prompt=prompt)
    st.caption("A live agent request uses your OpenAI API credits. The local demo below makes no OpenAI request.")
    if st.button("Run local demo — no LLM", key="local_demo"):
        run_with_progress(local=True)

    st.subheader("Campaign CSV")
    upload = st.file_uploader("Upload a campaign CSV", type=["csv"])
    if upload is not None and st.button("Validate and save CSV"):
        try:
            filename = save_campaign_upload(upload.name, upload.getvalue())
            st.success(f"Saved {filename}. Use this filename in your request.")
        except Exception as exc:
            show_error(exc)
    filenames = sorted(path.name for path in CAMPAIGN_DIRECTORY.glob("*.csv"))
    if filenames:
        filename = st.selectbox("CSV to inspect", filenames)
        if st.button("Calculate metrics locally"):
            try:
                metrics = analyze_csv(filename)
                st.json(metrics["totals"])
                st.dataframe(metrics["channels"], width="stretch", hide_index=True)
                st.caption(f"Data status: {metrics['data_status']}; currency: {metrics['currency'] or 'unspecified'}")
            except Exception as exc:
                show_error(exc)
    run_id = st.session_state.get("selected_run")
    if run_id:
        run = store.get_run(run_id)
        if run["final_output"]:
            st.subheader("Latest result")
            st.markdown(run["final_output"])
        elif run["status"] == "failed":
            st.error("The last workflow failed. Open the visualizer to inspect its steps.")

elif view == "Workflow visualizer":
    st.subheader("Agent Workflow Visualizer")
    runs = store.list_runs(100)
    selected = None
    if runs:
        ids = [run["run_id"] for run in runs]
        current = st.session_state.get("selected_run")
        selected_id = st.selectbox("Recorded workflow", ids, index=ids.index(current) if current in ids else 0,
            format_func=lambda run_id: next(f"{run['started_at'][:19]} · {run['status']} · {run_id[:8]}"
                                           for run in runs if run["run_id"] == run_id))
        st.session_state["selected_run"] = selected_id
        selected = store.get_run(selected_id)
    if st.button("Refresh recorded workflows"):
        st.rerun()
    mode = st.radio("Diagram mode", ["Architecture", "Execution"], horizontal=True)
    if mode == "Architecture":
        show_diagram(architecture_diagram(selected, presentation), "architecture")
        st.caption("Solid components are implemented and active in the selected path; dashed components are inactive or explicitly optional. Dotted arrows identify separate API requests or saved-result inspection.")
    elif selected:
        show_diagram(execution_diagram(selected, presentation), "execution")
        st.caption("Arrows show recorded operation start order. No steps are inferred from the prompt. Blue = running; green = completed; red = failed.")
    else:
        st.info("No recorded workflows yet. Run an agent request or the explicitly labeled local demo.")

    if selected:
        if (selected.get("configuration") or {}).get("mode") == "offline_local_demo":
            st.info("Local demo: actual retrieval, calculations, and MCP operations. No LLM or autonomous planning was used.")
        columns = st.columns(3)
        columns[0].metric("Status", selected["status"])
        columns[1].metric("Tool operations", len(selected["steps"]))
        duration = selected.get("duration_seconds")
        columns[2].metric("Duration", f"{duration:.3f}s" if duration is not None else "Running / unavailable")
        steps = selected["steps"]
        if steps:
            step = st.selectbox("Inspect an execution step", steps,
                format_func=lambda item: f"{item['sequence']}. {TOOL_LABELS.get(item['tool'], item['tool'])} — {item['status']}")
            st.caption(f"Tool: {step['tool']} · started: {step['started_at']} · duration: {step.get('duration_seconds')}s")
            left, right = st.columns(2)
            with left:
                st.write("Inputs")
                st.json(step["inputs"])
            with right:
                st.write("Outputs")
                st.json(step["outputs"] or {})
            if step["error"]:
                st.error(str(step["error"]))
        else:
            st.caption("No tool operations were recorded for this run.")
        with st.expander("Main-model calls and run configuration"):
            st.json({"configuration": selected.get("configuration"), "model_calls": selected.get("model_calls")})
        if selected["error"]:
            st.error(str(selected["error"]))
        if selected["final_output"]:
            st.subheader("Final output")
            st.markdown(selected["final_output"])
            st.download_button("Download report (.md)", selected["final_output"], file_name="marketpilot-report.md")
        st.download_button("Download execution record (.json)", json.dumps(selected, indent=2), file_name="execution.json")

elif view == "Knowledge":
    st.subheader("Inspect the knowledge base")
    st.caption("Sample documents are fictional. Keyword inspection works without an API key; indexing and semantic/hybrid search use embeddings.")
    if st.button("Build or refresh embedding index", disabled=not has_key):
        try:
            with st.spinner("Indexing knowledge"):
                st.json(asyncio.run(build_index()))
        except Exception as exc:
            show_error(exc)
    query = st.text_input("Knowledge query", value="StudySprint supported features")
    retrieval_mode = st.selectbox("Retrieval mode", ["keyword", "semantic", "hybrid"])
    if st.button("Retrieve evidence"):
        try:
            st.json(asyncio.run(retrieve_knowledge(query, mode=retrieval_mode)))
        except Exception as exc:
            show_error(exc)
    for document in load_documents():
        with st.expander(document.source):
            st.json(document.metadata)
            st.markdown(document.body)

elif view == "MCP":
    st.subheader("Local MCP integration")
    st.write("Host: MarketPilot · Client: Agents SDK · Server: a separate local Python process over stdio.")
    st.caption("Tools are callable actions. Resources are application-loaded data. Prompts are user-selected templates. Listing a resource or prompt does not automatically put it in model context.")
    if st.button("Inspect real MCP connection — no API key"):
        try:
            with st.spinner("Connecting to the local server"):
                st.json(asyncio.run(inspect_mcp()))
        except Exception as exc:
            show_error(exc)

else:
    st.subheader("Explain the project")
    st.write("The LLM chooses actions. The SDK validates and executes tool requests, adds results to history, and calls the model again. Python retrieves evidence, calculates metrics, and saves state.")
    st.markdown("Read **docs/INTERVIEW_GUIDE.md** for the demo script, file map, limitations, and practice questions.")
    st.code("app.py / cli.py → agent.py → SDK runner → tools.py → retrieval / analytics / MCP → tool result → model → report")
    st.caption("Implemented: tool calling, hybrid RAG, pandas analytics, SQLite state, MCP primitives, Markdown procedures, SDK hooks, and these diagrams. Not implemented: subagents, plugin packaging, automatic memory, publishing, or automatic resume.")
