# Onboarding Brief — FDE Day-One Answers

## 1. What is the primary data ingestion path?
The primary data ingestion path can be inferred from the data sources with an in-degree of 0. These sources, which are the beginning of the lineage graph, come from dbt project configurations and staging model schemas.

*Evidence:* ['dbt_project.yml:jaffle_shop', 'models/schema.yml:customers', 'models/schema.yml:orders', 'models/staging/schema.yml:stg_customers', 'models/staging/schema.yml:stg_orders', 'models/staging/schema.yml:stg_payments']

## 2. What are the 3-5 most critical output datasets/endpoints?
The most critical output datasets/endpoints are the data sinks, as they represent the final transformed data. These output datasets are `jaffle_shop`, `customers`, `orders`, `stg_customers`, `stg_orders`, and `stg_payments`.

*Evidence:* ['jaffle_shop', 'customers', 'orders', 'stg_customers', 'stg_orders', 'stg_payments']

## 3. What is the blast radius if the most critical module fails?
The blast radius if the most critical module fails is difficult to assess without knowing which module is considered the most critical. However, if one of the staging models (e.g., `stg_customers`) fails, it will impact the downstream models that depend on it.

*Evidence:* Needs further analysis to identify dependencies of each module; based on the listed sources, the failure of `stg_customers` would impact the 'customers' sink.

## 4. Where is the business logic concentrated vs. distributed?
Without specific details on the code within each file, it's difficult to pinpoint where the business logic is concentrated. It's likely distributed between the staging models for data cleaning and transformation, and the final models for aggregations and business-specific calculations.

*Evidence:* Inferred from file paths; business logic would likely involve calculations in the `models` directory rather than `models/staging`.

## 5. What has changed most frequently in the last 90 days (git velocity)?
The data provided does not include information about git velocity or file change frequency. Therefore, I cannot determine which files have changed most frequently in the last 90 days.

*Evidence:* No 'High-velocity files' present; empty list indicates no velocity information.
