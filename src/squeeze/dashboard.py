"""Build the static dashboard. The wording is for a general reader."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from squeeze.figures import growth, load, quarter_label, rnd
from squeeze.paths import DASHBOARD, INSIGHTS, MANIFEST
from squeeze.reference import COLOURS, HOUSEHOLDS

ORDER = ["P1", "P3", "P2", "PBLCI", "P4"]


def _pct(value: float | None, digits: int = 1) -> str:
    number = rnd(value, digits)
    if number is None:
        return "—"
    return f"{number:.{digits}f}%"


def _num(value: float | None, digits: int = 1) -> str:
    number = rnd(value, digits)
    if number is None:
        return "—"
    return f"{number:.{digits}f}"


def _kpi(value: str, label: str, takeaway: str, tone: str) -> dict:
    return {"value": value, "label": label, "takeaway": takeaway, "tone": tone}


def _line(title: str, subtitle: str, periods: list[str], series: list[dict], unit: str = "%") -> dict:
    return {
        "kind": "line",
        "title": title,
        "subtitle": subtitle,
        "unit": unit,
        "x": [quarter_label(period) for period in periods],
        "series": series,
    }


def _bars(title: str, subtitle: str, categories: list[str], series: list[dict], unit: str = "%") -> dict:
    return {
        "kind": "bar",
        "title": title,
        "subtitle": subtitle,
        "unit": unit,
        "categories": categories,
        "series": series,
    }


def _range(title: str, subtitle: str, categories: list[str], lows, points, highs, colors) -> dict:
    return {
        "kind": "range",
        "title": title,
        "subtitle": subtitle,
        "unit": "%",
        "categories": categories,
        "low": lows,
        "point": points,
        "high": highs,
        "colors": colors,
    }


def _slice(periods: list[str], start: str) -> list[str]:
    return [period for period in periods if period >= start]


def _yoy_series(data: dict, code: str, periods: list[str]) -> list[float | None]:
    table = data["households"][code]
    return [None if period not in table or table[period]["yoy"] is None else rnd(table[period]["yoy"], 1) for period in periods]


def build_dashboard(database: str | None = None) -> dict:
    data = load(database)
    manifest = json.loads(MANIFEST.read_text())
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "access_date": manifest["access_date"],
        "banner": _banner(data),
        "pages": {
            "squeeze": _squeeze(data),
            "behind": _behind(data),
            "where": _where(data),
            "next": _next(data),
        },
        "sources": _sources(manifest),
    }
    DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD.write_text(json.dumps(payload) + "\n")
    INSIGHTS.parent.mkdir(parents=True, exist_ok=True)
    INSIGHTS.write_text(json.dumps(_technical(data), indent=2) + "\n")
    return payload


def _banner(data: dict) -> dict:
    living = rnd(data["households"]["P1"]["2026-Q3"]["yoy"], 1)
    prices = rnd(data["prices"]["50"]["2026-Q3"]["yoy"], 1)
    wages = rnd(data["wages"]["2026-Q2"]["yoy"], 1)
    return {
        "kicker": "Australia · updated from the September quarter 2026 figures",
        "title": "Working households are losing the cost-of-living race",
        "dek": (
            f"Living costs for working households rose {_num(living)}% over the year to September 2026. "
            f"Prices rose {_num(prices)}%. The latest wage result, for the year to June, was {_num(wages)}%. "
            "September wages are due on 18 November 2026."
        ),
    }


def _index(table: dict, period: str, field: str = "index") -> float:
    return float(table[period][field])


def _squeeze(data: dict) -> dict:
    living = data["households"]["P1"]["2026-Q3"]["yoy"]
    prices = data["prices"]["50"]["2026-Q3"]["yoy"]
    wages = data["wages"]["2026-Q2"]["yoy"]
    wage_gap = rnd(data["wages"]["2026-Q2"]["yoy"], 1) - rnd(data["households"]["P1"]["2026-Q2"]["yoy"], 1)
    since_costs = growth(_index(data["households"]["P1"], "2026-Q2"), _index(data["households"]["P1"], "2021-Q3"))
    since_wages = growth(_index(data["wages"], "2026-Q2"), _index(data["wages"], "2021-Q3"))
    cash = data["cash"]["decisions"][-1]
    august = next(item for item in data["cash"]["decisions"] if item["date"] == "2025-08-13")
    rises = sum(1 for item in data["cash"]["decisions"] if item["date"].startswith("2026") and str(item["change"]).startswith("+"))
    periods = sorted(data["households"]["P1"])
    views = {}
    for key, start, label in (
        ("y2016", "2016-Q1", "Since 2016"),
        ("y2019", "2019-Q1", "Since 2019"),
        ("y2021", "2021-Q3", "Since Sep 2021"),
    ):
        window = _slice(periods, start)
        series = []
        for code in ("P1", "P3", "P2", "P4"):
            series.append(
                {
                    "name": HOUSEHOLDS[code],
                    "color": COLOURS[code],
                    "values": _yoy_series(data, code, window),
                }
            )
        series.append(
            {
                "name": "Prices",
                "color": COLOURS["prices"],
                "values": [
                    None
                    if data["prices"]["50"].get(period, {}).get("yoy") is None
                    else rnd(data["prices"]["50"][period]["yoy"], 1)
                    for period in window
                ],
            }
        )
        series.append(
            {
                "name": "Wages",
                "color": COLOURS["wages"],
                "values": [
                    None if data["wages"].get(period, {}).get("yoy") is None else rnd(data["wages"][period]["yoy"], 1)
                    for period in window
                ],
            }
        )
        views[key] = {
            "label": label,
            "hero": _line(
                "Living costs are running ahead of pay",
                "Change over the year. Wages stop at June 2026 because the September result is not out yet.",
                window,
                series,
            )
        }
    latest_order = sorted(ORDER, key=lambda code: data["households"][code]["2026-Q3"]["yoy"], reverse=True)
    mortgage = _rebased_mortgage(data)
    return {
        "kpis": [
            _kpi(_pct(living), "Working households", "Living costs over the year to September 2026.", "bad"),
            _kpi(_pct(prices), "Prices", "Prices across the eight capitals, over the same year.", "warn"),
            _kpi(
                _pct(wages),
                "Wages",
                "Latest official result, over the year to June 2026. September is due 18 November.",
                "warn",
            ),
            _kpi(
                f"{_num(since_costs)}% vs {_num(since_wages)}%",
                "Since September 2021",
                "Working-household living costs against wages, both to June 2026.",
                "bad",
            ),
            _kpi(
                _pct(cash["rate"], 2),
                "Cash rate",
                f"Set on 4 November 2026. It was {_pct(august['rate'], 2)} in August 2025, and has been raised {rises} times in 2026.",
                "info",
            ),
        ],
        "filters": [{"id": key, "label": views[key]["label"]} for key in ("y2019", "y2021", "y2016")],
        "default_filter": "y2019",
        "views": views,
        "supporting": [
            _bars(
                "Working households had the fastest rise in the latest year",
                "Change in living costs over the year to September 2026.",
                [HOUSEHOLDS[code] for code in latest_order],
                [
                    {
                        "name": "Living costs",
                        "color": COLOURS["P1"],
                        "colors": [COLOURS[code] for code in latest_order],
                        "values": [rnd(data["households"][code]["2026-Q3"]["yoy"], 1) for code in latest_order],
                    }
                ],
            ),
            _line(
                "Mortgage interest has climbed much faster than the rest of the basket",
                "Working households. September 2021 = 100.",
                [point["period"] for point in mortgage],
                [
                    {
                        "name": "Mortgage interest",
                        "color": COLOURS["mortgage"],
                        "values": [rnd(point["mortgage"], 1) for point in mortgage],
                    },
                    {
                        "name": "All living costs",
                        "color": COLOURS["P1"],
                        "values": [rnd(point["basket"], 1) for point in mortgage],
                    },
                ],
                unit="",
            ),
            _cash_chart(data),
        ],
        "means": (
            f"In the June quarter, the last time pay and living costs can be compared, wages rose "
            f"{_num(data['wages']['2026-Q2']['yoy'])}% and working-household living costs rose "
            f"{_num(data['households']['P1']['2026-Q2']['yoy'])}%. Pay was {_num(abs(wage_gap))} percentage points behind. "
            f"By September, living costs had jumped to {_num(living)}% while prices were {_num(prices)}%. "
            "About two-fifths of that September-quarter rise came from mortgage interest."
        ),
        "exact": _exact_households(data),
    }


def _rebased_mortgage(data: dict) -> list[dict]:
    path = [point for point in data["mortgage"]["employee_path"] if point["period"] >= "2021-Q3"]
    basket = data["households"]["P1"]
    base_m = next(point["index"] for point in path if point["period"] == "2021-Q3")
    base_b = basket["2021-Q3"]["index"]
    return [
        {
            "period": point["period"],
            "mortgage": point["index"] / base_m * 100,
            "basket": basket[point["period"]]["index"] / base_b * 100,
        }
        for point in path
        if point["period"] in basket
    ]


def _cash_chart(data: dict) -> dict:
    points = [item for item in data["cash"]["months"] if item["date"] >= "2022-01-01"]
    latest = data["cash"]["decisions"][-1]
    if latest["date"] > points[-1]["date"]:
        points = points + [{"date": latest["date"], "rate": latest["rate"]}]
    labels = []
    for item in points:
        year, month, _day = item["date"].split("-")
        names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        labels.append(f"{names[int(month) - 1]} {year}")
    return {
        "kind": "line",
        "title": f"The cash rate is {_num(latest['rate'], 2)}%, after a run of rises in 2026",
        "subtitle": "Cash-rate target. Monthly average, with the 4 November decision added.",
        "unit": "%",
        "x": labels,
        "series": [
            {
                "name": "Cash rate",
                "color": COLOURS["prices"],
                "values": [rnd(item["rate"], 2) for item in points],
            }
        ],
    }


def _window_growth(data: dict, start: str, end: str) -> dict[str, float]:
    values = {}
    for code in HOUSEHOLDS:
        values[code] = growth(_index(data["households"][code], end), _index(data["households"][code], start))
    values["prices"] = growth(_index(data["prices"]["50"], end), _index(data["prices"]["50"], start))
    if end in data["wages"] and start in data["wages"]:
        values["wages"] = growth(_index(data["wages"], end), _index(data["wages"], start))
    return values


def _behind(data: dict) -> dict:
    sep = {code: data["households"][code]["2026-Q3"]["yoy"] for code in HOUSEHOLDS}
    jun = {code: data["households"][code]["2026-Q2"]["yoy"] for code in HOUSEHOLDS}
    prices_sep = data["prices"]["50"]["2026-Q3"]["yoy"]
    prices_jun = data["prices"]["50"]["2026-Q2"]["yoy"]
    wages_jun = data["wages"]["2026-Q2"]["yoy"]
    long = _window_growth(data, "2021-Q3", "2026-Q2")
    long_sep = _window_growth(data, "2021-Q3", "2026-Q3")
    weights = data["weights"]
    latest_weight_period = max(weights["P1"])
    earlier_weight = weights["P1"].get("2022-Q3")

    def household_bars(values: dict[str, float], title: str, subtitle: str) -> dict:
        codes = sorted(ORDER, key=lambda code: values[code], reverse=True)
        return _bars(
            title,
            subtitle,
            [HOUSEHOLDS[code] for code in codes],
            [
                {
                    "name": "Living costs",
                    "color": COLOURS["P1"],
                    "colors": [COLOURS[code] for code in codes],
                    "values": [rnd(values[code], 1) for code in codes],
                }
            ],
        )

    def ahead_bars(values: dict[str, float], price: float, title: str) -> dict:
        gaps = {code: rnd(values[code], 1) - rnd(price, 1) for code in ORDER}
        codes = sorted(ORDER, key=lambda code: gaps[code], reverse=True)
        return _bars(
            title,
            "Percentage points. Above zero means living costs rose faster than prices.",
            [HOUSEHOLDS[code] for code in codes],
            [
                {
                    "name": "Ahead of prices",
                    "color": COLOURS["behind"],
                    "colors": [COLOURS[code] for code in codes],
                    "values": [gaps[code] for code in codes],
                }
            ],
            unit="pts",
        )

    weight_codes = sorted(ORDER, key=lambda code: weights[code][latest_weight_period], reverse=True)
    weight_chart = _bars(
        "Interest charges take a far bigger share of a working household's budget",
        f"Share of the budget at the {quarter_label(latest_weight_period)} update, the latest available. "
        f"For working households that share was {_num(earlier_weight)}% in September 2022.",
        [HOUSEHOLDS[code] for code in weight_codes],
        [
            {
                "name": "Interest charges",
                "color": COLOURS["mortgage"],
                "values": [rnd(weights[code][latest_weight_period], 1) for code in weight_codes],
            }
        ],
    )
    rebased = _rebased_lines(data)
    views = {
        "sep": {
            "label": "Year to Sep 2026",
            "hero": household_bars(sep, "Who faced the fastest living-cost rise", "Over the year to September 2026. Wages for this quarter are not out yet."),
            "supporting": [
                ahead_bars(sep, prices_sep, "How far living costs ran ahead of prices"),
                weight_chart,
                rebased,
            ],
            "means": (
                f"Age-pensioner costs rose {_num(sep['P2'])}%. The pensioner benchmark rose {_num(sep['PBLCI'])}%, "
                f"a little faster, and prices rose {_num(prices_sep)}%. An update that follows the higher of prices "
                "and that benchmark is keeping up with age-pensioner costs. "
                f"Households on other payments rose {_num(sep['P3'])}%, "
                f"{_num(rnd(sep['P3'], 1) - rnd(prices_sep, 1))} percentage points above prices. "
                f"Self-funded retirees, at {_num(sep['P4'])}%, were the only group below prices."
            ),
        },
        "jun": {
            "label": "Year to Jun 2026",
            "hero": household_bars(jun, "The last year when pay can be set beside living costs", f"Over the year to June 2026. Wages rose {_num(wages_jun)}%."),
            "supporting": [
                ahead_bars(jun, prices_jun, "How far living costs ran ahead of prices"),
                weight_chart,
                rebased,
            ],
            "means": (
                f"In the year to June, working-household living costs rose {_num(jun['P1'])}% and wages rose {_num(wages_jun)}%. "
                f"Pay was {_num(rnd(jun['P1'], 1) - rnd(wages_jun, 1))} percentage points behind living costs, and "
                f"{_num(rnd(prices_jun, 1) - rnd(wages_jun, 1))} percentage points behind prices."
            ),
        },
        "since": {
            "label": "Since Sep 2021",
            "hero": _bars(
                "Since September 2021, working households have worn the biggest rise",
                "Rise to June 2026, so wages can be compared on the same dates. September 2021 = the start.",
                ["Working households", "Other payment households", "Age pensioners", "Pensioner benchmark", "Self-funded retirees", "Prices", "Wages"],
                [
                    {
                        "name": "Rise",
                        "color": COLOURS["P1"],
                        "colors": [COLOURS["P1"], COLOURS["P3"], COLOURS["P2"], COLOURS["PBLCI"], COLOURS["P4"], COLOURS["prices"], COLOURS["wages"]],
                        "values": [
                            rnd(long[code], 1) for code in ("P1", "P3", "P2", "PBLCI", "P4")
                        ]
                        + [rnd(long["prices"], 1), rnd(long["wages"], 1)],
                    }
                ],
            ),
            "supporting": [
                _bars(
                    "How far the rise ran ahead of prices, to June 2026",
                    "Percentage points since September 2021. Wages are included.",
                    ["Working households", "Other payment households", "Age pensioners", "Pensioner benchmark", "Self-funded retirees", "Wages"],
                    [
                        {
                            "name": "Ahead of prices",
                            "color": COLOURS["behind"],
                            "colors": [COLOURS["P1"], COLOURS["P3"], COLOURS["P2"], COLOURS["PBLCI"], COLOURS["P4"], COLOURS["wages"]],
                            "values": [
                                rnd(rnd(long[code], 1) - rnd(long["prices"], 1), 1) for code in ("P1", "P3", "P2", "PBLCI", "P4")
                            ]
                            + [rnd(rnd(long["wages"], 1) - rnd(long["prices"], 1), 1)],
                        }
                    ],
                    unit="pts",
                ),
                weight_chart,
                rebased,
            ],
            "means": (
                f"From September 2021 to June 2026, working-household living costs rose {_num(long['P1'])}% "
                f"and wages rose {_num(long['wages'])}%. "
                f"By September 2026 living costs for those households were up {_num(long_sep['P1'])}% on September 2021, "
                f"against a {_num(long_sep['prices'])}% rise in prices."
            ),
        },
    }
    return {
        "kpis": [
            _kpi(_pct(sep["P1"]), "Working households", "Fastest living-cost rise over the year to September 2026.", "bad"),
            _kpi(_pct(sep["P3"]), "Other payments", "Next fastest. These households are not wage earners.", "bad"),
            _kpi(
                f"{_num(sep['P2'])}% vs {_num(sep['PBLCI'])}%",
                "Age pensioners",
                "Their own living costs, beside the pensioner and beneficiary benchmark.",
                "warn",
            ),
            _kpi(_pct(sep["P4"]), "Self-funded retirees", "The only group whose living costs rose more slowly than prices.", "ok"),
        ],
        "filters": [{"id": key, "label": views[key]["label"]} for key in ("sep", "jun", "since")],
        "default_filter": "sep",
        "views": views,
        "exact": _exact_households(data),
    }


def _rebased_lines(data: dict) -> dict:
    periods = [period for period in sorted(data["households"]["P1"]) if period >= "2021-Q3"]
    series = []
    for code in ("P1", "P3", "P2", "P4", "PBLCI"):
        base = data["households"][code]["2021-Q3"]["index"]
        series.append(
            {
                "name": HOUSEHOLDS[code],
                "color": COLOURS[code],
                "values": [rnd(data["households"][code][period]["index"] / base * 100, 1) for period in periods],
            }
        )
    price_base = data["prices"]["50"]["2021-Q3"]["index"]
    series.append(
        {
            "name": "Prices",
            "color": COLOURS["prices"],
            "values": [rnd(data["prices"]["50"][period]["index"] / price_base * 100, 1) for period in periods],
        }
    )
    wage_base = data["wages"]["2021-Q3"]["index"]
    series.append(
        {
            "name": "Wages",
            "color": COLOURS["wages"],
            "values": [
                None
                if period not in data["wages"]
                else rnd(data["wages"][period]["index"] / wage_base * 100, 1)
                for period in periods
            ],
        }
    )
    return _line(
        "The gap has been building since 2021",
        "September 2021 = 100. Wages stop at June 2026.",
        periods,
        series,
        unit="",
    )


def _where(data: dict) -> dict:
    states = []
    for state in data["states"]:
        wage = rnd(state["wage_yoy"], 1)
        prices = rnd(state["cpi_yoy"], 1)
        states.append({**state, "wage_r": wage, "price_r": prices, "behind": rnd(prices - wage, 1)})
    states.sort(key=lambda item: item["behind"], reverse=True)
    widest = states[0]
    narrowest = states[-1]
    industries_all = data["industries"]["7"]
    industries_private = data["industries"]["1"]
    slowest = industries_all[0]
    jobless = [row for row in data["unemployment"] if row["region"] != "AUS"]
    national = next(row for row in data["unemployment"] if row["region"] == "AUS")
    grouped = _bars(
        "Pay rose more slowly than capital-city prices in every state",
        "Year to June 2026. Pay is the state result. Prices are the capital city.",
        [item["state"] for item in states],
        [
            {"name": "Pay", "color": COLOURS["wages"], "values": [item["wage_r"] for item in states]},
            {"name": "Prices", "color": COLOURS["prices"], "values": [item["price_r"] for item in states]},
        ],
    )
    gap = _bars(
        f"{widest['state']} is furthest behind. Every state is behind.",
        "How far pay trailed capital-city prices, in percentage points, year to June 2026.",
        [item["state"] for item in states],
        [
            {
                "name": "Points behind",
                "color": COLOURS["behind"],
                "values": [item["behind"] for item in states],
            }
        ],
        unit="pts",
    )
    jobless_chart = _bars(
        f"{_num(national['rate'])}% of the workforce was looking for work in September",
        "September 2026. The Northern Territory and the ACT are not in this release.",
        [row["name"] for row in sorted(jobless, key=lambda item: item["rate"], reverse=True)],
        [
            {
                "name": "Looking for work",
                "color": "#8EB6FF",
                "values": [rnd(row["rate"], 1) for row in sorted(jobless, key=lambda item: item["rate"], reverse=True)],
            }
        ],
    )

    def industry_chart(rows: list[dict], who: str) -> dict:
        ordered = sorted(rows, key=lambda item: item["yoy"])
        return _bars(
            f"{ordered[0]['name']} had the smallest pay rise among {who}",
            "Change in pay over the year to June 2026. Farm jobs are not in this set.",
            [item["name"] for item in ordered],
            [{"name": "Pay", "color": COLOURS["wages"], "values": [rnd(item["yoy"], 1) for item in ordered]}],
        )

    return {
        "kpis": [
            _kpi(
                f"{_num(widest['behind'])} pts",
                widest["state"],
                f"Pay {_num(widest['wage_r'])}%, {widest['capital']} prices {_num(widest['price_r'])}%. Widest gap.",
                "bad",
            ),
            _kpi(
                f"{_num(narrowest['behind'])} pts",
                narrowest["state"],
                f"The narrowest gap, and still behind. Pay {_num(narrowest['wage_r'])}%, {narrowest['capital']} prices {_num(narrowest['price_r'])}%.",
                "warn",
            ),
            _kpi("8 of 8", "States behind", "In every state, pay trailed capital-city prices over the year to June.", "bad"),
            _kpi(
                _pct(slowest["yoy"]),
                slowest["name"],
                "Smallest pay rise over the year to June 2026, across all employers.",
                "warn",
            ),
            _kpi(
                _pct(national["rate"]),
                "Looking for work",
                "Share of the workforce, September 2026.",
                "info",
            ),
        ],
        "filters": [
            {"id": "all", "label": "All employers"},
            {"id": "private", "label": "Private employers"},
        ],
        "default_filter": "all",
        "hero": gap,
        "views": {
            "all": {"supporting": [grouped, industry_chart(industries_all, "all employers"), jobless_chart]},
            "private": {"supporting": [grouped, industry_chart(industries_private, "private employers"), jobless_chart]},
        },
        "means": (
            f"Living-cost figures are published for Australia as a whole, not state by state. "
            f"This page puts each state's pay beside prices in its capital. "
            f"{widest['state']} has the widest gap. {narrowest['state']} has the narrowest, and pay is still behind prices there. "
            "The September wage result will show whether any state closed the gap."
        ),
        "exact": {
            "columns": ["State", "Capital", "Pay, year to Jun 2026", "Prices, year to Jun 2026", "Points behind"],
            "rows": [
                [item["state"], item["capital"], _pct(item["wage_yoy"]), _pct(item["cpi_yoy"]), _num(item["behind"])]
                for item in states
            ],
        },
    }


def _next(data: dict) -> dict:
    by_id = {item["series_id"]: item for item in data["nowcast"]}
    order = [("lci_P1", "P1"), ("lci_P3", "P3"), ("lci_P2", "P2"), ("lci_PBLCI", "PBLCI"), ("lci_P4", "P4"), ("cpi", None)]
    living = [by_id[key] for key, _code in order if key in by_id and key != "wpi"]
    wages = by_id["wpi"]
    workers = by_id["lci_P1"]
    backtest = data["backtest"].get("lci_P1", [])
    hits = sum(1 for row in backtest if float(row["lo95_yoy"]) <= float(row["actual_yoy"]) <= float(row["hi95_yoy"]))
    checked = len(backtest)
    recent = backtest[-8:]
    cash = data["cash"]["decisions"][-1]
    hero = _range(
        "Where living costs may land in the December quarter",
        "Change over the year. The mark is the estimate. The line is the wider range from past misses.",
        [item["label"] for item in living],
        [rnd(float(item["lo95_yoy"]), 1) for item in living],
        [rnd(float(item["point_yoy"]), 1) for item in living],
        [rnd(float(item["hi95_yoy"]), 1) for item in living],
        [COLOURS.get(key.split("_")[-1], COLOURS["prices"]) if key != "cpi" else COLOURS["prices"] for key, _ in order if key != "wpi"],
    )
    wage_chart = _range(
        "The September wage result, due 18 November",
        f"The June result was {_num(data['wages']['2026-Q2']['yoy'])}%. The mark is the estimate for September. The line is the wider range.",
        ["Wages, September quarter"],
        [rnd(float(wages["lo95_yoy"]), 1)],
        [rnd(float(wages["point_yoy"]), 1)],
        [rnd(float(wages["hi95_yoy"]), 1)],
        [COLOURS["wages"]],
    )
    history = _line(
        "How close past estimates came for working households",
        f"The wider range contained the actual result in {hits} of the last {checked} quarters.",
        [row["period"] for row in recent],
        [
            {"name": "What happened", "color": COLOURS["P1"], "values": [rnd(float(row["actual_yoy"]), 1) for row in recent]},
            {"name": "Estimate", "color": COLOURS["wages"], "values": [rnd(float(row["predicted_yoy"]), 1) for row in recent]},
            {"name": "Wider range, low", "color": "#5C6B82", "values": [rnd(float(row["lo95_yoy"]), 1) for row in recent], "band": "low"},
            {"name": "Wider range, high", "color": "#5C6B82", "values": [rnd(float(row["hi95_yoy"]), 1) for row in recent], "band": "high"},
        ],
    )
    return {
        "kpis": [
            _kpi(
                _pct(float(wages["point_yoy"])),
                "Wages, September",
                f"Estimate for the result due 18 November. Wider range {_num(float(wages['lo95_yoy']))}% to {_num(float(wages['hi95_yoy']))}%.",
                "info",
            ),
            _kpi(
                _pct(float(workers["point_yoy"])),
                "Working households, December",
                f"Estimate of living costs over the year to December. Wider range {_num(float(workers['lo95_yoy']))}% to {_num(float(workers['hi95_yoy']))}%.",
                "warn",
            ),
            _kpi(
                f"{hits} of {checked}",
                "Range checked on the past",
                "How often the wider range for working households contained the actual result. A high count can still mean the range is wide.",
                "info",
            ),
            _kpi(_pct(cash["rate"], 2), "Cash rate", "Still the rate set on 4 November 2026. The next living-cost figures will show whether the rises are still feeding through.", "info"),
        ],
        "hero": hero,
        "supporting": [wage_chart, history],
        "means": (
            f"The September wage estimate is {_num(float(wages['point_yoy']))}%, "
            f"inside a wider range of {_num(float(wages['lo95_yoy']))}% to {_num(float(wages['hi95_yoy']))}%. "
            f"For working households, the December living-cost estimate is {_num(float(workers['point_yoy']))}%, "
            f"with a wider range of {_num(float(workers['lo95_yoy']))}% to {_num(float(workers['hi95_yoy']))}%. "
            f"That wider range contained the actual working-household result in {hits} of the last {checked} quarters. "
            "The range is wide because living costs have jumped around."
        ),
        "exact": {
            "columns": ["Series", "Quarter", "Estimate", "Tighter range", "Wider range", "Typical miss"],
            "rows": [
                [
                    item["label"],
                    quarter_label(item["target_period"]),
                    _pct(float(item["point_yoy"])),
                    f"{_num(float(item['lo80_yoy']))}% to {_num(float(item['hi80_yoy']))}%",
                    f"{_num(float(item['lo95_yoy']))}% to {_num(float(item['hi95_yoy']))}%",
                    _pct(float(item["mae_yoy"])),
                ]
                for item in data["nowcast"]
            ],
        },
    }


def _exact_households(data: dict) -> dict:
    rows = []
    for code in ORDER:
        sep = data["households"][code]["2026-Q3"]["yoy"]
        jun = data["households"][code]["2026-Q2"]["yoy"]
        rows.append([HOUSEHOLDS[code], _pct(sep), _pct(jun)])
    rows.append(["Prices", _pct(data["prices"]["50"]["2026-Q3"]["yoy"]), _pct(data["prices"]["50"]["2026-Q2"]["yoy"])])
    rows.append(["Wages", "Not released", _pct(data["wages"]["2026-Q2"]["yoy"])])
    return {
        "columns": ["Group", "Year to Sep 2026", "Year to Jun 2026"],
        "rows": rows,
    }


def _sources(manifest: dict) -> list[dict]:
    return [
        {
            "name": "Selected living cost indexes",
            "publisher": "Australian Bureau of Statistics",
            "note": "Household living costs, including mortgage interest for working households. Australia only.",
        },
        {
            "name": "Wage price index",
            "publisher": "Australian Bureau of Statistics",
            "note": "Pay rates. The national result is the usual headline. State and industry results are as published.",
        },
        {
            "name": "Consumer price index",
            "publisher": "Australian Bureau of Statistics",
            "note": "Prices in the eight capitals. The annual change is calculated from the published price levels.",
        },
        {
            "name": "Labour force",
            "publisher": "Australian Bureau of Statistics",
            "note": "Share of people looking for work.",
        },
        {
            "name": "Cash rate",
            "publisher": "Reserve Bank of Australia",
            "note": "The announced target, and the monthly average.",
        },
        {
            "name": "Checked",
            "publisher": "Public releases",
            "note": f"Figures checked on {manifest['access_date']}. Free sources, no account required.",
        },
    ]


def _technical(data: dict) -> dict:
    """Numbers for the project write-up. Not shown on the public dashboard."""
    workers = data["households"]["P1"]
    return {
        "employee_lci_yoy_2026q3": workers["2026-Q3"]["yoy"],
        "employee_lci_yoy_2026q2": workers["2026-Q2"]["yoy"],
        "cpi_yoy_2026q3": data["prices"]["50"]["2026-Q3"]["yoy"],
        "cpi_yoy_2026q2": data["prices"]["50"]["2026-Q2"]["yoy"],
        "wage_yoy_2026q2": data["wages"]["2026-Q2"]["yoy"],
        "wage_sectors_2026q2": data["wages"].get("_sectors_2026q2", {}),
        "since_2021q3_to_2026q2": _window_growth(data, "2021-Q3", "2026-Q2"),
        "since_2021q3_to_2026q3": _window_growth(data, "2021-Q3", "2026-Q3"),
        "mortgage_employee_2026q3": data["mortgage"]["latest"].get("P1"),
        "interest_weight_employee": data["weights"].get("P1"),
        "states_2026q2": data["states"],
        "industries_2026q2": data["industries"],
        "unemployment": data["unemployment"],
        "cash_decisions": data["cash"]["decisions"],
        "nowcast": data["nowcast"],
    }
