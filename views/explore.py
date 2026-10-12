"""Explore diversifiers: which holdings in the preset universe would historically have lowered the fund's risk most."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from fundlab.model import HOLDING_KINDS
from ui import cached, charts, glossary, state
from ui import components as C

CHART_CONFIG = {"displayModeBar": False, "scrollZoom": False}
KINDS = ["jse_share", "jse_etf", "us_share", "us_etf"]

INTRO = """
This page takes every share and ETF in the app's preset list that your fund doesn't already hold, adds the same
rand amount of each one to your fund in turn, and measures what that would have done to the fund's **volatility**
over the fund's own history window. It is a way to **explore** how diversification works, not a list of things to
buy: the past relationships it measures can change, and a holding that lowers risk often lowers expected return too.
"""

BARS_WHAT = """
Each bar is one holding from the preset list, added with the rand amount you chose. A **blue** bar to the left
means the fund's volatility would have been lower with it; a **red** bar to the right means higher. The holdings
that lowered risk most are at the top.

Two things drive the result: how much the holding swings on its own, and how closely it moved with what you already
own. A holding that swings a lot can still lower the fund's risk if it tended to move differently from the rest.

These are historical measurements over one window, and correlations change: in 2022 shares and bonds, which usually
offset each other, fell together (see the case file below). The expected-return column in the table is far less
reliable than the volatility.
"""

BARS_MATHS = r"""
With the fund's measured weights $w$, covariance $\Sigma$ (estimated on the fund's window for the fund's holdings and
all candidates together, with the covariance method in your settings), and $x$ rands added to candidate $c$ on top of
the measured part of the fund worth $T$, let $s = x/(T+x)$. Then

$$\sigma'^2 = (1-s)^2\, w^\top\Sigma w + 2s(1-s)\,(\Sigma w)_c + s^2\,\Sigma_{cc}, \qquad
\mu' = (1-s)\, w^\top\mu + s\,\mu_c .$$

