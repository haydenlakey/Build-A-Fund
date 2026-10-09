"""Cached access to the universe, prices and comparisons."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from fundlab import active, analysis, data, factors, lookthrough
from fundlab.model import HOLDING_KINDS, Fund


@st.cache_resource
def universe() -> data.Universe:
    return data.load_universe()


@st.cache_resource
def store() -> data.PriceStore:
    return data.PriceStore(history_from=universe().history_limits())


def prices(tickers: list[str]) -> pd.DataFrame:
    return store().prices_zar(list(tickers))


def label(ticker: str) -> str:
    e = universe().get(ticker)
    if e:
        return f"{e['name']} ({ticker}) · {HOLDING_KINDS[e['kind']]}"
    return ticker


def name_of(ticker: str, fund: Fund | None = None) -> str:
    e = universe().get(ticker)
    if e:
        return e["name"]
    if fund and (h := fund.holding(ticker)):
        return h.name
    return ticker


@st.cache_data(max_entries=128, show_spinner=False)
def _compare(before_json: str, after_json: str) -> analysis.Comparison:
    before, after = Fund.from_json(before_json), Fund.from_json(after_json)
    tickers = list(dict.fromkeys(list(before.weights().index) + list(after.weights().index)))
    return analysis.compare(before, after, prices(tickers), after.settings)


def compare(before: Fund, after: Fund) -> analysis.Comparison:
    return _compare(before.to_json(), after.to_json())


@st.cache_resource
def lookthrough_data() -> lookthrough.LookThroughData:
    return lookthrough.load_lookthrough()


@st.cache_data(max_entries=64, show_spinner=False)
def _compose(fund_json: str) -> lookthrough.Composition:
    fund = Fund.from_json(fund_json)
    names = {h.ticker: h.name for h in fund.holdings}
    return lookthrough.compose(fund.weights(), universe().entries, lookthrough_data(), names)


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
    est = analysis.estimate(prices(tickers), tickers, fund.settings)
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
