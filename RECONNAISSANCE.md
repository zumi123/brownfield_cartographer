# RECONNAISSANCE — Manual Day-One Analysis

**Target:** This repository (brownfield_cartographer) — interim primary target.  
**Date:** March 2025 (interim submission).  
**Time spent:** ~30 minutes manual exploration.

---

## 1. What is the primary data ingestion path?

This repo is the Cartographer tool itself, not a data platform. There is no classical “ingestion” pipeline. The only data inputs are:

- **Repository files** (Python, SQL, YAML) discovered by the Surveyor and Hydrologist by walking the repo and parsing with tree-sitter / sqlglot.
- **Git history** (optional) used by the Surveyor for change velocity per file.

So the “primary ingestion path” is: **local or cloned repo path → `run_analyze()` → file discovery → AST/config parsing.**

---

## 2. What are the 3–5 most critical output datasets/endpoints?

Again, the repo is a tool, not a data product. The main **outputs** are:

1. **`.cartography/module_graph.json`** — module (file) nodes and import edges; used for PageRank, dead-code candidates, and structural overview.
2. **`.cartography/lineage_graph.json`** — dataset and transformation nodes from SQL and YAML (dbt/Airflow-style) config; used for lineage and blast-radius queries.
3. **(Planned)** CODEBASE.md, onboarding_brief.md, semantic index, cartography_trace.jsonl.

The “critical path” in the tool is: **CLI → orchestrator → Surveyor (module graph) → Hydrologist (lineage) → write JSONs.**

---

## 3. What is the blast radius if the most critical module fails?

If **`src/orchestrator.py`** is broken or removed:

- No analysis runs: the CLI calls `run_analyze()` only through the orchestrator. **Blast radius: entire pipeline.**

If **`src/graph/knowledge_graph.py`** is broken:

- Surveyor and Hydrologist both depend on it. No module graph or lineage graph can be built or serialized. **Blast radius: full pipeline.**

If **`src/agents/surveyor.py`** or **`src/agents/hydrologist.py`** is broken:

- Only that agent’s output is missing; the other still runs. Lineage can exist without the module graph and vice versa. **Blast radius: one agent’s outputs.**

---

## 4. Where is the business logic concentrated vs. distributed?

- **Concentrated:**  
  - **`src/graph/knowledge_graph.py`** — single place for module graph, lineage graph, PageRank, blast_radius, find_sources/find_sinks.  
  - **`src/orchestrator.py`** — single place that wires Surveyor → Hydrologist and writes artifacts.

- **Distributed:**  
  - **Parsing and extraction** are split by concern: `src/analyzers/tree_sitter_analyzer.py` (AST, imports), `src/analyzers/sql_lineage.py` (SQL tables), `src/analyzers/dag_config_parser.py` (YAML/dbt/Airflow).  
  - **Agents** are thin: Surveyor and Hydrologist mostly orchestrate analyzers and feed the knowledge graph.

---

## 5. What has changed most frequently in the last 90 days (git velocity)?

Without running `git log --follow` per file, a reasonable guess for a newly built repo:

- **High velocity:** `src/orchestrator.py`, `src/agents/surveyor.py`, `src/agents/hydrologist.py`, `src/graph/knowledge_graph.py`, `src/analyzers/*.py` — core pipeline and analyzers.
- **Lower velocity:** `src/models/schema.py`, `src/cli.py`, `README.md` — structure and entry point, touched when adding features or docs.

The Surveyor’s `_attach_git_velocity()` is intended to fill this with real commit counts per file (e.g. last 30 days).

---

## What was hardest to figure out manually?

- **Import structure:** Which files depend on which (e.g. relative vs absolute imports) required reading several files. The Cartographer’s module graph automates this.
- **Lineage:** There is only one sample SQL file (`sample_lineage/models/sample.sql`). Confirming “raw.customers” and “raw.orders” as sources was trivial by eye; in a large dbt/Airflow repo this would be painful without a lineage graph.
- **Blast radius:** Reasoning about “if X breaks, what fails” without a dependency graph is tedious; the tool’s blast_radius and lineage graph are meant to answer this directly.

---

## Where did I get lost?

- Not “lost,” but the **boundary between “data platform” and “tool that analyzes code”** had to be clarified: this repo is the latter, so Day-One answers are framed in terms of “inputs to the tool” and “outputs of the tool” rather than classic ingestion/marts.

---

## Ground truth for interim validation

- **Module graph:** Should contain all `src/**/*.py` (excluding venv) and edges for internal imports (e.g. orchestrator → surveyor, hydrologist, knowledge_graph).
- **Lineage graph:** Should contain at least one transformation node from `sample_lineage/models/sample.sql` with sources `raw.customers` and `raw.orders`.
- **PageRank:** High on nodes that are imported by many others (e.g. `knowledge_graph`, `schema`); may be fallback uniform if numpy/scipy are not installed.
- **Dead code candidates:** Modules that are never imported by others (e.g. `cli.py` if nothing imports it, or leaf packages).

This RECONNAISSANCE serves as the manual baseline to compare against the Cartographer’s generated outputs in the interim report.
