MODEL (
  name bronze.lci_weights,
  kind FULL,
  audits (
    not_null(columns := (household_type, index_code, time_period, weight_pct)),
    accepted_range(column := weight_pct, min_v := 0, max_v := 100)
  )
);

SELECT
  houshold_type::VARCHAR AS household_type,
  index::VARCHAR AS index_code,
  time_period::VARCHAR AS time_period,
  obs_value::DOUBLE AS weight_pct
FROM read_csv('data/snapshot/lci_weights.csv.gz', header = true)
