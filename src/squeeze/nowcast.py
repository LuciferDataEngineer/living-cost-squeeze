"""Next-quarter estimates with walk-forward checks and conformal ranges.

statsforecast fits a seasonal baseline and an automatic ARIMA. The published
estimate is whichever had the smaller error on annual change. The shaded
range is the library's conformal interval from the same walk-forward errors.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import duckdb
import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, SeasonalNaive
from statsforecast.utils import ConformalIntervals

from squeeze.paths import WAREHOUSE
from squeeze.reference import HOUSEHOLDS

WINDOWS = 20
FAST_WINDOWS = 8


def quarter_end(period: str) -> pd.Timestamp:
    year, quarter = period.split("-Q")
    month = {"1": 3, "2": 6, "3": 9, "4": 12}[quarter]
    return (pd.Timestamp(year=int(year), month=month, day=1) + pd.offsets.MonthEnd(0)).normalize()


def period_from_timestamp(stamp: pd.Timestamp) -> str:
    stamp = pd.Timestamp(stamp)
    quarter = (stamp.month - 1) // 3 + 1
    return f"{stamp.year}-Q{quarter}"


def next_period(period: str) -> str:
    year, quarter = period.split("-Q")
    quarter_num = int(quarter)
    if quarter_num == 4:
        return f"{int(year) + 1}-Q1"
    return f"{year}-Q{quarter_num + 1}"


def _yoy(value: float, base: float) -> float:
    return (value / base - 1.0) * 100.0


@dataclass
class SeriesResult:
    series_id: str
    label: str
    group: str
    model: str
    history_end: str
    target_period: str
    point_index: float
    lo80_index: float
    hi80_index: float
    lo95_index: float
    hi95_index: float
    point_yoy: float
    lo80_yoy: float
    hi80_yoy: float
    lo95_yoy: float
    hi95_yoy: float
    mae_yoy: float
    rmse_yoy: float
    coverage80: float
    coverage95: float
    n_windows: int
    backtest: list[dict[str, float | str]]


def _frame(periods: list[str], values: list[float], series_id: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "unique_id": series_id,
            "ds": [quarter_end(period) for period in periods],
            "y": values,
        }
    )


def _models(fast: bool) -> list:
    windows = FAST_WINDOWS if fast else WINDOWS
    intervals = ConformalIntervals(h=1, n_windows=windows, method="conformal_error")
    chosen = [SeasonalNaive(season_length=4, prediction_intervals=intervals)]
    if not fast:
        chosen.append(AutoARIMA(season_length=4, prediction_intervals=intervals))
    return chosen


def _score_model(
    name: str,
    cross: pd.DataFrame,
    history: dict[pd.Timestamp, float],
) -> tuple[float, float, float, float, list[dict[str, float | str]]]:
    errors: list[float] = []
    hit80 = 0
    hit95 = 0
    rows: list[dict[str, float | str]] = []
    usable = 0
    for record in cross.to_dict(orient="records"):
        target = pd.Timestamp(record["ds"]).normalize()
        base_stamp = (target.to_period("Q") - 4).to_timestamp(how="end").normalize()
        base = history.get(base_stamp)
        actual = float(record["y"])
        point = float(record[name])
        lo80 = float(record[f"{name}-lo-80"])
        hi80 = float(record[f"{name}-hi-80"])
        lo95 = float(record[f"{name}-lo-95"])
        hi95 = float(record[f"{name}-hi-95"])
        if base is None or base == 0:
            continue
        usable += 1
        actual_yoy = _yoy(actual, base)
        point_yoy = _yoy(point, base)
        error = point_yoy - actual_yoy
        errors.append(error)
        if lo80 <= actual <= hi80:
            hit80 += 1
        if lo95 <= actual <= hi95:
            hit95 += 1
        rows.append(
            {
                "period": period_from_timestamp(target),
                "actual_yoy": actual_yoy,
                "predicted_yoy": point_yoy,
                "lo95_yoy": _yoy(lo95, base),
                "hi95_yoy": _yoy(hi95, base),
            }
        )
    if not errors:
        return 1e9, 1e9, 0.0, 0.0, rows
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = (sum(error * error for error in errors) / len(errors)) ** 0.5
    return mae, rmse, hit80 / usable, hit95 / usable, rows


def forecast_series(
    series_id: str,
    label: str,
    group: str,
    periods: list[str],
    values: list[float],
    *,
    fast: bool = False,
) -> SeriesResult:
    frame = _frame(periods, values, series_id)
    history = {pd.Timestamp(stamp).normalize(): float(value) for stamp, value in zip(frame["ds"], frame["y"], strict=True)}
    windows = FAST_WINDOWS if fast else WINDOWS
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stats = StatsForecast(models=_models(fast), freq="QE", n_jobs=1)
        cross = stats.cross_validation(df=frame, h=1, n_windows=windows, step_size=1, level=[80, 95])
        stats.fit(frame)
        prediction = stats.predict(h=1, level=[80, 95])
    names = [column for column in prediction.columns if "-" not in column and column not in {"unique_id", "ds"}]
    scored = {name: _score_model(name, cross, history) for name in names}
    winner = min(scored, key=lambda name: scored[name][0])
    mae, rmse, coverage80, coverage95, backtest = scored[winner]
    row = prediction.iloc[0]
    target = pd.Timestamp(row["ds"]).normalize()
    base_stamp = (target.to_period("Q") - 4).to_timestamp(how="end").normalize()
    base = history[base_stamp]
    point = float(row[winner])
    lo80 = float(row[f"{winner}-lo-80"])
    hi80 = float(row[f"{winner}-hi-80"])
    lo95 = float(row[f"{winner}-lo-95"])
    hi95 = float(row[f"{winner}-hi-95"])
    return SeriesResult(
        series_id=series_id,
        label=label,
        group=group,
        model=winner,
        history_end=periods[-1],
        target_period=period_from_timestamp(target),
        point_index=point,
        lo80_index=lo80,
        hi80_index=hi80,
        lo95_index=lo95,
        hi95_index=hi95,
        point_yoy=_yoy(point, base),
        lo80_yoy=_yoy(lo80, base),
        hi80_yoy=_yoy(hi80, base),
        lo95_yoy=_yoy(lo95, base),
        hi95_yoy=_yoy(hi95, base),
        mae_yoy=mae,
        rmse_yoy=rmse,
        coverage80=coverage80,
        coverage95=coverage95,
        n_windows=windows,
        backtest=backtest,
    )


def _load_pairs(connection: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> tuple[list[str], list[float]]:
    rows = connection.execute(sql, params or []).fetchall()
    return [row[0] for row in rows], [float(row[1]) for row in rows]


def run_nowcast(database: str | None = None, *, fast: bool = False) -> list[SeriesResult]:
    connection = duckdb.connect(database or str(WAREHOUSE))
    jobs: list[tuple[str, str, str, list[str], list[float]]] = []
    for code, label in HOUSEHOLDS.items():
        periods, values = _load_pairs(
            connection,
            """
            SELECT time_period, lci_index
            FROM silver.lci_all_groups
            WHERE household_type = ? AND lci_index IS NOT NULL
            ORDER BY time_period
            """,
            [code],
        )
        jobs.append((f"lci_{code}", label, "living_cost", periods, values))
    periods, values = _load_pairs(
        connection,
        """
        SELECT time_period, cpi_index
        FROM silver.cpi_national
        WHERE cpi_index IS NOT NULL
        ORDER BY time_period
        """,
    )
    jobs.append(("cpi", "Prices", "prices", periods, values))
    periods, values = _load_pairs(
        connection,
        """
        SELECT time_period, wage_index
        FROM silver.wage_national
        WHERE wage_index IS NOT NULL
        ORDER BY time_period
        """,
    )
    jobs.append(("wpi", "Wages", "wages", periods, values))
    connection.close()

    results = []
    for series_id, label, group, periods, values in jobs:
        print(f"estimating {label}", flush=True)
        results.append(forecast_series(series_id, label, group, periods, values, fast=fast))
    _store(results, database)
    return results


def _store(results: list[SeriesResult], database: str | None) -> None:
    connection = duckdb.connect(database or str(WAREHOUSE))
    summary = pd.DataFrame(
        [
            {
                "series_id": item.series_id,
                "label": item.label,
                "group_name": item.group,
                "model_name": item.model,
                "history_end": item.history_end,
                "target_period": item.target_period,
                "point_yoy": item.point_yoy,
                "lo80_yoy": item.lo80_yoy,
                "hi80_yoy": item.hi80_yoy,
                "lo95_yoy": item.lo95_yoy,
                "hi95_yoy": item.hi95_yoy,
                "mae_yoy": item.mae_yoy,
                "rmse_yoy": item.rmse_yoy,
                "coverage80": item.coverage80,
                "coverage95": item.coverage95,
                "n_windows": item.n_windows,
            }
            for item in results
        ]
    )
    backtest_rows = []
    for item in results:
        for row in item.backtest:
            backtest_rows.append({"series_id": item.series_id, **row})
    connection.execute("CREATE SCHEMA IF NOT EXISTS published")
    connection.register("summary_frame", summary)
    connection.execute("CREATE OR REPLACE TABLE published.nowcast AS SELECT * FROM summary_frame")
    backtest = pd.DataFrame(backtest_rows)
    connection.register("backtest_frame", backtest)
    connection.execute("CREATE OR REPLACE TABLE published.nowcast_backtest AS SELECT * FROM backtest_frame")
    connection.close()
