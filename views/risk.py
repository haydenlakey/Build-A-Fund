"""Risk in detail: how sure the numbers are, VaR and ES three ways, a fan chart, stress tests,
drawdowns, rolling volatility and borrowing to invest."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import streamlit as st

from fundlab import estimators, leverage, risk, var
from ui import cached, charts, insights, state
from ui import components as C

CHART_CONFIG = {"displayModeBar": False, "scrollZoom": False}
WEAK_R2 = 0.3  # below this, a factor estimate explains little of the holding's movement

INTRO = """
The Build page gives one number for each kind of risk. This page looks underneath them: how much the
estimates can be trusted, three different ways to size a bad month, what the next few years might look
like, how today's fund would have done in past crises, and what borrowing to invest does to all of it.
"""

UNCERTAIN_MATHS = r"""
The expected return is the average weekly return $\bar r$ times 52, shrunk toward the prior
$\mu_0 = r_f + S\sigma$ with weight $a$: $\hat\mu = (1-a)\,52\bar r + a\,\mu_0$. Its standard error from
$n$ weekly returns with standard deviation $s$ is

$$SE(52\bar r) = 52\,\frac{s}{\sqrt n} = \frac{\sigma_{\text{annual}}}{\sqrt{n/52}},$$

so with 5 years of data and 20% volatility it is about $20\%/\sqrt5 \approx 9\%$ a year. The rough 95% range is
$\hat\mu \pm 1.96\,SE$.

**Covariance, three ways** (all annualised, $\times 52$):
- *Sample*: $\hat\Sigma = \frac{1}{n-1}\sum_t (r_t-\bar r)(r_t-\bar r)^\top$.
- *Ledoit-Wolf*: $\hat\Sigma_{LW} = \delta F + (1-\delta)\hat\Sigma$, pulled toward a constant-correlation
  matrix $F$ with the weight $\delta$ that minimises expected error.
- *Exponentially weighted*: $\Sigma_t = \lambda \Sigma_{t-1} + (1-\lambda)(r_t-\bar r)(r_t-\bar r)^\top$,
  $\lambda = 0.97$ a week, so the last few months count most.
"""

VAR_WHAT = """
**Value at Risk (VaR)** answers: *"in a bad period, how much might I lose?"* At 95% over one month, it is a loss
the fund would be expected to exceed in about one month out of twenty. It says nothing about **how much worse**
those bad months get. **Expected shortfall (ES)** fills that gap: the average loss *in* the worst 5% of periods.

The three ways differ in what they assume:
- **Historical** replays every overlapping period in the measured window. No assumptions about shape, but it
  only knows the crashes that happened to be in the window.
- **Parametric** uses a formula: the normal curve, or the fatter-tailed Student-t.
- **Monte Carlo** simulates thousands of possible paths week by week, with normal or Student-t shocks.

When the historical figure is well above the normal one, the fund's real history had fatter tails than the bell
curve allows. The chart shows the simulated rand outcomes; the orange bars are the tail the VaR cuts off, and ES
is their average.
"""

VAR_MATHS = r"""
For a horizon of $h$ weeks, $\mu_h = \mu\,h/52$ and $\sigma_h = \sigma\sqrt{h/52}$. With confidence $\alpha$
(e.g. 0.95), losses as positive numbers:

**Normal:** $\text{VaR} = -(\mu_h + z_{1-\alpha}\sigma_h)$, $\;\text{ES} = -\mu_h + \sigma_h\,\dfrac{\varphi(z_{1-\alpha})}{1-\alpha}$.

**Student-t** with $\nu$ degrees of freedom, scaled to the same standard deviation, $s = \sigma_h\sqrt{(\nu-2)/\nu}$:
$\text{VaR} = -(\mu_h + q_{1-\alpha}\,s)$, $\;\text{ES} = -\mu_h + s\,\dfrac{f_\nu(q)\,(\nu + q^2)}{(\nu-1)(1-\alpha)}$.

