MODEL (
  name silver.cpi_quarter,
  kind FULL,
  audits (
    unique_combination_of_columns(columns := (time_period, region)),
    not_null(columns := (index_level))
  )
);

WITH levels AS (
  SELECT
    time_period,
    region,
    index_level,
    CAST(SUBSTRING(time_period, 1, 4) AS INT) AS year_num,
    SUBSTRING(time_period, 6, 2) AS quarter_code
  FROM bronze.cpi
)
SELECT
  current_row.time_period,
  current_row.region,
  current_row.index_level,
  CASE
    WHEN previous_row.index_level IS NULL OR previous_row.index_level = 0 THEN NULL
    ELSE (current_row.index_level / previous_row.index_level - 1) * 100
  END AS yoy_pct
FROM levels AS current_row
LEFT JOIN levels AS previous_row
  ON current_row.region = previous_row.region
  AND current_row.quarter_code = previous_row.quarter_code
  AND current_row.year_num = previous_row.year_num + 1
