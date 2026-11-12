"""Headline numbers read from the DuckDB warehouse."""

from __future__ import annotations

import decimal

import duckdb

from squeeze.paths import WAREHOUSE
from squeeze.reference import HOUSEHOLDS, INDUSTRIES, STATES

QUARTER_MONTH = {"1": "Mar", "2": "Jun", "3": "Sep", "4": "Dec"}


def rnd(value: float | None, digits: int = 1) -> float | None:
    if value is None:
        return None
    quant = decimal.Decimal("1") if digits == 0 else decimal.Decimal(10) ** -digits
    number = decimal.Decimal(str(value)).quantize(quant, rounding=decimal.ROUND_HALF_UP)
    return float(number)


def quarter_label(period: str) -> str:
    year, quarter = period.split("-Q")
    return f"{QUARTER_MONTH[quarter]} {year}"


def growth(latest: float, earlier: float) -> float:
    return (latest / earlier - 1.0) * 100.0


def load(database: str | None = None) -> dict:
    connection = duckdb.connect(database or str(WAREHOUSE), read_only=True)
    try:
        households = _households(connection)
        prices = _prices(connection)
        wages = _wages(connection)
        states = _states(connection)
        industries = _industries(connection)
        weights = _weights(connection)
        mortgage = _mortgage(connection)
        cash = _cash(connection)
        unemployment = _unemployment(connection)
        nowcast, backtest = _nowcast(connection)
    finally:
        connection.close()
    return {
        "households": households,
        "prices": prices,
        "wages": wages,
        "states": states,
        "industries": industries,
        "weights": weights,
        "mortgage": mortgage,
        "cash": cash,
        "unemployment": unemployment,
        "nowcast": nowcast,
        "backtest": backtest,
    }


def _rows(connection, sql: str, params: list | None = None) -> list[tuple]:
    return connection.execute(sql, params or []).fetchall()


def _households(connection) -> dict[str, dict[str, dict[str, float]]]:
    series: dict[str, dict[str, dict[str, float]]] = {code: {} for code in HOUSEHOLDS}
    for period, household, index, yoy in _rows(
        connection,
        """
        SELECT time_period, household_type, lci_index, lci_yoy
        FROM gold.household_gap
        ORDER BY time_period
        """,
    ):
        series[household][period] = {"index": float(index), "yoy": None if yoy is None else float(yoy)}
    return series


def _prices(connection) -> dict[str, dict[str, dict[str, float]]]:
    series: dict[str, dict[str, dict[str, float]]] = {}
    for period, region, index, yoy in _rows(
        connection,
        """
        SELECT time_period, region, index_level, yoy_pct
        FROM silver.cpi_quarter
        ORDER BY time_period
        """,
    ):
        series.setdefault(region, {})[period] = {
            "index": float(index),
            "yoy": None if yoy is None else float(yoy),
        }
    return series


def _wages(connection) -> dict[str, dict[str, float]]:
    series: dict[str, dict[str, float]] = {}
    for period, yoy, index in _rows(
        connection,
        "SELECT time_period, wage_yoy, wage_index FROM silver.wage_national ORDER BY time_period",
    ):
        series[period] = {"yoy": None if yoy is None else float(yoy), "index": float(index)}
    sector_rows = _rows(
        connection,
        """
        SELECT sector, obs_value
        FROM bronze.wpi
        WHERE time_period = '2026-Q2'
          AND measure = '3'
          AND index_code = 'THRPEB'
          AND industry = 'TOT'
          AND tsest = '20'
          AND region = 'AUS'
        """,
    )
    series["_sectors_2026q2"] = {sector: float(value) for sector, value in sector_rows}
    return series


def _states(connection) -> list[dict]:
    rows = []
    for period, code, wage, prices, gap in _rows(
        connection,
        """
        SELECT time_period, state_code, wage_yoy, cpi_yoy, wage_minus_price_pp
        FROM gold.state_gap
        WHERE time_period = '2026-Q2'
        ORDER BY wage_minus_price_pp
        """,
    ):
        state, capital = STATES[code]
        rows.append(
            {
                "code": code,
                "state": state,
                "capital": capital,
                "wage_yoy": float(wage),
                "cpi_yoy": float(prices),
                "gap": float(gap),
            }
        )
    return rows


