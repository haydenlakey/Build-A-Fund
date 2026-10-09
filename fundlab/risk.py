"""Portfolio risk statistics. Weights are fractions that sum to one."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import PERIODS_PER_YEAR


def _align(weights: pd.Series, cov: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    cov = cov.loc[weights.index, weights.index]
    return weights.to_numpy(dtype=float), cov.to_numpy(dtype=float)


def portfolio_return(weights: pd.Series, mu: pd.Series) -> float:
    return float(weights @ mu.loc[weights.index])


def portfolio_vol(weights: pd.Series, cov: pd.DataFrame) -> float:
    w, s = _align(weights, cov)
    return float(np.sqrt(max(w @ s @ w, 0.0)))


def risk_contributions(weights: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """Euler risk contributions RC_i = w_i (Sigma w)_i / sigma_p. They sum to sigma_p."""
    w, s = _align(weights, cov)
    sigma = np.sqrt(w @ s @ w)
    if sigma == 0:
        return pd.Series(0.0, index=weights.index)
    return pd.Series(w * (s @ w) / sigma, index=weights.index)


def risk_shares(weights: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """Fraction of total volatility from each holding (sums to one)."""
    rc = risk_contributions(weights, cov)
    total = rc.sum()
    return rc / total if total else rc


def sharpe(ret: float, vol: float, rf: float) -> float:
    return float((ret - rf) / vol) if vol > 0 else float("nan")


def diversification_ratio(weights: pd.Series, cov: pd.DataFrame) -> float:
    """Weighted average volatility divided by portfolio volatility (>= 1 when long-only).

    1 means no diversification benefit at all; higher is better.
    """
    w, s = _align(weights, cov)
    sd = np.sqrt(np.diag(s))
    vol = np.sqrt(w @ s @ w)
    return float((w @ sd) / vol) if vol > 0 else float("nan")


def effective_holdings(weights: pd.Series) -> float:
    """Inverse Herfindahl index 1 / sum(w_i^2): how many equal-sized holdings this is like."""
    w = weights.to_numpy(dtype=float)
    return float(1.0 / np.sum(w**2)) if len(w) else 0.0


def portfolio_returns(weights: pd.Series, returns: pd.DataFrame) -> pd.Series:
    """Weekly returns of a portfolio rebalanced back to `weights` every week."""
    return returns[weights.index] @ weights


def drawdown_series(port_returns: pd.Series) -> pd.Series:
    wealth = (1.0 + port_returns).cumprod()
    return wealth / wealth.cummax() - 1.0


def max_drawdown(port_returns: pd.Series) -> float:
    """Worst peak-to-trough fall, as a negative fraction."""
    if port_returns.empty:
        return float("nan")
    return float(drawdown_series(port_returns).min())


def average_correlation(weights: pd.Series, cov: pd.DataFrame) -> float:
    """Weight-weighted average pairwise correlation, excluding the diagonal."""
    w, s = _align(weights, cov)
    if len(w) < 2:
        return float("nan")
    sd = np.sqrt(np.diag(s))
    corr = s / np.outer(sd, sd)
    ww = np.outer(w, w)
    np.fill_diagonal(ww, 0.0)
    return float((ww * corr).sum() / ww.sum()) if ww.sum() > 0 else float("nan")


def annualised_vol(port_returns: pd.Series) -> float:
    return float(port_returns.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR))


def rolling_vol(port_returns: pd.Series, window: int = 26) -> pd.Series:
    return port_returns.rolling(window).std(ddof=1) * np.sqrt(PERIODS_PER_YEAR)
