"""Sensitivities (betas) to market factors, and clustering of holdings by correlation.

Betas come from ordinary least squares on weekly rand returns,

    r_fund,t = a + b * f_t + e_t,

with Newey-West (HAC) standard errors, because weekly returns can show
autocorrelation and changing volatility that make plain OLS standard errors
too small. Confidence intervals use the t distribution with n - k degrees of freedom.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform

from . import PERIODS_PER_YEAR

MIN_OBS = 52

# key -> (ticker of the rand price series, label, plain-language reading of beta = 1)
FACTORS = {
    "top40": ("STX40.JO", "JSE Top 40", "moves one for one with the Top 40"),
    "sp500": ("SPY", "S&P 500 in rand", "moves one for one with US shares measured in rand"),
    "usdzar": ("ZAR=X", "US dollar in rand", "gains 1% for each 1% the rand weakens against the dollar"),
    "gold": ("GC=F", "Gold in rand", "moves one for one with the rand gold price"),
    "commodities": ("DBC", "Broad commodities in rand", "moves one for one with a broad commodity basket in rand"),
}


def newey_west_lags(n: int) -> int:
    """Rule-of-thumb lag length L = floor(4 (n/100)^(2/9)) (Newey and West, 1994)."""
    return int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0)))


@dataclass
class OLSResult:
    coef: np.ndarray
    se: np.ndarray
    r2: float
    n: int
    lags: int

    def ci(self, conf: float = 0.95) -> tuple[np.ndarray, np.ndarray]:
        k = len(self.coef)
        q = stats.t.ppf(0.5 + conf / 2, max(self.n - k, 1))
        return self.coef - q * self.se, self.coef + q * self.se


def ols_hac(y: np.ndarray, X: np.ndarray, lags: int | None = None) -> OLSResult:
    """OLS of y on X (X includes the constant) with Newey-West covariance.

    b = (X'X)^-1 X'y,  V = (X'X)^-1 S (X'X)^-1,
    S = sum_t u_t^2 x_t x_t' + sum_{l=1..L} (1 - l/(L+1)) sum_t u_t u_{t-l} (x_t x_{t-l}' + x_{t-l} x_t'),
    scaled by n/(n-k) as a small-sample correction.
    """
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    n, k = X.shape
    L = newey_west_lags(n) if lags is None else lags
    xtx_inv = np.linalg.inv(X.T @ X)
    b = xtx_inv @ X.T @ y
    u = y - X @ b
    xu = X * u[:, None]
    S = xu.T @ xu
    for lag in range(1, L + 1):
        w = 1 - lag / (L + 1)
        g = xu[lag:].T @ xu[:-lag]
        S += w * (g + g.T)
    V = xtx_inv @ S @ xtx_inv * n / max(n - k, 1)
    tss = ((y - y.mean()) ** 2).sum()
    r2 = 1 - (u @ u) / tss if tss > 0 else float("nan")
    return OLSResult(b, np.sqrt(np.clip(np.diag(V), 0, None)), float(r2), n, L)


@dataclass
class Beta:
    key: str
    label: str
    beta: float
    se: float
    lo: float
    hi: float
    r2: float
    alpha: float  # annualised intercept (simple), not a forecast
    n: int
    corr: float

    @property
    def significant(self) -> bool:
        return self.lo > 0 or self.hi < 0


def factor_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Weekly simple returns of the factor price series (columns renamed to factor keys)."""
    cols = {FACTORS[k][0]: k for k in FACTORS if FACTORS[k][0] in prices.columns}
    return prices[list(cols)].rename(columns=cols).pct_change(fill_method=None)


def single_betas(port: pd.Series, fac: pd.DataFrame, conf: float = 0.95) -> list[Beta]:
    """One regression per factor, each on the weeks where both series exist."""
    out = []
    for key in fac.columns:
        df = pd.concat([port.rename("y"), fac[key].rename("x")], axis=1, join="inner").dropna()
        if len(df) < MIN_OBS:
            continue
        X = np.column_stack([np.ones(len(df)), df["x"].to_numpy()])
        res = ols_hac(df["y"].to_numpy(), X)
        lo, hi = res.ci(conf)
        out.append(Beta(key, FACTORS[key][1], float(res.coef[1]), float(res.se[1]), float(lo[1]), float(hi[1]),
                        res.r2, float(res.coef[0] * PERIODS_PER_YEAR), res.n, float(df["y"].corr(df["x"]))))
    return out


def joint_betas(port: pd.Series, fac: pd.DataFrame, conf: float = 0.95) -> tuple[pd.DataFrame, float, int]:
    """All factors in one regression: each beta holds the others fixed. Returns (table, R^2, n)."""
    df = pd.concat([port.rename("y"), fac], axis=1, join="inner").dropna()
    if len(df) < MIN_OBS + fac.shape[1]:
        return pd.DataFrame(), float("nan"), len(df)
    X = np.column_stack([np.ones(len(df)), df[fac.columns].to_numpy()])
    res = ols_hac(df["y"].to_numpy(), X)
    lo, hi = res.ci(conf)
    t = pd.DataFrame({"beta": res.coef[1:], "se": res.se[1:], "lo": lo[1:], "hi": hi[1:]}, index=list(fac.columns))
    return t, res.r2, res.n


# ---- correlation clustering ------------------------------------------------------------

def correlation(cov: pd.DataFrame) -> pd.DataFrame:
    sd = np.sqrt(np.diag(cov.to_numpy()))
    c = cov.to_numpy() / np.outer(sd, sd)
    return pd.DataFrame(np.clip(c, -1, 1), index=cov.index, columns=cov.columns)


@dataclass
class Clustering:
    order: list[str]
    groups: list[list[str]]  # groups of 2+ holdings that move closely together
    corr: pd.DataFrame  # reordered


def cluster(corr: pd.DataFrame, together: float = 0.7) -> Clustering:
    """Average-linkage clustering on the distance d_ij = sqrt((1 - rho_ij) / 2).

    Leaves are ordered so similar holdings sit side by side (optimal leaf ordering).
    Groups are cut where average correlation within a group is about `together` or more.
    """
    names = list(corr.index)
    if len(names) < 3:
        return Clustering(names, [names] if len(names) == 2 and corr.iloc[0, 1] >= together else [], corr)
    d = np.sqrt(np.clip((1 - corr.to_numpy()) / 2, 0, None))
    np.fill_diagonal(d, 0)
    Z = hierarchy.linkage(squareform(d, checks=False), method="average", optimal_ordering=True)
    order = [names[i] for i in hierarchy.leaves_list(Z)]
    labels = hierarchy.fcluster(Z, t=np.sqrt((1 - together) / 2), criterion="distance")
    groups = {}
    for n, g in zip(names, labels):
        groups.setdefault(g, []).append(n)
    multi = [sorted(g, key=order.index) for g in groups.values() if len(g) > 1]
    multi.sort(key=lambda g: order.index(g[0]))
    return Clustering(order, multi, corr.loc[order, order])
