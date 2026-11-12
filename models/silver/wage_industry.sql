MODEL (
  name silver.wage_industry,
  kind FULL,
  audits (not_null(columns := (time_period, sector, industry_code, wage_yoy)))
);

SELECT
  time_period,
  sector,
  industry AS industry_code,
  obs_value AS wage_yoy
FROM bronze.wpi
WHERE
  measure = '3'
  AND index_code = 'THRPEB'
  AND tsest = '10'
  AND region = 'AUS'
  AND industry != 'TOT'
  AND sector IN ('1', '7')
