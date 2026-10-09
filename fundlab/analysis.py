"""Turn a Fund plus rand prices into statistics, and compare two versions of a fund.

History rule
------------
Statistics use the window that every included holding shares, cut to the
lookback the user chose. A holding with fewer than MIN_WEEKS of history in that
window is left out of the statistics (and reported); if the shared window is
shorter than WARN_WEEKS, the holdings that shortened it are flagged.

Before/after comparisons estimate everything on the window of the *union* of
both funds' holdings, so a change in the numbers reflects the holding, not a
change of sample period.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import estimators, frontier, risk, var
from .model import Fund, FundSettings

MIN_WEEKS = 52
WARN_WEEKS = 156


@dataclass
class HistoryReport:
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    n_weeks: int
    included: list[str]
    excluded: dict[str, str] = field(default_factory=dict)  # ticker -> reason
    short: dict[str, int] = field(default_factory=dict)  # ticker -> weeks available, if < WARN_WEEKS
    limited_by: str | None = None  # holding whose listing date cut the lookback short

    @property
    def is_short(self) -> bool:
        return self.n_weeks < WARN_WEEKS


def history_window(prices: pd.DataFrame, tickers: list[str], lookback_years: float | None,
                   min_weeks: int = MIN_WEEKS) -> HistoryReport:
    tickers = list(dict.fromkeys(tickers))
    excluded = {t: "No price data available." for t in tickers if t not in prices.columns
                or prices[t].notna().sum() == 0}
    have = [t for t in tickers if t not in excluded]
    if not have:
        return HistoryReport(None, None, 0, [], excluded)

    end = min(prices[t].last_valid_index() for t in have)
    lb_start = prices.index[0] if not lookback_years else end - pd.DateOffset(days=int(round(365.25 * lookback_years)))
    firsts = {t: prices[t].first_valid_index() for t in have}
    avail = {t: int(((prices.index >= max(firsts[t], lb_start)) & (prices.index <= end)).sum()) - 1
             for t in have}
    for t in have:
        if avail[t] < min_weeks:
            excluded[t] = f"Only {max(avail[t], 0)} weeks of price history (at least {min_weeks} needed)."
    included = [t for t in have if t not in excluded]
    if not included:
        return HistoryReport(None, None, 0, [], excluded)

    latest_first = max(included, key=lambda t: firsts[t])
    start = max(lb_start, firsts[latest_first])
    limited_by = latest_first if firsts[latest_first] > lb_start else None
    n_weeks = int(((prices.index >= start) & (prices.index <= end)).sum()) - 1
    short = {t: avail[t] for t in included if avail[t] < WARN_WEEKS}
    return HistoryReport(start, end, n_weeks, included, excluded, short, limited_by)


def window_returns(prices: pd.DataFrame, report: HistoryReport) -> pd.DataFrame:
    if not report.included:
        return pd.DataFrame()
    p = prices.loc[report.start:report.end, report.included]
    return estimators.prices_to_returns(p).dropna()


@dataclass
class Estimates:
    """Means and covariance estimated once on a window, shared by funds being compared."""
    returns: pd.DataFrame
    mu: pd.Series
    cov: pd.DataFrame
    report: HistoryReport


def estimate(prices: pd.DataFrame, tickers: list[str], settings: FundSettings) -> Estimates:
    report = history_window(prices, tickers, settings.lookback_years)
    rets = window_returns(prices, report)
    if rets.empty:
        return Estimates(rets, pd.Series(dtype=float), pd.DataFrame(), report)
    target = estimators.equal_sharpe_target(rets, settings.risk_free, settings.prior_sharpe)
    mu = estimators.mean_returns(rets, settings.mean_shrinkage, target)
    cov = estimators.covariance(rets, settings.cov_method)
    return Estimates(rets, mu, cov, report)


@dataclass
class FundStats:
    weights: pd.Series  # weights used in the statistics (renormalised over included holdings)
    coverage: float  # share of the fund's rands that the statistics cover
    total_zar: float
    exp_return: float
    exp_return_se: float
    vol: float
    sharpe: float
    max_drawdown: float
    var: float  # parametric normal, horizon and confidence from settings, positive fraction
    es: float
    var_hist: float
    div_ratio: float
    eff_holdings: float
    avg_corr: float
    risk_shares: pd.Series
    port_returns: pd.Series
    frontier: frontier.Frontier
    efficiency_gap: float
    excluded: dict[str, str]

    @property
    def var_zar(self) -> float:
        return self.var * self.total_zar

    def as_dict(self) -> dict[str, float]:
        return {k: getattr(self, k) for k in METRICS}


METRICS = ["exp_return", "vol", "sharpe", "max_drawdown", "var", "div_ratio", "eff_holdings"]


def fund_stats(fund: Fund, est: Estimates, settings: FundSettings | None = None,
               frontier_points: int = 25) -> FundStats | None:
    """Statistics for one fund using shared estimates. None if nothing can be measured."""
    s = settings or fund.settings
    w_all = fund.weights()
    if w_all.empty:
        return None
    inc = [t for t in w_all.index if t in est.mu.index]
    excluded = {t: est.report.excluded.get(t, "Not in the estimation window.") for t in w_all.index if t not in inc}
    if not inc:
        return None
    coverage = float(w_all[inc].sum())
    w = w_all[inc] / coverage
    mu, cov = est.mu[inc], est.cov.loc[inc, inc]

    ret = risk.portfolio_return(w, mu)
    vol = risk.portfolio_vol(w, cov)
    pr = risk.portfolio_returns(w, est.returns)
    p_var, p_es = var.parametric_var_es(ret, vol, s.var_horizon_weeks, s.var_alpha)
    h_var, _ = var.historical_var_es(pr, s.var_horizon_weeks, s.var_alpha)
    if frontier_points:
        fr = frontier.efficient_frontier(mu, cov, frontier_points)
        gap = frontier.efficiency_gap(ret, vol, fr)
    else:  # caller measures against a shared frontier instead
        fr, gap = frontier.Frontier(np.array([]), np.array([]), []), float("nan")
    return FundStats(
        weights=w, coverage=coverage, total_zar=fund.total_zar,
        exp_return=ret, exp_return_se=estimators.mean_standard_error(pr),
        vol=vol, sharpe=risk.sharpe(ret, vol, s.risk_free),
        max_drawdown=risk.max_drawdown(pr), var=p_var, es=p_es, var_hist=h_var,
        div_ratio=risk.diversification_ratio(w, cov), eff_holdings=risk.effective_holdings(w),
        avg_corr=risk.average_correlation(w, cov), risk_shares=risk.risk_shares(w, cov),
        port_returns=pr, frontier=fr, efficiency_gap=gap,
        excluded=excluded,
    )


@dataclass
class Comparison:
    """Before and after, measured on one shared window and against one shared frontier.

    `frontier` is built from every measurable holding in either version, i.e. the
    opportunity set the change is about, so both gaps are comparable.
    """
    before: FundStats | None
    after: FundStats | None
    est: Estimates
    frontier: frontier.Frontier
    gap_before: float = float("nan")
    gap_after: float = float("nan")

    def delta(self, metric: str) -> float:
        if self.before is None or self.after is None:
            return float("nan")
        return getattr(self.after, metric) - getattr(self.before, metric)


def compare(before: Fund, after: Fund, prices: pd.DataFrame, settings: FundSettings | None = None,
            frontier_points: int = 25) -> Comparison:
    s = settings or after.settings
    tickers = list(dict.fromkeys(list(before.weights().index) + list(after.weights().index)))
    est = estimate(prices, tickers, s)
    b = fund_stats(before, est, s, frontier_points=0)
    a = fund_stats(after, est, s, frontier_points=0)
    if est.mu.empty:
        return Comparison(b, a, est, frontier.Frontier(np.array([]), np.array([]), []))
    fr = frontier.efficient_frontier(est.mu, est.cov, frontier_points)
    gb = frontier.efficiency_gap(b.exp_return, b.vol, fr) if b else float("nan")
    ga = frontier.efficiency_gap(a.exp_return, a.vol, fr) if a else float("nan")
    return Comparison(b, a, est, fr, gb, ga)


def correlation_with_rest(ticker: str, weights: pd.Series, returns: pd.DataFrame) -> float:
    """Correlation of one holding's weekly returns with the rest of the fund (excluding it)."""
    if ticker not in returns.columns:
        return float("nan")
    rest = weights.drop(ticker, errors="ignore")
    rest = rest[rest.index.isin(returns.columns)]
    if rest.empty or rest.sum() <= 0:
        return float("nan")
    rest_r = returns[rest.index] @ (rest / rest.sum())
    return float(np.corrcoef(returns[ticker], rest_r)[0, 1])


def asset_vol(ticker: str, cov: pd.DataFrame) -> float:
    return float(np.sqrt(cov.loc[ticker, ticker])) if ticker in cov.index else float("nan")
