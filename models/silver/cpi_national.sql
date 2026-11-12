MODEL (
  name silver.cpi_national,
  kind FULL,
  audits (not_null(columns := (time_period, cpi_index)))
);

SELECT
  time_period,
  yoy_pct AS cpi_yoy,
  index_level AS cpi_index
FROM silver.cpi_quarter
WHERE region = '50'
