from squeeze.nowcast import forecast_series, next_period, period_from_timestamp, quarter_end


def test_quarter_helpers():
    assert next_period("2026-Q3") == "2026-Q4"
    assert next_period("2026-Q4") == "2027-Q1"
    stamp = quarter_end("2026-Q3")
    assert period_from_timestamp(stamp) == "2026-Q3"


def test_fast_conformal_range_contains_the_point():
    periods = [f"{year}-Q{quarter}" for year in range(2016, 2026) for quarter in range(1, 5)]
    values = [100 + index * 0.4 + (index % 4) * 0.2 for index in range(len(periods))]
    result = forecast_series("synthetic", "Synthetic", "living_cost", periods, values, fast=True)
    assert result.lo95_yoy <= result.point_yoy <= result.hi95_yoy
    assert result.lo80_yoy <= result.point_yoy <= result.hi80_yoy
    assert result.lo95_yoy <= result.lo80_yoy
    assert result.hi80_yoy <= result.hi95_yoy
    assert 0 <= result.coverage95 <= 1
    assert result.mae_yoy >= 0
    assert result.n_windows == 8
    assert result.target_period == "2026-Q1"
