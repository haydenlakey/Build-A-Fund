"""Reusable bits of page: disclaimer, chart notes, maths toggles, metric panels."""
from __future__ import annotations

import math

import streamlit as st

from fundlab.analysis import Comparison, FundStats
from ui import cached, glossary, state

DISCLAIMER = ("**Education, not financial advice.** This tool explains what a fund's characteristics mean "
              "and what history says about them. It never tells you to buy or sell anything. Past returns "
              "are a poor guide to future returns.")


def disclaimer() -> None:
    st.caption("⚠️ " + DISCLAIMER)


def chart_notes(what: str, maths: str, key: str) -> None:
    """The 'what am I looking at' note and 'show me the maths' toggle every chart carries."""
    with st.expander("What am I looking at?"):
        glossary.markdown(what)
    if st.toggle("Show me the maths", key=f"maths_{key}"):
        st.markdown(maths)


def rand(x: float, decimals: int = 0) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    s = f"{abs(x):,.{decimals}f}".replace(",", " ")
    return f"{'-' if x < 0 else ''}R{s}"


def table_height(n_rows: int) -> int:
    """Pixel height that shows a dataframe's header and n_rows rows without an inner scroll bar."""
    return 35 * (n_rows + 1) + 3


def pct(x: float, decimals: int = 1) -> str:
    return "–" if x is None or math.isnan(x) else f"{x * 100:.{decimals}f}%"


# (attribute, label, formatter, delta formatter, "higher"/"lower" is better, help)
METRICS = [
    ("exp_return", "Expected return", pct, lambda d: f"{d * 100:+.1f} pp", "higher",
     "Historical average yearly return (shrunk toward a prior). The least reliable number on the page: "
     "see the ± range under it."),
    ("vol", "Volatility", pct, lambda d: f"{d * 100:+.1f} pp", "lower",
     "How much the fund's value typically swings in a year (annualised standard deviation of weekly returns)."),
    ("sharpe", "Sharpe ratio", lambda x: f"{x:.2f}", lambda d: f"{d:+.2f}", "higher",
     "Return above the risk-free rate per unit of volatility."),
    ("max_drawdown", "Worst fall", pct, lambda d: f"{d * 100:+.1f} pp", "higher",
     "Largest peak-to-trough drop over the measured window (rebalanced weekly)."),
    ("var", "1-month VaR (95%)", pct, lambda d: f"{d * 100:+.1f} pp", "lower",
     "A loss the fund would exceed in roughly one month out of twenty, assuming normal returns."),
    ("div_ratio", "Diversification ratio", lambda x: f"{x:.2f}", lambda d: f"{d:+.2f}", "higher",
     "Average holding volatility divided by fund volatility. 1.00 means no diversification benefit."),
    ("eff_holdings", "Effective holdings", lambda x: f"{x:.1f}", lambda d: f"{d:+.1f}", "higher",
     "How many equal-sized holdings the fund behaves like (1 / sum of squared weights)."),
]


def _var_label(stats: FundStats, settings) -> str:
    h = settings.var_horizon_weeks
    horizon = "1-month" if h == 4 else f"{h}-week"
    return f"{horizon} VaR ({settings.var_alpha:.0%})"


def metric_panel(cmp: Comparison, settings, moved: bool) -> None:
    b, a = cmp.before, cmp.after
    cur = a if a is not None else b
    if cur is None:
        return
    per_row = 4
    cols = []
    for i, (attr, label, fmt, dfmt, better, help_) in enumerate(METRICS):
        if i % per_row == 0:  # build row by row so phones (which stack columns) keep the order
            cols = st.columns(per_row)
        if attr == "var":
            label = _var_label(cur, settings)
        value = getattr(cur, attr)
        delta, colour = None, "normal"
        if moved and b is not None and a is not None:
            d = getattr(a, attr) - getattr(b, attr)
            if not math.isnan(d):
                delta = dfmt(d)
                colour = "normal" if better == "higher" else "inverse"
                if not any(ch in "123456789" for ch in delta):  # rounds to zero at display precision
                    colour = "off"
                    delta = delta.replace("+", "±").replace("-", "±")
        extra = ""
        if attr == "exp_return":
            extra = f"± {pct(cur.exp_return_se)} (1 standard error)"
        elif attr == "var":
            extra = f"about {rand(cur.var_zar)} on {rand(cur.total_zar * cur.coverage)}"
        with cols[i % per_row].container(border=True, height="stretch"):
            st.metric(label, fmt(value), delta, delta_color=colour, help=help_)
            if extra:
                st.caption(extra)


def pick_benchmark(fund) -> str:
    bms = cached.universe().benchmarks
    current = cached.benchmark_key(fund)
    key = st.selectbox("Benchmark", list(bms), index=list(bms).index(current), format_func=lambda k: bms[k]["name"],
                       help="What you compare your fund against. You can change it at any time.")
    if key != fund.settings.benchmark:
        f = fund.copy(keep_id=True)
        f.settings.benchmark = key
        state.put(f)
    b = bms[key]
    parts = " + ".join(f"{w:.0%} {cached.name_of(t)}" for t, w in b["components"].items())
    st.caption(f"{parts}. {b.get('note', '')}")
    return key
