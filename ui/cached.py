"""Cached access to the universe, prices and comparisons."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from fundlab import analysis, data
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
