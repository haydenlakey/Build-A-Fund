"""Stress tests: replay today's fund through past episodes.

Buy and hold through the episode: with weights w_i at the start and prices P_i,

    V_t = sum_i w_i P_{i,t} / P_{i,0},     episode return R = V_T - 1,   worst point = min_t V_t - 1.

A holding with no prices for the episode (listed later) is **estimated** from its sensitivity
to two factors, the FTSE/JSE Top 40 index and the S&P 500 in rand, fitted by OLS on all the
weekly returns it does have:  r_i,t ~ a_i + b_i1 f_1,t + b_i2 f_2,t.  In the episode its weekly
return is b_i1 f_1,t + b_i2 f_2,t (the intercept a_i is dropped: past outperformance is not
assumed to repeat in a crisis). R^2 shows how much of its movement the factors explained.

Unlisted holdings (no prices) follow the listed part through their one-factor model:
r_u = beta_u r_S with beta_u = rho_u sigma_u / sigma_S (see `unlisted`). In practice their
valuations are often only marked down late, which hides the fall rather than avoiding it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import estimators
from .model import Fund
from .unlisted import assumptions_of

EPISODES_PATH = Path(__file__).resolve().parent.parent / "content" / "stress_tests.yaml"
FACTORS = {"^J200.JO": "Top 40 index", "SPY": "S&P 500 in rand"}
MIN_WEEKS = 52


@dataclass(frozen=True)
class Episode:
    key: str
    name: str
    start: pd.Timestamp
    end: pd.Timestamp
    what: str
    article: str | None = None


def load_episodes(path: Path = EPISODES_PATH) -> list[Episode]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["episodes"]
    out = []
    for e in raw:
        start, end = pd.Timestamp(e["start"]), pd.Timestamp(e["end"])
        if end <= start:
            raise ValueError(f"{e['key']}: end must be after start")
        out.append(Episode(e["key"], e["name"], start, end, e["what"], e.get("article")))
    return out


@dataclass
class Proxy:
    betas: pd.Series  # factor -> beta
    r2: float
    n: int


def fit_proxy(asset_returns: pd.Series, factor_returns: pd.DataFrame, min_weeks: int = MIN_WEEKS) -> Proxy | None:
    """OLS of the asset's weekly returns on the factors (with an intercept) over the weeks they share."""
    df = pd.concat([asset_returns.rename("_y"), factor_returns], axis=1).dropna()
    if len(df) < min_weeks:
        return None
    y = df["_y"].to_numpy()
    X = np.column_stack([np.ones(len(df)), df[factor_returns.columns].to_numpy()])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    tss = ((y - y.mean()) ** 2).sum()
    r2 = float(1 - (resid ** 2).sum() / tss) if tss > 0 else float("nan")
    return Proxy(pd.Series(coef[1:], index=factor_returns.columns), r2, len(df))


@dataclass
class Replay:
    episode: Episode
    path: pd.Series  # fund value through the episode (listed part), starting at 1
    fund_return: float
    worst: float  # lowest point of the path minus 1 (<= 0 if it ever dipped)
    by_holding: pd.DataFrame  # ticker -> return, method ("Measured" / "Estimated"), r2
    measured_share: float  # share of the (listed) weights with real prices in the episode
    benchmarks: pd.DataFrame  # factor value paths, starting at 1
    whole_return: float = float("nan")  # incl. unlisted holdings, if any
    notes: list[str] = field(default_factory=list)


def replay(weights: pd.Series, prices: pd.DataFrame, factor_prices: pd.DataFrame, episode: Episode) -> Replay | None:
    """Buy-and-hold replay of the weights (summing to one) through the episode.

    `prices` are rand prices for the holdings over all available history (used for the proxies too);
    `factor_prices` holds the FACTORS columns. None if the factors don't cover the episode.
    """
    fac = factor_prices.loc[episode.start:episode.end, list(FACTORS)]
    if len(fac) < 2 or fac.iloc[0].isna().any() or fac.iloc[-1].isna().any():
        return None
    fac = fac.ffill()
    weeks = fac.index
    fac_r = estimators.prices_to_returns(fac)
    all_fac_r = estimators.prices_to_returns(factor_prices[list(FACTORS)])

    paths, rows = {}, []
    for t, w in weights.items():
        p = prices[t].reindex(weeks) if t in prices.columns else pd.Series(np.nan, index=weeks)
        if p.notna().all():
            paths[t] = p / p.iloc[0]
            rows.append((t, float(paths[t].iloc[-1] - 1), "Measured", float("nan")))
            continue
        hist = estimators.prices_to_returns(prices[[t]].dropna())[t] if t in prices.columns else pd.Series(dtype=float)
        proxy = fit_proxy(hist, all_fac_r)
        if proxy is None:
            rows.append((t, float("nan"), "Not enough history to estimate", float("nan")))
            continue
        est_r = fac_r[proxy.betas.index] @ proxy.betas
        paths[t] = pd.concat([pd.Series([1.0], index=weeks[:1]), (1 + est_r).cumprod()])
        rows.append((t, float(paths[t].iloc[-1] - 1), "Estimated", proxy.r2))

    by = pd.DataFrame(rows, columns=["ticker", "return", "method", "r2"]).set_index("ticker")
    usable = [t for t in weights.index if t in paths]
    if not usable:
        return None
    w = weights[usable] / weights[usable].sum()
    path = pd.DataFrame(paths)[usable] @ w
    measured = float(weights[[t for t in usable if by.loc[t, "method"] == "Measured"]].sum() / weights.sum())
    bench = fac / fac.iloc[0]
    notes = []
    if len(usable) < len(weights):
        notes.append("Some holdings couldn't be measured or estimated and are left out.")
    return Replay(episode, path, float(path.iloc[-1] - 1), float(min(path.min() - 1, 0.0)), by, measured, bench,
                  notes=notes)


def whole_fund_return(fund: Fund, listed_return: float, listed_vol: float) -> float:
    """Episode return of the whole fund, unlisted holdings following r_u = rho_u sigma_u / sigma_S * r_S."""
    total = fund.total_zar
    unl = fund.unlisted()
    if total <= 0 or not unl:
        return listed_return
    listed_amt = total - sum(h.amount_zar for h in unl)
    out = listed_amt / total * listed_return
    for h in unl:
        a = assumptions_of(h)
        beta = a.corr * a.total_vol / listed_vol if listed_vol > 0 else 0.0
        out += h.amount_zar / total * max(beta * listed_return, -1.0)
    return float(out)
