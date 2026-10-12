"""Explore diversifiers: what adding new money to each holding in the preset universe would historically
have done to the fund's volatility.

Everything is measured on the fund's own history window, so every candidate faces the same weeks; a
candidate without prices for the whole window is skipped (and reported). One covariance matrix is
estimated for the fund's holdings and all candidates together.

Adding x rands to candidate c (not yet held) on top of a measured fund worth T: with s = x / (T + x),

    w' = (1 - s) w + s e_c
    sigma'^2 = (1 - s)^2 w'Sw + 2 s (1 - s) (S w)_c + s^2 S_cc
    mu' = (1 - s) w'mu + s mu_c

At the margin (s -> 0), d sigma / d s = sigma (beta_c - 1), where beta_c = (S w)_c / sigma^2 is the
candidate's beta to the fund: anything with beta below 1 lowers risk when a little is added.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import estimators
from .model import FundSettings


@dataclass
class Exploration:
    table: pd.DataFrame  # index ticker: vol, ret, corr, beta, vol_after, d_vol, ret_after, d_ret; sorted by d_vol
    vol_before: float
    ret_before: float
    add_share: float  # s: share of the enlarged measured fund that is the new holding
    start: pd.Timestamp
    end: pd.Timestamp
    n_weeks: int
    skipped: dict[str, str] = field(default_factory=dict)


def explore(prices: pd.DataFrame, weights: pd.Series, candidates: list[str], start: pd.Timestamp,
            end: pd.Timestamp, settings: FundSettings, add_zar: float, measured_zar: float) -> Exploration | None:
    """Rank candidates by the change in fund volatility from adding `add_zar` rands to each.

    `weights` are the fund's measured weights (summing to 1), `measured_zar` the rands they cover.
    """
    held = list(weights.index)
    window = prices.loc[start:end]
    skipped, ok = {}, []
    for c in dict.fromkeys(candidates):
        if c in held:
            continue
        if c not in window.columns or window[c].notna().sum() == 0:
            skipped[c] = "No price data."
        elif window[c].isna().any():
            first = prices[c].first_valid_index()
            skipped[c] = (f"Prices start {first:%d %b %Y}, after this window starts." if first is not None and first > start
                          else "Gaps in its prices over this window.")
        else:
            ok.append(c)
    if not ok or window[held].isna().any().any() or add_zar <= 0 or measured_zar <= 0:
        return None
    rets = estimators.prices_to_returns(window[held + ok])
    target = estimators.equal_sharpe_target(rets, settings.risk_free, settings.prior_sharpe)
    mu = estimators.mean_returns(rets, settings.mean_shrinkage, target)
    cov = estimators.covariance(rets, settings.cov_method)

    w = weights.reindex(held).to_numpy(dtype=float)
    s_ff = cov.loc[held, held].to_numpy()
    var_p = float(w @ s_ff @ w)
    vol_p, ret_p = float(np.sqrt(var_p)), float(w @ mu[held].to_numpy())
    cross = cov.loc[ok, held].to_numpy() @ w  # (S w)_c
    var_c = np.diag(cov.loc[ok, ok].to_numpy())
    s = add_zar / (measured_zar + add_zar)
    vol_after = np.sqrt((1 - s) ** 2 * var_p + 2 * s * (1 - s) * cross + s ** 2 * var_c)
    ret_after = (1 - s) * ret_p + s * mu[ok].to_numpy()
    table = pd.DataFrame({
        "vol": np.sqrt(var_c), "ret": mu[ok].to_numpy(),
        "corr": cross / (np.sqrt(var_c) * vol_p), "beta": cross / var_p,
        "vol_after": vol_after, "d_vol": vol_after - vol_p,
        "ret_after": ret_after, "d_ret": ret_after - ret_p,
    }, index=pd.Index(ok, name="ticker")).sort_values("d_vol")
    return Exploration(table, vol_p, ret_p, s, window.index[0], window.index[-1], len(rets), skipped)
