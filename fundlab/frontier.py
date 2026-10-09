"""Long-only mean-variance efficient frontier."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass
class Frontier:
    rets: np.ndarray
    vols: np.ndarray
    weights: list[pd.Series]

    def vol_at(self, target_ret: float) -> float:
        """Frontier volatility at a given expected return (linear interpolation)."""
        if len(self.rets) == 0:
            return float("nan")
        if target_ret <= self.rets[0]:
            return float(self.vols[0])
        if target_ret >= self.rets[-1]:
            return float(self.vols[-1])
        return float(np.interp(target_ret, self.rets, self.vols))


def _min_var(cov: np.ndarray, mu: np.ndarray, target: float | None,
             w0: np.ndarray | None = None) -> np.ndarray | None:
    n = len(mu)
    ones = np.ones(n)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: ones}]
    if target is not None:
        cons.append({"type": "eq", "fun": lambda w: w @ mu - target, "jac": lambda w: mu})
    start = np.full(n, 1.0 / n) if w0 is None else w0
    res = minimize(lambda w: w @ cov @ w, start, jac=lambda w: 2 * cov @ w,
                   bounds=[(0.0, 1.0)] * n, constraints=cons, method="SLSQP",
                   options={"maxiter": 500, "ftol": 1e-12})
    return res.x if res.success else None


def efficient_frontier(mu: pd.Series, cov: pd.DataFrame, n_points: int = 30) -> Frontier:
    """Upper (efficient) branch of the long-only frontier, from min-variance to max return."""
    idx = mu.index
    m = mu.to_numpy(dtype=float)
    s = cov.loc[idx, idx].to_numpy(dtype=float)
    if len(m) == 1:
        return Frontier(np.array([m[0]]), np.array([np.sqrt(s[0, 0])]), [pd.Series([1.0], index=idx)])
    w0 = _min_var(s, m, None)
    if w0 is None:
        return Frontier(np.array([]), np.array([]), [])
    r_lo, r_hi = float(w0 @ m), float(m.max())
    rets, vols, ws = [], [], []
    prev = w0
    for t in np.linspace(r_lo, r_hi, n_points):
        w = w0 if t == r_lo else _min_var(s, m, t, prev)  # warm start from the previous point
        if w is None:
            continue
        prev = w
        w = np.clip(w, 0, None)
        w /= w.sum()
        rets.append(float(w @ m))
        vols.append(float(np.sqrt(w @ s @ w)))
        ws.append(pd.Series(w, index=idx))
    order = np.argsort(rets)
    return Frontier(np.array(rets)[order], np.array(vols)[order], [ws[i] for i in order])


def efficiency_gap(port_ret: float, port_vol: float, frontier: Frontier) -> float:
    """Extra volatility the fund carries versus the frontier at the same expected return.

    Zero means the fund sits on its own frontier.
    """
    return max(0.0, port_vol - frontier.vol_at(port_ret))
