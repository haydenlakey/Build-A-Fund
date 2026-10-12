"""Reality check: what the fund costs, how today's mix would have done, and what an optimiser would do."""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from fundlab import backtest, costs, frontier, risk
from ui import cached, charts, glossary, state
from ui import components as C

CHART_CONFIG = {"displayModeBar": False, "scrollZoom": False}

INTRO = """
Three checks that bring the earlier pages down to earth: what owning the fund **costs**, how today's mix
would actually have done in the past next to simple alternatives, and what a mathematical **optimiser** would
do with the same holdings (and why its answer shouldn't be taken at face value).
"""

COST_WHAT = """
Costs come in three layers:
- **Fund charges** (TER and transaction costs) of ETFs and unit trusts are taken out inside the fund, every day.
  You never see a bill, but the price is lower by that much. Every history-based number in this app is already
  *after* them.
- **Platform and account fees**: EasyEquities charges a yearly fee on unit trusts, and a fixed monthly fee unless
  it is waived. A fixed fee weighs far more on a small fund than on a large one.
- **Trading costs**: brokerage, settlement, levies and VAT on every buy and sell, plus securities transfer tax on
  buying shares, and a currency fee to move rand into dollars for US shares.

The chart grows the fund at the yearly return you set, with no costs, after fund charges, and after everything.
The gap between the lines is money that compounds for someone else. A cost of 1% a year sounds small, but it is
taken every year from a growing amount.
"""

COST_MATHS = r"""
With starting amount $A$, growth $g$ a year before costs, fund charges $c_f$ (weighted TER + TC), platform fees
$c_p$, monthly account fee $F$, and buy and sell costs $b$ and $s$ (fractions of the amount):

$$V_0 = A(1+g)^n, \qquad V_1 = A(1 + g - c_f)^n,$$
$$V_2 = \Big[A(1-b)(1+r)^n - 12F\,\frac{(1+r)^n - 1}{r}\Big](1 - s), \qquad r = g - c_f - c_p .$$

Trading costs per rand: $(\text{commission} + \text{settlement} + \text{levy}) \times 1.15$ (VAT), plus 0.25% STT
when buying JSE shares, plus 0.5% to move rand to dollars for US holdings. Fees are taken once a year here, a
close approximation of the monthly deductions.
"""

BT_WHAT = """
Today's mix of holdings, replayed over the measured window and **rebalanced** back to today's weights on the
schedule you pick, next to simple alternatives: the **Top 40** (Satrix 40), the **S&P 500 in rand**, the
app's **balanced proxy** (50% Top 40, 25% world shares, 25% SA government bonds) and an **equal-weight** version of
your own holdings. Every line starts with your fund's rands.

Read it with care. You chose today's holdings *knowing* how they did, so the replay flatters any fund built from
recent winners (**hindsight bias**). Trading costs are charged on every rebalance, which is why rebalancing every
week can lose to rebalancing once a year.
"""

BT_MATHS = r"""
Each week holding $i$ grows by $(1 + r_{i,t})$. On a rebalance week the fund (value $V$) trades
$d_i = V w_i - h_i$ back to the target weights $w$, paying
$C = b\sum_i \max(d_i, 0) + s\sum_i \max(-d_i, 0)$. **Turnover** is $\sum_i |d_i| / 2V$.

*Yearly return* is the compound annual growth rate $(V_T/V_0)^{1/T} - 1$; *volatility* is the annualised standard
deviation of weekly returns; the *Sharpe ratio* here is $(\text{CAGR} - r_f)/\sigma$.
"""

OPT_WHAT = """
A mean-variance **optimiser** takes the same expected returns and covariance matrix the app uses and finds the
weights that are "best" for a goal you choose, holding only what you already hold (no borrowing, no short selling).

The thin whiskers are the warning. The optimiser was re-run 200 times with each holding's expected return
nudged within its own uncertainty (one standard error, the same ± range shown on the Build page). If the whisker
runs from 0% to 80%, the "best" weight for that holding is mostly a reflection of noise in a few years of
returns. This is why professionals rarely use raw optimiser output: it piles into whatever happened to do well,
and small changes in the inputs swing the answer wildly. Richard Michaud called mean-variance optimisers
"estimation-error maximizers" in [*The Markowitz Optimization Enigma: Is 'Optimized' Optimal?*](https://rpc.cfainstitute.org/research/financial-analysts-journal/1989/the-markowitz-optimization-enigma-is-optimized-optimal)
(*Financial Analysts Journal*, 1989; accessed 11 October 2026); the re-runs below are a simple version of the
resampling he later proposed.
"""

