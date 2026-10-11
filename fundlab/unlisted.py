"""Unlisted holdings: no price history, so everything comes from the user's stated assumptions.

Inputs per holding (annual, as fractions):
    exp_return    the return if things go to plan, r
    low, high     a bad and a good year if it survives, read as the 5th and 95th percentiles
    lockin_years  how long the money is locked in, L
    p_loss        the chance per year of losing everything, p
    corr          correlation with the listed part of the fund, rho (default 0.5)

Derived:
    sigma      = (high - low) / (2 * 1.645)                  volatility if it survives
    E[R]       = (1 - p)(1 + r) - 1                         expected return after the loss chance
    Var[R]     = p + (1 - p)(sigma^2 + r^2) - E[R]^2         total variance, including the loss
    P(lost over L years) = 1 - (1 - p)^L

Whole-fund view: the listed sleeve S (history-based mu_S, sigma_S) and each unlisted holding i form
a one-factor model, Cov(i, S) = rho_i sd_i sigma_S and Cov(i, j) = rho_i rho_j sd_i sd_j, which is
always positive semi-definite.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import PERIODS_PER_YEAR
from .model import Fund, Holding

Z95 = 1.645
DEFAULTS = {"exp_return": 0.12, "low": -0.10, "high": 0.30, "lockin_years": 5.0, "p_loss": 0.02, "corr": 0.5,
            "category": "Other"}
CATEGORIES = ["Property development", "Private business", "Property syndication", "Private loan or note",
              "Crypto or trading scheme", "Other"]
# rules of thumb for the warnings (shown to the user as such)
HIGH_RETURN = 0.20  # well above what listed shares have paid over long periods
EXTREME_RETURN = 0.50


@dataclass(frozen=True)
class Assumptions:
    exp_return: float
    low: float
    high: float
    lockin_years: float
    p_loss: float
    corr: float = 0.5
    category: str = "Other"

    def __post_init__(self):
        if not self.low <= self.exp_return <= self.high:
            raise ValueError("the return if it goes to plan must lie between the bad-year and good-year returns")
        if self.low <= -1:
            raise ValueError("a bad year can't lose more than everything (use the chance of total loss for that)")
        if not 0 <= self.p_loss < 1:
            raise ValueError("the chance of total loss must be between 0% and 100%")
        if not -1 <= self.corr <= 1:
            raise ValueError("the correlation must be between -1 and 1")
        if self.lockin_years < 0:
            raise ValueError("the lock-in can't be negative")

    @classmethod
    def from_params(cls, params: dict) -> "Assumptions":
        p = {**DEFAULTS, **(params or {})}
        return cls(**{k: (p[k] if k == "category" else float(p[k])) for k in DEFAULTS})

    def to_params(self) -> dict:
        return {k: getattr(self, k) for k in DEFAULTS}

    @property
    def vol_if_survives(self) -> float:
        return (self.high - self.low) / (2 * Z95)

    @property
    def expected_return(self) -> float:
        """E[R] = (1 - p)(1 + r) - 1."""
        return (1 - self.p_loss) * (1 + self.exp_return) - 1

    @property
    def total_vol(self) -> float:
        """sqrt(p + (1 - p)(sigma^2 + r^2) - E[R]^2)."""
        p, r, s = self.p_loss, self.exp_return, self.vol_if_survives
        return float(np.sqrt(max(p + (1 - p) * (s * s + r * r) - self.expected_return ** 2, 0.0)))

    def p_lost_over(self, years: float) -> float:
        return 1 - (1 - self.p_loss) ** years

    def warnings(self) -> list[str]:
        """Plain-language flags; each is a pattern the scam and liquidity case files describe."""
        out = []
        if self.exp_return >= EXTREME_RETURN:
            out.append(f"A promised {self.exp_return:.0%} a year is far beyond what any listed market has paid over "
                       "long periods. Schemes such as MTI advertised returns like this.")
        elif self.exp_return >= HIGH_RETURN:
            out.append(f"{self.exp_return:.0%} a year is well above what listed shares have paid over long periods "
                       "(this app's rule of thumb is 20%). High promised returns usually come with high risk, "
                       "or aren't real.")
        if self.p_loss == 0:
            out.append("You've set no chance of losing everything. Very few unlisted investments can honestly "
                       "promise that.")
        if self.high - self.low < 0.05:
            out.append("The range of outcomes is very narrow: a near-guaranteed return. Guarantees are a classic "
                       "warning sign unless a large, regulated institution stands behind them.")
        if self.lockin_years >= 5:
            out.append(f"The money is locked in for {self.lockin_years:g} years. You can't sell it if you need "
                       "the cash or if things start going wrong.")
        return out


def assumptions_of(h: Holding) -> Assumptions:
    return Assumptions.from_params(h.params)


# ---- illiquidity ----------------------------------------------------------------------------

LIQUIDITY_BUCKETS = ["Can be sold within days", "Locked up to 1 year", "Locked 1 to 5 years", "Locked over 5 years"]


def liquidity_ladder(fund: Fund) -> pd.Series:
    """Rand amounts by how soon they could be turned into cash (listed and unit trusts: within days)."""
    out = pd.Series(0.0, index=LIQUIDITY_BUCKETS)
    for h in fund.holdings:
        if h.amount_zar <= 0:
            continue
        if h.kind != "unlisted":
            out[LIQUIDITY_BUCKETS[0]] += h.amount_zar
            continue
        L = assumptions_of(h).lockin_years
        b = 0 if L == 0 else 1 if L <= 1 else 2 if L <= 5 else 3
        out[LIQUIDITY_BUCKETS[b]] += h.amount_zar
    return out


def illiquid_share(fund: Fund) -> float:
    """Share of the fund's rands in unlisted holdings (none of which can be sold on an exchange)."""
    total = fund.total_zar
    return float(sum(h.amount_zar for h in fund.unlisted()) / total) if total > 0 else 0.0


