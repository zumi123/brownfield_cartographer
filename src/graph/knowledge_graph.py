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
        """JSON-serializable module graph with pagerank and analytical metadata."""
        pr = self.pagerank_modules()
        nodes = []
        for n in self.module_graph.nodes:
            nd = {
                "id": n,
                "language": self.module_graph.nodes[n].get("language"),
                "pagerank": round(pr.get(n, 0.0), 6),
                "change_velocity_30d": self.module_graph.nodes[n].get("change_velocity_30d"),
                "is_dead_code_candidate": self.module_graph.nodes[n].get("is_dead_code_candidate", False),
            }
            if self.module_graph.nodes[n].get("purpose_statement") is not None:
                nd["purpose_statement"] = self.module_graph.nodes[n]["purpose_statement"]
            if self.module_graph.nodes[n].get("domain_cluster") is not None:
                nd["domain_cluster"] = self.module_graph.nodes[n]["domain_cluster"]
            nodes.append(nd)
        edges = [
            {"source": u, "target": v, "type": EdgeTypes.IMPORTS.value, "weight": self.module_graph.edges[u, v].get("weight", 1)}
            for u, v in self.module_graph.edges
        ]
        # Top high-velocity files (descending by change_velocity_30d); at least top 10 or top 20%
        velocity_list = [(n, self.module_graph.nodes[n].get("change_velocity_30d") or 0) for n in self.module_graph.nodes]
        velocity_list.sort(key=lambda x: -x[1])
        k = min(len(velocity_list), max(10, (len(velocity_list) + 4) // 5))
        high_velocity = [path for path, _ in velocity_list[:k]]
        return {"nodes": nodes, "edges": edges, "high_velocity_files": high_velocity}

    def from_module_graph_dict(self, data: Dict[str, Any]) -> None:
        """Deserialize module graph from JSON-compatible dict (shared service read)."""
        self.module_graph.clear()
        for node in data.get("nodes") or []:
            nid = node.get("id") or node.get("path")
            if nid:
                attrs = {
                    "language": node.get("language", "python"),
                    "change_velocity_30d": node.get("change_velocity_30d"),
                    "is_dead_code_candidate": node.get("is_dead_code_candidate", False),
                }
                if node.get("purpose_statement") is not None:
                    attrs["purpose_statement"] = node["purpose_statement"]
                if node.get("domain_cluster") is not None:
                    attrs["domain_cluster"] = node["domain_cluster"]
                self.module_graph.add_node(nid, **attrs)
        for edge in data.get("edges") or []:
            u, v = edge.get("source"), edge.get("target")
            if u and v:
                self.module_graph.add_edge(u, v, weight=edge.get("weight", 1))

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

    def blast_radius_with_paths(self, node_id: str, direction: str = "downstream") -> List[tuple[str, List[str]]]:
        """Like blast_radius but returns (node_id, path_from_start) for each reachable node (BFS path)."""
        if not self.lineage_graph.has_node(node_id):
            return []
        out: List[tuple[str, List[str]]] = []
        if direction == "downstream":
            for succ in nx.descendants(self.lineage_graph, node_id):
                try:
                    path = nx.shortest_path(self.lineage_graph, node_id, succ)
                    out.append((succ, path))
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    pass
        else:
            for pred in nx.ancestors(self.lineage_graph, node_id):
                try:
                    path = nx.shortest_path(self.lineage_graph, pred, node_id)
                    out.append((pred, path))
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    pass
        return out

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

    def from_lineage_graph_dict(self, data: Dict[str, Any]) -> None:
        """Deserialize lineage graph from JSON-compatible dict (shared service read)."""
        self.lineage_graph.clear()
        self._transformation_nodes.clear()
        for node in data.get("nodes") or []:
            nid = node.get("id")
            if not nid:
                continue
            attrs = {k: v for k, v in node.items() if k != "id"}
            if attrs.get("line_range") and isinstance(attrs["line_range"], list):
                attrs["line_range"] = tuple(attrs["line_range"]) if len(attrs["line_range"]) >= 2 else None
            self.lineage_graph.add_node(nid, **attrs)
        for edge in data.get("edges") or []:
            u, v = edge.get("source"), edge.get("target")
            if u and v and self.lineage_graph.has_node(u) and self.lineage_graph.has_node(v):
                self.lineage_graph.add_edge(u, v, type=edge.get("type", "PRODUCES"))