OPT_MATHS = r"""
With expected returns $\mu$ and covariance $\Sigma$, over weights $w \ge 0$, $\sum_i w_i = 1$:

- *Same risk*: $\max_w\; w^\top\mu$ subject to $w^\top\Sigma w \le \sigma_F^2$.
- *Same expected return*: $\min_w\; w^\top\Sigma w$ subject to $w^\top\mu \ge \mu_F$.
- *Highest Sharpe ratio*: $\max_w\; (w^\top\mu - r_f)/\sqrt{w^\top\Sigma w}$.

Solved with SLSQP. **Resampling**: draw $\tilde\mu_i \sim N(\mu_i, SE_i^2)$ independently with
$SE_i = \sigma_i/\sqrt{\text{years}}$, re-optimise, repeat 200 times (seeded); the whiskers are the 10th to 90th
percentiles of each weight.
"""


def link(slug: str) -> None:
    lib = cached.library()
    if slug in lib:
        st.page_link("views/library.py", label=f"Read more: {lib[slug].title}", icon=":material/menu_book:",
                     query_params={"article": slug})


def tile(col, label: str, value: str, caption: str = "", help_: str | None = None) -> None:
    with col.container(border=True, height="stretch"):
        st.metric(label, value, help=help_)
        if caption:
            st.caption(caption)


def cost_inputs(fund) -> tuple[costs.TradingCosts, float, float, float]:
    pc = cached.platform_costs()
    default = costs.TradingCosts.from_platform(pc)
    with st.expander(f"Cost assumptions (EasyEquities ZAR account, cost profile of {pc['as_of']:%d %B %Y})"):
        st.caption(f"Defaults from [{pc['source_title']}]({pc['source']}) and EasyEquities' "
                   f"[Fees and costs]({pc['support_source']}) page, accessed {pc['accessed']:%d %B %Y}. "
                   "Change any of them to match your own account.")
        c1, c2 = st.columns(2)
        buy_share = c1.number_input("Cost to buy a JSE share, %", 0.0, 5.0, round(default.buy_share * 100, 3), 0.01,
                                    format="%.3f", key="c_buy_share",
                                    help="Brokerage 0.25%, settlement 0.0795% and investor protection levy, plus 15% "
                                         "VAT on those, plus 0.25% securities transfer tax on share purchases.") / 100
        buy_other = c2.number_input("Cost to buy an ETF or US share, %", 0.0, 5.0, round(default.buy_other * 100, 3),
                                    0.01, format="%.3f", key="c_buy_other",
                                    help="As for a share but without securities transfer tax. Whether that tax "
                                         "applies to ETF units wasn't verified for this app; add 0.25 if it does.") / 100
        sell = c1.number_input("Cost to sell, %", 0.0, 5.0, round(default.sell * 100, 3), 0.01, format="%.3f",
                               key="c_sell", help="Brokerage, settlement and levy plus VAT.") / 100
        fx = c2.number_input("Extra to move rand to dollars (US holdings), %", 0.0, 5.0, default.fx * 100, 0.05,
                             key="c_fx", help="EasyFX transfer fee. Costs inside the USD account itself weren't found "
                                              "in a published cost profile, so they aren't included.") / 100
        ut_fee = c1.number_input("Unit trust platform fee, % a year", 0.0, 3.0, pc["unit_trust_platform_fee"] * 100, 0.05,
                                 key="c_ut") / 100
        monthly = c2.number_input("Monthly account fee, rand", 0.0, 500.0, float(pc["thrive_fee_monthly"]), 5.0,
                                  key="c_month", help="EasyEquities' Thrive fee: R25 a month, waived at Thrive Level 3 "
                                                      "or if you are under 21 or over 65. Set it to 0 if it's waived.")
    return costs.TradingCosts(buy_share, buy_other, sell, fx), ut_fee, monthly, buy_other


