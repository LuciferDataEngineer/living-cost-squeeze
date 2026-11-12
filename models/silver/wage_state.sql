MODEL (
  name silver.wage_state,
  kind FULL,
  audits (not_null(columns := (time_period, state_code, wage_yoy)))
);

-- States are published original, not seasonally adjusted, in this extract.
SELECT
  time_period,
  region AS state_code,
  obs_value AS wage_yoy
FROM bronze.wpi
WHERE
  measure = '3'
  AND index_code = 'THRPEB'
  AND sector = '7'
  AND industry = 'TOT'
  AND tsest = '10'
  AND region != 'AUS'
