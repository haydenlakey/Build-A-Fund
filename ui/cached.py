"""Cached access to the universe, prices and comparisons."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from fundlab import (active, analysis, content, data, estimators, factors, lookthrough, risk,
                     stress, synthetic, unit_trusts, unlisted, var)
from fundlab.model import HOLDING_KINDS, Fund


@st.cache_resource
def universe() -> data.Universe:
    return data.load_universe()


@st.cache_resource
def unit_trust_list() -> unit_trusts.UnitTrustList:
    return unit_trusts.load_unit_trusts()


@st.cache_resource
def store() -> data.PriceStore:
    return data.PriceStore(history_from=universe().history_limits())


def prices(tickers: list[str]) -> pd.DataFrame:
    return store().prices_zar(list(tickers))


def fund_prices(*funds: Fund) -> pd.DataFrame:
    """Rand prices for every holding of the funds: listed from the store, unit trusts uploaded or modelled."""
    rf = funds[-1].settings.risk_free if funds else 0.0
    return synthetic.price_frame(list(funds), prices, rf)


def label(ticker: str) -> str:
    e = universe().get(ticker)
    if e:
        return f"{e['name']} ({ticker}) · {HOLDING_KINDS[e['kind']]}"
    return ticker


def name_of(ticker: str, fund: Fund | None = None) -> str:
    e = universe().get(ticker)
    if e:
        return e["name"]
    if ut := unit_trust_list().get(ticker):
        return ut.name
    if fund and (h := fund.holding(ticker)):
        return h.name
    return ticker


@st.cache_data(max_entries=128, show_spinner=False)
def _compare(before_json: str, after_json: str) -> analysis.Comparison:
    before, after = Fund.from_json(before_json), Fund.from_json(after_json)
    return analysis.compare(before, after, fund_prices(before, after), after.settings)


def compare(before: Fund, after: Fund) -> analysis.Comparison:
    return _compare(before.to_json(), after.to_json())


@st.cache_resource
def lookthrough_data() -> lookthrough.LookThroughData:
    return lookthrough.load_lookthrough()


@st.cache_data(max_entries=64, show_spinner=False)
def _compose(fund_json: str) -> lookthrough.Composition:
    fund = Fund.from_json(fund_json)
    names = {h.ticker: h.name for h in fund.holdings}
    extra = unit_trusts.extra_profiles(fund, universe().entries, unit_trust_list())
    return lookthrough.compose(fund.weights(), universe().entries, lookthrough_data(), names, extra)


def compose(fund: Fund) -> lookthrough.Composition:
    return _compose(fund.to_json())


@st.cache_data(max_entries=64, show_spinner=False)
def _sensitivities(fund_json: str):
    fund = Fund.from_json(fund_json)
    stats = compare(fund, fund).after
    if stats is None:
        return None
    fac = factors.factor_returns(prices([t for t, _, _ in factors.FACTORS.values()]))
    port = stats.port_returns
    fac = fac.loc[port.index.min():port.index.max()]
    single = factors.single_betas(port, fac)
    joint, r2, n = factors.joint_betas(port, fac)
    return single, joint, r2, n


def sensitivities(fund: Fund):
    """(single-factor betas, joint table, joint R², joint n) for the fund's estimation window, or None."""
    return _sensitivities(fund.to_json())


def benchmark_key(fund: Fund) -> str:
    keys = universe().benchmarks
    return fund.settings.benchmark if fund.settings.benchmark in keys else "top40"


@st.cache_data(max_entries=64, show_spinner=False)
def _active(fund_json: str, key: str):
    fund = Fund.from_json(fund_json)
    bench = pd.Series(universe().benchmarks[key]["components"], dtype=float)
    bench = bench / bench.sum()
    w = fund.weights()
    tickers = list(dict.fromkeys(list(w.index) + list(bench.index)))
    px = fund_prices(fund).combine_first(prices(list(bench.index)))
    est = analysis.estimate(px, tickers, fund.settings)
    missing = [t for t in bench.index if t not in est.mu.index]
    if missing or est.mu.empty:
        return None, est.report, missing
    inc = [t for t in w.index if t in est.mu.index]
    if not inc:
        return None, est.report, []
    fw = w[inc] / w[inc].sum()
    return active.analyse(fw, bench, est.mu, est.cov), est.report, []


