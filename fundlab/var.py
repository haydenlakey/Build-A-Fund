"""Value at Risk and Expected Shortfall, three ways.

Conventions: losses are reported as positive fractions of fund value over a
horizon of `h` weeks at confidence level `alpha` (for example 0.95).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import PERIODS_PER_YEAR


def parametric_var_es(mu_annual: float, vol_annual: float, h_weeks: int, alpha: float = 0.95,
                      dist: str = "normal", df: float = 5.0) -> tuple[float, float]:
    """Closed-form VaR and ES assuming horizon returns are normal or Student-t.

    The t distribution is scaled so its standard deviation equals vol.
    """
    mu_h = mu_annual * h_weeks / PERIODS_PER_YEAR
    sd_h = vol_annual * np.sqrt(h_weeks / PERIODS_PER_YEAR)
    if dist == "normal":
        z = stats.norm.ppf(1 - alpha)
        var = -(mu_h + z * sd_h)
        es = -mu_h + sd_h * stats.norm.pdf(z) / (1 - alpha)
    elif dist == "t":
        if df <= 2:
            raise ValueError("df must exceed 2 for a finite variance")
        scale = sd_h * np.sqrt((df - 2) / df)
        q = stats.t.ppf(1 - alpha, df)
        var = -(mu_h + q * scale)
        es = -mu_h + scale * (stats.t.pdf(q, df) * (df + q**2) / (df - 1)) / (1 - alpha)
    else:
        raise ValueError(f"unknown dist {dist!r}")
    return float(var), float(es)


def horizon_returns(port_weekly: pd.Series, h_weeks: int) -> pd.Series:
    """Overlapping compounded h-week returns from a weekly return series."""
    log_r = np.log1p(port_weekly.dropna())
    return np.expm1(log_r.rolling(h_weeks).sum().dropna())


def historical_var_es(port_weekly: pd.Series, h_weeks: int, alpha: float = 0.95) -> tuple[float, float]:
    r = horizon_returns(port_weekly, h_weeks).to_numpy()
    if r.size < 20:
        return float("nan"), float("nan")
    q = np.quantile(r, 1 - alpha)
    tail = r[r <= q]
    return float(-q), float(-tail.mean())


def simulate_weekly(mu_annual: pd.Series, cov_annual: pd.DataFrame, weights: pd.Series,
                    h_weeks: int, n_sims: int = 20_000, dist: str = "normal", df: float = 5.0,
                    seed: int = 42) -> np.ndarray:
    """Simulated weekly fund returns, shape (n_sims, h_weeks), rebalancing weekly.

    Weekly asset returns are drawn as mu/52 + L z, where z is standard normal or
    standardised multivariate t (the same draw of the chi-square mixing variable
    is shared across assets, so crashes hit everything together). Only the fund's
    return w'mu/52 + (w'L) z is kept.
    """
    if dist == "t" and df <= 2:
        raise ValueError("df must exceed 2")
    rng = np.random.default_rng(seed)
    idx = weights.index
    w = weights.to_numpy(dtype=float)
    mu_w = mu_annual.loc[idx].to_numpy(dtype=float) / PERIODS_PER_YEAR
    cov_w = cov_annual.loc[idx, idx].to_numpy(dtype=float) / PERIODS_PER_YEAR
    chol = np.linalg.cholesky(cov_w + 1e-14 * np.eye(len(w)))
    port_mu = w @ mu_w
    load = w @ chol  # (k,)
    out = np.empty((n_sims, h_weeks))
    for t in range(h_weeks):
        z = rng.standard_normal((n_sims, len(w)))
        if dist == "t":
            chi = rng.chisquare(df, size=n_sims)
            z = z * np.sqrt((df - 2) / chi)[:, None]
        out[:, t] = np.maximum(port_mu + z @ load, -1.0)
    return out


def simulate_paths(mu_annual: pd.Series, cov_annual: pd.DataFrame, weights: pd.Series,
                   h_weeks: int, n_sims: int = 20_000, dist: str = "normal", df: float = 5.0,
                   seed: int = 42) -> np.ndarray:
    """Compounded h-week fund returns prod(1 + r_t) - 1 from `simulate_weekly` (n_sims values)."""
    weekly = simulate_weekly(mu_annual, cov_annual, weights, h_weeks, n_sims, dist, df, seed)
    return np.prod(1.0 + weekly, axis=1) - 1.0


def fan(wealth: np.ndarray, percentiles=(5, 25, 50, 75, 95)) -> pd.DataFrame:
    """Percentiles of simulated wealth paths, shape (n_sims, T+1) -> rows = week 0..T, columns = percentiles."""
    return pd.DataFrame(np.percentile(wealth, percentiles, axis=0).T, columns=list(percentiles))


def mc_var_es(sim_returns: np.ndarray, alpha: float = 0.95) -> tuple[float, float]:
    q = np.quantile(sim_returns, 1 - alpha)
    return float(-q), float(-sim_returns[sim_returns <= q].mean())
