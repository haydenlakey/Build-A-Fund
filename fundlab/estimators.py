"""Estimators for expected return and covariance from weekly returns.

All inputs are pandas DataFrames of simple weekly returns (rows = weeks,
columns = assets). Outputs are annualised.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import PERIODS_PER_YEAR

COV_METHODS = {
    "ledoit_wolf": "Ledoit-Wolf (shrunk to constant correlation)",
    "sample": "Sample covariance",
    "ewma": "Exponentially weighted (recent weeks count more)",
}


def prices_to_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple returns from a price frame. Leading NaNs (before listing) stay NaN."""
    return prices.pct_change(fill_method=None).iloc[1:]


def mean_returns(returns: pd.DataFrame, shrinkage: float = 0.0) -> pd.Series:
    """Annualised historical mean, optionally shrunk toward the cross-sectional average.

    mu_i* = (1 - a) * mu_i + a * mean(mu)   with a in [0, 1].
    Shrinkage is a blunt but honest response to how noisy sample means are.
    """
    if not 0.0 <= shrinkage <= 1.0:
        raise ValueError("shrinkage must be between 0 and 1")
    mu = returns.mean() * PERIODS_PER_YEAR
    return (1.0 - shrinkage) * mu + shrinkage * mu.mean()


def mean_standard_error(returns: pd.Series) -> float:
    """Annualised standard error of the mean return: sigma / sqrt(years)."""
    n = returns.dropna().shape[0]
    if n < 2:
        return float("nan")
    sigma_annual = returns.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR)
    years = n / PERIODS_PER_YEAR
    return float(sigma_annual / np.sqrt(years))


def sample_cov(returns: pd.DataFrame) -> pd.DataFrame:
    return returns.cov(ddof=1) * PERIODS_PER_YEAR


def ewma_cov(returns: pd.DataFrame, lam: float = 0.97) -> pd.DataFrame:
    """Exponentially weighted covariance. Weight on week t-k is proportional to lam**k.

    lam = 0.97 on weekly data gives a half-life of about 23 weeks.
    """
    if not 0.0 < lam < 1.0:
        raise ValueError("lam must be in (0, 1)")
    x = returns.to_numpy()
    n = x.shape[0]
    w = lam ** np.arange(n - 1, -1, -1)
    w = w / w.sum()
    mu = w @ x
    xc = x - mu
    cov = (xc * w[:, None]).T @ xc
    # bias correction for weighted samples
    cov = cov / (1.0 - np.sum(w**2))
    return pd.DataFrame(cov * PERIODS_PER_YEAR, index=returns.columns, columns=returns.columns)


def ledoit_wolf_cov(returns: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Ledoit & Wolf (2004) shrinkage toward the constant-correlation target.

    Reference: Ledoit, O. & Wolf, M. (2004) "Honey, I shrunk the sample
    covariance matrix", Journal of Portfolio Management 30(4).
    Returns (annualised covariance, shrinkage intensity delta in [0, 1]).
    """
    x = returns.to_numpy()
    n, p = x.shape
    if p == 1:
        return sample_cov(returns), 0.0
    xc = x - x.mean(axis=0)
    s = xc.T @ xc / n
    var = np.diag(s)
    sd = np.sqrt(var)
    corr = s / np.outer(sd, sd)
    rbar = (corr.sum() - p) / (p * (p - 1))
    f = rbar * np.outer(sd, sd)
    np.fill_diagonal(f, var)

    # pi-hat: sum of asymptotic variances of the sample covariance entries
    y = xc**2
    pi_mat = (y.T @ y) / n - s**2
    pi_hat = pi_mat.sum()

    # rho-hat: asymptotic covariances between target and sample entries.
    # theta[i, j] = mean((x_i^2 - s_ii)(x_i x_j - s_ij)) = mean(x_i^3 x_j) - s_ii s_ij
    theta_mat = ((xc**3).T @ xc) / n - var[:, None] * s
    rho_off = rbar / 2.0 * (
        (np.outer(1 / sd, sd)) * theta_mat + (np.outer(sd, 1 / sd)) * theta_mat.T
    )
    np.fill_diagonal(rho_off, 0.0)
    rho_hat = np.diag(pi_mat).sum() + rho_off.sum()

    gamma_hat = np.linalg.norm(f - s, "fro") ** 2
    kappa = (pi_hat - rho_hat) / gamma_hat if gamma_hat > 0 else 0.0
    delta = float(max(0.0, min(1.0, kappa / n)))
    shrunk = delta * f + (1.0 - delta) * s
    # rescale from 1/n to the usual 1/(n-1) convention, then annualise
    shrunk = shrunk * n / (n - 1) * PERIODS_PER_YEAR
    return pd.DataFrame(shrunk, index=returns.columns, columns=returns.columns), delta


def covariance(returns: pd.DataFrame, method: str = "ledoit_wolf", **kwargs) -> pd.DataFrame:
    if method == "sample":
        return sample_cov(returns)
    if method == "ewma":
        return ewma_cov(returns, **kwargs)
    if method == "ledoit_wolf":
        return ledoit_wolf_cov(returns)[0]
    raise ValueError(f"unknown covariance method {method!r}")


def cov_to_corr(cov: pd.DataFrame) -> pd.DataFrame:
    sd = np.sqrt(np.diag(cov))
    return cov / np.outer(sd, sd)
