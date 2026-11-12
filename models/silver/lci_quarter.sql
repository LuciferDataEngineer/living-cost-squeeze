MODEL (
  name silver.lci_quarter,
  kind FULL,
  audits (
    unique_combination_of_columns(columns := (time_period, household_type, index_code)),
    not_null(columns := (time_period, household_type, index_code))
  )
);

SELECT
  time_period,
  household_type,
  index_code,
  MAX(CASE WHEN measure = '1' THEN obs_value END) AS index_level,
  MAX(CASE WHEN measure = '2' THEN obs_value END) AS qoq_pct,
  MAX(CASE WHEN measure = '3' THEN obs_value END) AS yoy_pct,
  MAX(CASE WHEN measure = '4' THEN obs_value END) AS contribution_points,
  MAX(CASE WHEN measure = '5' THEN obs_value END) AS contribution_change
FROM bronze.lci
GROUP BY time_period, household_type, index_code
