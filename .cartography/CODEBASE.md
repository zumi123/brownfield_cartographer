# CODEBASE.md — Living context

## Architecture Overview
This codebase has 19 modules and 35 import edges. The Cartographer pipeline (Surveyor → Hydrologist → Semanticist → Archivist) produced this file. Primary entry: CLI; orchestration and graph storage are central.

## Critical Path (top 5 modules by PageRank)
1. **app_ui.py** — Entry script: app_ui.py (skipped for LLM)....
2. **src/orchestrator.py** — The module orchestrates a full code analysis pipeline, utilizing agents to survey, understand dependencies, extract sema...
3. **src/agents/navigator.py** — The `Navigator` module enables querying a codebase's structure and lineage using a knowledge graph. It provides tools to...
4. **src/graph/knowledge_graph.py** — This module defines the KnowledgeGraph class, which stores and manages two directed graphs: a module import graph and a ...
5. **src/agents/archivist.py** — The `Archivist` class generates living artifacts like `CODEBASE.md` and `onboarding_brief.md` to document the codebase's...

## Data Sources & Sinks
- **Sources (in-degree 0):** ['raw.customers', 'raw.orders', 'file.csv', 'file.parquet', 'postgres:///db_name', 'venv/lib/python3.13/site-packages/pandas/core/generic.py:python_data_flow', 'doesnt_exist', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_gcs.py:python_data_flow', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_http_headers.py:python_data_flow', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_parquet.py:python_data_flow', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_compression.py:python_data_flow', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_fsspec.py:python_data_flow', 'test', 'venv/lib/python3.13/site-packages/pandas/tests/io/parser/test_network.py:python_data_flow', 'test_file.zip']
- **Sinks (out-degree 0):** ['sample_lineage/models/sample.sql', 'venv/lib/python3.13/site-packages/narwhals/functions.py:python_data_flow', 'venv/lib/python3.13/site-packages/narwhals/_typing.py:python_data_flow', 'venv/lib/python3.13/site-packages/narwhals/stable/v2/__init__.py:python_data_flow', 'venv/lib/python3.13/site-packages/pandas/io/sql.py:python_data_flow', 'folder/subfolder/out.csv', 'out.csv', 'out.zip', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_common.py:python_data_flow', 'gs://test/test.csv', '/tmp/junk.parquet', 'memory://fastparquet_user_agent.parquet', '~/file.parquet', 'memory://test/test.csv', 'nonfsspecpath', 'testmem://test/test.csv', 'venv/lib/python3.13/site-packages/pandas/tests/io/parser/test_unsupported.py:python_data_flow', 's3://an_s3_bucket_data_doesnt_exit/not_real.csv', 's3://an_s3_bucket_data_doesnt_exit/not_real.parquet', 'venv/lib/python3.13/site-packages/pandas/tests/io/parser/test_compression.py:python_data_flow']

## Known Debt
- **Circular dependencies:** []
- **Documentation drift (docstring vs implementation):** ['src/orchestrator.py', 'src/agents/navigator.py', 'src/graph/knowledge_graph.py', 'src/agents/archivist.py', 'src/agents/hydrologist.py', 'src/agents/semanticist.py', 'src/agents/surveyor.py', 'src/cli.py', 'src/analyzers/tree_sitter_analyzer.py', 'src/models/schema.py', 'src/analyzers/dag_config_parser.py', 'src/analyzers/python_data_flow.py', 'src/analyzers/sql_lineage.py', 'src/analyzers/__init__.py', 'src/models/__init__.py']

## High-Velocity Files (likely pain points)
- src/orchestrator.py
- src/graph/knowledge_graph.py
- src/agents/hydrologist.py
- src/agents/surveyor.py
- src/cli.py
- src/analyzers/tree_sitter_analyzer.py
- src/models/schema.py
- src/analyzers/sql_lineage.py
- src/analyzers/__init__.py
- src/__init__.py

## Module Purpose Index

- **app_ui.py**: Entry script: app_ui.py (skipped for LLM).
- **src/orchestrator.py**: The module orchestrates a full code analysis pipeline, utilizing agents to survey, understand dependencies, extract semantics, and generate documentation. It supports incremental analysis by re-analyz
- **src/agents/navigator.py**: The `Navigator` module enables querying a codebase's structure and lineage using a knowledge graph. It provides tools to find implementations, trace data lineage, assess the impact of changes, and exp
- **src/graph/knowledge_graph.py**: This module defines the KnowledgeGraph class, which stores and manages two directed graphs: a module import graph and a data lineage graph. It provides methods to add nodes and edges to these graphs, 
- **src/agents/archivist.py**: The `Archivist` class generates living artifacts like `CODEBASE.md` and `onboarding_brief.md` to document the codebase's architecture and answer key onboarding questions. It also maintains a trace log
- **src/agents/hydrologist.py**: The module performs data flow and lineage analysis on a code repository. It extracts data transformations from SQL, DAG configuration files, and Python code to build a knowledge graph representing dat
- **src/agents/semanticist.py**: The `semanticist` module leverages LLMs to extract purpose statements from code, cluster code into domains, and answer high-level "Day-One" questions about the code base. It intelligently manages API 
- **src/agents/surveyor.py**: The `Surveyor` analyzes Python code in a Git repository to build a module import graph. It identifies potential dead code, calculates change velocity using Git history, and stores this information in 
- **src/cli.py**: The module defines a command-line interface for the Brownfield Cartographer tool. It allows users to analyze a codebase and subsequently query the generated Cartography artifacts.
- **src/__init__.py**: The `src` module serves as the root package for the Brownfield Cartographer application. It likely organizes and encapsulates the application's submodules and functionalities related to mapping and ma
- **src/analyzers/tree_sitter_analyzer.py**: The module provides language-agnostic AST parsing using tree-sitter to extract information from source code files. Specifically, it extracts imports and public symbols (functions, classes) from Python
- **src/models/schema.py**: This module defines the schema for representing code artifacts, datasets, and their relationships in a data lineage graph. It includes Pydantic models for different node types (modules, datasets, func
- **src/agents/__init__.py**: This module exposes a collection of agent classes. These agents appear to be specialized for tasks like content archiving, hydrological analysis, navigation, semantic understanding, and surveying.
- **src/analyzers/dag_config_parser.py**: The module parses Airflow DAG and dbt schema YAML files to extract pipeline topology and model/table references. It identifies dependencies and creates transformation nodes representing the data pipel
- **src/analyzers/python_data_flow.py**: The module analyzes Python code to extract data flow information. It identifies read and write operations on datasets (files, tables) based on regular expression patterns.
- **src/analyzers/sql_lineage.py**: The module extracts data lineage from SQL files by parsing them and identifying source and target tables. It supports various SQL dialects (PostgreSQL, BigQuery, Snowflake, DuckDB) and handles dbt `re
- **src/graph/__init__.py**: The module defines the graph subpackage. It exposes the `KnowledgeGraph` class, likely representing a knowledge graph data structure.
- **src/analyzers/__init__.py**: The module exposes several code analyzers. These analyzers are used for static code analysis, including DAG configuration parsing, Python data flow analysis, SQL lineage extraction, and generic code a
- **src/models/__init__.py**: This module defines the data structures (schemas) for representing nodes and edges in a computational graph. It includes node types such as datasets, functions, modules, and transformations, as well a
