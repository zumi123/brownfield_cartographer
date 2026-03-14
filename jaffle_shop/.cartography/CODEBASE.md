# CODEBASE.md — Living context

## Architecture Overview
This codebase has 0 modules and 0 import edges. The Cartographer pipeline (Surveyor → Hydrologist → Semanticist → Archivist) produced this file. Primary entry: CLI; orchestration and graph storage are central.

## Critical Path (top 5 modules by PageRank)

## Data Sources & Sinks
- **Sources (in-degree 0):** ['dbt_project.yml:jaffle_shop', 'models/schema.yml:customers', 'models/schema.yml:orders', 'models/staging/schema.yml:stg_customers', 'models/staging/schema.yml:stg_orders', 'models/staging/schema.yml:stg_payments']
- **Sinks (out-degree 0):** ['jaffle_shop', 'customers', 'orders', 'stg_customers', 'stg_orders', 'stg_payments']

## Known Debt
- **Circular dependencies:** []
- **Documentation drift (docstring vs implementation):** []

## High-Velocity Files (likely pain points)

## Module Purpose Index

