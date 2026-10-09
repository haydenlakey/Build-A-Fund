"""Build-a-Fund Lab: entry point. Run with `streamlit run app.py`."""
from __future__ import annotations

import json

import streamlit as st

from fundlab.estimators import COV_METHODS
from fundlab.model import Fund, FundSettings
from ui import state
from ui.components import DISCLAIMER

st.set_page_config(page_title="Build-a-Fund Lab", page_icon="🧪", layout="wide")
state.init()


def fund_manager() -> None:
    ss = st.session_state
    funds = ss.funds
    ids = list(funds)
    choice = st.selectbox("Your funds", ids, index=ids.index(ss.active),
                          format_func=lambda i: funds[i].name or "Untitled fund")
    if choice != ss.active:
        ss.active = choice
        st.rerun()
    fund = state.active()

    c1, c2, c3 = st.columns(3)
    if c1.button("New", width="stretch", help="Start an empty fund"):
        state.put(Fund(f"Fund {len(funds) + 1}"))
        st.rerun()
    if c2.button("Copy", width="stretch", help="Duplicate this fund to try changes on the copy"):
        state.put(fund.copy(name=f"{fund.name} (copy)"))
        st.rerun()
    if c3.button("Delete", width="stretch", disabled=len(funds) == 1 and not fund.holdings):
        state.remove(fund.id)
        st.rerun()

    st.download_button("Save fund to a file", fund.to_json(), file_name=f"{fund.name or 'fund'}.fund.json",
                       mime="application/json", width="stretch", icon=":material/download:")
    up = st.file_uploader("Open a saved fund", type=["json"], key="fund_upload",
                          help="A .fund.json file saved from this app, for example one a friend sent you.")
    if up is not None and ss.get("uploaded_id") != up.file_id:
        ss.uploaded_id = up.file_id
        try:
            loaded = Fund.from_json(up.getvalue())
            if loaded.id in funds:
                loaded = loaded.copy()
            state.put(loaded)
            st.rerun()
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            st.error(f"That file isn't a fund saved by this app ({e}).")

    with st.expander("Share with a friend"):
        st.caption("This link contains the whole fund. Nothing is stored on a server: "
                   "your friend gets their own copy to play with.")
        st.code(state.share_url(fund), language=None, wrap_lines=True)


def settings_panel() -> None:
    fund = state.active()
    s = fund.settings
    with st.expander("Assumptions and settings"):
        lookbacks = {3.0: "3 years", 5.0: "5 years", 10.0: "10 years", 0.0: "All available"}
        lb = st.selectbox("History to use", list(lookbacks), format_func=lookbacks.get,
                          index=list(lookbacks).index(s.lookback_years or 0.0))
        cov = st.selectbox("Covariance estimate", list(COV_METHODS), format_func=COV_METHODS.get,
                           index=list(COV_METHODS).index(s.cov_method))
        shrink = st.slider("Shrink expected returns toward the prior", 0.0, 1.0, float(s.mean_shrinkage), 0.05,
                           help="0 = use raw historical averages; 1 = ignore history and use the prior entirely.")
        prior = st.slider("Prior Sharpe ratio (your assumption)", 0.0, 1.0, float(s.prior_sharpe), 0.05,
                          help="The prior gives every holding the same return per unit of risk: "
                               "risk-free rate + this × its volatility.")
        rf = st.number_input("Risk-free rate, % a year (your assumption)", 0.0, 30.0, s.risk_free * 100, 0.25,
                             help="Used for the Sharpe ratio and the prior. A South African money-market or "
                                  "Treasury bill yield is the usual choice.")
        conf = st.select_slider("VaR confidence", [0.9, 0.95, 0.975, 0.99], value=s.var_alpha,
                                format_func=lambda x: f"{x:.1%}".replace(".0%", "%"))
        horizon = st.select_slider("VaR horizon (weeks)", [1, 2, 4, 13, 26, 52], value=s.var_horizon_weeks)
        seed = st.number_input("Random seed (for simulations)", 0, 2**31 - 1, s.seed, 1,
                               help="Simulations use this seed so results are reproducible. Change it to see "
                                    "how much the answers wobble.")
        new = FundSettings(lookback_years=lb or None, cov_method=cov, mean_shrinkage=shrink, prior_sharpe=prior,
                           risk_free=rf / 100, var_alpha=conf, var_horizon_weeks=horizon, seed=int(seed),
                           benchmark=s.benchmark)
        if new != s:
            f = fund.copy(keep_id=True)
            f.settings = new
            state.put(f)
            st.rerun()


pages = [
    st.Page("views/build.py", title="Build your fund", icon=":material/construction:", default=True),
    st.Page("views/composition.py", title="What kind of fund is it?", icon=":material/donut_large:"),
    st.Page("views/active_bets.py", title="Against a benchmark", icon=":material/compare_arrows:"),
    st.Page("views/library.py", title="Library", icon=":material/menu_book:"),
    st.Page("views/about.py", title="About and data", icon=":material/info:"),
]
nav = st.navigation(pages)

with st.sidebar:
    fund_manager()
    settings_panel()
    st.caption(DISCLAIMER)

if st.session_state.get("share_error"):
    st.warning(st.session_state.pop("share_error"))
nav.run()
