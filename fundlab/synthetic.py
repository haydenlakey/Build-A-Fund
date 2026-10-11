"""Weekly rand price series for holdings that Yahoo doesn't have: uploaded prices and allocation models.

Both end up as ordinary columns in the price frame (under the holding's ticker), so the rest of
the app treats them like any other holding. Only returns matter downstream, so a price file in
cents or rand gives the same answers.

Allocation model
----------------
A unit trust that publishes its asset allocation a_k (summing to 1) is modelled as a weekly
rebalanced mix of proxy series, less its annual fee:

    r_t = sum_k a_k r_{k,t} - TER / 52

Cash earns the user's risk-free rate, rf / 52 a week, with no volatility. The model ignores
everything the manager does within each asset class (stock picking, timing), so it captures the
fund's broad risk, not its manager's skill.
"""
from __future__ import annotations

import io
from collections.abc import Callable

import numpy as np
import pandas as pd

from . import PERIODS_PER_YEAR
from .model import Fund, Holding

CASH = "cash"
# key -> (label, proxy ticker or CASH, note)
ASSET_CLASSES: dict[str, tuple[str, str, str]] = {
    "sa_equity": ("SA shares", "STX40.JO", "Satrix 40 ETF (JSE Top 40, total return)"),
    "sa_property": ("SA listed property", "CSPROP.JO", "10X SA Property Income ETF (history from 2011)"),
    "sa_bonds": ("SA bonds", "STXGOV.JO", "Satrix SA Bond ETF (history only from May 2020)"),
    "sa_ilb": ("SA inflation-linked bonds", "STXILB.JO", "Satrix ILBI ETF (history from 2017)"),
    "sa_cash": ("SA cash and money market", CASH, "the risk-free rate in your settings, with no volatility"),
    "global_equity": ("Global shares", "VT", "Vanguard Total World Stock ETF in rand"),
    "global_bonds": ("Global bonds", "BND", "Vanguard Total Bond Market ETF (US bonds) in rand"),
    "global_property": ("Global property", "VNQ", "Vanguard Real Estate ETF (US property) in rand"),
    "global_cash": ("Offshore cash", "ZAR=X", "the US dollar in rand (currency moves only, no interest)"),
    "commodities": ("Gold and commodities", "GLD.JO", "NewGold gold ETF"),
}
MIN_UPLOAD_WEEKS = 53  # 52 weekly returns, the same minimum the statistics use


def proxy_tickers(allocation: dict[str, float]) -> list[str]:
    return [ASSET_CLASSES[k][1] for k, a in allocation.items()
            if a != 0 and k in ASSET_CLASSES and ASSET_CLASSES[k][1] != CASH]


def normalise_allocation(allocation: dict[str, float]) -> dict[str, float]:
    """Drop zero or unknown classes and scale to sum to one (fact sheets often add up to 99.9%).

    Negative weights (derivative overlays some fact sheets publish, e.g. cash -14.9%) are kept.
    """
    a = {k: float(v) for k, v in (allocation or {}).items() if k in ASSET_CLASSES and float(v) != 0}
    total = sum(a.values())
    if total <= 0 or not any(v > 0 for v in a.values()):
        raise ValueError("the allocation needs at least one asset class above zero")
    return {k: v / total for k, v in a.items()}


def allocation_prices(allocation: dict[str, float], ter: float, proxies: pd.DataFrame,
                      risk_free: float) -> pd.Series:
    """Price index (first value 100) of the modelled fund: r_t = sum_k a_k r_{k,t} - TER/52.

    Starts once every proxy with a non-zero weight has a price.
    """
    a = normalise_allocation(allocation)
    rets = pd.DataFrame(index=proxies.index)
    for k, w in a.items():
        t = ASSET_CLASSES[k][1]
        if t == CASH:
            rets[k] = risk_free / PERIODS_PER_YEAR
        elif t in proxies.columns:
            rets[k] = proxies[t].pct_change(fill_method=None)
        else:
            raise KeyError(f"no prices for the {ASSET_CLASSES[k][0]} proxy {t}")
    first = max((proxies[ASSET_CLASSES[k][1]].first_valid_index() for k in a if ASSET_CLASSES[k][1] != CASH),
                default=proxies.index[0])
    rets = rets.loc[rets.index > first].dropna()
    r = rets @ pd.Series(a) - ter / PERIODS_PER_YEAR
    idx = pd.concat([pd.Series([100.0], index=[first]), 100.0 * (1 + r).cumprod()])
    return idx.rename(None)


