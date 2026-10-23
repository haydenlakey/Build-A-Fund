"""One-page fund fact sheet, in the style of a South African unit trust minimum disclosure document.

Everything here is assembled from results the app has already computed (statistics, look-through,
benchmark report, costs, insight rules); nothing new is estimated. Rows are formatted once, so the
on-screen sheet and the PDF show the same text.

Performance is a simulation: today's weights applied to past weekly returns, rebalanced on a
schedule (see `fundlab.backtest.run`). For a period of n years ending at the last week T,

    annualised return = (W_T / W_{T - 52n})^(1/n) - 1,

where W is the simulated wealth. A calendar year's return is W at its last week over W at the last
week of the year before, minus one; the 12-month figures use every 52-week window.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import PERIODS_PER_YEAR
from .lookthrough import ASSET_LABELS, COUNTRY_NAMES
from .model import HOLDING_KINDS, Fund

# Five-step risk scale used on SA fact sheets, applied here to volatility. The bands are the app's own
# rule of thumb: managers set their labels with more than volatility. Checked against the app's curated
# unit trusts (2026-10-23, 5-year weekly prices): 17 of 27 land on their own published level, the
# other 10 one step away.
RISK_LEVELS = [(0.04, "Low"), (0.07, "Low to medium"), (0.09, "Medium"), (0.12, "Medium to high"),
               (math.inf, "High")]
TOP_HOLDINGS = 10
TOP_SLICES = 6  # sectors and countries beyond this are grouped as "Other"
PERIOD_YEARS = (1, 3, 5)
N_INSIGHTS = 3
SCHEDULE = "quarterly"
DISCLAIMER = ("Made with Build-a-Fund Lab. A model fund for learning, not a real unit trust: nobody manages it "
              "and it cannot be bought as a whole. Education, not financial advice. Past returns are a poor "
              "guide to future returns.")


def rand(x: float) -> str:
    return "–" if x is None or not math.isfinite(x) else f"{'-' if x < 0 else ''}R{abs(x):,.0f}".replace(",", " ")


def pct(x: float | None, decimals: int = 1, signed: bool = False) -> str:
    if x is None or not math.isfinite(x):
        return "–"
    return f"{x * 100:{'+' if signed else ''}.{decimals}f}%"


def risk_level(vol: float) -> str:
    if not math.isfinite(vol):
        return "–"
    return next(label for bound, label in RISK_LEVELS if vol < bound)


# ---- performance ---------------------------------------------------------------------------

@dataclass
class Performance:
    growth: pd.DataFrame  # R1 000 at the start: column "fund", and "benchmark" where it has prices
    periods: pd.DataFrame  # index "1 year", "3 years", ...; columns fund, benchmark (annualised)
    calendar: pd.DataFrame  # index "2022", ..., "2026 to 23 Oct"; columns fund, benchmark
    best_12m: float
    worst_12m: float
    start: pd.Timestamp
    end: pd.Timestamp


def _annualised(w: pd.Series, weeks: int) -> float:
    if len(w) <= weeks:
        return float("nan")
    a, b = w.iloc[-1 - weeks], w.iloc[-1]
    if not (np.isfinite(a) and np.isfinite(b)) or a <= 0:
        return float("nan")
    return float((b / a) ** (PERIODS_PER_YEAR / weeks) - 1)


def _calendar(w: pd.Series) -> pd.Series:
    """Return per calendar year: complete years, plus the last year to date."""
    w = w.dropna()
    if len(w) < 2:
        return pd.Series(dtype=float)
    year_end = w.groupby(w.index.year).last()
    end = w.index[-1]
    out = {}
    for y in year_end.index:
        if y - 1 not in year_end.index:
            continue  # no value at the end of the year before: the year isn't complete
        complete = y < end.year or (end.month == 12 and end.day >= 25)  # the last Friday of a year is on or after the 25th
        out[str(y) if complete else f"{y} to {end:%d %b}"] = float(year_end[y] / year_end[y - 1] - 1)
    return pd.Series(out, dtype=float)


def performance(fund_wealth: pd.Series, bench_wealth: pd.Series | None = None) -> Performance:
    """Annualised returns over 1, 3 and 5 years (where the window allows), calendar years, the best
    and worst 52-week returns of the fund, and growth of R1 000. The benchmark is shown only where it
    has prices at both ends of a period."""
    w = fund_wealth.astype(float)
    b = (bench_wealth.astype(float).reindex(w.index) if bench_wealth is not None
         else pd.Series(np.nan, index=w.index))
    if b.notna().any():
        first = b.first_valid_index()
        b = b / b[first] * w[first]  # the benchmark starts level with the fund where its prices begin
    weeks = len(w) - 1
    rows = {}
    for n in PERIOD_YEARS:
        if weeks >= n * PERIODS_PER_YEAR:
            rows[f"{n} year{'s' if n > 1 else ''}"] = (_annualised(w, n * PERIODS_PER_YEAR),
                                                        _annualised(b, n * PERIODS_PER_YEAR))
    longest = max([n for n in PERIOD_YEARS if weeks >= n * PERIODS_PER_YEAR], default=0)
    if weeks - longest * PERIODS_PER_YEAR > 4:  # the whole window is noticeably longer than the last period
        rows[f"Whole window ({weeks / PERIODS_PER_YEAR:.1f} years)"] = (_annualised(w, weeks), _annualised(b, weeks))
    periods = pd.DataFrame(rows, index=["fund", "benchmark"]).T if rows else pd.DataFrame(columns=["fund", "benchmark"])
    calendar = pd.DataFrame({"fund": _calendar(w), "benchmark": _calendar(b)})
    roll = (w / w.shift(PERIODS_PER_YEAR) - 1).dropna()
    growth = pd.DataFrame({"fund": 1000 * w / w.iloc[0]})
    if b.notna().any():
        growth["benchmark"] = 1000 * b / w.iloc[0]
    return Performance(growth, periods, calendar,
                       float(roll.max()) if len(roll) else float("nan"),
                       float(roll.min()) if len(roll) else float("nan"), w.index[0], w.index[-1])


# ---- the sheet -----------------------------------------------------------------------------

@dataclass
class InsightLine:
    title: str
    noticed: str
    severity: str
    article: str  # library slug
    article_title: str


@dataclass
class FactSheet:
    name: str
    objective: str
    as_of: pd.Timestamp | None
    details: list[tuple[str, str]]
    holdings: pd.DataFrame  # columns name, type, weight (top 10, then "Other (n holdings)")
    by_asset: pd.Series
    by_sector: pd.Series
    by_country: pd.Series
    performance: Performance | None
    benchmark: str
    risk: list[tuple[str, str]]
    fees: list[tuple[str, str]]
    insights: list[InsightLine]
    notes: list[str] = field(default_factory=list)
    risk_level: str = "–"


def _top(s: pd.Series, n: int = TOP_SLICES, other: str = "Other") -> pd.Series:
    s = s[s > 1e-9].sort_values(ascending=False)
    if len(s) <= n + 1:
        return s
    return pd.concat([s.iloc[:n], pd.Series({other: s.iloc[n:].sum()})])


def holdings_table(fund: Fund, names: dict[str, str]) -> pd.DataFrame:
    w = fund.weights().sort_values(ascending=False)
    kinds = {h.ticker: h.kind for h in fund.holdings}
    rows = [{"name": names.get(t, t), "type": HOLDING_KINDS.get(kinds.get(t, ""), ""), "weight": float(v)}
            for t, v in w.iloc[:TOP_HOLDINGS].items()]
    if len(w) > TOP_HOLDINGS:
        rest = w.iloc[TOP_HOLDINGS:]
        rows.append({"name": f"Other ({len(rest)} holdings)", "type": "", "weight": float(rest.sum())})
    return pd.DataFrame(rows, columns=["name", "type", "weight"])


def top_insights(tripped: list, articles: dict[str, str], n: int = N_INSIGHTS) -> list[InsightLine]:
    """Warnings first, then the order of content/rules.yaml (`tripped` is in file order)."""
    ordered = sorted(tripped, key=lambda i: i.rule.severity != "warning")
    return [InsightLine(i.rule.title, i.noticed, i.rule.severity, i.rule.article,
                        articles.get(i.rule.article, i.rule.article)) for i in ordered[:n]]


def build(fund: Fund, *, names: dict[str, str], stats=None, comp=None, active_report=None,
          benchmark: str = "", fund_wealth: pd.Series | None = None, bench_wealth: pd.Series | None = None,
          cost_summary=None, whole=None, illiquid: float = 0.0, tripped: list | None = None,
          articles: dict[str, str] | None = None, as_of: pd.Timestamp | None = None,
          var_label: str = "VaR") -> FactSheet:
    """Assemble the sheet. Any input may be None (no price history, no benchmark report...): the
    matching rows then show "–" and a note says why."""
    notes = []
    perf = performance(fund_wealth, bench_wealth) if fund_wealth is not None and len(fund_wealth) > 1 else None
    if perf is None:
        notes.append("No performance: none of the holdings has enough price history.")
    elif stats is not None and stats.coverage < 0.999:
        notes.append(f"Performance and risk cover the {pct(stats.coverage, 0)} of the fund that has price history; "
                     "unlisted holdings and short histories are left out of them.")

    vol_for_level = whole.vol if whole is not None else (stats.vol if stats is not None else float("nan"))
    level = risk_level(vol_for_level)
    details = [
        ("Fund size", rand(fund.total_zar)),
        ("Holdings", str(len(fund.weights()))),
        ("Benchmark", benchmark or "–"),
        ("Risk level", f"{level} (volatility {pct(vol_for_level)} a year)" if level != "–" else "–"),
        ("Effective holdings", f"{stats.eff_holdings:.1f}" if stats is not None else "–"),
        ("Can't be sold in a hurry", pct(illiquid, 0)),
    ]
    if perf is not None:
        details.append(("Price history used", f"{perf.start:%d %b %Y} to {perf.end:%d %b %Y}"))

    risk = []
    if stats is not None:
        risk += [("Volatility", f"{pct(stats.vol)} a year"),
                 ("Worst fall (from a high)", pct(stats.max_drawdown)),
                 ("Sharpe ratio", f"{stats.sharpe:.2f}"),
                 (var_label, pct(stats.var))]
    if perf is not None:
        risk += [("Best 12 months", pct(perf.best_12m, signed=True)),
                 ("Worst 12 months", pct(perf.worst_12m, signed=True))]
    if active_report is not None:
        risk += [("Beta to the benchmark", f"{active_report.beta:.2f}"),
                 ("Tracking error", f"{pct(active_report.te)} a year")]
    if whole is not None:
        risk.append(("Whole fund volatility (with unlisted)", f"{pct(whole.vol)} a year"))

    fees = []
    if comp is not None:
        fees += [("Total expense ratio (TER)", pct(comp.weighted_ter, 2)),
                 ("Transaction costs (TC)", pct(comp.weighted_tc, 2)),
                 ("Total investment charge (TIC)", pct(comp.weighted_ter + comp.weighted_tc, 2))]
    if cost_summary is not None:
        fees += [("Platform and account fees", f"{pct(cost_summary.platform + cost_summary.account, 2)} a year"),
                 ("One-off cost of buying it all", f"{rand(cost_summary.buy * cost_summary.total_zar)} "
                                                f"({pct(cost_summary.buy, 2)})")]

    def labelled(s: pd.Series, mapping: dict) -> pd.Series:
        return _top(s.rename(index=lambda k: mapping.get(k, k)).groupby(level=0).sum())

    empty = pd.Series(dtype=float)
    return FactSheet(
        name=fund.name or "Untitled fund", objective=fund.objective or "", as_of=as_of, details=details,
        holdings=holdings_table(fund, names),
        by_asset=labelled(comp.by_asset, ASSET_LABELS) if comp is not None else empty,
        by_sector=_top(comp.by_sector) if comp is not None else empty,
        by_country=labelled(comp.by_country, COUNTRY_NAMES) if comp is not None else empty,
        performance=perf, benchmark=benchmark, risk=risk, fees=fees,
        insights=top_insights(tripped or [], articles or {}), notes=notes, risk_level=level)
