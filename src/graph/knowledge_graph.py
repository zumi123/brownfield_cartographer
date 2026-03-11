"""NetworkX-backed knowledge graph with module and lineage graphs."""

from __future__ import annotations

from typing import Any, Dict, List

import networkx as nx

from ..models.schema import (
    EdgeTypes,
    ModuleNode as ModuleNodeSchema,
    TransformationNode,
    transformation_node_to_dict,
)


class KnowledgeGraph:
    """
    Central store: module import graph (NetworkX) and data lineage graph (NetworkX).
    All nodes/edges conform to Pydantic schemas where applicable.
    """

    def __init__(self) -> None:
        self.module_graph: nx.DiGraph = nx.DiGraph()
        self.lineage_graph: nx.DiGraph = nx.DiGraph()
        self._transformation_nodes: Dict[str, TransformationNode] = {}

    # --- Module graph (Surveyor) ---

    def add_module(self, module: ModuleNodeSchema | None = None, path: str | None = None, language: str = "python") -> None:
        if module is not None:
            path = module.path
            language = module.language
        if path is None:
            return
        if not self.module_graph.has_node(path):
            self.module_graph.add_node(path, language=language)

    def add_import_edge(self, source_path: str, target_path: str, weight: int = 1) -> None:
        self.module_graph.add_edge(source_path, target_path)
        if self.module_graph.has_edge(source_path, target_path):
            w = self.module_graph.edges[source_path, target_path].get("weight", 0)
            self.module_graph.edges[source_path, target_path]["weight"] = w + weight
        else:
            self.module_graph.add_edge(source_path, target_path, weight=weight)

    def pagerank_modules(self) -> Dict[str, float]:
        """Return PageRank for module graph (architectural hubs)."""
        try:
            return nx.pagerank(self.module_graph)
        except Exception:
            # Fallback when numpy/scipy not available: uniform score
            n = max(len(self.module_graph.nodes), 1)
            return {node: 1.0 / n for node in self.module_graph.nodes}

    def strongly_connected_components(self) -> List[List[str]]:
        """Circular dependencies in the module graph."""
        try:
            return list(nx.strongly_connected_components(self.module_graph))
        except Exception:
            return []

    def to_module_graph_dict(self) -> Dict[str, List]:
        """JSON-serializable module graph with optional pagerank."""
        pr = self.pagerank_modules()
        nodes = [
            {
                "id": n,
                "language": self.module_graph.nodes[n].get("language"),
                "pagerank": round(pr.get(n, 0.0), 6),
            }
            for n in self.module_graph.nodes
        ]
        edges = [
            {"source": u, "target": v, "type": EdgeTypes.IMPORTS.value, "weight": self.module_graph.edges[u, v].get("weight", 1)}
            for u, v in self.module_graph.edges
        ]
        return {"nodes": nodes, "edges": edges}

    # --- Lineage graph (Hydrologist) ---

    def add_transformation(self, t: TransformationNode) -> None:
        self._transformation_nodes[t.id] = t
        self.lineage_graph.add_node(t.id, kind="transformation", **transformation_node_to_dict(t))
        for src in t.source_datasets:
            self.lineage_graph.add_node(src, kind="dataset")
            self.lineage_graph.add_edge(src, t.id, type=EdgeTypes.CONSUMES.value)
        for tgt in t.target_datasets:
            self.lineage_graph.add_node(tgt, kind="dataset")
            self.lineage_graph.add_edge(t.id, tgt, type=EdgeTypes.PRODUCES.value)

    def blast_radius(self, node_id: str, direction: str = "downstream") -> List[str]:
        """Nodes reachable from node_id (downstream = dependents, upstream = dependencies)."""
        if direction == "downstream":
            if not self.lineage_graph.has_node(node_id):
                return []
            return list(nx.descendants(self.lineage_graph, node_id))
        else:
            if not self.lineage_graph.has_node(node_id):
                return []
            return list(nx.ancestors(self.lineage_graph, node_id))

    def find_sources(self) -> List[str]:
        """Nodes with in-degree 0 (entry points)."""
        return [n for n in self.lineage_graph.nodes if self.lineage_graph.in_degree(n) == 0]

    def find_sinks(self) -> List[str]:
        """Nodes with out-degree 0 (exit points)."""
        return [n for n in self.lineage_graph.nodes if self.lineage_graph.out_degree(n) == 0]

    def to_lineage_graph_dict(self) -> Dict[str, Any]:
        """JSON-serializable lineage graph."""
        nodes = []
        for n in self.lineage_graph.nodes:
            data = dict(self.lineage_graph.nodes[n])
            if "line_range" in data and data["line_range"] is not None:
                data["line_range"] = list(data["line_range"])
            nodes.append({"id": n, **data})
        edges = [
            {"source": u, "target": v, "type": self.lineage_graph.edges[u, v].get("type", "PRODUCES")}
            for u, v in self.lineage_graph.edges
        ]
        return {"nodes": nodes, "edges": edges}
