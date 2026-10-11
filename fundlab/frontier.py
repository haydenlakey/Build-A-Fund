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


# ---- single optimised portfolios --------------------------------------------------------

GOALS = {"same_risk": "Same risk, highest expected return", "same_return": "Same expected return, lowest risk",
         "max_sharpe": "Highest Sharpe ratio"}


def _slsqp(obj, jac, n: int, cons: list, w0: np.ndarray | None = None) -> np.ndarray | None:
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones(n)}] + cons
    res = minimize(obj, np.full(n, 1.0 / n) if w0 is None else w0, jac=jac, bounds=[(0.0, 1.0)] * n,
                   constraints=cons, method="SLSQP", options={"maxiter": 500, "ftol": 1e-12})
    if not res.success:
        return None
    w = np.clip(res.x, 0, None)
    return w / w.sum()


def optimise(mu: pd.Series, cov: pd.DataFrame, goal: str, target_vol: float = float("nan"),
             target_ret: float = float("nan"), rf: float = 0.0) -> pd.Series | None:
    """Long-only weights (sum to one, each 0..1) for one goal:

    same_risk:   max w'mu       subject to w' Sigma w <= target_vol^2
    same_return: min w' Sigma w subject to w'mu >= target_ret
    max_sharpe:  max (w'mu - rf) / sqrt(w' Sigma w)
    """
    idx = mu.index
    m = mu.to_numpy(dtype=float)
    s = cov.loc[idx, idx].to_numpy(dtype=float)
    n = len(m)
    if n == 1:
        return pd.Series([1.0], index=idx)
    if goal == "same_risk":
        cons = [{"type": "ineq", "fun": lambda w: target_vol ** 2 - w @ s @ w, "jac": lambda w: -2 * s @ w}]
        w = _slsqp(lambda w: -(w @ m), lambda w: -m, n, cons)
    elif goal == "same_return":
        cons = [{"type": "ineq", "fun": lambda w: w @ m - target_ret, "jac": lambda w: m}]
        w = _slsqp(lambda w: w @ s @ w, lambda w: 2 * s @ w, n, cons)
    elif goal == "max_sharpe":
        def neg_sr(w):
            v = np.sqrt(max(w @ s @ w, 1e-16))
            return -(w @ m - rf) / v

        def neg_sr_jac(w):
            v = np.sqrt(max(w @ s @ w, 1e-16))
            return -(m * v - (w @ m - rf) * (s @ w) / v) / v ** 2
        w = _slsqp(neg_sr, neg_sr_jac, n, [])
    else:
        raise ValueError(f"unknown goal {goal!r}")
    return None if w is None else pd.Series(w, index=idx)


def resampled_weights(mu: pd.Series, se: pd.Series, cov: pd.DataFrame, goal: str, n_draws: int = 200,
                      seed: int = 42, **targets) -> pd.DataFrame:
    """Re-run `optimise` with expected returns drawn from N(mu_i, se_i^2) (independently), to show how much the
    'best' weights depend on estimates nobody knows precisely. Rows = draws, columns = holdings."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_draws):
        m = mu + rng.standard_normal(len(mu)) * se.loc[mu.index].to_numpy()
        w = optimise(m, cov, goal, **targets)
        if w is not None:
            out.append(w)
    return pd.DataFrame(out, columns=mu.index)
