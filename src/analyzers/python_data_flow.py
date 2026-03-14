"""Python data-flow extraction for lineage (pandas, PySpark, SQLAlchemy patterns)."""

from __future__ import annotations

import logging
import pathlib
import re
from typing import List, Optional

from ..models.schema import TransformationNode

log = logging.getLogger(__name__)

# Patterns: method name -> (sources from args, targets from args)
READ_PATTERNS = [
    (r"\.read_csv\s*\(\s*['\"]([^'\"]+)['\"]", "file"),
    (r"\.read_parquet\s*\(\s*['\"]([^'\"]+)['\"]", "file"),
    (r"read_sql\s*\(\s*[^,]+,\s*['\"]([^'\"]+)['\"]", "table"),
    (r"\.read\s*\(\s*['\"]([^'\"]+)['\"]", "file"),
    (r"pd\.read_csv\s*\(\s*['\"]([^'\"]+)['\"]", "file"),
    (r"spark\.read\.(?:parquet|csv|table)\s*\(\s*['\"]([^'\"]+)['\"]", "table"),
]
WRITE_PATTERNS = [
    (r"\.to_csv\s*\(\s*['\"]([^'\"]+)['\"]", "file"),
    (r"\.to_parquet\s*\(\s*['\"]([^'\"]+)['\"]", "file"),
    (r"\.write\.(?:parquet|csv|saveAsTable)\s*\(\s*['\"]([^'\"]+)['\"]", "file"),
    (r"\.write\.saveAsTable\s*\(\s*['\"]([^'\"]+)['\"]", "table"),
]


class PythonDataFlowAnalyzer:
    """Extract dataset read/write from Python source (string patterns)."""

    def __init__(self, repo_root: pathlib.Path) -> None:
        self.repo_root = pathlib.Path(repo_root)

    def extract_from_file(self, path: pathlib.Path) -> List[TransformationNode]:
        """Return transformation nodes for reads/writes found in file."""
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            log.warning("Could not read %s: %s", path, e)
            return []
        rel = str(path.relative_to(self.repo_root))
        sources: set[str] = set()
        targets: set[str] = set()
        for pattern, _ in READ_PATTERNS:
            for m in re.finditer(pattern, source):
                sources.add(m.group(1))
        for pattern, _ in WRITE_PATTERNS:
            for m in re.finditer(pattern, source):
                targets.add(m.group(1))
        if not sources and not targets:
            return []
        nodes: List[TransformationNode] = []
        nodes.append(
            TransformationNode(
                id=f"{rel}:python_data_flow",
                source_datasets=sorted(sources),
                target_datasets=sorted(targets),
                transformation_type="python",
                source_file=rel,
            )
        )
        return nodes

    def run(self, changed_paths: Optional[set[str]] = None) -> List[TransformationNode]:
        out: List[TransformationNode] = []
        for path in self.repo_root.rglob("*.py"):
            if ".git" in path.parts or ".cartography" in path.parts:
                continue
            rel = str(path.relative_to(self.repo_root))
            if changed_paths is not None and rel not in changed_paths:
                continue
            try:
                out.extend(self.extract_from_file(path))
            except Exception as e:
                log.warning("Python data-flow skip %s: %s", path, e)
        return out
