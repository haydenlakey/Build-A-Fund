"""Build your fund: add, resize and remove holdings, and see what each change does."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from fundlab import data, verdict
from fundlab.analysis import Comparison
from fundlab.model import HOLDING_KINDS, Fund
from ui import cached, charts, state
from ui import components as C

OTHER = "__other__"

RR_WHAT = """
Each grey dot is one holding: further right means it swings more, higher up means it has
earned more on average (in rand, after converting US holdings at the USD/ZAR rate).

The blue line is the **efficient frontier**: for each level of expected return, the lowest
risk you could have had by mixing *these same holdings* in different proportions (no borrowing,
no short selling). A fund on the line can't lower its risk without giving up return.

The orange dot is your fund. When you preview a change, the hollow dot shows where the fund
was, and the arrow shows where the change takes it. **Up and to the left is better**: more
return for less risk. Moving toward the blue line means the mix became more efficient.

Expected returns come from history and are very uncertain, so treat the vertical positions
as rough. The horizontal positions (risk) are estimated much more reliably.
"""

RR_MATHS = r"""
With weights $w$ (from your rand amounts), annualised expected returns $\mu$ and covariance
matrix $\Sigma$ estimated from weekly returns:

$$\mu_p = w^\top \mu, \qquad \sigma_p = \sqrt{w^\top \Sigma\, w}$$

The frontier solves, for a grid of target returns $m$,

$$\min_w \; w^\top \Sigma\, w \quad \text{s.t.} \quad w^\top \mu = m,\;\; \mathbf{1}^\top w = 1,\;\; w \ge 0.$$

The *efficiency gap* is $\sigma_p - \sigma_{\text{frontier}}(\mu_p)$: how much extra volatility the
fund carries compared with the best mix of the same holdings at the same expected return.
Before and after are both measured on the same weeks and against the same frontier (built from
every holding in either version).

