"""
Streamlit UI for the Brownfield Cartographer.
Run: streamlit run app_ui.py
"""

import io
import json
import pathlib
import sys
from contextlib import redirect_stdout

import streamlit as st

# Ensure project root is on path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from src.orchestrator import run_analyze
from src.agents.navigator import Navigator
from src.graph.knowledge_graph import KnowledgeGraph


def load_navigator(repo_path: pathlib.Path, cartography_dir: pathlib.Path):
    """Load KG and purpose index, return Navigator or None."""
    if not cartography_dir.exists():
        return None
    kg = KnowledgeGraph()
    mg_path = cartography_dir / "module_graph.json"
    lg_path = cartography_dir / "lineage_graph.json"
    if mg_path.exists():
        kg.from_module_graph_dict(json.loads(mg_path.read_text()))
    if lg_path.exists():
        kg.from_lineage_graph_dict(json.loads(lg_path.read_text()))
    index_path = cartography_dir / "semantic_index" / "purpose_index.json"
    purpose_index = {}
    if index_path.exists():
        purpose_index = json.loads(index_path.read_text())
    return Navigator(repo_root=repo_path, knowledge_graph=kg, purpose_index=purpose_index)


st.set_page_config(page_title="Brownfield Cartographer", layout="wide")
st.title("Brownfield Cartographer")
st.caption("Codebase intelligence: module graph, lineage, CODEBASE.md, and Navigator queries.")

tab_analyze, tab_artifacts, tab_query = st.tabs(["Analyze", "Artifacts", "Query"])

# --- Analyze tab ---
with tab_analyze:
    st.subheader("Run full pipeline")
    target = st.text_input(
        "Repo path or GitHub URL",
        value=".",
        help="Local path (e.g. . or /path/to/repo) or https://github.com/org/repo",
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        incremental = st.checkbox("Incremental (only changed files)", value=False)
    with col2:
        branch = st.text_input("Branch (GitHub only)", value="", help="Leave empty for default")
    with col3:
        output_dir = st.text_input("Output directory (optional)", value="", help="Default: <repo>/.cartography")
    if st.button("Run analysis", type="primary"):
        target_path = pathlib.Path(target.strip()).expanduser()
        out_dir = pathlib.Path(output_dir.strip()).expanduser() if output_dir.strip() else None
        buf = io.StringIO()
        with st.status("Running Surveyor → Hydrologist → Semanticist → Archivist...", expanded=True):
            with redirect_stdout(buf):
                try:
                    run_analyze(
                        target_path,
                        branch=branch.strip() or None,
                        output_dir=out_dir,
                        incremental=incremental,
                    )
                except Exception as e:
                    st.error(str(e))
                    raise
            st.text(buf.getvalue())
        st.success("Done. Check the Artifacts tab.")

# --- Artifacts tab ---
with tab_artifacts:
    st.subheader("View cartography artifacts")
    artifacts_path = st.text_input(
        "Path to repo (with .cartography)",
        value=".",
        key="artifacts_path",
        help="Directory that contains .cartography/",
    )
    cartography_dir = pathlib.Path(artifacts_path.strip()).expanduser() / ".cartography"
    if not cartography_dir.exists():
        st.info("No .cartography found. Run Analyze first.")
    else:
        codebase_md = cartography_dir / "CODEBASE.md"
        brief_md = cartography_dir / "onboarding_brief.md"
        module_json = cartography_dir / "module_graph.json"
        lineage_json = cartography_dir / "lineage_graph.json"
        artifact = st.radio(
            "Choose artifact",
            ["CODEBASE.md", "onboarding_brief.md", "module_graph.json (summary)", "lineage_graph.json (summary)"],
            horizontal=True,
        )
        if artifact == "CODEBASE.md" and codebase_md.exists():
            st.markdown(codebase_md.read_text())
        elif artifact == "onboarding_brief.md" and brief_md.exists():
            st.markdown(brief_md.read_text())
        elif artifact == "module_graph.json (summary)" and module_json.exists():
            data = json.loads(module_json.read_text())
            st.metric("Modules", len(data.get("nodes", [])))
            st.metric("Import edges", len(data.get("edges", [])))
            st.json(data.get("high_velocity_files", []))
            with st.expander("Full module_graph.json"):
                st.json(data)
        elif artifact == "lineage_graph.json (summary)" and lineage_json.exists():
            data = json.loads(lineage_json.read_text())
            nodes = data.get("nodes", [])
            st.metric("Lineage nodes", len(nodes))
            st.metric("Lineage edges", len(data.get("edges", [])))
            with st.expander("Full lineage_graph.json"):
                st.json(data)

# --- Query tab ---
with tab_query:
    st.subheader("Navigator: ask about the codebase")
    query_path = st.text_input("Repo path (with .cartography)", value=".", key="query_path")
    cartography_dir = pathlib.Path(query_path.strip()).expanduser() / ".cartography"
    nav = load_navigator(pathlib.Path(query_path.strip()).expanduser(), cartography_dir) if query_path.strip() else None
    if nav is None:
        st.warning("No .cartography found. Run Analyze first.")
    else:
        q = st.text_input(
            "Query",
            placeholder="e.g. upstream of raw.customers | blast radius of src/cli.py | explain src/orchestrator.py",
        )
        if q and st.button("Run query"):
            result = nav.run_query(q)
            try:
                parsed = json.loads(result)
                st.json(parsed)
            except json.JSONDecodeError:
                st.code(result)

st.sidebar.markdown("### Quick start")
st.sidebar.markdown("1. **Analyze**: enter a path (e.g. `.`) and Run analysis.")
st.sidebar.markdown("2. **Artifacts**: view CODEBASE.md, onboarding brief, graphs.")
st.sidebar.markdown("3. **Query**: run lineage, blast radius, explain, find.")
