MODEL (
  name gold.state_gap,
  kind FULL,
  audits (not_null(columns := (time_period, state_code, wage_yoy, cpi_yoy)))
);

SELECT
  wages.time_period,
  wages.state_code,
  prices.yoy_pct AS cpi_yoy,
  wages.wage_yoy,
  wages.wage_yoy - prices.yoy_pct AS wage_minus_price_pp,
  CASE SUBSTRING(wages.time_period, 6, 2)
    WHEN 'Q1' THEN SUBSTRING(wages.time_period, 1, 4) || '-03'
    WHEN 'Q2' THEN SUBSTRING(wages.time_period, 1, 4) || '-06'
    WHEN 'Q3' THEN SUBSTRING(wages.time_period, 1, 4) || '-09'
    WHEN 'Q4' THEN SUBSTRING(wages.time_period, 1, 4) || '-12'
  END AS quarter_month
FROM silver.wage_state AS wages
INNER JOIN silver.cpi_quarter AS prices
  ON wages.time_period = prices.time_period
  AND wages.state_code = prices.region
WHERE prices.yoy_pct IS NOT NULL