The bar is $\sigma' - \sigma$. At the margin ($s \to 0$),
$\dfrac{d\sigma'}{ds} = \sigma\,(\beta_c - 1)$ with $\beta_c = (\Sigma w)_c / \sigma^2$, the candidate's **beta to your
fund**: anything with a beta below 1 lowers the fund's risk when a little of it is added, whatever its own volatility.

Because one covariance matrix is estimated for the fund and every candidate, the "now" volatility here can differ
from the Build page's in the second decimal (Ledoit-Wolf shrinkage depends on the set of assets).
"""

SCATTER_WHAT = """
Every candidate as a dot: across, how closely its weekly returns moved with your fund's; down, how much it would
have lowered the fund's volatility. The dots slope upward: the lower the correlation, the more a holding tends to
lower risk. Holdings with the same correlation sit at different heights because of their own volatility, which
matters more as the amount added grows.
"""

SCATTER_MATHS = r"""
Correlation $\rho_c = (\Sigma w)_c / (\sigma_c\,\sigma)$. The beta in the maths above is $\beta_c = \rho_c\,\sigma_c/\sigma$,
so a holding lowers risk at the margin when $\rho_c < \sigma / \sigma_c$.
"""


def link(slug: str) -> None:
    lib = cached.library()
    if slug in lib:
        st.page_link("views/library.py", label=f"Read more: {lib[slug].title}", icon=":material/menu_book:",
                     query_params={"article": slug})


def add_copy(fund, ticker: str, amount: float) -> None:
    """A copy of the fund with the candidate added, stored beside it (the active fund doesn't change)."""
    uni = cached.universe()
    e = uni.get(ticker)
    name = e["name"] if e else ticker
    copy = fund.copy(name=f"{fund.name} + {name}")
    copy = copy.with_amount(ticker, amount, name=name, kind=uni.kind_of(ticker), currency=e["currency"])
    st.session_state.funds[copy.id] = copy
    st.session_state.explore_made = copy.name


st.title("Explore diversifiers")
C.disclaimer()
glossary.markdown(INTRO)

fund = state.active()
if not fund.holdings:
    st.info("Build a fund first: this page measures other holdings against the ones you have.",
            icon=":material/lightbulb:")
    st.stop()

default = float(max(100, round(fund.total_zar * 0.1 / 100) * 100))
c1, c2 = st.columns(2)
add = c1.number_input("Rand amount to add of each", 100.0, 10_000_000.0, default, 100.0, key="ex_amount",
                      help="The same amount is added to each candidate in turn, as new money (nothing is sold). "
                           "Starts at about 10% of your fund.")
kinds = c2.multiselect("Types to include", KINDS, default=KINDS, format_func=HOLDING_KINDS.get, key="ex_kinds")
show = st.select_slider("How many to list", [5, 10, 15, 20, 30], value=15, key="ex_n")

with st.spinner("Trying every holding in the preset list…"):
    ex = cached.diversifier_scan(fund, add)
if ex is None:
    st.info("None of the fund's holdings has enough price history to measure, so there's nothing to compare against.")
    st.stop()

uni = cached.universe()
table = ex.table[[uni.kind_of(t) in kinds for t in ex.table.index]]
if table.empty:
    st.info("No holdings of the chosen types to compare.")
    st.stop()
names = {t: cached.name_of(t) for t in table.index}
top = table.head(show)

cols = st.columns(4)
for col, (label, value, cap) in zip(cols, [
    ("Fund volatility now", C.pct(ex.vol_before), "measured part of the fund"),
    ("Lowest after adding one", C.pct(top["vol_after"].iloc[0]), names[top.index[0]]),
    ("Holdings compared", f"{len(table)}", f"{len(ex.skipped)} skipped (short history)" if ex.skipped else "none skipped"),
    ("Window", f"{ex.n_weeks / 52:.1f} years", f"{ex.start:%b %Y} to {ex.end:%b %Y}"),
]):
    with col.container(border=True, height="stretch"):
        st.metric(label, value)
        st.caption(cap)
st.caption(f"Adding {C.rand(add)} makes each candidate {ex.add_share:.0%} of the measured fund. "
           f"{(table['d_vol'] < 0).sum()} of {len(table)} would have lowered its volatility.")

st.subheader("Which holdings would have lowered the fund's risk most?")
st.plotly_chart(charts.diversifier_bars(top, names), config=CHART_CONFIG, key="ex_bars")
C.chart_notes(BARS_WHAT, BARS_MATHS, "ex_bars")

st.dataframe(pd.DataFrame({
    "Holding": [names[t] for t in top.index],
    "Ticker": top.index,
    "Type": [HOLDING_KINDS[uni.kind_of(t)] for t in top.index],
    "Its own volatility": top["vol"] * 100,
    "Correlation with your fund": top["corr"],
    "Beta to your fund": top["beta"],
    "Fund volatility after": top["vol_after"] * 100,
    "Change in volatility": top["d_vol"] * 100,
    "Change in expected return": top["d_ret"] * 100,
}), hide_index=True, width="stretch", height=C.table_height(len(top)), column_config={
    "Its own volatility": st.column_config.NumberColumn(format="%.1f%%"),
    "Correlation with your fund": st.column_config.NumberColumn(format="%.2f"),
    "Beta to your fund": st.column_config.NumberColumn(format="%.2f"),
    "Fund volatility after": st.column_config.NumberColumn(format="%.1f%%"),
    "Change in volatility": st.column_config.NumberColumn(format="%+.2f pp"),
    "Change in expected return": st.column_config.NumberColumn(
        format="%+.2f pp", help="From the same shrunk historical averages as the Build page: very uncertain."),
})

st.subheader("Why: how closely each one moved with your fund")
st.plotly_chart(charts.diversifier_scatter(table, names, list(top.index)), config=CHART_CONFIG, key="ex_scatter")
C.chart_notes(SCATTER_WHAT, SCATTER_MATHS, "ex_scatter")

st.subheader("Try one out")
st.caption("Makes a copy of your fund with the holding added, so you can put the two side by side. "
           "Your current fund doesn't change.")
t1, t2 = st.columns([3, 1], vertical_alignment="bottom")
pick = t1.selectbox("Holding", list(top.index), format_func=lambda t: f"{names[t]} ({t})", key="ex_pick")
t2.button("Make a copy with it", on_click=add_copy, args=(fund, pick, add), width="stretch")
if made := st.session_state.pop("explore_made", None):
    st.success(f"Made **{made}**. It's in *Your funds* in the sidebar.", icon=":material/check:")
    st.page_link("views/compare.py", label="Compare them side by side", icon=":material/compare:")

if ex.skipped:
    with st.expander(f"Skipped: {len(ex.skipped)} holdings without prices for the whole window"):
        st.dataframe(pd.DataFrame({"Holding": [cached.name_of(t) for t in ex.skipped], "Ticker": list(ex.skipped),
                                   "Why": list(ex.skipped.values())}), hide_index=True, width="stretch")
        st.caption("A shorter window under *Assumptions and settings* (History to use) lets more of them in.")

link("diversification")
link("stocks-bonds-2022")
