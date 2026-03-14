"""
Navigator agent: query interface with 4 tools (find_implementation, trace_lineage, blast_radius, explain_module).
Evidence cited: source file, line range, analysis method.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Optional

from ..graph.knowledge_graph import KnowledgeGraph


class Navigator:
    """Query the codebase map and lineage; every answer cites evidence."""

    def __init__(
        self,
        repo_root: pathlib.Path,
        knowledge_graph: KnowledgeGraph,
        purpose_index: Optional[dict[str, str]] = None,
    ) -> None:
        self.repo_root = pathlib.Path(repo_root)
        self.kg = knowledge_graph
        self.purpose_index = purpose_index or {}

    def find_implementation(self, concept: str) -> dict[str, Any]:
        """Semantic search: where is this concept implemented? Cites file + purpose (static/LLM)."""
        concept_lower = concept.lower()
        matches = []
        for path, purpose in self.purpose_index.items():
            if concept_lower in purpose.lower() or concept_lower in path.lower():
                matches.append({"path": path, "purpose": purpose[:300]})
        for path in self.kg.module_graph.nodes:
            if concept_lower in path:
                purpose = self.kg.module_graph.nodes[path].get("purpose_statement") or self.purpose_index.get(path, "")
                matches.append({"path": path, "purpose": (purpose or "(no purpose)")[:300]})
        return {
            "concept": concept,
            "matches": matches[:15],
            "evidence": "semantic_index + module_graph (static analysis + LLM purpose)",
            "method": "static + LLM",
        }

    def trace_lineage(self, dataset: str, direction: str = "upstream") -> dict[str, Any]:
        """Graph: what produces/consumes this dataset? Cites source_file, line_range."""
        if not self.kg.lineage_graph.has_node(dataset):
            return {
                "dataset": dataset,
                "direction": direction,
                "nodes": [],
                "edges": [],
                "evidence": "lineage_graph",
                "method": "static",
            }
        node_ids = self.kg.blast_radius(dataset, direction=direction)
        edges_with_meta = []
        for u, v in self.kg.lineage_graph.edges:
            if u in node_ids or v in node_ids:
                meta = dict(self.kg.lineage_graph.nodes.get(u, {}))
                meta.update(self.kg.lineage_graph.nodes.get(v, {}))
                source_file = meta.get("source_file", "")
                line_range = meta.get("line_range")
                edges_with_meta.append({"source": u, "target": v, "source_file": source_file, "line_range": line_range})
        return {
            "dataset": dataset,
            "direction": direction,
            "nodes": list(node_ids)[:50],
            "edges": edges_with_meta[:30],
            "evidence": f"lineage_graph traversal; source_file/line_range from transformation nodes",
            "method": "static",
        }

    def blast_radius(self, module_path: str) -> dict[str, Any]:
        """Graph: what breaks if this module/dataset changes? Cites dependencies."""
        downstream = self.kg.blast_radius(module_path, direction="downstream")
        with_paths = self.kg.blast_radius_with_paths(module_path, direction="downstream")
        return {
            "module": module_path,
            "downstream_dependents": list(downstream)[:50],
            "paths": [(n, p) for n, p in with_paths[:20]],
            "evidence": "lineage_graph BFS/shortest_path",
            "method": "static",
        }

    def explain_module(self, path: str) -> dict[str, Any]:
        """Generative: what does this module do? Cites purpose_statement (LLM) and graph context."""
        path = pathlib.Path(path).as_posix()
        if self.kg.module_graph.has_node(path):
            attrs = dict(self.kg.module_graph.nodes[path])
            purpose = attrs.get("purpose_statement") or self.purpose_index.get(path, "")
            in_degree = self.kg.module_graph.in_degree(path)
            out_degree = self.kg.module_graph.out_degree(path)
            return {
                "path": path,
                "purpose": purpose or "(no purpose generated)",
                "in_degree": in_degree,
                "out_degree": out_degree,
                "evidence": f"module_graph + purpose_statement (LLM); file:{path}",
                "method": "LLM + static",
            }
        return {
            "path": path,
            "purpose": "(module not in graph)",
            "evidence": "module_graph",
            "method": "static",
        }

    def run_query(self, query: str) -> str:
        """Parse a natural-language-ish query and return a tool result as string."""
        q = query.strip().lower()
        if "upstream" in q or "produce" in q or "feed" in q:
            parts = query.split()
            dataset = parts[-1] if parts else ""
            for w in ["upstream", "sources", "feed", "produce", "what"]:
                dataset = dataset.replace(w, "").strip()
            if not dataset:
                dataset = parts[0] if parts else ""
            result = self.trace_lineage(dataset, direction="upstream")
            return json.dumps(result, indent=2, default=str)
        if "downstream" in q or "consum" in q:
            parts = query.split()
            dataset = parts[-1] if parts else ""
            result = self.trace_lineage(dataset, direction="downstream")
            return json.dumps(result, indent=2, default=str)
        if "blast" in q or "break" in q:
            parts = query.split()
            path = " ".join(p for p in parts if not p.lower() in ("blast", "radius", "what", "would", "break", "if", "i", "change"))
            if not path or len(path) < 2:
                path = parts[0] if parts else ""
            result = self.blast_radius(path.strip())
            return json.dumps(result, indent=2, default=str)
        if "explain" in q or "what does" in q:
            parts = query.split()
            path = next((p for p in parts if "/" in p or p.endswith(".py")), parts[-1] if parts else "")
            result = self.explain_module(path)
            return json.dumps(result, indent=2, default=str)
        return json.dumps(self.find_implementation(query), indent=2, default=str)
