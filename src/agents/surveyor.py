"""Surveyor agent: static structure, module graph, PageRank, git velocity, dead code candidates."""

from __future__ import annotations

import logging
import pathlib
from typing import Optional, Set

from git import Repo

from ..analyzers.tree_sitter_analyzer import TreeSitterAnalyzer
from ..graph.knowledge_graph import KnowledgeGraph
from ..models.schema import ModuleNode

log = logging.getLogger(__name__)


class Surveyor:
    """
    Static structure analyst. Builds module import graph, computes PageRank,
    git change velocity, and flags dead code candidates.
    """

    def __init__(self, repo_root: pathlib.Path, knowledge_graph: KnowledgeGraph) -> None:
        self.repo_root = pathlib.Path(repo_root)
        self.kg = knowledge_graph
        self.analyzer = TreeSitterAnalyzer(self.repo_root)

    def run(self, changed_paths: Optional[Set[str]] = None) -> None:
        all_modules: Set[str] = set()
        for path in self.analyzer.iter_python_files():
            rel = str(path.relative_to(self.repo_root))
            if changed_paths is not None and rel not in changed_paths:
                continue
            try:
                self.kg.add_module(path=rel, language="python")
                all_modules.add(rel)
                for mod_name, is_relative in self.analyzer.extract_python_imports(path):
                    target_rel = self._resolve_import_to_path(rel, mod_name, is_relative)
                    if target_rel:
                        self.kg.add_module(path=target_rel, language="python")
                        self.kg.add_import_edge(rel, target_rel)
                        all_modules.add(target_rel)
            except Exception as e:
                log.warning("Surveyor skipped %s: %s", path, e)
                continue

        self._attach_git_velocity()

        referenced = set()
        for u, v in self.kg.module_graph.edges:
            referenced.add(v)
        for n in self.kg.module_graph.nodes:
            is_dead = n not in referenced and self.kg.module_graph.out_degree(n) > 0
            if is_dead and self.kg.module_graph.nodes[n].get("language") == "python":
                self.kg.module_graph.nodes[n]["is_dead_code_candidate"] = True
            else:
                self.kg.module_graph.nodes[n]["is_dead_code_candidate"] = False

    def _resolve_import_to_path(self, from_rel: str, import_name: str, is_relative: bool) -> str | None:
        if is_relative:
            stripped = import_name.lstrip(".")
            level = len(import_name) - len(stripped)
            base = (self.repo_root / from_rel).parent
            for _ in range(level - 1):
                base = base.parent
            parts = stripped.replace(".", "/")
            if not parts:
                return None
            for candidate in (base / f"{parts}.py", base / parts / "__init__.py"):
                if candidate.is_file():
                    return str(candidate.relative_to(self.repo_root))
            return None
        candidate = self.repo_root / (import_name.replace(".", "/") + ".py")
        if candidate.exists():
            return str(candidate.relative_to(self.repo_root))
        pkg = self.repo_root / import_name.replace(".", "/") / "__init__.py"
        if pkg.exists():
            return str(pkg.relative_to(self.repo_root))
        return None

    def _attach_git_velocity(self, days: int = 30) -> None:
        try:
            repo = Repo(self.repo_root)
            since = f"--since={days} days ago"
            for path in self.kg.module_graph.nodes:
                try:
                    full = self.repo_root / path
                    if not full.exists():
                        continue
                    count = len(list(repo.iter_commits(paths=str(full), max_count=500)))
                    self.kg.module_graph.nodes[path]["change_velocity_30d"] = count
                except Exception:
                    self.kg.module_graph.nodes[path]["change_velocity_30d"] = 0
        except Exception:
            for n in self.kg.module_graph.nodes:
                self.kg.module_graph.nodes[n]["change_velocity_30d"] = 0
