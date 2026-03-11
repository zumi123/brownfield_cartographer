-- Sample SQL for lineage extraction (interim demo).
-- In a real dbt project this would be in models/.
SELECT
  a.id,
  a.name,
  b.amount
FROM raw.customers a
LEFT JOIN raw.orders b ON a.id = b.customer_id;