def active_report(fund: Fund, key: str):
    """(ActiveReport or None, HistoryReport, benchmark tickers lacking history)."""
    return _active(fund.to_json(), key)


@st.cache_data(show_spinner=False)
def _library(stamp: tuple):
    return content.load_library()


def library() -> dict:
    """All library articles; re-read whenever a file in content/library changes."""
    files = sorted(content.LIBRARY_PATH.glob("*.md"))
    return _library(tuple((f.name, f.stat().st_mtime_ns) for f in files))


# ---- risk detail ------------------------------------------------------------------

@st.cache_resource
def episodes() -> list[stress.Episode]:
    return stress.load_episodes()


@st.cache_data(max_entries=32, show_spinner=False)
def _stress(fund_json: str) -> list[stress.Replay]:
    fund = Fund.from_json(fund_json)
    stats = compare(fund, fund).after
    if stats is None:
        return []
    px = fund_prices(fund)
    fac = prices(list(stress.FACTORS))
    out = []
    for ep in episodes():
        r = stress.replay(stats.weights, px, fac, ep)
        if r is not None:
            r.whole_return = stress.whole_fund_return(fund, r.fund_return, stats.vol)
            out.append(r)
    return out


def stress_tests(fund: Fund) -> list[stress.Replay]:
    """Replays of the fund's measured (listed) weights through each episode the factor data covers."""
    return _stress(fund.to_json())


@st.cache_data(max_entries=32, show_spinner=False)
def _cov_vols(fund_json: str) -> dict[str, float]:
    fund = Fund.from_json(fund_json)
    cmp = compare(fund, fund)
    a = cmp.after
    if a is None:
        return {}
    rets = cmp.est.returns[a.weights.index]
    return {m: risk.portfolio_vol(a.weights, estimators.covariance(rets, m)) for m in estimators.COV_METHODS}


def cov_vols(fund: Fund) -> dict[str, float]:
    """Fund volatility under each covariance estimate, on the same window."""
    return _cov_vols(fund.to_json())


@st.cache_data(max_entries=32, show_spinner=False)
def _weekly_sims(fund_json: str, h_weeks: int, n_sims: int, dist: str, df: float) -> np.ndarray:
    fund = Fund.from_json(fund_json)
    cmp = compare(fund, fund)
    a = cmp.after
    return var.simulate_weekly(cmp.est.mu, cmp.est.cov, a.weights, h_weeks, n_sims, dist, df, fund.settings.seed)


def weekly_sims(fund: Fund, h_weeks: int, n_sims: int, dist: str, df: float) -> np.ndarray:
    """Simulated weekly returns of the listed part, (n_sims, h_weeks), seeded from the fund's settings."""
    return _weekly_sims(fund.to_json(), h_weeks, n_sims, dist, float(df))


@st.cache_data(max_entries=32, show_spinner=False)
def _whole_paths(fund_json: str, h_weeks: int, n_sims: int) -> np.ndarray:
    fund = Fund.from_json(fund_json)
    a = compare(fund, fund).after
    mu, vol = (a.exp_return, a.vol) if a is not None else (0.0, 0.0)
    return unlisted.simulate_paths(fund, mu, vol, h_weeks, n_sims, fund.settings.seed)


def whole_paths(fund: Fund, h_weeks: int, n_sims: int) -> np.ndarray:
    """Whole-fund value paths including unlisted holdings (buy and hold), (n_sims, h_weeks + 1)."""
    return _whole_paths(fund.to_json(), h_weeks, n_sims)
