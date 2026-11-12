import duckdb


def test_latest_published_story():
    connection = duckdb.connect("warehouse/squeeze.duckdb", read_only=True)
    employee_sep, employee_jun = connection.execute(
        """
        SELECT
          MAX(CASE WHEN time_period = '2026-Q3' THEN lci_yoy END),
          MAX(CASE WHEN time_period = '2026-Q2' THEN lci_yoy END)
        FROM gold.household_gap
        WHERE household_type = 'P1'
        """
    ).fetchone()
    wage = connection.execute(
        "SELECT wage_yoy FROM silver.wage_national WHERE time_period = '2026-Q2'"
    ).fetchone()[0]
    price = connection.execute(
        "SELECT yoy_pct FROM silver.cpi_quarter WHERE region = '50' AND time_period = '2026-Q3'"
    ).fetchone()[0]
    gaps = connection.execute(
        "SELECT wage_minus_price_pp FROM gold.state_gap WHERE time_period = '2026-Q2'"
    ).fetchall()
    cash = connection.execute(
        """
        SELECT cash_rate_target FROM bronze.cash_rate
        WHERE series = 'decision'
        ORDER BY observed_on DESC
        LIMIT 1
        """
    ).fetchone()[0]
    prod_rows = connection.execute("SELECT COUNT(*) FROM gold.household_gap").fetchone()[0]
    dev_rows = connection.execute("SELECT COUNT(*) FROM gold__dev.household_gap").fetchone()[0]
    nowcast = connection.execute(
        """
        SELECT point_yoy, lo95_yoy, hi95_yoy, coverage95
        FROM published.nowcast
        WHERE series_id = 'lci_P1'
        """
    ).fetchone()
    connection.close()

    assert employee_sep == 5.1
    assert employee_jun == 3.7
    assert wage == 3.2
    assert round(price, 1) == 3.9
    assert employee_sep > price
    assert all(gap < 0 for (gap,) in gaps)
    assert len(gaps) == 8
    assert cash == 4.85
    assert prod_rows == dev_rows
    point, low, high, coverage = nowcast
    assert low <= point <= high
    assert 0 <= coverage <= 1
