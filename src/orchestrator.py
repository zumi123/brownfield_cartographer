"""
Orchestrator: wires Surveyor and Hydrologist in sequence,
serializes outputs to .cartography/.
"""

import json
import pathlib
from typing import Optional

from git import Repo

from .agents.hydrologist import Hydrologist
from .agents.surveyor import Surveyor
from .graph.knowledge_graph import KnowledgeGraph


def _ensure_local_repo(target: pathlib.Path, branch: Optional[str] = None) -> pathlib.Path:
    """
    If target is a directory, use it. If it looks like a GitHub URL, clone into cwd.
    """
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


def run_analyze(target: pathlib.Path, branch: Optional[str] = None, output_dir: Optional[pathlib.Path] = None) -> None:
    """
    Run Surveyor then Hydrologist; write module_graph.json and lineage_graph.json.
    output_dir: default is <repo>/.cartography
    """
    repo_path = _ensure_local_repo(target, branch=branch)
    cartography_dir = output_dir if output_dir is not None else repo_path / ".cartography"
    cartography_dir = pathlib.Path(cartography_dir)
    cartography_dir.mkdir(parents=True, exist_ok=True)

    kg = KnowledgeGraph()

    surveyor = Surveyor(repo_root=repo_path, knowledge_graph=kg)
    surveyor.run()

    hydrologist = Hydrologist(repo_root=repo_path, knowledge_graph=kg)
    hydrologist.run()

    module_graph_path = cartography_dir / "module_graph.json"
    with module_graph_path.open("w", encoding="utf-8") as f:
        json.dump(kg.to_module_graph_dict(), f, indent=2)
    print(f"Module graph written to {module_graph_path}")

    lineage_graph_path = cartography_dir / "lineage_graph.json"
    with lineage_graph_path.open("w", encoding="utf-8") as f:
        json.dump(kg.to_lineage_graph_dict(), f, indent=2)
    print(f"Lineage graph written to {lineage_graph_path}")
