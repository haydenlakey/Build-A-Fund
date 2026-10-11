"""Build your fund: add, resize and remove holdings, and see what each change does."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from fundlab import data, unlisted, var, verdict
from fundlab.analysis import Comparison
from fundlab.model import HOLDING_KINDS, Fund
from ui import cached, charts, pickers, state
from ui import diligence as dd
from ui import components as C

OTHER = "__other__"
ADD_KINDS = {"listed": "Share or ETF", "unit_trust": "Unit trust", "unlisted": "Unlisted investment"}

WHOLE_MATHS = r"""
History-based numbers above cover only holdings with prices. Here the listed part $S$ (its expected
return $\mu_S$ and volatility $\sigma_S$ from history) is combined with each unlisted holding $i$'s
stated assumptions: return if it goes to plan $r_i$, a bad and a good year read as the 5th and 95th
percentiles, a yearly chance of total loss $p_i$, and a correlation $\rho_i$ with the listed part.

$$\sigma_i^{\text{survive}} = \frac{\text{good} - \text{bad}}{2 \times 1.645}, \qquad
E[R_i] = (1-p_i)(1+r_i) - 1, \qquad
\operatorname{Var}[R_i] = p_i + (1-p_i)\big(\sigma_i^2 + r_i^2\big) - E[R_i]^2$$

Covariances follow a one-factor model, $\operatorname{Cov}(i,S) = \rho_i\,\mathrm{sd}_i\,\sigma_S$ and
$\operatorname{Cov}(i,j) = \rho_i\rho_j\,\mathrm{sd}_i\,\mathrm{sd}_j$, so the whole fund has
$\mu = w^\top\mu$ and $\sigma = \sqrt{w^\top\Sigma w}$ with $w$ from the rand amounts.

