MODEL (
  name bronze.lci,
  kind FULL,
  audits (
    not_null(columns := (measure, index_code, household_type, time_period, obs_value)),
    accepted_range(column := obs_value, min_v := -40, max_v := 400)
  )
);

SELECT
  measure::VARCHAR AS measure,
  index::VARCHAR AS index_code,
  houshold_type::VARCHAR AS household_type,
  region::VARCHAR AS region,
  time_period::VARCHAR AS time_period,
  obs_value::DOUBLE AS obs_value,
  unit_measure::VARCHAR AS unit_measure,
  'levels_and_changes' AS extract
FROM read_csv('data/snapshot/lci.csv.gz', header = true, union_by_name = true)
UNION ALL
SELECT
  measure::VARCHAR AS measure,
  index::VARCHAR AS index_code,
  houshold_type::VARCHAR AS household_type,
  region::VARCHAR AS region,
  time_period::VARCHAR AS time_period,
  obs_value::DOUBLE AS obs_value,
  unit_measure::VARCHAR AS unit_measure,
  'contribution_change' AS extract
FROM read_csv('data/snapshot/lci_contribution.csv.gz', header = true, union_by_name = true)
