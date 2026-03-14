"""
Archivist agent: CODEBASE.md, onboarding_brief.md, cartography_trace.jsonl, semantic_index.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from typing import Any, Optional

from ..graph.knowledge_graph import KnowledgeGraph


def _trace_entry(agent: str, action: str, evidence: str, confidence: str = "high") -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "action": action,
        "evidence": evidence,
        "confidence": confidence,
    }


class Archivist:
    """Produces living artifacts and trace log."""

    def __init__(
        self,
        repo_root: pathlib.Path,
        knowledge_graph: KnowledgeGraph,
        semanticist_purposes: Optional[dict[str, str]] = None,
        semanticist_drift: Optional[dict[str, bool]] = None,
        day_one_answers: Optional[dict[str, Any]] = None,
    ) -> None:
        self.repo_root = pathlib.Path(repo_root)
        self.kg = knowledge_graph
        self.purpose_statements = semanticist_purposes or {}
        self.doc_drift = semanticist_drift or {}
        self.day_one_answers = day_one_answers or {}
        self.trace_entries: list[dict] = []

    def log(self, agent: str, action: str, evidence: str, confidence: str = "high") -> None:
        self.trace_entries.append(_trace_entry(agent, action, evidence, confidence))

    def generate_CODEBASE_md(self) -> str:
        """Living context file for AI coding agents."""
        mg = self.kg.to_module_graph_dict()
        nodes = mg.get("nodes", [])
        edges = mg.get("edges", [])
        high_velocity = mg.get("high_velocity_files", [])[:10]
        pr = self.kg.pagerank_modules()
        top_modules = sorted(pr.keys(), key=lambda x: -pr.get(x, 0))[:5]
        sources = self.kg.find_sources()
        sinks = self.kg.find_sinks()
        scc = self.kg.strongly_connected_components()
        circular = [list(c) for c in scc if len(c) > 1]
        drift_files = [p for p, d in self.doc_drift.items() if d]

        sections = [
            "# CODEBASE.md — Living context",
            "",
            "## Architecture Overview",
            f"This codebase has {len(nodes)} modules and {len(edges)} import edges. "
            "The Cartographer pipeline (Surveyor → Hydrologist → Semanticist → Archivist) produced this file. "
            "Primary entry: CLI; orchestration and graph storage are central.",
            "",
            "## Critical Path (top 5 modules by PageRank)",
        ]
        for i, m in enumerate(top_modules, 1):
            purpose = self.purpose_statements.get(m, self.kg.module_graph.nodes[m].get("purpose_statement", ""))
            sections.append(f"{i}. **{m}** — {purpose[:120] or '(no purpose)'}...")
        sections.extend([
            "",
            "## Data Sources & Sinks",
            f"- **Sources (in-degree 0):** {sources[:20]}",
            f"- **Sinks (out-degree 0):** {sinks[:20]}",
            "",
            "## Known Debt",
            f"- **Circular dependencies:** {circular[:10]}",
            f"- **Documentation drift (docstring vs implementation):** {drift_files[:15]}",
            "",
            "## High-Velocity Files (likely pain points)",
        ])
        for f in high_velocity[:15]:
            sections.append(f"- {f}")
        sections.extend([
            "",
            "## Module Purpose Index",
            "",
        ])
        for n in nodes[:80]:
            path = n.get("id", "")
            purpose = self.purpose_statements.get(path, n.get("purpose_statement", ""))
            if purpose:
                sections.append(f"- **{path}**: {purpose[:200]}")
        sections.append("")
        return "\n".join(sections)

    def generate_onboarding_brief_md(self) -> str:
        """Day-One brief: five FDE questions with evidence."""
        lines = ["# Onboarding Brief — FDE Day-One Answers", ""]
        q_labels = {
            "1": "What is the primary data ingestion path?",
            "2": "What are the 3-5 most critical output datasets/endpoints?",
            "3": "What is the blast radius if the most critical module fails?",
            "4": "Where is the business logic concentrated vs. distributed?",
            "5": "What has changed most frequently in the last 90 days (git velocity)?",
        }
        for key in ["1", "2", "3", "4", "5"]:
            lines.append(f"## {key}. {q_labels.get(key, key)}")
            block = self.day_one_answers.get(key)
            if isinstance(block, dict):
                lines.append(block.get("answer", ""))
                lines.append(f"\n*Evidence:* {block.get('evidence', '')}")
            else:
                lines.append(str(block))
            lines.append("")
        return "\n".join(lines)

    def write_artifacts(self, cartography_dir: pathlib.Path) -> None:
        """Write CODEBASE.md, onboarding_brief.md, cartography_trace.jsonl, semantic_index."""
        cartography_dir = pathlib.Path(cartography_dir)
        cartography_dir.mkdir(parents=True, exist_ok=True)

        codebase_path = cartography_dir / "CODEBASE.md"
        codebase_path.write_text(self.generate_CODEBASE_md(), encoding="utf-8")
        self.log("archivist", "write_CODEBASE_md", str(codebase_path))

        brief_path = cartography_dir / "onboarding_brief.md"
        brief_path.write_text(self.generate_onboarding_brief_md(), encoding="utf-8")
        self.log("archivist", "write_onboarding_brief", str(brief_path))

        trace_path = cartography_dir / "cartography_trace.jsonl"
        with trace_path.open("a", encoding="utf-8") as f:
            for e in self.trace_entries:
                f.write(json.dumps(e, default=str) + "\n")
        self.log("archivist", "write_trace", str(trace_path))

        index_path = cartography_dir / "semantic_index"
        index_path.mkdir(exist_ok=True)
        index_file = index_path / "purpose_index.json"
        index_file.write_text(json.dumps(self.purpose_statements, indent=2), encoding="utf-8")
        self.log("archivist", "write_semantic_index", str(index_file))
