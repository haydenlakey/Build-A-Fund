"""Active bets against a benchmark: active weights, tracking error and its budget."""
from __future__ import annotations

from dataclasses import dataclass

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


def abs_weighted_vol_corr(active_w: pd.Series, cov: pd.DataFrame) -> tuple[float, float]:
    """Inputs for the rule of thumb: |a|-weighted average volatility, and |a_i a_j|-weighted
    average pairwise correlation (i != j)."""
    a = np.abs(active_w.to_numpy(dtype=float))
    s = cov.loc[active_w.index, active_w.index].to_numpy(dtype=float)
    sd = np.sqrt(np.clip(np.diag(s), 0, None))
    avg_vol = float(a @ sd / a.sum()) if a.sum() > 0 else float("nan")
    if len(a) < 2:
        return avg_vol, float("nan")
    corr = s / np.outer(sd, sd)
    ww = np.outer(a, a)
    np.fill_diagonal(ww, 0.0)
    return avg_vol, float((ww * corr).sum() / ww.sum()) if ww.sum() > 0 else float("nan")


@dataclass
class ActiveReport:
    fund_w: pd.Series
    bench_w: pd.Series
    active: pd.Series  # fund minus benchmark, per asset (sums to zero)
    te: float  # exact tracking error, annualised
    budget: pd.Series  # share of TE variance per bet (sums to one)
    exp_active: float  # a' mu: expected active return (least reliable number)
    info_ratio: float
    beta: float  # beta of the fund to the benchmark
    avg_vol: float
    avg_corr: float
    te_rule: float  # rule-of-thumb TE
    cov: pd.DataFrame | None = None

    @property
    def top_bet(self) -> tuple[str, float]:
        if self.budget.empty:
            return "", 0.0
        t = self.budget.idxmax()
        return t, float(self.budget[t])


def analyse(fund_w: pd.Series, bench_w: pd.Series, mu: pd.Series, cov: pd.DataFrame) -> ActiveReport:
    """Active bets of a fund against a benchmark mix, both as weights over assets in `cov`.

    Active return r_F - r_B = a'r with a = w_F - w_B, so TE = sqrt(a' Sigma a) exactly.
    Beta to the benchmark = w_F' Sigma w_B / (w_B' Sigma w_B). IR = a' mu / TE.
    """
    a = active_weights(fund_w, bench_w)
    a = a[a.abs() > 1e-12]
    fw = fund_w.reindex(a.index.union(fund_w.index), fill_value=0.0)
    bw = bench_w.reindex(fw.index, fill_value=0.0)
    te = tracking_error(a, cov)
    S = cov.loc[fw.index, fw.index].to_numpy(dtype=float)
    bvar = float(bw.to_numpy() @ S @ bw.to_numpy())
    beta = float(fw.to_numpy() @ S @ bw.to_numpy() / bvar) if bvar > 0 else float("nan")
    exp_a = float(a @ mu.loc[a.index])
    avg_vol, avg_corr = abs_weighted_vol_corr(a, cov)
    return ActiveReport(fund_w=fund_w, bench_w=bench_w, active=a.sort_values(), te=te,
                        budget=te_budget(a, cov), exp_active=exp_a,
                        info_ratio=exp_a / te if te > 0 else float("nan"), beta=beta,
                        avg_vol=avg_vol, avg_corr=avg_corr, te_rule=te_rule_of_thumb(a, avg_vol, avg_corr),
                        cov=cov.loc[fw.index, fw.index])