The simulation holds everything for a year without rebalancing (unlisted holdings can't be traded):
weekly normal returns, with each unlisted holding failing in any week with probability
$1-(1-p_i)^{1/52}$, after which it is worth nothing. The seed is the one in *Assumptions and settings*.
"""

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
    """Returns (ticker, amount) for the change being considered. amount is None until one is entered.

    Widget keys carry a generation number that apply() bumps, so after each change the picker
    really starts afresh (deleting the keys alone leaves the browser showing the old choice).
    """
    uni = cached.universe()
    gen = st.session_state.setdefault("picker_gen", 0)
    held = [h.ticker for h in fund.holdings]
    options = held + [t for t in uni.entries if t not in held] + [OTHER]
    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    sel = c1.selectbox(
        "Search for a share or ETF", options, index=None,
        placeholder="Type a name or ticker, e.g. Naspers or NPN", key=f"pick_{gen}",
        format_func=lambda t: "Another JSE or US ticker…" if t == OTHER else
        ("✓ " if t in held else "") + cached.label(t))
    ticker = sel
    if sel == OTHER:
        raw = c1.text_input("Ticker", placeholder="JSE tickers end in .JO, e.g. KIO.JO; US tickers have no suffix, e.g. AAPL",
                            key=f"other_ticker_{gen}").strip().upper()
        if not raw:
            return None, None
        if not data.is_supported(raw):
            st.error("Only JSE tickers (ending in .JO) and US-listed tickers are supported.")
            return None, None
        ticker = raw
    if not ticker:
        return None, None
    current = fund.amounts().get(ticker)
    amount = c2.number_input("Rand amount", min_value=0.0, value=float(current) if current else None, step=100.0,
                             format="%.2f", key=f"amt_{gen}_{ticker}", placeholder="e.g. 1000",
                             help="How many rand you'd put into this holding. Set it to 0 to remove it.")
    return ticker, amount


def apply(new: Fund, message: str) -> None:
    state.put(new)
    old = st.session_state.get("picker_gen", 0)
    for k in [k for k in st.session_state if str(k) in (f"pick_{old}", f"other_ticker_{old}")
              or str(k).startswith(f"amt_{old}_")]:
        st.session_state.pop(k, None)
    st.session_state.picker_gen = old + 1
    st.toast(message, icon=":material/check:")
    st.rerun()


def change_picker(fund: Fund):
    """(ticker, amount, spec) for the change being considered; spec feeds Fund.with_amount."""
    gen = st.session_state.setdefault("picker_gen", 0)
    kind = st.segmented_control("What are you adding?", list(ADD_KINDS), format_func=ADD_KINDS.get,
                                default="listed", key="add_kind") or "listed"
    if kind == "unit_trust":
        return pickers.unit_trust_picker(fund, gen)
    if kind == "unlisted":
        return pickers.unlisted_picker(fund, gen)
    ticker, amount = holding_picker(fund)
    if not ticker:
        return None, None, None
    uni = cached.universe()
    e = uni.get(ticker)
    h = fund.holding(ticker)
    spec = {"name": cached.name_of(ticker, fund), "kind": h.kind if h else uni.kind_of(ticker),
            "currency": e["currency"] if e else ("ZAR" if ticker.endswith(".JO") else "USD")}
    return ticker, amount, spec


def whole_numbers(f: Fund, stats) -> dict | None:
    """Whole-fund figures: the listed part from history plus unlisted holdings from their assumptions."""
    if not f.holdings:
        return None
    if stats is None and any(h.kind != "unlisted" for h in f.holdings if h.amount_zar > 0):
        return None
    mu, vol = (stats.exp_return, stats.vol) if stats is not None else (0.0, 0.0)
    wf = unlisted.whole_fund(f, mu, vol)
    if wf is None:
        return None
    sims = unlisted.simulate(f, mu, vol, 52, n_sims=20_000, seed=f.settings.seed)
    v, _ = var.mc_var_es(sims, 0.95)
    return {"illiquid": unlisted.illiquid_share(f), "exp_return": wf.exp_return, "vol": wf.vol, "var1y": v,
            "p_down20": float(np.mean(sims < -0.2))}


def unlisted_verdict(fund: Fund, after: Fund, cmp: Comparison, ticker: str, name: str) -> verdict.Verdict:
    """The verdict for an unlisted holding, from the whole-fund numbers (it has no price history)."""
    b_amt, a_amt = fund.amounts().get(ticker, 0.0), after.amounts().get(ticker, 0.0)
    action = ("add" if b_amt == 0 and a_amt > 0 else "remove" if a_amt == 0 else
              "increase" if a_amt > b_amt else "decrease" if a_amt < b_amt else "none")
    b, a = whole_numbers(fund, cmp.before), whole_numbers(after, cmp.after)
    if a is None:
        return verdict.Verdict(f"{name} is unlisted, so it has no price history to measure.", [], action)
    head = (f"Using your assumptions, the whole fund's expected return "
            + (f"goes from {C.pct(b['exp_return'])} to {C.pct(a['exp_return'])}" if b else f"is {C.pct(a['exp_return'])}")
            + f", and {C.pct(a['illiquid'], 0)} of it can't be sold in a hurry.")
    details = [f"{name} is unlisted, so the history-based numbers below leave it out. The whole-fund panel adds it "
               "with the return, range, lock-in and chance of loss you entered."]
    if b:
        details.append(f"Whole-fund volatility goes from {C.pct(b['vol'])} to {C.pct(a['vol'])}; the chance of losing "
                       f"over 20% in a year goes from {C.pct(b['p_down20'])} to {C.pct(a['p_down20'])}.")
    return verdict.Verdict(head, details, action)


def whole_fund_panel(fund: Fund, after: Fund, cmp: Comparison, moved: bool) -> None:
    """Listed part (history) + unlisted holdings (stated assumptions): the illiquid sleeve and whole-fund numbers."""
    st.subheader("Illiquid sleeve and the whole fund")
    b, a = whole_numbers(fund, cmp.before), whole_numbers(after, cmp.after)
    cur = a or b
    if cur is None:
        st.info("Add at least one holding with a price history to see the whole-fund numbers.")
        return
    labels = [("illiquid", "Can't be sold in a hurry", "lower", "Share of the fund's rands in unlisted holdings."),
              ("exp_return", "Expected return (whole fund)", "higher", "History for the listed part, your assumptions "
               "for the unlisted part, after the chance of total loss."),
              ("vol", "Volatility (whole fund)", "lower", "Includes the chance of total loss of unlisted holdings."),
              ("var1y", "1-year loss exceeded 1 year in 20", "lower", "From 20 000 simulated years (seeded)."),
              ("p_down20", "Chance of losing over 20% in a year", "lower", "From the same simulation.")]
    for i in range(0, len(labels), 3):  # rows of three, so phones keep the order
        cols = st.columns(3)
        for col, (k, label, better, help_) in zip(cols, labels[i:i + 3]):
            delta = None
            if moved and a and b:
                d = a[k] - b[k]
                delta = f"{d * 100:+.1f} pp" if abs(d) >= 0.0005 else None
            with col.container(border=True, height="stretch"):
                st.metric(label, C.pct(cur[k]), delta, delta_color="normal" if better == "higher" else "inverse",
                          help=help_)
    lad = unlisted.liquidity_ladder(after)
    if lad.iloc[1:].sum() > 0:
        df = pd.DataFrame({"How soon it could become cash": lad.index, "Amount": [C.rand(x) for x in lad.values],
                           "Share": lad.values / max(lad.sum(), 1e-9) * 100})
        st.dataframe(df, hide_index=True, width="stretch", column_config={
            "Share": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)})
    rows = []
    for h in after.unlisted():
        x = unlisted.assumptions_of(h)
        rows.append({"Holding": h.name, "Amount": C.rand(h.amount_zar), "What it is": x.category,
                     "If it goes to plan": C.pct(x.exp_return), "Expected (after loss chance)": C.pct(x.expected_return),
                     "Locked in (years)": f"{x.lockin_years:g}", "Chance lost a year": C.pct(x.p_loss),
                     "Correlation": f"{x.corr:.2f}"})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("These numbers rest on your own assumptions for the unlisted holdings, so they are only as good as "
               "those guesses. The Library's Woodford and MTI case files show what locked-up money and promised "
               "returns have meant in practice.")
    with st.expander("Show me the maths"):
        st.markdown(WHOLE_MATHS)


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
        h = fund.holding(t)
        if h is not None and h.kind == "unlisted":
            continue  # explained in the illiquid sleeve panel
        st.warning(f"**{cached.name_of(t, fund)}** is left out of the statistics: {why} Its rands still count "
                   "toward the fund's size.", icon=":material/warning:")
    if fund.unlisted():
        st.caption("Unlisted holdings have no price history, so the numbers above cover the listed part of the "
                   f"fund ({C.pct(cmp.after.coverage if cmp.after else 0, 0)} of its rands). The whole-fund view "
                   "below adds them using your assumptions.")
    uts = [h for h in fund.holdings if h.kind == "unit_trust"]
    if uts:
        st.caption("Unit trusts: " + "; ".join(f"**{h.name}** ({pickers.method_label(h.method).lower()})"
                                               for h in uts) + ". Unit price histories leave out the income a "
                   "fund pays out; modelled ones use index ETFs for each asset class (SA bonds: the whole "
                   "government bond market, so short-dated income funds come out more volatile than they are).")


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
                     "Type": HOLDING_KINDS[h.kind], "Measured by": pickers.method_label(h.method)})
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
ticker, amount, spec = change_picker(fund)

if ticker and spec:
    cl = dd.build(fund, ticker, spec)
    if cl is not None:
        dd.show(cl, f"{st.session_state.get('picker_gen', 0)}_{ticker}")

after, moved = fund, False
if ticker and amount is None:
    st.caption("Enter a rand amount to see what this holding would do to your fund.")
elif ticker:
    method = spec.get("method", "price_history")
    failures = cached.store().ensure([ticker]) if method == "price_history" else {}
    if ticker in failures:
        st.error(f"Couldn't get prices for {spec['name']}: {failures[ticker]}")
    else:
        after = fund.with_amount(ticker, amount, **spec)
        held = fund.holding(ticker)
        inputs_changed = held is not None and amount > 0 and (
            held.method != method or held.params != spec.get("params", held.params))
        if inputs_changed:
            after.holding(ticker).method = method
        moved = after.amounts().round(2).to_dict() != fund.amounts().round(2).to_dict() or inputs_changed

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
    v = (unlisted_verdict(fund, after, cmp, ticker, spec["name"]) if spec.get("kind") == "unlisted"
         else verdict.explain(cmp, ticker, spec["name"]))
    with st.container(border=True):
        st.markdown(f"**{v.headline}**")
        for d in v.details:
            st.markdown(f"- {d}")
        held_now = ticker in fund.amounts().index
        verb = {"add": "Add it", "increase": "Apply the increase", "decrease": "Apply the cut",
                "remove": "Remove it"}.get(v.action, "Apply")
        b1, b2, _ = st.columns([1, 1, 2])
        if b1.button(verb, type="primary", width="stretch"):
            apply(after, f"{v.action.title()}: {spec['name']}")
        if held_now and amount > 0 and b2.button("Remove instead", width="stretch"):
            apply(fund.without(ticker), f"Removed {spec['name']}")
    st.caption("Numbers below show **after** the change, with the change from before underneath. "
               "Nothing is applied until you press the button.")
else:
    st.subheader("Your fund at a glance")

C.metric_panel(cmp, after.settings, moved)
history_notes(cmp, after)

if fund.unlisted() or after.unlisted():
    whole_fund_panel(fund, after, cmp, moved)

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
