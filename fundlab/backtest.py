"""Backtests: today's mix replayed over the past, rebalanced on a schedule, with trading costs.

Holdings start at the target weights w (value 1, no purchase cost, so every line starts level).
Each week h_i <- h_i (1 + r_i). Before the first week of a new month, quarter or year (every week
for "weekly"), i.e. at the previous week's close, with V = sum h_i, the trades are d_i = V w_i - h_i
and the cost

    C = b * sum_i max(d_i, 0) + s * sum_i max(-d_i, 0)

is taken from the fund before it is reset to (V - C) w. Turnover is sum |d_i| / (2 V).
"Never" lets the weights drift (buy and hold).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import PERIODS_PER_YEAR, risk

SCHEDULES = {"never": "Never (let it drift)", "yearly": "Once a year", "quarterly": "Every quarter",
             "monthly": "Every month", "weekly": "Every week"}


def rebalance_weeks(index: pd.DatetimeIndex, schedule: str) -> np.ndarray:
    """Boolean mask of the weeks on which to rebalance (never the first week)."""
    if schedule == "never":
        return np.zeros(len(index), dtype=bool)
    if schedule == "weekly":
        out = np.ones(len(index), dtype=bool)
    else:
        key = {"monthly": index.year * 12 + index.month, "quarterly": index.year * 4 + index.quarter,
               "yearly": index.year}[schedule]
        key = np.asarray(key)
        out = np.concatenate([[False], key[1:] != key[:-1]])
    out[0] = False
    return out


@dataclass
class Run:
    wealth: pd.Series  # starts at 1 the week before the first return
    turnover: float  # total one-way turnover over the run, as a multiple of fund value
    costs: float  # total trading costs paid, as a fraction of starting value (approx., in start-value terms)
    n_rebalances: int


def run(returns: pd.DataFrame, weights: pd.Series, schedule: str = "quarterly", buy_cost: float = 0.0,
        sell_cost: float = 0.0) -> Run:
    w = (weights / weights.sum()).to_numpy(dtype=float)
    r = returns[weights.index].to_numpy(dtype=float)
    reb = rebalance_weeks(returns.index, schedule)
    h = w.copy()
    out = np.empty(len(r))
    turnover = costs = 0.0
    n = 0
    for t in range(len(r)):
        if reb[t]:  # trade at the previous week's close, so the new period starts on target
            V = h.sum()
            d = V * w - h
            c = buy_cost * d[d > 0].sum() - sell_cost * d[d < 0].sum()
            turnover += np.abs(d).sum() / (2 * V) if V > 0 else 0.0
            costs += c
            h = (V - c) * w
            n += 1
        h = h * (1 + r[t])
        out[t] = h.sum()
    start = returns.index[0] - pd.Timedelta(weeks=1)
    wealth = pd.Series(np.concatenate([[1.0], out]), index=pd.DatetimeIndex([start]).append(returns.index))
    return Run(wealth, float(turnover), float(costs), n)


def stats(wealth: pd.Series, risk_free: float) -> dict[str, float]:
    """Total return, yearly return (CAGR), volatility, worst fall and Sharpe ratio of a wealth path."""
    r = wealth.pct_change().dropna()
    years = len(r) / PERIODS_PER_YEAR
    total = float(wealth.iloc[-1] / wealth.iloc[0] - 1)
    cagr = float((1 + total) ** (1 / years) - 1) if years > 0 and total > -1 else float("nan")
    vol = risk.annualised_vol(r)
    return {"total": total, "cagr": cagr, "vol": vol, "worst": risk.max_drawdown(r),
            "sharpe": risk.sharpe(cagr, vol, risk_free)}
