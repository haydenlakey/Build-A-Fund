"""Compare funds side by side: the same numbers for each, measured on one shared history window."""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from fundlab import unlisted
from ui import cached, charts, state
from ui import components as C

CHART_CONFIG = {"displayModeBar": False, "scrollZoom": False}
MAX_FUNDS = 4

INTRO = """
Put up to four of your funds next to each other. Every number is measured over **one shared window**, the weeks
that all the funds' holdings have prices for, and with **one set of assumptions** (the active fund's), so the
differences come from what the funds hold and not from different periods or settings.
"""

RR_WHAT = """
Each coloured dot is one of your funds; the grey dots are the holdings they're made of. The dotted line is the
**efficient frontier** of all those holdings together: the lowest risk any mix of them could have had for each level
of expected return (no borrowing, no short selling). Further left means steadier; higher means a higher historical
average return. Expected returns are rough (see the ± range in the table); the left-right positions are much more
reliable.
"""

RR_MATHS = r"""
Each fund $k$ with weights $w_k$ (from its rand amounts, measured holdings only) has
$\mu_k = w_k^\top\mu$ and $\sigma_k = \sqrt{w_k^\top\Sigma w_k}$, where $\mu$ and $\Sigma$ are estimated once, on the
shared window, for the union of the funds' holdings. *Extra risk vs the frontier* is $\sigma_k - \sigma^*(\mu_k)$, the
frontier's volatility at the same expected return.
"""

GROWTH_WHAT = """
R1 000 in each fund at the start of the shared window, rebalanced every week back to today's weights. It shows how
differently the funds behaved along the way (the falls and recoveries), not what they will do next. Every fund here
was built today with hindsight, which flatters whatever did well recently.
"""

GROWTH_MATHS = r"""
$V_t = 1000\prod_{u \le t}(1 + w_k^\top r_u)$ with weekly simple returns $r_u$ over the shared window. No trading
costs; fund charges are already inside ETF and unit trust prices.
"""


def fund_label(f) -> str:
    return f.name or "Untitled fund"


def metric_rows(funds, mc, settings) -> pd.DataFrame:
    h = settings.var_horizon_weeks
    var_label = f"{'1-month' if h == 4 else f'{h}-week'} VaR ({settings.var_alpha:.0%})"
    rows = {}
    for f, s, gap in zip(funds, mc.stats, mc.gaps):
        comp = cached.compose(f)
        col = {
            "Rands": C.rand(f.total_zar),
            "Holdings": str(len(f.weights())),
            "Share measured by history": C.pct(s.coverage, 0) if s else "–",
            "Expected return": f"{C.pct(s.exp_return)} ± {C.pct(1.96 * s.exp_return_se, 0)}" if s else "–",
            "Volatility": C.pct(s.vol) if s else "–",
            "Sharpe ratio": f"{s.sharpe:.2f}" if s else "–",
            "Worst fall": C.pct(s.max_drawdown) if s else "–",
            var_label: C.pct(s.var) if s else "–",
            "Diversification ratio": f"{s.div_ratio:.2f}" if s else "–",
            "Effective holdings": f"{s.eff_holdings:.1f}" if s else "–",
            "Average correlation": f"{s.avg_corr:.2f}" if s else "–",
            "Extra risk vs the frontier": "–" if not s or math.isnan(gap) else f"{gap * 100:.1f} pp",
            "Shares (looked through)": C.pct(comp.by_asset.get("equity", 0.0), 0),
            "Largest holding": f"{cached.name_of(comp.largest[0], f)} {comp.largest[1]:.0%}" if comp.largest[0] else "–",
            "Fund charges a year": f"{comp.weighted_ter + comp.weighted_tc:.2%}",
            "Can't be sold in a hurry": C.pct(unlisted.illiquid_share(f), 0),
        }
        rows[fund_label(f)] = col
    return pd.DataFrame(rows)


st.title("Compare funds")
C.disclaimer()
st.markdown(INTRO)

