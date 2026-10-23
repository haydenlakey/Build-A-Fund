"""Against a benchmark: active weights, tracking error, its budget, and the rules of thumb."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import streamlit as st

from fundlab import active
from ui import cached, charts, glossary, state
from ui import components as C

CHART_CONFIG = {"displayModeBar": False, "scrollZoom": False}

INTRO = """
A **benchmark** is what you'd have held without making any choices, for example simply the
whole JSE Top 40. Every place your fund differs from it is an **active bet**: holding more of
something (an *overweight*) or less of it (an *underweight*). **Tracking error** measures how far
your fund's return typically strays from the benchmark's in a year. It is the risk you take by
being different, separate from the risk of the market itself.
"""

WEIGHTS_WHAT = """
Each bar is one holding's **active weight**: your weight minus the benchmark's. Blue bars point
right (you hold more than the benchmark), red bars point left (you hold less). They always add up
to zero, because every rand you put somewhere else is a rand not in the benchmark.

If you hold the benchmark's own ETF (e.g. Satrix 40 against the Top 40), it nets off: holding half
your fund in it shows as an underweight of the other half. A share that is also inside the
benchmark, such as Naspers inside the Top 40, shows as a bet *on top of* the index, which is what it is.
"""

WEIGHTS_MATHS = r"""
With fund weights $w_F$ and benchmark weights $w_B$ over the same assets, active weights are
$a = w_F - w_B$, with $\sum_i a_i = 0$. The fund's return minus the benchmark's is exactly $a^\top r$,
so the tracking error is

$$TE = \sqrt{a^\top \Sigma\, a},$$

using the covariance matrix $\Sigma$ from *Assumptions and settings* (annualised, weekly rand returns).
The fund's **beta to the benchmark** is $\beta = w_F^\top \Sigma w_B \,/\, w_B^\top \Sigma w_B$.
"""

BUDGET_WHAT = """
How much of your tracking error each bet is responsible for. The shares add to 100%. A bet can
take far more of the budget than its size suggests if it is volatile or unlike the benchmark,
and a bet that moves against your other bets takes a **negative** share (it partly cancels them).

When one bet takes most of the budget, your result against the benchmark mostly depends on
whether that single call works out.
"""

BUDGET_MATHS = r"""
The share of tracking-error *variance* from bet $i$ is

$$s_i = \frac{a_i\,(\Sigma a)_i}{a^\top \Sigma\, a}, \qquad \sum_i s_i = 1 .$$

This is the same Euler decomposition used for each holding's share of total risk, applied to active weights.
"""

RULE_MATHS = r"""
**Average-volatility, average-correlation approximation.** If every asset had the same volatility
$\bar\sigma$ and every pair the same correlation $\bar\rho$, and the active weights sum to zero, then

$$TE^2 = \bar\sigma^2 (1-\bar\rho) \sum_i a_i^2 \quad\Rightarrow\quad TE \approx \bar\sigma\sqrt{1-\bar\rho}\;\lVert a\rVert .$$

Here $\bar\sigma$ is the $|a_i|$-weighted average volatility and $\bar\rho$ the $|a_i a_j|$-weighted average
pairwise correlation of the assets you bet on. It is exact only when vols and correlations really are equal,
so the gap to the exact figure shows how uneven your bets are.

**Pairwise bet sizing.** Going $w$ over asset A and $w$ under asset B (volatilities $\sigma_A, \sigma_B$,
correlation $\rho$) gives $TE = w\sqrt{\sigma_A^2 + \sigma_B^2 - 2\rho\,\sigma_A\sigma_B}$. For a target tracking
error $T$:

