"""Pickers for holdings that aren't listed shares: unit trusts and unlisted investments.

Each picker returns (ticker, amount, spec) where spec holds the Fund.with_amount keyword arguments
(name, kind, method, params), or (None, None, None) until there is something to preview.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from fundlab import synthetic, unit_trusts
from fundlab.model import METHODS, Fund
from fundlab.unit_trusts import RISK_ORDER
from fundlab.unlisted import CATEGORIES, DEFAULTS, Assumptions
from ui import cached
from ui import components as C

NONE = (None, None, None)
OWN = "__own__"
METHOD_HELP = {
    "price_history": "Real unit prices from EasyEquities (from mid-2021 for most funds). Income the fund pays "
                     "out isn't added back, so returns look lower than investors actually earned.",
    "allocation_model": "Builds a price history from the fund's published mix of assets, using index ETFs for "
                        "each part, less the fund's fee. Captures the broad risk, not the manager's choices.",
    "uploaded": "Your own file of dates and prices (daily or weekly), e.g. exported from the manager's website.",
}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "holding"


def _amount(fund: Fund, ticker: str, key: str):
    current = fund.amounts().get(ticker)
    return st.number_input("Rand amount", min_value=0.0, value=float(current) if current else None, step=100.0,
                           format="%.2f", key=key, placeholder="e.g. 1000",
                           help="How many rand you'd put into this holding. Set it to 0 to remove it.")


def allocation_table(allocation: dict[str, float]) -> None:
    rows = [{"Asset class": synthetic.ASSET_CLASSES[k][0], "Share": v,
             "Modelled with": synthetic.ASSET_CLASSES[k][2]}
            for k, v in sorted(allocation.items(), key=lambda kv: -kv[1]) if k in synthetic.ASSET_CLASSES]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
        "Share": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)})


def _upload(gen: int, key: str):
    f = st.file_uploader("Price file (CSV: a date column and a price column)", type=["csv", "txt"],
                         key=f"ut_file_{gen}_{key}")
    if f is None:
        return None
    try:
        s = synthetic.parse_price_file(f.getvalue())
    except ValueError as e:
        st.error(str(e))
        return None
    st.caption(f"Read {len(s)} weeks, {s.index[0]:%d %b %Y} to {s.index[-1]:%d %b %Y}.")
    return synthetic.series_to_params(s)


def unit_trust_picker(fund: Fund, gen: int):
    uts = cached.unit_trust_list()
    held = [h for h in fund.holdings if h.kind == "unit_trust"]
    levels = RISK_ORDER + [OWN]
    names = {k: v["name"] for k, v in uts.levels.items()} | {OWN: "Describe your own"}
    level = st.segmented_control("Risk level", levels, format_func=names.get, default="medium_high",
                                 key=f"ut_level_{gen}") or "medium_high"
    if level == OWN:
        return _own_unit_trust(fund, gen, held)
    st.caption(uts.levels[level]["blurb"] + " Levels follow each fund's own published risk label (see *About these "
               "funds* below).")
    options = [f.ticker for f in uts.by_risk(level)]
    held_t = {h.ticker for h in held}
    sel = st.selectbox("Unit trust", options, index=None, key=f"ut_pick_{gen}_{level}",
                       placeholder="Choose a fund",
                       format_func=lambda t: ("✓ " if t in held_t else "") + f"{uts.get(t).name} · {uts.get(t).manager}")
    if not sel:
        return NONE
    ut = uts.get(sel)
    with st.container(border=True):
        a, b, c = st.columns(3)
        a.metric("Total expense ratio", C.pct(ut.ter, 2), help=f"Source: {ut.fees_src}.")
        b.metric("Fund size", ut.size.split(" (")[0])
        c.metric("Risk label", ut.risk_label.split(" (")[0])
        st.caption(f"**{ut.asisa}** · benchmark: {ut.benchmark} · since {ut.inception}"
                   + (f" · performance fee {ut.performance_fee}" if ut.performance_fee else ""))
        with st.expander("Asset allocation and sources"):
            allocation_table(ut.allocation)
            if ut.allocation_note:
                st.caption(ut.allocation_note)
            sh = ut.sheet
            host = {"manager": "the manager's site", "discovery": "Discovery's fund library",
                    "momentum": "Momentum's fund library",
                    "easyequities": "EasyEquities' resource site"}.get(sh["host"], sh["host"])
            st.markdown(f"Fact sheet: [{ut.name}, data as at {sh['as_of']}]({sh['url']}) (from {host}, accessed "
                        f"{sh.get('accessed') or uts.meta.get('accessed')}). Fees and size: EasyEquities fund page unless noted.")
    current = next((h for h in held if h.ticker == sel), None)
    methods = ["price_history", "allocation_model", "uploaded"]
    default = current.method if current else ut.method
    method = st.radio("How should the app measure it?", methods, index=methods.index(default), horizontal=True,
                      format_func=lambda m: {"price_history": "Price history", "allocation_model": "Model from allocation",
                                             "uploaded": "Upload prices"}[m], key=f"ut_method_{gen}_{sel}")
    st.caption(METHOD_HELP[method])
    params = ut.params()
    if method == "uploaded":
        pts = _upload(gen, sel) or (current.params.get("prices") if current and current.method == "uploaded" else None)
        if not pts:
            return NONE
        params["prices"] = pts
    amount = _amount(fund, sel, f"amt_{gen}_{sel}")
    return sel, amount, {"name": ut.name, "kind": "unit_trust", "method": method, "params": params}


def _own_unit_trust(fund: Fund, gen: int, held):
    st.caption("For a unit trust not in the list: give its name, and either its asset allocation from the fact "
               "sheet, a price file, or both (the allocation also drives the look-through charts).")
    own = [h for h in held if h.ticker.startswith(unit_trusts.CUSTOM_PREFIX)]
    pick = st.selectbox("Edit one you've added, or start a new one", ["__new__"] + [h.ticker for h in own],
                        format_func=lambda t: "A new unit trust" if t == "__new__" else fund.holding(t).name,
                        key=f"own_pick_{gen}")
    current = fund.holding(pick) if pick != "__new__" else None
    name = st.text_input("Fund name", value=current.name if current else "", key=f"own_name_{gen}_{pick}",
                         placeholder="e.g. Example Balanced Fund").strip()
    if not name:
        return NONE
    ticker = current.ticker if current else unit_trusts.CUSTOM_PREFIX + slug(name)
    prev = (current.params if current else {}) or {}
    method = st.radio("How should the app measure it?", ["allocation_model", "uploaded"], horizontal=True,
                      index=1 if (current and current.method == "uploaded") else 0,
                      format_func=lambda m: {"allocation_model": "Model from allocation", "uploaded": "Upload prices"}[m],
                      key=f"own_method_{gen}_{pick}")
    st.caption(METHOD_HELP[method])
    with st.expander("Asset allocation (% of the fund, from its fact sheet)", expanded=method == "allocation_model"):
        cols = st.columns(2)
        alloc = {}
        for i, (k, (label, _, _)) in enumerate(synthetic.ASSET_CLASSES.items()):
            alloc[k] = cols[i % 2].number_input(label, min_value=-100.0, max_value=200.0, step=1.0,
                                                value=float((prev.get("allocation") or {}).get(k, 0.0)),
                                                key=f"own_{k}_{gen}_{pick}")
        ter = st.number_input("Total expense ratio (%)", 0.0, 5.0, float(prev.get("ter", 0.01)) * 100, 0.05,
                              key=f"own_ter_{gen}_{pick}") / 100
        total = sum(alloc.values())
        st.caption(f"Adds up to {total:.1f}% (rescaled to 100%).")
    params = {"ter": ter}
    if any(v != 0 for v in alloc.values()):
        try:
            params["allocation"] = {k: round(v * 100, 4) for k, v in synthetic.normalise_allocation(alloc).items()}
        except ValueError as e:
            st.error(str(e))
            return NONE
    if method == "allocation_model" and "allocation" not in params:
        st.info("Enter the fund's asset allocation to model it.")
        return NONE
    if method == "uploaded":
        pts = _upload(gen, pick) or (prev.get("prices") if current and current.method == "uploaded" else None)
        if not pts:
            return NONE
        params["prices"] = pts
    amount = _amount(fund, ticker, f"amt_{gen}_{ticker}")
    return ticker, amount, {"name": name, "kind": "unit_trust", "method": method, "params": params}


# ---- unlisted -----------------------------------------------------------------------

def unlisted_picker(fund: Fund, gen: int):
    st.caption("Property developments, private businesses, syndications, loans to a business: things with no "
               "market price. The app never invents a price history for them. You describe them with your own "
               "assumptions, which are used in the whole-fund numbers and simulations below.")
    own = fund.unlisted()
    pick = st.selectbox("Edit one you've added, or start a new one", ["__new__"] + [h.ticker for h in own],
                        format_func=lambda t: "A new unlisted investment" if t == "__new__" else fund.holding(t).name,
                        key=f"ul_pick_{gen}")
    current = fund.holding(pick) if pick != "__new__" else None
    p = {**DEFAULTS, **((current.params if current else {}) or {})}
    name = st.text_input("Name", value=current.name if current else "", key=f"ul_name_{gen}_{pick}",
                         placeholder="e.g. Friend's coffee shop").strip()
    if not name:
        return NONE
    k = f"{gen}_{pick}"
    category = st.selectbox("What is it?", CATEGORIES, index=CATEGORIES.index(p["category"]) if p["category"] in CATEGORIES
                            else len(CATEGORIES) - 1, key=f"ul_cat_{k}")
    c1, c2, c3 = st.columns(3)
    r = c1.number_input("Return a year if it goes to plan (%)", -50.0, 500.0, p["exp_return"] * 100, 1.0, key=f"ul_r_{k}",
                        help="What the promoter projects, or your own estimate, if nothing goes badly wrong.") / 100
    low = c2.number_input("A bad year (%)", -99.0, 500.0, p["low"] * 100, 1.0, key=f"ul_lo_{k}",
                          help="A poor year if it survives: roughly a 1-in-20 bad year.") / 100
    high = c3.number_input("A good year (%)", -99.0, 1000.0, p["high"] * 100, 1.0, key=f"ul_hi_{k}",
                           help="A strong year: roughly a 1-in-20 good year.") / 100
    c4, c5, c6 = st.columns(3)
    lock = c4.number_input("Locked in for (years)", 0.0, 50.0, float(p["lockin_years"]), 0.5, key=f"ul_lock_{k}",
                           help="How long before you could get your money out. 0 if you can withdraw any time.")
    ploss = c5.number_input("Chance a year of losing everything (%)", 0.0, 99.0, p["p_loss"] * 100, 0.5,
                            key=f"ul_pl_{k}", help="Failure, fraud or collapse. 2% a year is about 1 in 50.") / 100
    corr = c6.slider("Moves with your listed holdings (correlation)", -1.0, 1.0, float(p["corr"]), 0.05,
                     key=f"ul_rho_{k}", help="0.5 by default: most businesses do worse when the economy and "
                                             "markets do.")
    try:
        a = Assumptions(r, low, high, lock, ploss, corr, category)
    except ValueError as e:
        st.error(str(e)[0].upper() + str(e)[1:] + ".")
        return NONE
    with st.container(border=True):
        m1, m2, m3 = st.columns(3)
        m1.metric("Expected return after the loss chance", C.pct(a.expected_return),
                  help="(1 − chance of loss) × (1 + return if it goes to plan) − 1")
        m2.metric("Volatility if it survives", C.pct(a.vol_if_survives),
                  help="(good year − bad year) ÷ (2 × 1.645): the 1-in-20 years taken as a 90% range.")
        horizon = max(lock, 1.0)
        m3.metric(f"Chance it's lost within {horizon:g} year{'s' if horizon != 1 else ''}", C.pct(a.p_lost_over(horizon)),
                  help="1 − (1 − yearly chance)^years")
    for w in a.warnings():
        st.warning(w, icon=":material/report:")
    ticker = current.ticker if current else "UL:" + slug(name)
    if not current and fund.holding(ticker):
        ticker += f"-{len(own) + 1}"
    amount = _amount(fund, ticker, f"amt_{gen}_{ticker}")
    return ticker, amount, {"name": name, "kind": "unlisted", "method": "assumptions", "params": a.to_params()}


def method_label(method: str) -> str:
    return {"price_history": "Price history", "uploaded": "Uploaded prices", "allocation_model": "Modelled",
            "assumptions": "Your assumptions"}.get(method, METHODS.get(method, method))