def costs_section(fund) -> tuple[costs.TradingCosts, costs.CostSummary, float]:
    st.subheader("What does it cost?")
    trading, ut_fee, monthly, bench_buy = cost_inputs(fund)
    comp = cached.compose(fund)
    ter = {t: p.ter for t, p in comp.profiles.items()}
    tc = {t: p.tc for t, p in comp.profiles.items()}
    s = costs.summarise(fund, ter, tc, trading, ut_fee, monthly)
    cols = st.columns(4)
    tile(cols[0], "Fund charges", f"{s.fund_costs:.2%}", "a year, already inside the prices",
         "Weighted TER plus transaction costs of your ETFs and unit trusts.")
    tile(cols[1], "Platform and account fees", f"{s.platform + s.account:.2%}",
         f"a year, incl. {C.rand(12 * monthly)} account fee" if monthly else "a year, no account fee")
    tile(cols[2], "To buy it all", C.rand(s.buy * s.total_zar), f"{s.buy:.2%} of the fund, once")
    tile(cols[3], "Yearly drag", f"{s.yearly:.2%}", "taken from returns every year")
    if s.account > 0.01:
        st.caption(f"The fixed {C.rand(monthly)} a month is {s.account:.1%} of a {C.rand(s.total_zar)} fund each year. "
                   "Fixed fees weigh heaviest on small funds.")

    growth = st.number_input("Yearly growth before any costs, % (your assumption)", -5.0, 25.0, 10.0, 0.5,
                             key="c_growth", help="Not a forecast. The app's own expected return is already after "
                                                  "fund charges and is the least reliable number it shows.") / 100
    paths = costs.value_paths(s.total_zar, growth, s, monthly, 20)
    st.plotly_chart(charts.cost_paths(paths), config=CHART_CONFIG, key="cost_paths")
    rows = []
    for n in (10, 20):
        pj = costs.project(s.total_zar, growth, s, monthly, n)
        rows.append({"After": f"{n} years", "With no costs": C.rand(pj.no_costs), "After all costs": C.rand(pj.after_all),
                     "Lost to costs": C.rand(pj.lost), "of which fund charges": C.rand(pj.lost_fund),
                     "of which platform, account and trading": C.rand(pj.lost_other),
                     "Share of the no-cost value": f"{pj.lost / pj.no_costs:.0%}" if pj.no_costs > 0 else "–"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    with st.expander("Costs by holding"):
        by = s.by_holding.copy()
        st.dataframe(pd.DataFrame({
            "Holding": [cached.name_of(t, fund) for t in by.index], "Amount": [C.rand(x) for x in by["amount"]],
            "TER": by["ter"] * 100, "Transaction costs": by["tc"] * 100, "Platform fee": by["platform"] * 100,
            "To buy": by["buy"] * 100, "To sell": by["sell"] * 100,
        }), hide_index=True, width="stretch",
            column_config={c: st.column_config.NumberColumn(format="%.2f%%") for c in
                           ["TER", "Transaction costs", "Platform fee", "To buy", "To sell"]})
    for n in s.notes:
        st.caption(n)
    link("fees")
    C.chart_notes(COST_WHAT, COST_MATHS, "costs")
    return trading, s, bench_buy


def backtest_section(fund, stats, s: costs.CostSummary, bench_buy: float) -> None:
    st.subheader("How would today's mix have done?")
    sched = st.segmented_control("Rebalance back to today's weights", list(backtest.SCHEDULES), default="quarterly",
                                 format_func=backtest.SCHEDULES.get, key="bt_sched") or "quarterly"
    lines, notes = cached.backtests(fund, sched, s.buy, s.sell, bench_buy)
    if not lines:
        st.info("Nothing to replay.")
        return
    amount = stats.total_zar * stats.coverage
    st.plotly_chart(charts.backtest_lines({k: r.wealth for k, r in lines.items()}, amount), config=CHART_CONFIG,
                    key="bt_chart")
    rf = fund.settings.risk_free
    rows = []
    for name, r in lines.items():
        st_ = backtest.stats(r.wealth, rf)
        rows.append({"": name, "End value": C.rand(r.wealth.iloc[-1] * amount), "Total return": st_["total"] * 100,
                     "Yearly return": st_["cagr"] * 100, "Volatility": st_["vol"] * 100,
                     "Worst fall": st_["worst"] * 100, "Sharpe ratio": st_["sharpe"],
                     "Trading costs": C.rand(r.costs * amount)})
    pc = st.column_config.NumberColumn(format="%.1f%%")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
        "Total return": pc, "Yearly return": pc, "Volatility": pc, "Worst fall": pc,
        "Sharpe ratio": st.column_config.NumberColumn(format="%.2f")})
    f = lines["Your fund"]
    w = stats.port_returns.index
    st.caption(f"{w[0]:%d %b %Y} to {w[-1]:%d %b %Y}, starting with {C.rand(amount)}. Your fund rebalanced "
               f"{f.n_rebalances} times, trading {f.turnover:.0%} of its value in total. Prices are after fund charges; "
               "platform and account fees aren't taken off here.")
    for n in notes:
        st.caption(n)
    link("buffett-bet")
    C.chart_notes(BT_WHAT, BT_MATHS, "bt")


