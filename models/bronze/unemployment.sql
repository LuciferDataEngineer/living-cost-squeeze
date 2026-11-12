MODEL (
  name bronze.unemployment,
  kind FULL,
  audits (
    not_null(columns := (region, month, rate)),
    accepted_range(column := rate, min_v := 0, max_v := 25)
  )
);

SELECT
  region::VARCHAR AS region,
  time_period::VARCHAR AS month,
  obs_value::DOUBLE AS rate
FROM read_csv('data/snapshot/unemployment.csv.gz', header = true)
WHERE measure = 'M13' AND sex = '3' AND age = '1599' AND tsest = '20'
