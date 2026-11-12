MODEL (
  name bronze.wpi,
  kind FULL,
  audits (
    not_null(columns := (measure, index_code, sector, industry, tsest, region, time_period, obs_value)),
    accepted_range(column := obs_value, min_v := -20, max_v := 300)
  )
);

SELECT
  measure::VARCHAR AS measure,
  index::VARCHAR AS index_code,
  sector::VARCHAR AS sector,
  industry::VARCHAR AS industry,
  tsest::VARCHAR AS tsest,
  region::VARCHAR AS region,
  time_period::VARCHAR AS time_period,
  obs_value::DOUBLE AS obs_value,
  'total' AS slice
FROM read_csv('data/snapshot/wpi_total.csv.gz', header = true)
UNION ALL
SELECT
  measure::VARCHAR AS measure,
  index::VARCHAR AS index_code,
  sector::VARCHAR AS sector,
  industry::VARCHAR AS industry,
  tsest::VARCHAR AS tsest,
  region::VARCHAR AS region,
  time_period::VARCHAR AS time_period,
  obs_value::DOUBLE AS obs_value,
  'industry' AS slice
FROM read_csv('data/snapshot/wpi_industry.csv.gz', header = true)
