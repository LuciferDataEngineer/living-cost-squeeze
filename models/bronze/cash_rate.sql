MODEL (
  name bronze.cash_rate,
  kind FULL,
  audits (
    not_null(columns := (series, observed_on, cash_rate_target)),
    accepted_range(column := cash_rate_target, min_v := 0, max_v := 20)
  )
);

SELECT
  series::VARCHAR AS series,
  CAST(observed_on AS DATE) AS observed_on,
  cash_rate_target::DOUBLE AS cash_rate_target,
  change_text::VARCHAR AS change_text
FROM read_csv('data/snapshot/rba_cash_rate.csv.gz', header = true)
