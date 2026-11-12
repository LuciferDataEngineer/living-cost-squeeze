MODEL (
  name bronze.cpi,
  kind FULL,
  audits (
    not_null(columns := (region, time_period, index_level)),
    accepted_range(column := index_level, min_v := 20, max_v := 250)
  )
);

SELECT
  region::VARCHAR AS region,
  tsest::VARCHAR AS tsest,
  time_period::VARCHAR AS time_period,
  obs_value::DOUBLE AS index_level
FROM read_csv('data/snapshot/cpi.csv.gz', header = true)
WHERE measure = '1' AND index = '10001' AND tsest = '10'
