# Interim Report — The Brownfield Cartographer

**Submission:** Interim — Thursday March 12, 03:00 UTC  
**Target:** This repository (brownfield_cartographer) as primary; optional second target: dbt jaffle_shop or mitodl/ol-data-platform.

---

## 1. RECONNAISSANCE.md content

The manual Day-One analysis is in **RECONNAISSANCE.md**. Summary:

- **Primary “ingestion”:** Repo path → file discovery → AST/config parsing (no classical data ingestion).
- **Critical outputs:** `.cartography/module_graph.json`, `.cartography/lineage_graph.json` (and planned CODEBASE.md, onboarding brief, trace).
- **Blast radius:** Orchestrator and knowledge_graph are single points of failure; agents are isolated.
- **Logic:** Concentrated in `knowledge_graph.py` and `orchestrator.py`; distributed across analyzers and agents.
- **Velocity:** Core pipeline and analyzers expected to change most; models and CLI less so.

---

## 2. Architecture diagram — four-agent pipeline (data flow)

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                     CLI (src/cli.py)                       │
                    │              cartographer <path|url>                     │
                    └───────────────────────────┬─────────────────────────────┘
                                                │
                                                ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │              Orchestrator (src/orchestrator.py)          │
                    │  _ensure_local_repo() → run_analyze()                    │
                    └───────┬─────────────────────────────────┬───────────────┘
                            │                                 │
                            ▼                                 ▼
    ┌───────────────────────────────────┐     ┌───────────────────────────────────┐
    │  Agent 1: Surveyor                │     │  Agent 2: Hydrologist              │
    │  (src/agents/surveyor.py)          │     │  (src/agents/hydrologist.py)       │
    │  • TreeSitterAnalyzer (imports)    │     │  • SQLLineageAnalyzer             │
    │  • Git velocity, dead-code flags   │     │  • DAGConfigAnalyzer               │
    │  • add_module, add_import_edge     │     │  • add_transformation             │
    └───────────────┬───────────────────┘     └───────────────┬───────────────────┘
                    │                                         │
                    │     ┌───────────────────────────────┐    │
                    └────►│   KnowledgeGraph              │◄───┘
                          │   (src/graph/knowledge_graph) │
                          │   • module_graph (NetworkX)   │
                          │   • lineage_graph (NetworkX) │
                          │   • PageRank, blast_radius    │
                          └───────────────┬───────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │  .cartography/                                         │
                    │  • module_graph.json   (nodes, edges, pagerank)         │
                    │  • lineage_graph.json  (datasets, transformations)     │
                    └─────────────────────────────────────────────────────────┘

    (Planned: Semanticist → purpose statements, Day-One answers; Archivist → CODEBASE.md, trace;
     Navigator → query tools.)
```

**Data flow:** CLI passes repo path to Orchestrator. Orchestrator creates KnowledgeGraph, runs Surveyor (feeds module graph), then Hydrologist (feeds lineage graph). Orchestrator serializes both graphs to `.cartography/`.

---

## 3. Progress summary

**Working:**

- **CLI:** Entry point; accepts local path or GitHub URL; runs full analyze pipeline.
- **Orchestrator:** Wires Surveyor → Hydrologist; writes `module_graph.json` and `lineage_graph.json` to `.cartography/`.
- **Models:** Pydantic schemas for ModuleNode, DatasetNode, FunctionNode, TransformationNode, EdgeTypes in `src/models/schema.py`.
- **Tree-sitter analyzer:** LanguageRouter (Python, SQL, YAML); `extract_python_imports()` with relative-import resolution; `extract_python_public_symbols()`; `parse_file()`.
- **SQL lineage:** sqlglot-based extraction from `.sql` files; table dependencies from SELECT/FROM/JOIN; multiple dialects; fallback for plain SELECTs.
- **DAG config parser:** YAML load; dbt schema.yml and Airflow-style DAG parsing; emits TransformationNodes.
- **Surveyor:** Module graph from Python imports (relative and absolute); git velocity per file; dead-code candidates (never-imported modules); PageRank (with fallback if no numpy).
- **Hydrologist:** DataLineageGraph from SQL + YAML; blast_radius(node, direction); find_sources() / find_sinks(); lineage serialization.
- **Knowledge graph:** NetworkX module_graph and lineage_graph; JSON serialization; PageRank and SCC for modules.
- **Cartography artifacts:** At least one target (this repo) produces `.cartography/module_graph.json` and `.cartography/lineage_graph.json`.

**In progress / partial:**

- **Lineage completeness:** Only SQL and YAML are ingested; Python data-flow (pandas read/write, PySpark, etc.) is not yet implemented.
- **dbt ref() in SQL:** dbt’s `ref('model_name')` in SQL is not specially resolved; we rely on table names from sqlglot.
- **Incremental update:** Re-analyzing only changed files (git diff) is not implemented.

---

## 4. Early accuracy observations

- **Module graph:** Matches manual inspection: all relevant `src/**/*.py` files appear; edges match import structure (orchestrator → surveyor, hydrologist, knowledge_graph; cli → orchestrator; analyzers/__init__ → analyzers; models/__init__ → schema; graph/__init__ → knowledge_graph). Relative imports (e.g. `..analyzers.tree_sitter_analyzer`) are resolved after fixing multi-dot relative handling.
- **Lineage graph:** For `sample_lineage/models/sample.sql`, the graph shows one transformation node with sources `raw.customers` and `raw.orders`, and CONSUMES edges from those datasets to the transformation. This matches the SQL. No target dataset is set for SELECT-only statements in the current fallback (acceptable for interim).
- **PageRank:** With edges present, PageRank would highlight frequently imported modules; current run may use uniform fallback if numpy/scipy are missing in the environment.

---

## 5. Known gaps and plan for final submission

**Gaps:**

- Semanticist agent (LLM purpose statements, doc drift, domain clustering, Day-One answers) not implemented.
- Archivist agent (CODEBASE.md, onboarding_brief.md, cartography_trace.jsonl) not implemented.
- Navigator agent and query interface (find_implementation, trace_lineage, blast_radius, explain_module) not implemented.
- Python data-flow extraction (pandas, PySpark, SQLAlchemy) in Hydrologist not implemented.
- Incremental update (re-analyze only changed files) not implemented.
- Second target codebase (e.g. jaffle_shop or ol-data-platform) not yet run and documented.

**Plan for final:**

- Implement Semanticist (with context-window budget and cheap model for bulk) and Archivist (CODEBASE.md, onboarding brief, trace).
- Implement Navigator LangGraph agent with the four tools and evidence citations.
- Add Python data-flow patterns to Hydrologist.
- Run Cartographer on a second real target (jaffle_shop or ol-data-platform), compare to manual RECON and document accuracy.
- Add incremental mode using `git diff` and optional “since” ref.
- Produce final PDF report and video demo per rubric.

---

*This interim report is intended for inclusion in the single PDF required for the interim submission (RECONNAISSANCE content, architecture diagram, progress summary, early accuracy, known gaps and plan).*