$$w = \frac{T}{\sqrt{\sigma_A^2 + \sigma_B^2 - 2\rho\,\sigma_A\sigma_B}}, \qquad
\text{A's share of TE variance} = \frac{\sigma_A^2 - \rho\,\sigma_A\sigma_B}{\sigma_A^2 + \sigma_B^2 - 2\rho\,\sigma_A\sigma_B}.$$

Example: with $T = 1\%$, $\sigma_A = 21\%$, $\sigma_B = 8\%$ and $\rho = -0.01$, the pair is about 4.4% each way,
and about 87% of the tracking-error variance comes from the more volatile side.
"""

RULES_WHAT = """
Professionals often size bets with two quick approximations instead of a full covariance matrix.
The **rule-of-thumb tracking error** (top of the page) pretends every asset is equally volatile and
equally correlated; the closer it is to the exact figure, the more even your bets are. The **pairwise
rule** answers "how big can one overweight-underweight pair be for a given tracking error?" using only
two volatilities and one correlation.
"""

IR_WHAT = """
**Expected active return** is your fund's expected return minus the benchmark's, from the same
historical averages (shrunk toward a prior) as the Build page. It is the least reliable number
here: a few years of history can't tell skill from luck. The **information ratio** divides it by
the tracking error, giving the reward per unit of active risk. The *Fundamental Law of Active
Management* links a sustained information ratio to how good each call is and how many independent
calls are made. Historically, few professional managers keep a high one for long.
"""


def headline(rep: active.ActiveReport, bench_name: str) -> None:
    c = st.columns(4)
    with c[0].container(border=True, height="stretch"):
        st.metric("Tracking error", C.pct(rep.te), help="How far the fund's yearly return typically strays from the "
                  "benchmark's (annualised standard deviation of the difference).")
        st.caption("exact, from the full covariance matrix")
    with c[1].container(border=True, height="stretch"):
        st.metric("Rule-of-thumb estimate", C.pct(rep.te_rule), help="Assumes every asset has the same volatility "
                  "and correlation. See the maths below.")
        st.caption(f"avg vol {C.pct(rep.avg_vol, 0)}, avg correlation {rep.avg_corr:.2f}"
                   if not math.isnan(rep.avg_corr) else f"avg vol {C.pct(rep.avg_vol, 0)}")
    with c[2].container(border=True, height="stretch"):
        st.metric("Beta to the benchmark", f"{rep.beta:.2f}", help="How much the fund has moved per 1% move in the "
                  "benchmark. Below 1 means it has swung less.")
    with c[3].container(border=True, height="stretch"):
        st.metric("Information ratio", "–" if math.isnan(rep.info_ratio) else f"{rep.info_ratio:.2f}",
                  help="Expected active return divided by tracking error. Treat with great caution.")
        st.caption(f"expected active return {rep.exp_active * 100:+.1f} pp a year")
    if rep.te < 0.005:
        st.caption(f"Your fund is very close to the {bench_name}: almost all of its risk is the market's own.")
    elif rep.te > 0.08:
        st.caption(f"A tracking error of {rep.te:.0%} is large: in about one year in three, the fund would be "
                   f"expected to beat or trail the {bench_name} by more than {rep.te:.0%}.")
    else:
        st.caption(f"In about two years out of three, the fund's return would be expected to land within "
                   f"{rep.te:.1%} of the {bench_name}'s (if returns were roughly normal).")


def pairwise(rep: active.ActiveReport, names: dict[str, str]) -> None:
    st.subheader("Rule of thumb: sizing one pair of bets")
    over = rep.active[rep.active > 0]
    under = rep.active[rep.active < 0]
    if over.empty or under.empty:
        return
    A, B = over.idxmax(), under.idxmin()
    sd = np.sqrt(np.diag(rep.cov.to_numpy()))
    idx = list(rep.cov.index)
    sa, sb = sd[idx.index(A)], sd[idx.index(B)]
    rho = float(rep.cov.loc[A, B] / (sa * sb))
    target = st.slider("Tracking error you'd accept from this one pair (% a year)", 0.5, 10.0, 1.0, 0.5,
                       key="te_target") / 100
    pb = active.pairwise_bet(target, sa, sb, rho)
    st.markdown(f"Take your biggest overweight, **{names[A]}** (volatility {sa:.0%}), against your biggest "
                f"underweight, **{names[B]}** (volatility {sb:.0%}); their correlation is {rho:.2f}. "
                f"Going **{pb['bet_size']:.1%} over one and {pb['bet_size']:.1%} under the other** would use "
                f"{target:.1%} of tracking error. {names[A]} would supply {pb['share_long']:.0%} of that pair's "
                f"tracking-error variance and {names[B]} {pb['share_short']:.0%}.")
    actual = min(over[A], -under[B])
    st.caption(f"Your actual pair is {actual:.1%} each way, about {actual / pb['bet_size']:.1f}× the size that would "
               f"use {target:.1%} on its own.")


# ---------------------------------------------------------------------------------

fund = state.active()
st.title("Against a benchmark")
C.disclaimer()
glossary.markdown(INTRO)

if not fund.holdings:
    st.info("This fund is empty. Add holdings on the **Build your fund** page, or open the example fund there.",
            icon=":material/lightbulb:")
    st.stop()

key = C.pick_benchmark(fund)
bench_name = cached.universe().benchmarks[key]["name"]
with st.spinner("Comparing with the benchmark…"):
    rep, hist, missing = cached.active_report(fund, key)
if rep is None:
    if missing:
        st.warning(f"Not enough price history for the benchmark ({', '.join(missing)}) in the chosen window.")
    else:
        st.warning("Not enough shared price history to compare this fund with the benchmark.")
    st.stop()
if hist.start is not None:
    st.caption(f"Measured on {hist.n_weeks} weeks, {hist.start:%d %b %Y} to {hist.end:%d %b %Y}, in rand.")
for t, why in hist.excluded.items():
    st.caption(f"{cached.name_of(t, fund)} is left out: {why}")

headline(rep, bench_name)
names = {t: cached.name_of(t, fund) + (" (benchmark)" if t in rep.bench_w.index else "") for t in rep.active.index}

st.subheader("Your active bets")
st.plotly_chart(charts.active_bars(rep.active, names), config=CHART_CONFIG, key="active_w")
C.chart_notes(WEIGHTS_WHAT, WEIGHTS_MATHS, "aw")

st.subheader("Where the tracking error comes from")
st.plotly_chart(charts.budget_bars(rep.budget, names), config=CHART_CONFIG, key="te_budget")
top, share = rep.top_bet
if share > 0.6 and top in rep.bench_w.index and rep.active[top] < 0:
    st.warning(f"{share:.0%} of your tracking error comes from holding {-rep.active[top]:.0%} less of "
               f"**{cached.name_of(top, fund)}** than the benchmark does. That gap is the flip side of everything you "
               f"hold instead: the further your other holdings behave from the {bench_name}, the more it costs in "
               "tracking error.", icon=":material/target:")
elif share > 0.6:
    st.warning(f"**{names[top]}** accounts for {share:.0%} of your tracking error: your result against the "
               f"{bench_name} rides mostly on this one bet.", icon=":material/target:")
if st.toggle("Show as a table", key="active_table"):
    st.dataframe(pd.DataFrame({
        "Holding": [names[t] for t in rep.active.index],
        "Your weight": rep.fund_w.reindex(rep.active.index, fill_value=0).values * 100,
        "Benchmark weight": rep.bench_w.reindex(rep.active.index, fill_value=0).values * 100,
        "Active weight": rep.active.values * 100,
        "Share of tracking error": rep.budget.reindex(rep.active.index).values * 100,
    }).iloc[::-1], hide_index=True, width="stretch",
        column_config={c: st.column_config.NumberColumn(format="%.1f%%") for c in
                       ["Your weight", "Benchmark weight", "Active weight", "Share of tracking error"]})
C.chart_notes(BUDGET_WHAT, BUDGET_MATHS, "budget")

pairwise(rep, names)
C.chart_notes(RULES_WHAT + IR_WHAT, RULE_MATHS, "rules")
