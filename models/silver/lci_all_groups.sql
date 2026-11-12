MODEL (
  name silver.lci_all_groups,
  kind FULL,
  audits (not_null(columns := (time_period, household_type, lci_index)))
);

SELECT
  time_period,
  household_type,
  index_level AS lci_index,
  yoy_pct AS lci_yoy
FROM silver.lci_quarter
WHERE index_code = '10001' AND index_level IS NOT NULL
