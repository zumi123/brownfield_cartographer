"""Hydrologist agent: data lineage graph, blast_radius, find_sources/find_sinks."""

from __future__ import annotations

import pathlib

from ..analyzers.dag_config_parser import DAGConfigAnalyzer
from ..analyzers.python_data_flow import PythonDataFlowAnalyzer
from ..analyzers.sql_lineage import SQLLineageAnalyzer
from ..graph.knowledge_graph import KnowledgeGraph


class Hydrologist:
    """
    Data flow and lineage analyst. Builds DataLineageGraph from SQL, YAML config, and Python data flow.
    """

    def __init__(self, repo_root: pathlib.Path, knowledge_graph: KnowledgeGraph) -> None:
        self.repo_root = pathlib.Path(repo_root)
        self.kg = knowledge_graph
        self.sql_analyzer = SQLLineageAnalyzer(repo_root)
        self.dag_analyzer = DAGConfigAnalyzer(repo_root)
        self.python_flow_analyzer = PythonDataFlowAnalyzer(repo_root)

    def run(self) -> None:
        for t in self.sql_analyzer.run():
            self.kg.add_transformation(t)
        for t in self.dag_analyzer.run():
            self.kg.add_transformation(t)
        for t in self.python_flow_analyzer.run():
            self.kg.add_transformation(t)

    def blast_radius(self, node_id: str, direction: str = "downstream") -> list[str]:
        """What would break if this node changed (downstream) or what it depends on (upstream)."""
        return self.kg.blast_radius(node_id, direction=direction)

    def blast_radius_with_paths(self, node_id: str, direction: str = "downstream") -> list[tuple[str, list[str]]]:
        """Blast radius with graph path to each dependent (BFS path)."""
        return self.kg.blast_radius_with_paths(node_id, direction=direction)

    def find_sources(self) -> list[str]:
        """Entry points: datasets with no upstream."""
        return self.kg.find_sources()

    def find_sinks(self) -> list[str]:
        """Exit points: datasets with no downstream."""
        return self.kg.find_sinks()
