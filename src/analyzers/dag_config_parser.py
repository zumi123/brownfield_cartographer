"""Airflow/dbt YAML config parsing for pipeline topology and data lineage."""

from __future__ import annotations

import pathlib
from typing import Any

from ..models.schema import TransformationNode


class DAGConfigAnalyzer:
    """
    Parse Airflow DAG YAML and dbt schema.yml to extract pipeline topology
    and model/table references.
    """

    def __init__(self, repo_root: pathlib.Path) -> None:
        self.repo_root = pathlib.Path(repo_root)

    def _load_yaml(self, path: pathlib.Path) -> Any:
        try:
            import yaml

            return yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return None

    def extract_from_dbt_schema(self, path: pathlib.Path) -> list[TransformationNode]:
        """From dbt schema.yml: model name as target, refs() as sources."""
        data = self._load_yaml(path)
        if not data or not isinstance(data, dict):
            return []

        nodes: list[TransformationNode] = []
        rel = str(path.relative_to(self.repo_root))

        models = data.get("models") or data.get("version") and []
        if isinstance(models, list):
            for m in models:
                if isinstance(m, dict):
                    name = m.get("name")
                    refs = []
                    for col in m.get("columns") or []:
                        if isinstance(col, dict) and "tests" in col:
                            for t in col.get("tests") or []:
                                if isinstance(t, dict) and "ref" in t:
                                    refs.append(str(t["ref"]))
                    if name:
                        nodes.append(
                            TransformationNode(
                                id=f"{rel}:{name}",
                                source_datasets=refs,
                                target_datasets=[name],
                                transformation_type="config",
                                source_file=rel,
                            )
                        )
        elif isinstance(models, dict):
            for name, cfg in models.items():
                if isinstance(cfg, dict):
                    refs = cfg.get("refs") or []
                    if isinstance(refs, list):
                        refs = [str(r) for r in refs]
                    else:
                        refs = []
                    nodes.append(
                        TransformationNode(
                            id=f"{rel}:{name}",
                            source_datasets=refs,
                            target_datasets=[name],
                            transformation_type="config",
                            source_file=rel,
                        )
                    )

        return nodes

    def extract_from_airflow_dag(self, path: pathlib.Path) -> list[TransformationNode]:
        """From Airflow DAG YAML (if any): task IDs and dependencies."""
        data = self._load_yaml(path)
        if not data or not isinstance(data, dict):
            return []

        nodes: list[TransformationNode] = []
        rel = str(path.relative_to(self.repo_root))

        tasks = data.get("tasks") or data.get("dags", [{}])[0].get("tasks") if isinstance(data.get("dags"), list) else []
        if isinstance(tasks, list):
            for t in tasks:
                if isinstance(t, dict):
                    task_id = t.get("task_id") or t.get("id")
                    if task_id:
                        deps = t.get("dependencies") or t.get("downstream_task_ids") or []
                        if isinstance(deps, list):
                            nodes.append(
                                TransformationNode(
                                    id=f"{rel}:{task_id}",
                                    source_datasets=[str(d) for d in deps],
                                    target_datasets=[str(task_id)],
                                    transformation_type="config",
                                    source_file=rel,
                                )
                            )
        return nodes

    def run(self) -> list[TransformationNode]:
        """Scan YAML files and return transformation nodes from dbt/Airflow config."""
        out: list[TransformationNode] = []
        for path in self.repo_root.rglob("*.yml"):
            if ".git" in path.parts or ".cartography" in path.parts:
                continue
            out.extend(self.extract_from_dbt_schema(path))
            out.extend(self.extract_from_airflow_dag(path))
        for path in self.repo_root.rglob("*.yaml"):
            if ".git" in path.parts or ".cartography" in path.parts:
                continue
            out.extend(self.extract_from_dbt_schema(path))
            out.extend(self.extract_from_airflow_dag(path))
        return out
