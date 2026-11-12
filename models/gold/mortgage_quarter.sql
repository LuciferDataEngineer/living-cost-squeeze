MODEL (
  name gold.mortgage_quarter,
  kind FULL,
  audits (not_null(columns := (time_period, household_type)))
);

WITH basket AS (
  SELECT time_period, household_type, index_level AS allgroups_index, yoy_pct AS allgroups_yoy, contribution_change AS allgroups_change
  FROM silver.lci_quarter
  WHERE index_code = '10001'
),
mortgage AS (
  SELECT time_period, household_type, index_level AS mortgage_index, yoy_pct AS mortgage_yoy, contribution_change AS mortgage_change
  FROM silver.lci_quarter
  WHERE index_code = '131278'
)
SELECT
  basket.time_period,
  basket.household_type,
  basket.allgroups_index,
  basket.allgroups_yoy,
  basket.allgroups_change,
  mortgage.mortgage_index,
  mortgage.mortgage_yoy,
  mortgage.mortgage_change,
  CASE
    WHEN basket.allgroups_change IS NULL OR basket.allgroups_change = 0 OR mortgage.mortgage_change IS NULL THEN NULL
    ELSE mortgage.mortgage_change / basket.allgroups_change
  END AS mortgage_share_of_quarter
FROM basket
LEFT JOIN mortgage
  ON basket.time_period = mortgage.time_period
  AND basket.household_type = mortgage.household_type
