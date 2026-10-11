"""Borrowing to invest: margin calls, forced selling and wipe-outs.

You put in equity E_0 = 1 and borrow D_0 = L - 1, so you hold assets A_0 = L
(leverage L). The debt is not rebalanced: each week

    A_t = A_{t-1} (1 + r_t)             the investments move with the fund
    D_t = D_{t-1} (1 + b / 52)          interest at the borrowing rate b accrues on the loan
    E_t = A_t - D_t                     your own money

The lender checks once a week. If your share of the assets E_t / A_t falls below
the maintenance level m, it sells s_t = A_t - L E_t of the assets and repays debt
with the proceeds, which restores E_t / A_t = 1 / L. If E_t <= 0 you are wiped out
(every rand you put in is gone; the loss beyond it is owed to the lender) and the
path stops at zero.

Weekly checks understate real margin calls, which happen during the day.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import PERIODS_PER_YEAR


def default_maintenance(leverage: float) -> float:
    """Half the starting equity share 1 / L (the app's assumption, editable)."""
    return 0.5 / leverage


@dataclass
class MarginPaths:
    equity: np.ndarray  # (n, T+1) your own money, starting at 1
    assets: np.ndarray  # (n, T+1) investments held, starting at L
    sold: np.ndarray  # (n, T) assets sold in forced sales (fraction of starting equity)
    wiped: np.ndarray  # (n,) bool
    wiped_at: np.ndarray  # (n,) week index of the wipe-out, -1 if never

    @property
    def n_calls(self) -> np.ndarray:
        return (self.sold > 0).sum(axis=1)

    @property
    def max_drawdown(self) -> np.ndarray:
        """Worst peak-to-trough fall in your own money, per path (negative fractions; -1 = wiped out)."""
        peak = np.maximum.accumulate(self.equity, axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            dd = np.where(peak > 0, self.equity / peak - 1.0, -1.0)
        return dd.min(axis=1)


def margin_paths(weekly: np.ndarray, leverage: float, borrow_rate: float,
                 maintenance: float | None = None) -> MarginPaths:
    """Apply the rules in the module docstring to weekly fund returns, shape (n, T) or (T,)."""
    r = np.atleast_2d(np.asarray(weekly, dtype=float))
    if leverage < 1:
        raise ValueError("leverage must be at least 1")
    m = default_maintenance(leverage) if maintenance is None else maintenance
    if leverage > 1 and not 0 < m < 1 / leverage:
        raise ValueError("the margin-call level must be above 0 and below your starting share 1/L")
    n, T = r.shape
    growth = 1.0 + borrow_rate / PERIODS_PER_YEAR
    A = np.full(n, float(leverage))
    D = np.full(n, float(leverage) - 1.0)
    eq = np.empty((n, T + 1)); eq[:, 0] = 1.0
    assets = np.empty((n, T + 1)); assets[:, 0] = A
    sold = np.zeros((n, T))
    wiped = np.zeros(n, dtype=bool)
    wiped_at = np.full(n, -1)
    for t in range(T):
        live = ~wiped
        A = np.where(live, A * (1.0 + r[:, t]), 0.0)
        D = np.where(live, D * growth, 0.0)
        E = A - D
        newly = live & (E <= 0)
        wiped |= newly
        wiped_at[newly] = t + 1
        A = np.where(wiped, 0.0, A)
        D = np.where(wiped, 0.0, D)
        E = np.where(wiped, 0.0, E)
        if leverage > 1:
            call = ~wiped & (E < m * A)
            s = np.where(call, A - leverage * E, 0.0)
            A, D = A - s, D - s
            sold[:, t] = s
        eq[:, t + 1] = E
        assets[:, t + 1] = A
    return MarginPaths(eq, assets, sold, wiped, wiped_at)


def history(port_returns: pd.Series, leverage: float, borrow_rate: float,
            maintenance: float | None = None) -> pd.DataFrame:
    """The rules applied to the fund's actual weekly returns. Columns: unlevered, equity, assets, sold
    (all relative to R1 of your own money at the start), indexed by week (the first row is the start)."""
    r = port_returns.dropna()
    mp = margin_paths(r.to_numpy(), leverage, borrow_rate, maintenance)
    start = r.index[0] - pd.Timedelta(weeks=1) if len(r) else pd.Timestamp("today")
    idx = pd.DatetimeIndex([start]).append(r.index)
    return pd.DataFrame({
        "unlevered": np.concatenate([[1.0], np.cumprod(1.0 + r.to_numpy())]),
        "equity": mp.equity[0], "assets": mp.assets[0], "sold": np.concatenate([[0.0], mp.sold[0]]),
    }, index=idx)


@dataclass
class SimSummary:
    p_wiped: float
    p_call: float
    median_end: float  # your money at the end, per R1 put in
    low_end: float  # 5th percentile of the same
    median_drawdown: float


def summarise(mp: MarginPaths) -> SimSummary:
    end = mp.equity[:, -1]
    return SimSummary(float(mp.wiped.mean()), float((mp.n_calls > 0).mean()), float(np.median(end)),
                      float(np.percentile(end, 5)), float(np.median(mp.max_drawdown)))
