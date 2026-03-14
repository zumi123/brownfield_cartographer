# Onboarding Brief — FDE Day-One Answers

## 1. What is the primary data ingestion path?
Based on the data sources, the primary data ingestion paths are quite diverse, including raw data represented by 'raw.customers' and 'raw.orders', file-based ingestion through 'file.csv' and 'file.parquet', a Postgres database connection 'postgres:///db_name', and other sources like zip files and pandas data flows. There also seems to be a data source that doesn't exist: `doesnt_exist`.

*Evidence:* ['raw.customers', 'raw.orders', 'file.csv', 'file.parquet', 'postgres:///db_name', 'venv/lib/python3.13/site-packages/pandas/core/generic.py:python_data_flow', 'doesnt_exist', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_gcs.py:python_data_flow', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_http_headers.py:python_data_flow', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_parquet.py:python_data_flow', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_compression.py:python_data_flow', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_fsspec.py:python_data_flow', 'test', 'venv/lib/python3.13/site-packages/pandas/tests/io/parser/test_network.py:python_data_flow', 'test_file.zip']

## 2. What are the 3-5 most critical output datasets/endpoints?
The most critical output datasets/endpoints appear to be 'sample_lineage/models/sample.sql', 'folder/subfolder/out.csv', 'out.csv', and 'gs://test/test.csv'. These represent SQL models, CSV files in various locations (local and cloud), suggesting they are important results of processing the data. Other outputs include parquet files stored locally and within memory.

*Evidence:* ['sample_lineage/models/sample.sql', 'venv/lib/python3.13/site-packages/narwhals/functions.py:python_data_flow', 'venv/lib/python3.13/site-packages/narwhals/_typing.py:python_data_flow', 'venv/lib/python3.13/site-packages/narwhals/stable/v2/__init__.py:python_data_flow', 'venv/lib/python3.13/site-packages/pandas/io/sql.py:python_data_flow', 'folder/subfolder/out.csv', 'out.csv', 'out.zip', 'venv/lib/python3.13/site-packages/pandas/tests/io/test_common.py:python_data_flow', 'gs://test/test.csv', '/tmp/junk.parquet', 'memory://fastparquet_user_agent.parquet', '~/file.parquet', 'memory://test/test.csv', 'nonfsspecpath']

## 3. What is the blast radius if the most critical module fails?
Based on the purpose statements, `src/orchestrator.py` is a critical module. If it fails, the blast radius is significant as it orchestrates the entire code analysis pipeline. This encompasses dependency analysis, semantic extraction, documentation generation, and the creation of code understanding artifacts like module graphs and semantic indices.

*Evidence:* src/orchestrator.py': "The module orchestrates a full code analysis pipeline, utilizing agents to survey, understand dependencies, extract semantics, and generate documentation. It supports incremental analysis by re-analyzing only the changed files, and it produces various code understanding artifacts such as module graphs and semantic indices."

## 4. Where is the business logic concentrated vs. distributed?
Business logic appears concentrated in modules like `src/orchestrator.py`, which controls the overall analysis workflow, and likely within the analyzer modules (`src/analyzers/*`, e.g., `src/analyzers/sql_lineage.py`). It is also distributed within the agents (`src/agents/*`) responsible to survey the code and understand dependencies.

*Evidence:* ['src/orchestrator.py', 'src/agents/hydrologist.py', 'src/agents/surveyor.py', 'src/analyzers/tree_sitter_analyzer.py', 'src/analyzers/sql_lineage.py']

## 5. What has changed most frequently in the last 90 days (git velocity)?
The files that have changed most frequently are provided as 'High-velocity files'. These include core components like `src/orchestrator.py`, `src/graph/knowledge_graph.py`, agent modules (`src/agents/*`), analyzer modules (`src/analyzers/*`), the CLI entry point (`src/cli.py`), and the `src/models/schema.py` file, which likely defines data structures related to the analysis results. This suggests a focus on enhancing and refining the core code analysis pipeline and its data representation.

*Evidence:* High-velocity files: ['src/orchestrator.py', 'src/graph/knowledge_graph.py', 'src/agents/hydrologist.py', 'src/agents/surveyor.py', 'src/cli.py', 'src/analyzers/tree_sitter_analyzer.py', 'src/models/schema.py', 'src/analyzers/sql_lineage.py', 'src/analyzers/__init__.py', 'src/__init__.py'].
