MODEL (
  name silver.wage_national,
  kind FULL,
  audits (not_null(columns := (time_period, wage_index)))
);

-- Headline wage result: total hourly rates excluding bonuses, private and
-- public together, seasonally adjusted, Australia.
SELECT
  time_period,
  MAX(CASE WHEN measure = '3' THEN obs_value END) AS wage_yoy,
  MAX(CASE WHEN measure = '1' THEN obs_value END) AS wage_index
FROM bronze.wpi
WHERE
  index_code = 'THRPEB'
  AND sector = '7'
  AND industry = 'TOT'
  AND tsest = '20'
  AND region = 'AUS'
GROUP BY time_period