**Historical:** the $1-\alpha$ quantile of the overlapping compounded returns $\prod_{k=1}^{h}(1+r_{t-k+1}) - 1$,
and ES is the mean of the returns at or below it.

**Monte Carlo:** each week the fund returns $w^\top\mu/52 + (w^\top L) z$, where $LL^\top = \Sigma/52$ and $z$ is
standard normal or standardised multivariate t (one shared $\chi^2_\nu$ draw per week, so all holdings get fat
tails together). Paths are compounded and rebalanced weekly; VaR and ES come from the simulated quantile. The seed
in the sidebar makes it repeatable.

**Whole fund with unlisted holdings:** buy and hold, the listed part normal as above, each unlisted holding
following its stated return, range and weekly chance of total loss (see the Build page's maths).
"""

FAN_WHAT = """
Each simulated path is one possible future for the fund's value. The dark band holds the middle half of them,
the light band 90%; the line is the middle outcome. The bands widen with time because uncertainty compounds.

Everything here starts from the **expected return**, the least reliable number on this page, and assumes the future
behaves like the measured window. Real values are also hit by inflation, which isn't taken off here.
"""

FAN_MATHS = r"""
Wealth after $t$ weeks on path $j$ is $V_{j,t} = V_0\prod_{k=1}^{t}(1 + r_{j,k})$, with weekly returns simulated as
in the VaR section. At each week the bands are the 5th, 25th, 50th, 75th and 95th percentiles of
$\{V_{j,t}\}_j$. A path's percentile can change from week to week, so the median line is not one path.
Over $T$ years the median grows roughly like $e^{(\mu - \sigma^2/2)T}$, below the average $e^{\mu T}$:
volatility drags the typical outcome down.
"""

STRESS_WHAT = """
Today's fund, held unchanged through five past episodes, next to the **Top 40 index** and the **S&P 500 in rand**.
The bar is the change from the episode's start to its end; the table also gives the lowest point along the way.

If a holding didn't exist yet, its path is **estimated** from how it has moved with the Top 40 and the S&P 500
since it listed. An estimate with a low R² (marked *weak*) explains little of the holding's movement, so treat that
episode's figure as rough. The *measured* column shows how much of the fund used real prices.
"""

STRESS_MATHS = r"""
Buy and hold from the episode's start: $V_t = \sum_i w_i\,P_{i,t}/P_{i,0}$, episode return $V_T - 1$, lowest point
$\min_t V_t - 1$.

A holding without prices in the episode gets weekly returns $\hat r_{i,t} = b_{i1} f_{1,t} + b_{i2} f_{2,t}$, with
$b$ from the OLS regression $r_{i,t} = a_i + b_{i1} f_{1,t} + b_{i2} f_{2,t} + \varepsilon_{i,t}$ on all its weekly
history ($f_1$ = Top 40 index, $f_2$ = S&P 500 in rand). The intercept $a_i$ is left out, so past outperformance
isn't assumed to carry on through a crisis.

Unlisted holdings move with the listed part through their one-factor model: $r_u = \beta_u r_S$,
$\beta_u = \rho_u\sigma_u/\sigma_S$.

The Top 40 here is the **price index** (dividends not included), the only Top 40 series going back to 2008.
"""

DD_WHAT = """
How far the fund was below its previous high at each point in the measured window. Zero means a new high. The
deepest dip is the **worst fall** (maximum drawdown) from the Build page; the width of each dip shows how long it
took to recover.
"""

DD_MATHS = r"""
With wealth $W_t = \prod_{k \le t}(1 + r_k)$ (rebalanced weekly to today's weights), the drawdown is
$D_t = W_t / \max_{s \le t} W_s - 1$, and the maximum drawdown is $\min_t D_t$.
"""

ROLL_WHAT = """
Volatility measured over a moving window. Risk is not constant: it bunches up in crises and fades in calm
years. When the line is far above the dotted whole-window figure, the fund was swinging much more than its
average suggests.
"""

ROLL_MATHS = r"""
$\sigma_t = \sqrt{52}\;\text{sd}(r_{t-k+1}, \dots, r_t)$ for a window of $k$ weeks.
"""

LEV_WHAT = """
**Borrowing to invest** (gearing, or buying on margin) means you hold more than you put in. If you put in R1 and
borrow R1, you hold R2 of investments (2×). Gains and losses on the whole R2 land on your R1, and the loan charges
interest whether the fund goes up or not.

The lender protects itself with a **margin call**: if your own money falls below a set share of the investments,
it sells some of them to repay part of the loan, at whatever the price is that day. That **forced selling** happens
after a fall, so the loss is locked in, and you own less for the recovery. If the fund falls far enough between
checks, your money is **wiped out**: at 4×, a fall of 25% does it.

With **normal** shocks, a single week bad enough to wipe you out almost never comes up, because margin calls
shrink the loan first. Switch the simulations to **Student-t** to see how fatter tails, where sudden crashes
are more common, change that.

Unlisted holdings are left out here: a lender can't sell them in a margin call. Real lenders check during the
day, so this weekly version understates how often calls happen.
"""

LEV_MATHS = r"""
Start with your money $E_0 = 1$, debt $D_0 = L - 1$ and investments $A_0 = L$. Each week

$$A_t = A_{t-1}(1 + r_t), \qquad D_t = D_{t-1}\left(1 + \tfrac{b}{52}\right), \qquad E_t = A_t - D_t .$$

If $E_t / A_t < m$ (the margin-call level), the lender sells $s_t = A_t - L E_t$ of the investments and repays
$s_t$ of the debt, which brings $E_t / A_t$ back to $1/L$. If $E_t \le 0$ you are wiped out and the path stops.
The loan is not topped up after gains, so leverage drifts down as the fund rises.

A fall of $1/L$ in one step wipes you out: 50% at 2×, 25% at 4×. The simulated chances use 20 000 one-year paths
of weekly returns, as in the VaR section, with the same rules.
"""


def pct_or_dash(x: float, d: int = 1) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else C.pct(x, d)


def tile(col, label: str, value: str, caption: str = "", help_: str | None = None) -> None:
    with col.container(border=True, height="stretch"):
        st.metric(label, value, help=help_)
        if caption:
            st.caption(caption)


def how_sure(fund, stats) -> None:
    st.subheader("How sure can we be?")
    se = stats.exp_return_se
    lo, hi = stats.exp_return - 1.96 * se, stats.exp_return + 1.96 * se
    st.warning(f"**Expected return: {C.pct(stats.exp_return)} a year, but the rough 95% range is {C.pct(lo, 0)} to "
               f"{C.pct(hi, 0)}.** This is the least reliable number in the app. A few years of history can't pin "
               "down an average return, and everything projected forward on this page (the fan chart, the "
               "Monte Carlo VaR) leans on it.", icon=":material/help:")
    vols = cached.cov_vols(fund)
    chosen = fund.settings.cov_method
    cols = st.columns(len(vols))
    for col, (m, v) in zip(cols, vols.items()):
        tile(col, f"Volatility: {estimators.COV_METHODS[m]}", C.pct(v),
             "used on every page" if m == chosen else "", help_="The fund's yearly volatility with this "
             "covariance estimate. Change which one the app uses in Assumptions and settings.")
    spread = max(vols.values()) - min(vols.values()) if vols else 0
    st.caption(f"The three estimates are {spread * 100:.1f} percentage points apart. Volatility is far easier to "
               "estimate than the average return: it depends on the size of the weekly moves, not on where they "
               "ended up. A big gap with the exponentially weighted figure means recent months have been calmer or "
               "wilder than the window as a whole.")
    if st.toggle("Show me the maths", key="maths_sure"):
        st.markdown(UNCERTAIN_MATHS)


def var_section(fund, stats, dist: str, df: float) -> None:
    s = fund.settings
    h, a = s.var_horizon_weeks, s.var_alpha
    horizon = "one month" if h == 4 else "one year" if h == 52 else f"{h} weeks"
    st.subheader("How much could a bad period cost? VaR and ES three ways")
    st.caption(f"Over **{horizon}** at **{a:.1%}** confidence".replace(".0%", "%") +
               " (change both in *Assumptions and settings*). Losses are shown as positive numbers.")
    base = stats.total_zar * stats.coverage
    sims = {d: np.prod(1 + cached.weekly_sims(fund, h, 20_000, d, df), axis=1) - 1 for d in ("normal", "t")}
    rows = [("Historical", "Every overlapping period in the window", var.historical_var_es(stats.port_returns, h, a)),
            ("Parametric, normal", "Bell-curve formula", var.parametric_var_es(stats.exp_return, stats.vol, h, a)),
            ("Parametric, Student-t", f"Fat-tailed formula, {df:g} degrees of freedom",
             var.parametric_var_es(stats.exp_return, stats.vol, h, a, "t", df)),
            ("Monte Carlo, normal", "20 000 simulated paths", var.mc_var_es(sims["normal"], a)),
            ("Monte Carlo, Student-t", f"20 000 simulated paths, {df:g} degrees of freedom", var.mc_var_es(sims["t"], a))]
    table = [{"Method": m, "VaR": v, "VaR in rand": C.rand(v * base), "ES": e, "ES in rand": C.rand(e * base),
              "How": how} for m, how, (v, e) in rows]
    if fund.unlisted():
        whole = cached.whole_paths(fund, h, 20_000)[:, -1] - 1
        v, e = var.mc_var_es(whole, a)
        table.append({"Method": "Whole fund, with unlisted", "VaR": v, "VaR in rand": C.rand(v * stats.total_zar),
                      "ES": e, "ES in rand": C.rand(e * stats.total_zar),
                      "How": "Your assumptions for unlisted holdings, buy and hold"})
    df_t = pd.DataFrame(table)
    df_t["VaR"] *= 100
    df_t["ES"] *= 100
    st.dataframe(df_t, hide_index=True, width="stretch", column_config={
        "VaR": st.column_config.NumberColumn(format="%.1f%%"), "ES": st.column_config.NumberColumn(format="%.1f%%")})
    hist_v, norm_v = rows[0][2][0], rows[1][2][0]
    if not math.isnan(hist_v) and hist_v > norm_v * 1.15:
        st.caption(f"The historical VaR ({C.pct(hist_v)}) is well above the normal formula's ({C.pct(norm_v)}): "
                   "this fund's real bad periods were worse than a bell curve predicts.")
    note = f"Rand amounts are on the {C.rand(base)} the history covers"
    st.caption(note + (f"; the whole-fund row uses all {C.rand(stats.total_zar)}." if fund.unlisted() else "."))

    v, e = var.mc_var_es(sims[dist], a)
    st.plotly_chart(charts.outcome_hist(sims[dist] * base, v * base, e * base, a), config=CHART_CONFIG,
                    key="var_hist")
    C.chart_notes(VAR_WHAT, VAR_MATHS, "var")


def fan_section(fund, stats, dist: str, df: float) -> None:
    st.subheader("Where could the fund be in a few years?")
    years = st.segmented_control("Look ahead", [1, 3, 5, 10], default=5, format_func=lambda y: f"{y} year"
                                 + ("s" if y > 1 else ""), key="fan_years") or 5
    weeks = 52 * years
    if fund.unlisted():
        paths = cached.whole_paths(fund, weeks, 5_000)
        start = stats.total_zar
        label = "the whole fund, with your assumptions for the unlisted holdings (normal shocks)"
    else:
        weekly = cached.weekly_sims(fund, weeks, 5_000, dist, df)
        paths = np.concatenate([np.ones((len(weekly), 1)), np.cumprod(1 + weekly, axis=1)], axis=1)
        start = stats.total_zar * stats.coverage
        label = "the measured part of the fund" + (", Student-t shocks" if dist == "t" else ", normal shocks")
    bands = var.fan(paths)
    st.plotly_chart(charts.fan_chart(bands, start, start), config=CHART_CONFIG, key="fan")
    end = paths[:, -1]
    st.caption(f"5 000 simulated paths of {label}. After {years} year{'s' if years > 1 else ''}: middle outcome "
               f"{C.rand(np.median(end) * start)}, 1 in 20 paths below {C.rand(np.percentile(end, 5) * start)}. "
               f"{np.mean(end < 1):.0%} of paths end below what you put in.")
    C.chart_notes(FAN_WHAT, FAN_MATHS, "fan")


def stress_section(fund, stats) -> None:
    st.subheader("How would today's fund have done in past crises?")
    reps = cached.stress_tests(fund)
    if not reps:
        st.info("No episode could be replayed for this fund.")
        return
    has_unl = bool(fund.unlisted())
    rows = [{"episode": r.episode.name, "fund": r.fund_return, "bench_j200": float(r.benchmarks["^J200.JO"].iloc[-1] - 1),
             "bench_spy": float(r.benchmarks["SPY"].iloc[-1] - 1)} for r in reps]
    st.plotly_chart(charts.stress_bars(rows), config=CHART_CONFIG, key="stress_bars")
    st.caption("The Top 40 here is the price index (dividends not included), the only Top 40 series that reaches "
               "back to 2008. The S&P 500 is the SPY ETF converted to rand.")
    table = []
    for r, row in zip(reps, rows):
        weak = r.by_holding[(r.by_holding["method"] == "Estimated") & (r.by_holding["r2"] < WEAK_R2)]
        t = {"Episode": r.episode.name, "Your fund": row["fund"] * 100, "Lowest point": r.worst * 100}
        if has_unl:
            t["Whole fund, with unlisted"] = r.whole_return * 100
        t |= {"Top 40 index": row["bench_j200"] * 100, "S&P 500 in rand": row["bench_spy"] * 100,
              "Measured": r.measured_share * 100, "Weak estimates": len(weak),
              "Dates": f"{r.episode.start:%d %b %Y} to {r.episode.end:%d %b %Y}"}
        table.append(t)
    pc = st.column_config.NumberColumn(format="%+.1f%%")
    st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch", column_config={
        **{c: pc for c in ["Your fund", "Lowest point", "Whole fund, with unlisted", "Top 40 index", "S&P 500 in rand"]},
        "Measured": st.column_config.ProgressColumn("Measured share", format="%.0f%%", min_value=0, max_value=100,
                                                    help="Share of the fund with real prices in the episode; the "
                                                         "rest is estimated.")})
    if has_unl:
        st.caption("Unlisted holdings have no prices, so the whole-fund column moves them with the listed part at the "
                   "correlation you set. In real crises their valuations are often only marked down later.")

    names = [r.episode.name for r in reps]
    pick = st.selectbox("Look at one episode week by week", names, index=len(names) - 1, key="stress_pick")
    rep = reps[names.index(pick)]
    st.markdown(rep.episode.what)
    st.plotly_chart(charts.stress_path(rep), config=CHART_CONFIG, key="stress_path")
    by = rep.by_holding.copy()
    by.insert(0, "Holding", [cached.name_of(t, fund) for t in by.index])
    by["return"] *= 100
    by["How"] = [m if m != "Estimated" else ("Estimated (weak)" if r2 < WEAK_R2 else "Estimated")
                 for m, r2 in zip(by["method"], by["r2"])]
    with st.expander(f"Each holding in {pick}"):
        st.dataframe(by[["Holding", "return", "How", "r2"]], hide_index=True, width="stretch", column_config={
            "return": st.column_config.NumberColumn("Change", format="%+.1f%%"),
            "r2": st.column_config.NumberColumn("R² of the estimate", format="%.2f")})
    if rep.episode.article and rep.episode.article in cached.library():
        st.page_link("views/library.py", label=f"Read more: {cached.library()[rep.episode.article].title}",
                     icon=":material/menu_book:", query_params={"article": rep.episode.article})
    C.chart_notes(STRESS_WHAT, STRESS_MATHS, "stress")


def history_section(stats) -> None:
    st.subheader("Falls from the top")
    pr = stats.port_returns
    st.plotly_chart(charts.drawdown_chart(risk.drawdown_series(pr)), config=CHART_CONFIG, key="drawdown")
    C.chart_notes(DD_WHAT, DD_MATHS, "dd")

    st.subheader("Risk changes over time")
    window = st.segmented_control("Measure over", [13, 26, 52], default=26, format_func=lambda k: f"{k} weeks",
                                  key="roll_window") or 26
    rv = risk.rolling_vol(pr, window)
    st.plotly_chart(charts.rolling_vol_chart(rv, risk.annualised_vol(pr), window), config=CHART_CONFIG,
                    key="rolling_vol")
    if rv.notna().any():
        st.caption(f"Over the window it ranged from {C.pct(rv.min(), 0)} to {C.pct(rv.max(), 0)} a year "
                   f"(highest in the {window} weeks to {rv.idxmax():%d %b %Y}).")
    C.chart_notes(ROLL_WHAT, ROLL_MATHS, "roll")


def leverage_section(fund, stats, dist: str, df: float) -> None:
    st.subheader("What if you borrowed to invest?")
    L = st.segmented_control("Hold this many rands of investments for every rand of your own", [1.0, 1.5, 2.0, 3.0, 4.0],
                             default=1.0, format_func=lambda x: "No borrowing" if x == 1 else f"{x:g}×",
                             key="lev") or 1.0
    insights.popups(fund, extra={"leverage": L}, only={"leverage_on"})
    if L == 1:
        st.caption("Pick a multiple to see how borrowing changes the falls, the chance of a margin call and the chance "
                   "of being wiped out.")
        C.chart_notes(LEV_WHAT, LEV_MATHS, "lev")
        return
    c1, c2 = st.columns(2)
    rate = c1.number_input("Borrowing rate, % a year (your assumption)", 0.0, 40.0,
                           round(fund.settings.risk_free * 100 + 3, 2), 0.25, key="lev_rate",
                           help="Interest on the loan. Lending to individuals usually costs more than the "
                                "risk-free rate.") / 100
    start_share = 1 / L
    m = c2.slider("Margin call when your money falls below this share of the investments", 1.0,
                  float(math.floor(start_share * 100 - 1)), float(round(leverage.default_maintenance(L) * 100)), 1.0,
                  format="%.0f%%", key=f"lev_m_{L}",
                  help=f"You start at {start_share:.0%}. The app's default is half that.") / 100
    amount = stats.total_zar * stats.coverage

    hist = leverage.history(stats.port_returns, L, rate, m)
    st.plotly_chart(charts.leverage_chart(hist, L, amount), config=CHART_CONFIG, key="lev_chart")
    eq = hist["equity"]
    dd_lev = float((eq / eq.cummax() - 1).min()) if eq.max() > 0 else -1.0
    n_calls = int((hist["sold"] > 0).sum())
    wiped = eq.iloc[1:].le(0)
    cols = st.columns(4)
    tile(cols[0], "Worst fall, no borrowing", C.pct(stats.max_drawdown))
    tile(cols[1], f"Worst fall at {L:g}×", C.pct(dd_lev), "of your own money")
    tile(cols[2], "Forced sales", f"{n_calls}", f"lender sold {C.rand(hist['sold'].sum() * amount)} in total"
         if n_calls else "none in this window")
    tile(cols[3], "Your money at the end", C.rand(eq.iloc[-1] * amount),
         f"wiped out on {wiped.idxmax():%d %b %Y}" if wiped.any() else f"vs {C.rand(hist['unlevered'].iloc[-1] * amount)}"
         " without borrowing")
    st.caption(f"Replayed on the fund's actual weekly returns, {stats.port_returns.index[0]:%b %Y} to "
               f"{stats.port_returns.index[-1]:%b %Y}, starting with {C.rand(amount)} of your own money.")

    st.markdown(f"**Over the next year, from 20 000 simulated years** ({'Student-t' if dist == 't' else 'normal'} "
                "shocks, as chosen above)")
    weekly = cached.weekly_sims(fund, 52, 20_000, dist, df)
    base = leverage.summarise(leverage.margin_paths(weekly, 1.0, rate))
    lev = leverage.summarise(leverage.margin_paths(weekly, L, rate, m))
    tab = pd.DataFrame({
        "": ["Chance of being wiped out", "Chance of at least one margin call", "Middle outcome for your money",
             "1 year in 20, your money ends below", "Typical worst fall during the year"],
        "No borrowing": [C.pct(base.p_wiped), "–", C.rand(base.median_end * amount), C.rand(base.low_end * amount),
                         C.pct(base.median_drawdown)],
        f"{L:g}×": [C.pct(lev.p_wiped, 2), C.pct(lev.p_call), C.rand(lev.median_end * amount),
                    C.rand(lev.low_end * amount), C.pct(lev.median_drawdown)],
    })
    st.dataframe(tab, hide_index=True, width="stretch")
    for slug in ("leverage", "ltcm", "situational-awareness"):
        if slug in cached.library():
            st.page_link("views/library.py", label=f"Read more: {cached.library()[slug].title}",
                         icon=":material/menu_book:", query_params={"article": slug})
    C.chart_notes(LEV_WHAT, LEV_MATHS, "lev")


# ---------------------------------------------------------------------------------

fund = state.active()
st.title("Risk in detail")
C.disclaimer()
st.markdown(INTRO)

if not fund.holdings:
    st.info("This fund is empty. Add holdings on the **Build your fund** page, or open the example fund there.",
            icon=":material/lightbulb:")
    st.stop()

with st.spinner("Measuring risk…"):
    cmp = cached.compare(fund, fund)
stats = cmp.after
if stats is None:
    st.warning("Nothing in this fund has enough price history to measure. Unlisted holdings are covered by the "
               "whole-fund panel on the Build page.")
    st.stop()
rep = cmp.est.report
st.caption(f"Measured on {rep.n_weeks} weeks, {rep.start:%d %b %Y} to {rep.end:%d %b %Y}, in rand, covering "
           f"{C.pct(stats.coverage, 0)} of the fund ({C.rand(stats.total_zar * stats.coverage)}).")
for t in stats.excluded:
    h = fund.holding(t)
    if not (h and h.kind == "unlisted"):
        st.caption(f"{cached.name_of(t, fund)} is left out: {stats.excluded[t]}")
if fund.unlisted():
    st.caption("Unlisted holdings have no price history. Sections based on history cover the listed part; rows "
               "marked *whole fund* add the unlisted holdings using your assumptions.")

how_sure(fund, stats)

c1, c2 = st.columns(2)
dist = c1.segmented_control("Shocks in the simulations", ["normal", "t"], default="normal", key="sim_dist",
                            format_func={"normal": "Normal (bell curve)", "t": "Student-t (fat tails)"}.get) or "normal"
df = c2.number_input("Student-t degrees of freedom (lower = fatter tails)", 3.0, 30.0, 5.0, 1.0, key="t_df",
                     help="Used by the Student-t rows and, when chosen, the charts. 3 to 6 is typical for weekly "
                          "share returns; 30 is close to normal.")
var_section(fund, stats, dist, df)
fan_section(fund, stats, dist, df)
stress_section(fund, stats)
history_section(stats)
leverage_section(fund, stats, dist, df)
