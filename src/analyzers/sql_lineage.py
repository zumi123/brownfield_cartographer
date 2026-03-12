"""SQL dependency extraction using sqlglot for data lineage."""

from __future__ import annotations

import logging
import re
import pathlib
from typing import Any

import sqlglot
from sqlglot import exp

from ..models.schema import TransformationNode

log = logging.getLogger(__name__)


class SQLLineageAnalyzer:
    """
    Extract table dependencies from SQL files (raw .sql and dbt models).
    Supports PostgreSQL, BigQuery, Snowflake, DuckDB via sqlglot.
    """

    DIALECTS = ("postgres", "bigquery", "snowflake", "duckdb")

    def __init__(self, repo_root: pathlib.Path) -> None:
        self.repo_root = pathlib.Path(repo_root)

    def extract_from_file(self, path: pathlib.Path) -> list[TransformationNode]:
        """
        Parse a single SQL file and return transformation nodes with
        source/target dataset names from SELECT/FROM/JOIN/CTEs.
        """
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        rel_path = str(path.relative_to(self.repo_root))
        nodes: list[TransformationNode] = []

        for dialect in self.DIALECTS:
            try:
                parsed = sqlglot.parse(source, dialect=dialect)
                if not parsed:
                    continue
                for stmt in parsed:
                    if not isinstance(stmt, exp.Query):
                        continue
                    sources: set[str] = set()
                    targets: set[str] = set()

                    # INSERT/UPDATE/MERGE target
                    if stmt.find(exp.Insert):
                        ins = stmt.find(exp.Insert)
                        if ins and ins.this:
                            t = self._table_name(ins.this)
                            if t:
                                targets.add(t)
                    if stmt.find(exp.Create):
                        cre = stmt.find(exp.Create)
                        if cre and cre.this:
                            t = self._table_name(cre.this)
                            if t:
                                targets.add(t)

                    # FROM, JOIN, CTEs as sources
                    for table in stmt.find_all(exp.Table):
                        name = self._table_name(table)
                        if name:
                            if targets:
                                sources.add(name)
                            else:
                                sources.add(name)
                    # dbt ref() in same file (basic pattern)
                    for ref_name in self._extract_ref_calls(source):
                        sources.add(ref_name)

                    if not targets and sources:
                        # CTE-based or SELECT: use last/most specific as logical target
                        ctes = list(stmt.find_all(exp.CTE))
                        if ctes:
                            for cte in ctes:
                                alias = cte.alias
                                if alias and hasattr(alias, "this"):
                                    targets.add(alias.this)  # type: ignore
                        else:
                            targets.add("__query_result__")

                    node_id = f"{rel_path}:{stmt.start or 0}-{stmt.end or 0}"
                    nodes.append(
                        TransformationNode(
                            id=node_id,
                            source_datasets=sorted(sources),
                            target_datasets=sorted(targets),
                            transformation_type="sql",
                            source_file=rel_path,
                            line_range=(stmt.start or 0, stmt.end or 0),
                            sql_query_if_applicable=stmt.sql(dialect=dialect)[:2000],
                        )
                    )
                break  # one dialect succeeded
            except Exception as e:
                log.debug("SQL parse failed for %s with dialect %s: %s", rel_path, dialect, e)
                continue

        if not nodes:
            # Fallback: single node with all tables we can find
            try:
                parsed = sqlglot.parse(source)
                all_tables: set[str] = set()
                for stmt in parsed or []:
                    for table in stmt.find_all(exp.Table):
                        n = self._table_name(table)
                        if n:
                            all_tables.add(n)
                # Basic dbt ref() pattern: ref('model_name') or ref("model_name")
                for ref_name in self._extract_ref_calls(source):
                    all_tables.add(ref_name)
                if all_tables:
                    nodes.append(
                        TransformationNode(
                            id=rel_path,
                            source_datasets=sorted(all_tables),
                            target_datasets=[],
                            transformation_type="sql",
                            source_file=rel_path,
                        )
                    )
            except Exception as e:
                log.warning("SQL parse fallback failed for %s: %s", rel_path, e)

        return nodes

    def _extract_ref_calls(self, source: str) -> list[str]:
        """Extract dbt ref() targets from raw SQL (Jinja not rendered)."""
        refs: list[str] = []
        for m in re.finditer(r"ref\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", source, re.IGNORECASE):
            refs.append(m.group(1))
        return refs

    def _table_name(self, table: exp.Table | Any) -> str | None:
        if not isinstance(table, exp.Table):
            return None
        parts = []
        if table.catalog:
            parts.append(table.catalog)
        if table.db:
            parts.append(table.db)
        if table.name:
            parts.append(table.name)
        return ".".join(parts) if parts else None

    def run(self) -> list[TransformationNode]:
        """Scan repo for .sql files and return all transformation nodes."""
        out: list[TransformationNode] = []
        for path in self.repo_root.rglob("*.sql"):
            if ".git" in path.parts or ".cartography" in path.parts:
                continue
            out.extend(self.extract_from_file(path))
        return out