Expected returns are shrunk toward an equal-Sharpe prior:
$\hat\mu_i = (1-a)\,\bar r_i + a\,(r_f + S\,\hat\sigma_i)$, where $\bar r_i$ is the historical
mean, $a$ the shrinkage and $S$ the prior Sharpe ratio (both in *Assumptions and settings*).
"""


def holding_picker(fund: Fund):
    """Returns (ticker, amount) for the change being considered, or (None, None)."""
    uni = cached.universe()
    held = [h.ticker for h in fund.holdings]
    options = held + [t for t in uni.entries if t not in held] + [OTHER]
    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    sel = c1.selectbox(
        "Search for a share or ETF", options, index=None, key="pick",
        placeholder="Type a name or ticker, e.g. Naspers or NPN",
        format_func=lambda t: "Another JSE or US ticker…" if t == OTHER else
        ("✓ " if t in held else "") + cached.label(t))
    ticker = sel
    if sel == OTHER:
        raw = c1.text_input("Ticker", placeholder="JSE tickers end in .JO, e.g. KIO.JO; US tickers have no suffix, e.g. AAPL",
                            key="other_ticker").strip().upper()
        if not raw:
            return None, None
        if not data.is_supported(raw):
            st.error("Only JSE tickers (ending in .JO) and US-listed tickers are supported.")
            return None, None
        ticker = raw
    if not ticker:
        return None, None
    current = float(fund.amounts().get(ticker, 0.0))
    amount = c2.number_input("Rand amount", min_value=0.0, value=current or 1000.0, step=100.0,
                             format="%.2f", key=f"amt_{ticker}",
                             help="How many rand you'd put into this holding. Set it to 0 to remove it.")
    return ticker, amount


def apply(new: Fund, message: str) -> None:
    state.put(new)
    for k in [k for k in st.session_state if str(k).startswith("amt_")] + ["pick", "other_ticker"]:
        st.session_state.pop(k, None)
    st.toast(message, icon=":material/check:")
    st.rerun()


def history_notes(cmp: Comparison, fund: Fund) -> None:
    rep = cmp.est.report
    if rep.start is not None:
        st.caption(f"Statistics use {rep.n_weeks} weeks of returns, {rep.start:%d %b %Y} to "
                   f"{rep.end:%d %b %Y}, all in rand.")
        if rep.limited_by:
            st.caption(f"The window starts later than your chosen lookback because "
                       f"**{cached.name_of(rep.limited_by, fund)}** only has prices from {rep.start:%b %Y}.")
        if rep.is_short:
            st.warning(f"Only {rep.n_weeks} weeks of shared history (under three years). Every number here is "
                       "rough, and the expected returns especially so.", icon=":material/history:")
    for t, why in rep.excluded.items():
        st.warning(f"**{cached.name_of(t, fund)}** is left out of the statistics: {why} Its rands still count "
                   "toward the fund's size.", icon=":material/warning:")


def holdings_table(fund: Fund, cmp: Comparison) -> None:
    stats = cmp.after
    w = fund.weights()
    if w.empty:
        return
    risk = stats.risk_shares * stats.coverage if stats is not None else pd.Series(dtype=float)
    rows = []
    for t, amt in fund.amounts().sort_values(ascending=False).items():
        h = fund.holding(t)
        # most important columns first: on a phone the right-hand columns scroll off-screen
        rows.append({"Holding": cached.name_of(t, fund), "Amount": C.rand(amt, 2), "Share of rands": w[t] * 100,
                     "Share of risk": risk.get(t, float("nan")) * 100, "Ticker": t,
                     "Type": HOLDING_KINDS[h.kind]})
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Amount": st.column_config.TextColumn(),
        "Share of rands": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
        "Share of risk": st.column_config.ProgressColumn(
            format="%.1f%%", min_value=0, max_value=100,
            help="Each holding's contribution to the fund's volatility. Holdings that swing a lot, or move with "
                 "everything else, take a bigger share of the risk than of the rands."),
    })
    st.caption(f"Total: {C.rand(fund.total_zar, 2)} across {len(rows)} holding{'s' if len(rows) != 1 else ''}.")


# ---------------------------------------------------------------------------------

fund = state.active()
st.title("Build your fund")
C.disclaimer()

name = st.text_input("Fund name", fund.name, max_chars=60)
if name != fund.name:
    fund = fund.copy(keep_id=True, name=name)
    state.put(fund)

st.subheader("Add, resize or remove a holding")
ticker, amount = holding_picker(fund)

after, moved = fund, False
if ticker:
    uni = cached.universe()
    failures = cached.store().ensure([ticker])
    if ticker in failures:
        st.error(f"Couldn't get prices for {ticker}: {failures[ticker]}")
    else:
        e = uni.get(ticker)
        after = fund.with_amount(ticker, amount, name=cached.name_of(ticker, fund), kind=uni.kind_of(ticker),
                                 currency=e["currency"] if e else ("ZAR" if ticker.endswith(".JO") else "USD"))
        moved = after.amounts().round(2).to_dict() != fund.amounts().round(2).to_dict()

if not fund.holdings and not moved:
    st.info("Start by searching for a holding above and entering a rand amount, or open an example.",
            icon=":material/lightbulb:")
    if st.button("Open the example fund"):
        state.put(state.example_fund())
        st.rerun()
    st.stop()

with st.spinner("Crunching the numbers…"):
    cmp = cached.compare(fund, after)

if moved:
    st.subheader("What does this change do?")
    v = verdict.explain(cmp, ticker, cached.name_of(ticker, fund))
    with st.container(border=True):
        st.markdown(f"**{v.headline}**")
        for d in v.details:
            st.markdown(f"- {d}")
        held_now = ticker in fund.amounts().index
        verb = {"add": "Add it", "increase": "Apply the increase", "decrease": "Apply the cut",
                "remove": "Remove it"}.get(v.action, "Apply")
        b1, b2, _ = st.columns([1, 1, 2])
        if b1.button(verb, type="primary", width="stretch"):
            apply(after, f"{v.action.title()}: {cached.name_of(ticker, fund)}")
        if held_now and amount > 0 and b2.button("Remove instead", width="stretch"):
            apply(fund.without(ticker), f"Removed {cached.name_of(ticker, fund)}")
    st.caption("Numbers below show **after** the change, with the change from before underneath. "
               "Nothing is applied until you press the button.")
else:
    st.subheader("Your fund at a glance")

C.metric_panel(cmp, after.settings, moved)
history_notes(cmp, after)

st.subheader("Risk and return")
names = {t: cached.name_of(t, after) for t in cmp.est.mu.index}
fig = charts.risk_return(cmp, names, moved)
st.plotly_chart(fig, config={"displayModeBar": False, "scrollZoom": False}, key="rr_chart")
C.chart_notes(RR_WHAT, RR_MATHS, "rr")

st.subheader("Holdings" + (" after the change" if moved else ""))
holdings_table(after, cmp)
src = cached.store()
st.caption(f"Prices: Yahoo Finance weekly closes (dividends reinvested), bundled dataset to "
           f"{src.sample_date}. JSE prices converted from cents; US prices converted at USD/ZAR.")