def parse_price_file(raw: bytes | str) -> pd.Series:
    """Read a CSV of dates and prices into weekly (Friday) closes.

    Accepts a header or not, comma or semicolon separators, ISO or day-first dates, and daily,
    weekly or monthly rows. Uses the first column that parses as dates and the first numeric
    column after it. Raises ValueError with a plain-language reason when the file can't be used.
    """
    text = raw.decode("utf-8-sig", errors="replace") if isinstance(raw, bytes) else raw
    lines = max(text.count("\n"), 1)
    sep = ";" if text.count(";") >= lines else ","  # ';' files often use decimal commas
    df = pd.read_csv(io.StringIO(text), sep=sep, header=None, dtype=str, skip_blank_lines=True)
    if df.shape[1] < 2:
        raise ValueError("The file needs at least two columns: a date and a price.")
    date_col = dates = None
    for c in df.columns:
        d = _parse_dates(df[c])
        if d.notna().mean() > 0.8:
            date_col, dates = c, d
            break
    if date_col is None:
        raise ValueError("Couldn't find a column of dates (use e.g. 2024-01-31 or 31/01/2024).")
    price = None
    for c in df.columns[df.columns.get_loc(date_col) + 1:]:
        txt = df[c].str.replace(r"[\sR]", "", regex=True)
        if sep == ";":
            txt = txt.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        else:
            txt = txt.str.replace(",", "", regex=False)
        v = pd.to_numeric(txt, errors="coerce")
        if v.notna().mean() > 0.8:
            price = v
            break
    if price is None:
        raise ValueError("Couldn't find a column of prices after the date column.")
    s = pd.Series(price.to_numpy(), index=dates).dropna()
    s = s[~s.index.isna()].sort_index()
    s = s[~s.index.duplicated(keep="last")]
    if (s <= 0).any():
        raise ValueError("Prices must all be above zero.")
    if len(s) > 1 and (s.index.to_series().diff().dt.days.median() or 0) > 10:
        raise ValueError("The prices look monthly or less frequent. Weekly or daily prices are needed, because "
                         "the app measures risk from weekly returns.")
    weekly = s.resample("W-FRI").last().dropna()
    if len(weekly) < MIN_UPLOAD_WEEKS:
        raise ValueError(f"Only {len(weekly)} weeks of prices; at least {MIN_UPLOAD_WEEKS} are needed.")
    weekly.index.name = None
    return weekly.astype(float)


def _parse_dates(col: pd.Series) -> pd.Series:
    iso = pd.to_datetime(col, errors="coerce", format="ISO8601")
    if iso.notna().mean() > 0.8:
        return iso
    return pd.to_datetime(col, errors="coerce", dayfirst=True, format="mixed")


def series_to_params(s: pd.Series) -> list[list]:
    """Weekly series → [[YYYY-MM-DD, price], ...] for storing in Holding.params (saved files, share links)."""
    return [[d.strftime("%Y-%m-%d"), round(float(v), 6)] for d, v in s.items()]


def params_to_series(points: list[list]) -> pd.Series:
    s = pd.Series({pd.Timestamp(d): float(v) for d, v in points}, dtype=float).sort_index()
    return s


def needed_tickers(funds: list[Fund]) -> list[str]:
    """Every ticker to fetch from the price store: listed holdings plus the proxies of modelled ones."""
    out = []
    for f in funds:
        for h in f.holdings:
            if h.method == "price_history":
                out.append(h.ticker)
            elif h.method == "allocation_model":
                out += proxy_tickers(h.params.get("allocation", {}))
    return list(dict.fromkeys(out))


def holding_series(h: Holding, store_prices: pd.DataFrame, risk_free: float) -> pd.Series | None:
    if h.method == "uploaded":
        return params_to_series(h.params.get("prices", []))
    if h.method == "allocation_model":
        return allocation_prices(h.params.get("allocation", {}), float(h.params.get("ter", 0.0)),
                                 store_prices, risk_free)
    return None


def price_frame(funds: list[Fund], get_prices: Callable[[list[str]], pd.DataFrame],
                risk_free: float) -> pd.DataFrame:
    """Weekly rand prices for every holding of the funds that has (real or modelled) prices.

    Unlisted holdings get no column: they have no price history, and the app never invents one.
    When funds hold the same modelled ticker with different inputs (before/after an edit), the
    last fund's version is used.
    """
    store = get_prices(needed_tickers(funds))
    cols = {t: store[t] for t in store.columns}
    for f in funds:
        for h in f.holdings:
            if h.ticker in cols and h.method == "price_history":
                continue
            try:
                s = holding_series(h, store, risk_free)
            except (KeyError, ValueError):
                s = None
            if s is not None and not s.empty:
                cols[h.ticker] = s
    if not cols:
        return pd.DataFrame()
    # both the store and uploads sit on Friday week-ends, so the columns line up
    return pd.DataFrame(cols).sort_index().astype(float).replace([np.inf, -np.inf], np.nan)
