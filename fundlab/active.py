"""Active bets against a benchmark: active weights, tracking error and its budget."""
from __future__ import annotations

import numpy as np
import pandas as pd


def active_weights(fund_w: pd.Series, bench_w: pd.Series) -> pd.Series:
    idx = fund_w.index.union(bench_w.index)
    return fund_w.reindex(idx, fill_value=0.0) - bench_w.reindex(idx, fill_value=0.0)


def tracking_error(active_w: pd.Series, cov: pd.DataFrame) -> float:
    a = active_w.to_numpy(dtype=float)
    s = cov.loc[active_w.index, active_w.index].to_numpy(dtype=float)
    return float(np.sqrt(max(a @ s @ a, 0.0)))


def te_budget(active_w: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """Share of tracking-error variance from each active bet: a_i (Sigma a)_i / a'Sigma a.

    Shares sum to one; a negative share means the bet hedges the others.
    """
    a = active_w.to_numpy(dtype=float)
    s = cov.loc[active_w.index, active_w.index].to_numpy(dtype=float)
    v = a @ s @ a
    if v <= 0:
        return pd.Series(0.0, index=active_w.index)
    return pd.Series(a * (s @ a) / v, index=active_w.index)


def pairwise_bet(te_target: float, vol_long: float, vol_short: float, rho: float) -> dict:
    """Size of an overweight/underweight pair that uses exactly `te_target` of tracking error.

    Going long `w` of A and short `w` of B gives TE^2 = w^2 (s_A^2 + s_B^2 - 2 rho s_A s_B).
    """
    pair_var = vol_long**2 + vol_short**2 - 2 * rho * vol_long * vol_short
    w = te_target / np.sqrt(pair_var)
    share_long = (vol_long**2 - rho * vol_long * vol_short) / pair_var
    share_short = (vol_short**2 - rho * vol_long * vol_short) / pair_var
    return {"bet_size": float(w), "share_long": float(share_long), "share_short": float(share_short)}


def te_rule_of_thumb(active_w: pd.Series, avg_vol: float, avg_corr: float) -> float:
    """Average-volatility, average-correlation approximation.

    If every asset had volatility s and pairwise correlation r, and active weights
    sum to zero, then TE^2 = s^2 (1 - r) sum(a_i^2), so TE ~ s sqrt(1 - r) ||a||.
    """
    a = active_w.to_numpy(dtype=float)
    return float(avg_vol * np.sqrt(max(1.0 - avg_corr, 0.0)) * np.sqrt(np.sum(a**2)))