def _industries(connection) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {"7": [], "1": []}
    for sector, code, yoy in _rows(
        connection,
        """
        SELECT sector, industry_code, wage_yoy
        FROM silver.wage_industry
        WHERE time_period = '2026-Q2'
        ORDER BY wage_yoy, industry_code
        """,
    ):
        grouped[sector].append(
            {"code": code, "name": INDUSTRIES.get(code, code), "yoy": float(yoy)}
        )
    return grouped


def _weights(connection) -> dict[str, dict[str, float]]:
    weights: dict[str, dict[str, float]] = {}
    for period, household, weight in _rows(
        connection,
        """
        SELECT time_period, household_type, weight_pct
        FROM bronze.lci_weights
        WHERE index_code = '130427'
        ORDER BY time_period
        """,
    ):
        weights.setdefault(household, {})[period] = float(weight)
    return weights


def _mortgage(connection) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for household, yoy, change, all_change, share, index in _rows(
        connection,
        """
        SELECT household_type, mortgage_yoy, mortgage_change, allgroups_change,
               mortgage_share_of_quarter, mortgage_index
        FROM gold.mortgage_quarter
        WHERE time_period = '2026-Q3'
        """,
    ):
        latest[household] = {
            "yoy": None if yoy is None else float(yoy),
            "change": None if change is None else float(change),
            "all_change": None if all_change is None else float(all_change),
            "share": None if share is None else float(share),
            "index": None if index is None else float(index),
        }
    path: dict[str, list[dict]] = {code: [] for code in HOUSEHOLDS}
    for period, household, index, yoy in _rows(
        connection,
        """
        SELECT time_period, household_type, mortgage_index, mortgage_yoy
        FROM gold.mortgage_quarter
        WHERE household_type = 'P1' AND mortgage_index IS NOT NULL
        ORDER BY time_period
        """,
    ):
        path[household].append(
            {"period": period, "index": float(index), "yoy": None if yoy is None else float(yoy)}
        )
    return {"latest": latest, "employee_path": path["P1"]}


def _cash(connection) -> dict:
    months = [
        {"date": observed.isoformat(), "rate": float(rate)}
        for observed, rate in _rows(
            connection,
            """
            SELECT observed_on, cash_rate_target
            FROM bronze.cash_rate
            WHERE series = 'month_average' AND observed_on >= DATE '2019-01-01'
            ORDER BY observed_on
            """,
        )
    ]
    decisions = [
        {"date": observed.isoformat(), "rate": float(rate), "change": change or ""}
        for observed, rate, change in _rows(
            connection,
            """
            SELECT observed_on, cash_rate_target, change_text
            FROM bronze.cash_rate
            WHERE series = 'decision' AND observed_on >= DATE '2024-01-01'
            ORDER BY observed_on
            """,
        )
    ]
    return {"months": months, "decisions": decisions}


def _unemployment(connection) -> list[dict]:
    rows = []
    for region, month, rate in _rows(
        connection,
        """
        SELECT region, month, rate
        FROM bronze.unemployment
        WHERE month = (SELECT MAX(month) FROM bronze.unemployment WHERE region = 'AUS')
        ORDER BY region
        """,
    ):
        name = "Australia" if region == "AUS" else STATES.get(region, (region, ""))[0]
        rows.append({"region": region, "name": name, "month": month, "rate": float(rate)})
    return rows


def _nowcast(connection) -> tuple[list[dict], dict[str, list[dict]]]:
    tables = {
        name
        for (name,) in _rows(
            connection,
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'published'
            """,
        )
    }
    if "nowcast" not in tables:
        return [], {}
    summary = []
    columns = [item[0] for item in connection.execute("DESCRIBE published.nowcast").fetchall()]
    for row in _rows(connection, "SELECT * FROM published.nowcast ORDER BY series_id"):
        summary.append(dict(zip(columns, row, strict=True)))
    backtest: dict[str, list[dict]] = {}
    columns = [item[0] for item in connection.execute("DESCRIBE published.nowcast_backtest").fetchall()]
    for row in _rows(connection, "SELECT * FROM published.nowcast_backtest ORDER BY series_id, period"):
        record = dict(zip(columns, row, strict=True))
        backtest.setdefault(record["series_id"], []).append(record)
    return summary, backtest
