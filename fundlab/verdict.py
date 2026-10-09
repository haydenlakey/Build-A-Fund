"""Plain-language verdict on what a change to the fund did.

Describes, never recommends: every sentence says what happened to the numbers
and why, in terms of correlation and the holding's own volatility.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .analysis import Comparison, asset_vol, correlation_with_rest

RET_EPS = 0.001  # changes smaller than 0.1 percentage points count as "about the same"
VOL_EPS = 0.001
HIGH_CORR, LOW_CORR = 0.7, 0.3


@dataclass
class Verdict:
    headline: str
    details: list[str]
    action: str  # add | increase | decrease | remove | none
    corr: float = float("nan")


def _pp(x: float) -> str:
    return f"{x * 100:.1f}%"


def _action(before_w, after_w, ticker: str) -> str:
    b, a = before_w.get(ticker, 0.0), after_w.get(ticker, 0.0)
    if b == 0 and a > 0:
        return "add"
    if a == 0 and b > 0:
        return "remove"
    if a > b:
        return "increase"
    if a < b:
        return "decrease"
    return "none"


def explain(cmp: Comparison, ticker: str, name: str | None = None) -> Verdict:
    name = name or ticker
    b, a = cmp.before, cmp.after
    if a is None and b is None:
        return Verdict("Not enough price history to measure this fund yet.", [], "none")
    if b is None:
        vol = a.vol
        return Verdict(f"{name} is your first holding, so the fund's risk is simply its risk: "
                       f"about {_pp(vol)} a year of volatility.", [], "add")
    if a is None:
        return Verdict(f"With {name} gone, there is nothing left to measure.", [], "remove")

    action = _action(b.weights, a.weights, ticker)
    if ticker not in cmp.est.returns.columns:
        reason = cmp.est.report.excluded.get(ticker, "it has too little price history")
        return Verdict(f"{name} can't be measured, so the statistics ignore it: {reason}", [], action)

    # "what you already hold" = the rest of the fund, whose proportions this change leaves untouched
    rho = correlation_with_rest(ticker, b.weights, cmp.est.returns)
    own_vol = asset_vol(ticker, cmp.est.cov)
    d_ret, d_vol = a.exp_return - b.exp_return, a.vol - b.vol

    ret_word = ("adds expected return" if d_ret > RET_EPS else
                "lowers expected return" if d_ret < -RET_EPS else
                "leaves expected return about the same")
    adding = action in ("add", "increase")
    subject = name if adding else f"Cutting {name}" if action == "decrease" else f"Removing {name}"

    if np.isnan(rho):
        risk_clause = f"volatility goes from {_pp(b.vol)} to {_pp(a.vol)}"
    elif adding:
        if rho >= HIGH_CORR and d_vol > VOL_EPS:
            risk_clause = (f"but it's {rho:.2f} correlated with what you already hold, "
                           f"so risk rises almost one for one ({_pp(b.vol)} → {_pp(a.vol)})")
        elif rho >= HIGH_CORR and d_vol < -VOL_EPS:
            risk_clause = (f"and risk falls ({_pp(b.vol)} → {_pp(a.vol)}), but only because it is calmer "
                           f"itself ({_pp(own_vol)} volatility): at {rho:.2f} correlation it barely diversifies")
        elif rho >= HIGH_CORR:
            risk_clause = f"and at {rho:.2f} correlation with what you hold, it adds little diversification"
        elif rho < LOW_CORR and d_vol < -VOL_EPS:
            risk_clause = (f"and because it has low correlation ({rho:.2f}) with the rest of the fund, "
                           f"risk falls ({_pp(b.vol)} → {_pp(a.vol)})")
        elif rho < LOW_CORR:
            risk_clause = (f"and risk moves {_pp(b.vol)} → {_pp(a.vol)}. Its low correlation ({rho:.2f}) "
                           f"softens the effect of its own {_pp(own_vol)} volatility")
        else:
            risk_clause = (f"and it is partly correlated ({rho:.2f}) with what you hold, so it diversifies "
                           f"a little: risk {_pp(b.vol)} → {_pp(a.vol)}")
    else:
        if d_vol > VOL_EPS and rho < LOW_CORR:
            risk_clause = (f"and risk rises ({_pp(b.vol)} → {_pp(a.vol)}): it had low correlation ({rho:.2f}) "
                           f"with the rest, so it was doing diversification work")
        elif d_vol < -VOL_EPS and rho >= HIGH_CORR:
            risk_clause = (f"and risk falls ({_pp(b.vol)} → {_pp(a.vol)}): it was {rho:.2f} correlated "
                           f"with the rest, so it mostly doubled up on the same bet")
        else:
            risk_clause = f"and risk moves {_pp(b.vol)} → {_pp(a.vol)} (correlation with the rest: {rho:.2f})"

    headline = f"{subject} {ret_word}, {risk_clause}."
    headline = headline[0].upper() + headline[1:]

    details = []
    d_sharpe = a.sharpe - b.sharpe
    if abs(d_sharpe) >= 0.01:
        details.append(f"Return per unit of risk (Sharpe ratio) {'improves' if d_sharpe > 0 else 'worsens'} "
                       f"from {b.sharpe:.2f} to {a.sharpe:.2f}.")
    d_gap = cmp.gap_after - cmp.gap_before
    if d_gap < -0.002:
        details.append(f"The fund moves closer to the efficient frontier: its excess risk over the best "
                       f"mix of these holdings at the same expected return falls from {_pp(cmp.gap_before)} "
                       f"to {_pp(cmp.gap_after)}.")
    elif d_gap > 0.002:
        details.append(f"The fund moves further from the efficient frontier: its excess risk over the best "
                       f"mix of these holdings at the same expected return rises from {_pp(cmp.gap_before)} "
                       f"to {_pp(cmp.gap_after)}.")
    else:
        details.append("Its distance from the efficient frontier barely changes.")
    if a.eff_holdings - b.eff_holdings <= -0.5:
        details.append(f"It concentrates the fund: it now behaves like {a.eff_holdings:.1f} equal-sized "
                       f"holdings, down from {b.eff_holdings:.1f}.")
    return Verdict(headline, details, action, rho)
