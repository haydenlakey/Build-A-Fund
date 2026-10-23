"""Per-visitor session state: the funds this visitor has open and which one is active."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from fundlab.model import Fund, Holding

EXAMPLE_FUND = [
    ("STX40.JO", "Satrix 40", "jse_etf", "ZAR", 10_000.0),
    ("STX500.JO", "Satrix S&P 500", "jse_etf", "ZAR", 5_000.0),
    ("CPI.JO", "Capitec Bank", "jse_share", "ZAR", 1_500.0),
    ("GLD.JO", "NewGold Gold ETF", "jse_etf", "ZAR", 2_000.0),
]


def example_fund() -> Fund:
    return Fund("Example fund", [Holding(t, n, k, a, c) for t, n, k, c, a in EXAMPLE_FUND],
                objective="A simple mix of South African and US shares with some gold.")


def init() -> None:
    ss = st.session_state
    if "funds" in ss:
        return
    ss.funds = {}
    ss.share_error = None
    fund = None
    code = st.query_params.get("fund")
    if code:
        try:
            fund = Fund.from_share_code(code)
        except Exception:  # noqa: BLE001 - any malformed link
            ss.share_error = "That share link couldn't be read, so a blank fund was opened instead."
    fund = fund or Fund("My fund")
    ss.funds[fund.id] = fund
    ss.active = fund.id


def active() -> Fund:
    return st.session_state.funds[st.session_state.active]


def put(fund: Fund) -> None:
    """Store a fund (new or edited) and make it active."""
    st.session_state.funds[fund.id] = fund
    st.session_state.active = fund.id


def remove(fund_id: str) -> None:
    ss = st.session_state
    ss.funds.pop(fund_id, None)
    if not ss.funds:
        f = Fund("My fund")
        ss.funds[f.id] = f
    if ss.active not in ss.funds:
        ss.active = next(iter(ss.funds))


def share_url(fund: Fund) -> str:
    code = fund.to_share_code()
    try:
        base = (st.context.url or "").split("?")[0]
    except Exception:  # noqa: BLE001
        base = ""
    return f"{base}?fund={code}" if base else f"?fund={code}"


PAGES = {p.stem for p in (Path(__file__).resolve().parent.parent / "views").glob("*.py")}


def app_url() -> str:
    """The app's root address (this page's address without its page path or query), or "" when unknown."""
    try:
        url = (st.context.url or "").split("?")[0].rstrip("/")
    except Exception:  # noqa: BLE001 - no browser context (tests)
        return ""
    head, _, last = url.rpartition("/")
    return head if last in PAGES and "//" in head else url