ss = st.session_state
funds_all = {i: f for i, f in ss.funds.items() if f.holdings}
if len(funds_all) < 2:
    st.info("You need at least two funds with holdings. Use **Copy** in the sidebar to duplicate this fund and change "
            "the copy, open a saved fund, or make a copy with a new holding on the *Explore diversifiers* page.",
            icon=":material/lightbulb:")
    st.page_link("views/explore.py", label="Explore diversifiers", icon=":material/travel_explore:")
    st.stop()

ids = list(funds_all)
default = ([ss.active] if ss.active in funds_all else []) + [i for i in reversed(ids) if i != ss.active]
chosen = st.multiselect("Funds to compare", ids, default=default[:MAX_FUNDS], max_selections=MAX_FUNDS,
                        format_func=lambda i: fund_label(funds_all[i]), key="cmp_funds")
if len(chosen) < 2:
    st.info("Pick at least two funds.")
    st.stop()
funds = [funds_all[i] for i in chosen]
if len({fund_label(f) for f in funds}) < len(funds):  # make duplicate names distinguishable
    seen = {}
    for f in funds:
        seen[fund_label(f)] = seen.get(fund_label(f), 0) + 1
    funds = [f.copy(keep_id=True, name=f"{fund_label(f)} ({f.id[:4]})") if seen[fund_label(f)] > 1 else f
             for f in funds]
settings_from = state.active() if ss.active in chosen else funds[0]

with st.spinner("Measuring the funds together…"):
    mc = cached.compare_many(funds, settings_from)
rep = mc.est.report
if rep.start is None:
    st.warning("None of these funds' holdings has enough price history to measure.")
    st.stop()
st.caption(f"Shared window: {rep.start:%d %b %Y} to {rep.end:%d %b %Y} ({rep.n_weeks / 52:.1f} years). "
           f"Assumptions from **{fund_label(settings_from)}**.")
if rep.limited_by:
    st.caption(f"The window starts when {cached.name_of(rep.limited_by)} begins trading; the funds without it are "
               "measured over the same shorter window.")

st.subheader("The numbers side by side")
table = metric_rows(funds, mc, settings_from.settings)
st.dataframe(table, width="stretch", height=C.table_height(len(table)))
excluded = {t: r for s in mc.stats if s for t, r in s.excluded.items()}
if excluded:
    with st.expander(f"Holdings left out of the history-based numbers ({len(excluded)})"):
        for t, r in excluded.items():
            st.markdown(f"- **{cached.name_of(t)}**: {r}")

names = {t: cached.name_of(t) for t in mc.est.mu.index}
labels = [fund_label(f) for f in funds]
st.subheader("Risk and return")
st.plotly_chart(charts.funds_risk_return(mc, labels, names), config=CHART_CONFIG, key="cmp_rr")
C.chart_notes(RR_WHAT, RR_MATHS, "cmp_rr")

st.subheader("How they would have moved")
lines = {fund_label(f): (1 + s.port_returns).cumprod() for f, s in zip(funds, mc.stats) if s is not None}
st.plotly_chart(charts.backtest_lines(lines, 1000.0), config=CHART_CONFIG, key="cmp_growth")
C.chart_notes(GROWTH_WHAT, GROWTH_MATHS, "cmp_growth")

st.subheader("What each one holds")
amounts = pd.DataFrame({fund_label(f): f.weights() for f in funds}).fillna(0.0)
amounts = amounts.loc[amounts.max(axis=1).sort_values(ascending=False).index]
held_by = (amounts > 0).sum(axis=1)
st.dataframe(pd.concat([pd.Series([cached.name_of(t) for t in amounts.index], index=amounts.index, name="Holding"),
                        amounts * 100,
                        held_by.map(lambda n: "all" if n == len(funds) else str(n)).rename("In how many")], axis=1),
             hide_index=True, width="stretch", height=C.table_height(min(len(amounts), 20)),
             column_config={c: st.column_config.NumberColumn(format="%.1f%%") for c in amounts.columns})
st.caption("Share of each fund's rands. Funds can also overlap through the companies inside their ETFs and unit "
           "trusts; *What kind of fund is it?* shows that for one fund at a time.")