def optimiser_section(fund, stats) -> None:
    st.subheader("What would an optimiser do with the same holdings?")
    if len(stats.weights) < 2:
        st.info("The optimiser needs at least two holdings with price history.")
        return
    goal = st.segmented_control("Goal", list(frontier.GOALS), default="same_risk", format_func=frontier.GOALS.get,
                                key="opt_goal") or "same_risk"
    with st.spinner("Optimising (and re-running 200 times)…"):
        res = cached.optimised(fund, goal)
    if res is None:
        st.warning("The optimiser couldn't find a solution for this fund and goal.")
        return
    w, draws, _ = res
    cmp = cached.compare(fund, fund)
    mu, cov = cmp.est.mu[w.index], cmp.est.cov.loc[w.index, w.index]
    o_ret, o_vol = risk.portfolio_return(w, mu), risk.portfolio_vol(w, cov)
    rf = fund.settings.risk_free
    cols = st.columns(3)
    tile(cols[0], "Expected return", C.pct(o_ret), f"yours {C.pct(stats.exp_return)}")
    tile(cols[1], "Volatility", C.pct(o_vol), f"yours {C.pct(stats.vol)}")
    tile(cols[2], "Sharpe ratio", f"{risk.sharpe(o_ret, o_vol, rf):.2f}", f"yours {stats.sharpe:.2f}")
    lo, hi = draws.quantile(0.1), draws.quantile(0.9)
    names = {t: cached.name_of(t, fund) for t in w.index}
    st.plotly_chart(charts.weights_compare(stats.weights, w, lo, hi, names), config=CHART_CONFIG, key="opt_w")
    moved = (w - stats.weights).abs().sum() / 2
    widest = (hi - lo).idxmax()
    st.markdown(f"The optimiser would move **{moved:.0%}** of the fund. But in 200 re-runs with expected returns "
                f"varied within their uncertainty, its weight for **{names[widest]}** ranged from "
                f"**{lo[widest]:.0%} to {hi[widest]:.0%}**. Treat its answer as a sketch of what the past few years "
                "rewarded, not as a better fund.")
    if not math.isnan(stats.exp_return_se) and stats.exp_return_se > 0:
        st.caption(f"For scale: the expected return the optimiser chases is only known to about "
                   f"± {C.pct(stats.exp_return_se)} a year for your fund as a whole.")
    link("estimation-error")
    link("efficient-frontier")
    C.chart_notes(OPT_WHAT, OPT_MATHS, "opt")


# ---------------------------------------------------------------------------------

fund = state.active()
st.title("Reality check")
C.disclaimer()
glossary.markdown(INTRO)

if not fund.holdings:
    st.info("This fund is empty. Add holdings on the **Build your fund** page, or open the example fund there.",
            icon=":material/lightbulb:")
    st.stop()

trading, summary, bench_buy = costs_section(fund)

with st.spinner("Replaying history…"):
    stats = cached.compare(fund, fund).after
if stats is None:
    st.warning("Nothing in this fund has enough price history for a backtest or an optimiser.")
    st.stop()
if fund.unlisted():
    st.caption("Unlisted holdings have no price history, so the backtest and the optimiser cover the listed part of "
               f"the fund ({C.pct(stats.coverage, 0)} of it).")
backtest_section(fund, stats, summary, bench_buy)
optimiser_section(fund, stats)
