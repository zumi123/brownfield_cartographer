"""
Orchestrator: full pipeline Surveyor -> Hydrologist -> Semanticist -> Archivist.
Writes CODEBASE.md, onboarding_brief.md, module_graph.json, lineage_graph.json,
cartography_trace.jsonl, semantic_index. Supports incremental mode (re-analyze changed files only).
"""

from __future__ import annotations

import json
import pathlib
from typing import Optional, Set

from git import Repo

from .agents.archivist import Archivist
from .agents.hydrologist import Hydrologist
from .agents.navigator import Navigator
from .agents.semanticist import Semanticist
from .agents.surveyor import Surveyor
from .graph.knowledge_graph import KnowledgeGraph


def _ensure_local_repo(target: pathlib.Path, branch: Optional[str] = None) -> pathlib.Path:
    if target.is_dir():
        return target
    if "github.com" in str(target):
        parent = pathlib.Path(".").resolve()
        repo_name = str(target).rstrip("/").split("/")[-1].replace(".git", "")
        dest = parent / repo_name
        if not dest.exists():
            Repo.clone_from(str(target), dest, branch=branch if branch else None)
        return dest
    raise ValueError(f"Target {target} is not a directory and not a recognized GitHub URL.")


def _get_changed_paths(repo_path: pathlib.Path, cartography_dir: pathlib.Path) -> Optional[Set[str]]:
    """Return set of relative paths changed since last run, or None for full run."""
    last_run_file = cartography_dir / "last_run_commit"
    if not last_run_file.exists():
        return None
    try:
        last_commit = last_run_file.read_text().strip()
        repo = Repo(repo_path)
        diff = repo.git.diff("--name-only", last_commit, "HEAD")
        return set(line.strip() for line in diff.splitlines() if line.strip())
    except Exception:
        return None


def _save_last_run_commit(repo_path: pathlib.Path, cartography_dir: pathlib.Path) -> None:
    try:
        repo = Repo(repo_path)
        commit = repo.head.commit.hexsha
        (cartography_dir / "last_run_commit").write_text(commit)
    except Exception:
        pass


def run_analyze(
    target: pathlib.Path,
    branch: Optional[str] = None,
    output_dir: Optional[pathlib.Path] = None,
    incremental: bool = False,
) -> None:
    """
    Full pipeline: Surveyor -> Hydrologist -> Semanticist -> Archivist.
    Writes all artifacts to .cartography/ (or output_dir).
    When incremental=True and .cartography exists, re-analyzes only changed files and merges.
    """
    repo_path = _ensure_local_repo(target, branch=branch)
    cartography_dir = output_dir if output_dir is not None else repo_path / ".cartography"
    cartography_dir = pathlib.Path(cartography_dir)
    cartography_dir.mkdir(parents=True, exist_ok=True)

    kg = KnowledgeGraph()
    changed_paths: Optional[Set[str]] = None
    if incremental:
        changed_paths = _get_changed_paths(repo_path, cartography_dir)
        if changed_paths is not None:
            mg_path = cartography_dir / "module_graph.json"
            lg_path = cartography_dir / "lineage_graph.json"
            if mg_path.exists():
                try:
                    kg.from_module_graph_dict(json.loads(mg_path.read_text()))
                except Exception:
                    pass
            if lg_path.exists():
                try:
                    kg.from_lineage_graph_dict(json.loads(lg_path.read_text()))
                except Exception:
                    pass
            # Remove changed-file nodes so we re-add them fresh
            for path in changed_paths:
                if kg.module_graph.has_node(path):
                    kg.module_graph.remove_node(path)
            to_remove = [n for n in kg.lineage_graph.nodes if kg.lineage_graph.nodes[n].get("source_file") in changed_paths]
            for n in to_remove:
                kg.lineage_graph.remove_node(n)

    # Surveyor
    print("Running Surveyor (module graph, PageRank, git velocity, dead code)...")
    surveyor = Surveyor(repo_root=repo_path, knowledge_graph=kg)
    surveyor.run(changed_paths=changed_paths)

    # Hydrologist
    print("Running Hydrologist (lineage graph)...")
    hydrologist = Hydrologist(repo_root=repo_path, knowledge_graph=kg)
    hydrologist.run(changed_paths=changed_paths)

    # Serialize graphs (so Semanticist/Archivist see full state)
    module_graph_path = cartography_dir / "module_graph.json"
    with module_graph_path.open("w", encoding="utf-8") as f:
        json.dump(kg.to_module_graph_dict(), f, indent=2)
    print(f"Module graph written to {module_graph_path}")

    lineage_graph_path = cartography_dir / "lineage_graph.json"
    with lineage_graph_path.open("w", encoding="utf-8") as f:
        json.dump(kg.to_lineage_graph_dict(), f, indent=2)
    print(f"Lineage graph written to {lineage_graph_path}")

    # Semanticist
    print("Running Semanticist (purpose statements, domains, Day-One answers)...")
    semanticist = Semanticist(repo_root=repo_path, knowledge_graph=kg)
    semanticist.run()

    # Re-serialize module graph with purpose_statement and domain_cluster
    with module_graph_path.open("w", encoding="utf-8") as f:
        json.dump(kg.to_module_graph_dict(), f, indent=2)

    # Archivist
    print("Running Archivist (CODEBASE.md, onboarding brief, trace, semantic index)...")
    archivist = Archivist(
        repo_root=repo_path,
        knowledge_graph=kg,
        semanticist_purposes=semanticist.purpose_statements,
        semanticist_drift=semanticist.doc_drift,
        day_one_answers=semanticist.day_one_answers,
    )
    archivist.log("orchestrator", "run_surveyor", "Surveyor completed", "high")
    archivist.log("orchestrator", "run_hydrologist", "Hydrologist completed", "high")
    archivist.log("orchestrator", "run_semanticist", "Semanticist completed", "high")
    archivist.write_artifacts(cartography_dir)

    _save_last_run_commit(repo_path, cartography_dir)
    print("CODEBASE.md, onboarding_brief.md, cartography_trace.jsonl, semantic_index written.")
    print("Done.")


def run_query(repo_path: pathlib.Path, cartography_dir: Optional[pathlib.Path] = None) -> None:
    """Load .cartography and start Navigator interactive query loop."""
    cartography_dir = pathlib.Path(cartography_dir or repo_path / ".cartography")
    if not cartography_dir.exists():
        print("No .cartography found. Run: cartographer analyze <path> first.")
        return
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
    nav = Navigator(repo_root=repo_path, knowledge_graph=kg, purpose_index=purpose_index)
    print("Navigator ready. Commands: ask about lineage (e.g. 'upstream of X'), blast_radius, explain <path>, or a concept to find.")
    print("Type 'quit' or 'exit' to stop.")
    while True:
        try:
            q = input("\nQuery> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("quit", "exit", "q"):
            break
        print(nav.run_query(q))
    print("Bye.")
