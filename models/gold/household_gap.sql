MODEL (
  name gold.household_gap,
  kind FULL,
  audits (not_null(columns := (time_period, household_type, lci_yoy)))
);

SELECT
  living.time_period,
  living.household_type,
  living.lci_index,
  living.lci_yoy,
  wages.wage_yoy,
  wages.wage_index,
  prices.cpi_yoy,
  prices.cpi_index,
  wages.wage_yoy - living.lci_yoy AS wage_minus_living_cost_pp,
  living.lci_yoy - prices.cpi_yoy AS living_cost_minus_cpi_pp
FROM silver.lci_all_groups AS living
LEFT JOIN silver.wage_national AS wages
  ON living.time_period = wages.time_period
LEFT JOIN silver.cpi_national AS prices
  ON living.time_period = prices.time_period
WHERE living.lci_yoy IS NOT NULL