# ---- whole fund ------------------------------------------------------------------------------

@dataclass
class WholeFund:
    weights: pd.Series  # listed sleeve "Listed" + each unlisted ticker
    mu: pd.Series
    cov: pd.DataFrame
    exp_return: float
    vol: float
    listed_share: float


def whole_fund(fund: Fund, listed_mu: float, listed_vol: float) -> WholeFund | None:
    """Expected return and volatility of the whole fund from the listed sleeve's statistics plus the
    unlisted holdings' stated assumptions (one-factor covariance, see the module docstring)."""
    unl = fund.unlisted()
    total = fund.total_zar
    if total <= 0:
        return None
    listed_amt = total - sum(h.amount_zar for h in unl)
    has_listed = listed_amt > 1e-9
    if has_listed and not (np.isfinite(listed_mu) and np.isfinite(listed_vol)):
        return None
    a = {h.ticker: assumptions_of(h) for h in unl}
    rows = ([("Listed", listed_amt, listed_mu, listed_vol, 1.0)] if has_listed else []) +         [(h.ticker, h.amount_zar, a[h.ticker].expected_return, a[h.ticker].total_vol, a[h.ticker].corr) for h in unl]
    names = [r[0] for r in rows]
    w = pd.Series([r[1] for r in rows], index=names) / total
    mu = pd.Series([r[2] for r in rows], index=names)
    sd = pd.Series([r[3] for r in rows], index=names)
    load = pd.Series([r[4] for r in rows], index=names) * sd
    cov = pd.DataFrame(np.outer(load, load), index=names, columns=names)
    for t in names:
        cov.loc[t, t] = sd[t] ** 2
    er = float(w @ mu)
    vol = float(np.sqrt(max(w @ cov @ w, 0.0)))
    return WholeFund(w, mu, cov, er, vol, float(max(listed_amt, 0.0) / total))


def simulate(fund: Fund, listed_mu: float, listed_vol: float, h_weeks: int, n_sims: int = 20_000,
             seed: int = 42) -> np.ndarray:
    """Simulated whole-fund returns over h weeks, buy and hold (unlisted holdings can't be rebalanced).

    Listed sleeve: weekly normal returns, mean mu_S/52, sd sigma_S/sqrt(52) (as var.simulate_paths).
    Unlisted i, while it survives: weekly mean m_i = (1 + r_i)^(1/52) - 1 and weekly sd s_i chosen so a
    year compounds to exactly mean r_i and sd sigma_i:  s_i^2 = ((1 + r_i)^2 + sigma_i^2)^(1/52) - (1 + m_i)^2.
    Its shock is rho_i z_S + sqrt(1 - rho_i^2) e_i. Each week it fails with probability 1 - (1 - p_i)^(1/52),
    after which it is worth nothing.
    """
    rng = np.random.default_rng(seed)
    unl = fund.unlisted()
    total = fund.total_zar
    listed_amt = total - sum(h.amount_zar for h in unl)
    a = [assumptions_of(h) for h in unl]
    listed = np.full(n_sims, listed_amt / total)
    vals = np.tile(np.array([h.amount_zar / total for h in unl]), (n_sims, 1))
    alive = np.ones_like(vals, dtype=bool)
    m = np.array([(1 + x.exp_return) ** (1 / PERIODS_PER_YEAR) - 1 for x in a])
    s = np.sqrt(np.maximum(np.array([((1 + x.exp_return) ** 2 + x.vol_if_survives ** 2) ** (1 / PERIODS_PER_YEAR)
                                     for x in a]) - (1 + m) ** 2, 0.0))
    rho = np.array([x.corr for x in a])
    q = np.array([1 - (1 - x.p_loss) ** (1 / PERIODS_PER_YEAR) for x in a])
    mu_s, sd_s = listed_mu / PERIODS_PER_YEAR, (listed_vol if np.isfinite(listed_vol) else 0.0) / np.sqrt(PERIODS_PER_YEAR)
    for _ in range(h_weeks):
        z = rng.standard_normal(n_sims)
        listed *= 1 + mu_s + sd_s * z
        if len(a):
            e = rng.standard_normal(vals.shape)
            shock = rho * z[:, None] + np.sqrt(1 - rho ** 2) * e
            vals *= 1 + m + s * shock
            alive &= rng.random(vals.shape) >= q
            vals = np.where(alive, vals, 0.0)
    return listed + vals.sum(axis=1) - 1.0
