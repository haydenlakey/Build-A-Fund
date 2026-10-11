"""Price data: the curated universe, Yahoo downloads, cleaning, caching and rand conversion.

Prices are stored as weekly closes in their *native* unit after cleaning
(JSE securities already divided from cents into rand, US securities in dollars),
and converted to rand on the way out, so FX can always be re-applied.

Lookup order for a ticker: bundled sample -> local parquet cache -> live yfinance.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_PATH = ROOT / "data" / "universe.yaml"
SAMPLE_PATH = ROOT / "data" / "sample" / "prices_native.parquet"
CACHE_PATH = ROOT / "data" / "cache" / "prices_native.parquet"
USDZAR = "ZAR=X"
START = "1995-01-01"
UNIT_TRUST_PREFIX = "UT:"  # UT:<ISIN>, priced from EasyEquities' public feed (unit prices in cents)
EE_PRICES = "https://pricing.easyequities.co.za/api/prices?ISINCode={isin}&period=0"

KIND_BY_SECTION = {"jse_shares": "jse_share", "jse_etfs": "jse_etf",
                   "us_shares": "us_share", "us_etfs": "us_etf"}


# ---- universe ------------------------------------------------------------------

@dataclass
class Universe:
    entries: dict[str, dict]
    factors: dict[str, dict]
    as_of: str = ""
    benchmarks: dict[str, dict] = field(default_factory=dict)  # key -> {name, components {ticker: weight}, note}

    def get(self, ticker: str) -> dict | None:
        return self.entries.get(ticker)

    def history_limits(self) -> dict[str, str]:
        return {t: str(e["history_from"]) for t, e in self.entries.items() if e.get("history_from")}

    def kind_of(self, ticker: str) -> str:
        e = self.entries.get(ticker)
        if e:
            return e["kind"]
        return "jse_share" if ticker.upper().endswith(".JO") else "us_share"

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Case-insensitive match on ticker or name; ticker-prefix matches first."""
        q = query.strip().lower()
        if not q:
            return list(self.entries.values())[:limit]
        starts, contains = [], []
        for e in self.entries.values():
            t, n = e["ticker"].lower(), e["name"].lower()
            if t.startswith(q) or t.split(".")[0] == q:
                starts.append(e)
            elif q in t or q in n:
                contains.append(e)
        return (starts + contains)[:limit]

    def all_tickers(self, include_factors: bool = True) -> list[str]:
        out = list(self.entries)
        if include_factors:
            out += [f["ticker"] for f in self.factors.values() if f["ticker"] not in out]
        if USDZAR not in out:
            out.append(USDZAR)
        return out


def load_universe(path: Path | str = UNIVERSE_PATH) -> Universe:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    entries = {}
    for section, kind in KIND_BY_SECTION.items():
        for e in raw.get(section, []) or []:
            e = dict(e, kind=kind)
            e.setdefault("themes", [])
            e["currency"] = "ZAR" if kind.startswith("jse") else "USD"
            entries[e["ticker"]] = e
    factors = {f["key"]: dict(f) for f in raw.get("factors", []) or []}
    benchmarks = {b["key"]: dict(b) for b in raw.get("benchmarks", []) or []}
    return Universe(entries, factors, str(raw.get("as_of", "")), benchmarks)


# ---- quoting conventions ---------------------------------------------------------

def quote_unit(ticker: str) -> str:
    """How Yahoo quotes a ticker: 'ZAc' (JSE cents), 'points' (an index), 'rate' (FX) or 'USD'."""
    t = ticker.upper()
    if t.startswith(UNIT_TRUST_PREFIX):
        return "ZAc"
    if t == USDZAR:
        return "rate"
    if t.startswith("^"):
        return "points"
    if t.endswith(".JO"):
        return "ZAc"
    return "USD"


def is_supported(ticker: str) -> bool:
    """Only JSE (.JO) and US-listed tickers (no exchange suffix) are supported."""
    t = ticker.strip().upper()
    if not t or " " in t:
        return False
    if t.endswith(".JO") or t.startswith("^") or t.endswith("=X") or t.endswith("=F"):
        return True
    return "." not in t.replace("-", "")  # e.g. BRK-B is fine, VOD.L is not


def repair_hundredfold(s: pd.Series) -> pd.Series:
    """Fix Yahoo's unit glitches on JSE series, where stretches appear in rand instead of cents.

    Walks backwards from the latest price (assumed correct) and treats any week-on-week
    ratio between 50x and 200x (or its inverse) as a unit switch, not a real move.
    """
    x = s.dropna()
    if len(x) < 2:
        return s
    vals = x.to_numpy(dtype=float)
    out = vals.copy()
    scale = 1.0
    for t in range(len(vals) - 1, 0, -1):
        r = vals[t] / vals[t - 1] if vals[t - 1] else np.nan
        if 50 < r < 200:
            scale *= 100.0
        elif 1 / 200 < r < 1 / 50:
            scale /= 100.0
        out[t - 1] = vals[t - 1] * scale
    fixed = pd.Series(out, index=x.index)
    return fixed.reindex(s.index)


def remove_spikes(s: pd.Series, jump: float, calm: float) -> pd.Series:
    """Replace isolated bad ticks: a point more than `jump` away from both neighbours, in the same
    direction, while the neighbours are within `calm` of each other. Such points are interpolated.

    Used for exchange rates only (Yahoo's ZAR=X has one-week ticks like 14.86 between 17.28 and
    18.10 in Nov 2024). Shares are left alone: volatile shares really do jump and reverse.
    """
    x = s.dropna()
    if len(x) < 3:
        return s
    prev, nxt = x.shift(1), x.shift(-1)
    up, down = x / prev - 1, x / nxt - 1
    bad = (up.abs() > jump) & (down.abs() > jump) & (np.sign(up) == np.sign(down)) & ((nxt / prev - 1).abs() < calm)
    if not bad.any():
        return s
    fixed = x.mask(bad).interpolate(method="time", limit_area="inside")
    return fixed.reindex(s.index).where(s.notna())


def to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """Daily closes -> weekly closes labelled by the Friday that ends each week.

    Yahoo's own weekly bars use different anchors per ticker (Monday for JSE, Sunday
    for US, and Thursday-to-Wednesday weeks for some JSE ETFs), so we resample ourselves.
    """
    idx = pd.DatetimeIndex(daily.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    daily = daily.set_axis(idx.normalize()).sort_index()
    weekly = daily.resample("W-FRI").last()
    weekly.index.name = "week"
    return weekly


def clean_native(raw_daily: pd.DataFrame) -> pd.DataFrame:
    """Raw daily Yahoo closes -> clean weekly native prices (JSE cents -> rand, glitches repaired)."""
    out = {}
    for t in raw_daily.columns:
        s = raw_daily[t].astype(float)
        s = s.where(s > 0)
        if quote_unit(t) == "ZAc":
            s = repair_hundredfold(s) / 100.0
        elif quote_unit(t) == "rate":
            s = remove_spikes(s, jump=0.05, calm=0.02)
        out[t] = s
    return to_weekly(pd.DataFrame(out, index=raw_daily.index)).dropna(how="all")


def to_zar(native: pd.DataFrame, usdzar: pd.Series) -> pd.DataFrame:
    """Convert native prices to rand. USD columns are multiplied by USD/ZAR for the same week.

    USD prices in weeks without an exchange rate become NaN, which is what limits US
    holdings to Dec 2003 onwards.
    """
    out = native.copy()
    fx = usdzar.reindex(out.index).ffill(limit=2)
    for t in out.columns:
        if quote_unit(t) == "USD":
            out[t] = out[t] * fx
    return out


# ---- downloading -----------------------------------------------------------------

def download_native(tickers: list[str], start: str = START, retries: int = 3,
                    pause: float = 2.0) -> tuple[pd.DataFrame, dict[str, str]]:
    """Download daily adjusted closes from Yahoo, clean them and resample to weekly.

    Returns (clean native prices, failures {ticker: reason}). Never raises on
    network trouble: a ticker that cannot be fetched is reported as a failure.
    """
    failures: dict[str, str] = {}
    tickers = list(dict.fromkeys(t.strip().upper() for t in tickers))
    ut = [t for t in tickers if t.startswith(UNIT_TRUST_PREFIX)]
    if ut:
        got, fail = download_unit_trusts(ut, retries=retries, pause=pause)
        failures.update(fail)
        rest, fail2 = download_native([t for t in tickers if t not in ut], start, retries, pause)             if len(ut) < len(tickers) else (pd.DataFrame(), {})
        failures.update(fail2)
        frames = [f for f in (got, rest) if not f.empty]
        return (pd.concat(frames, axis=1).sort_index() if frames else pd.DataFrame()), failures

    import yfinance as yf  # imported lazily so the app can run from the bundled sample alone

    bad = [t for t in tickers if not is_supported(t)]
    failures.update({t: "Only JSE (.JO) and US-listed tickers are supported." for t in bad})
    tickers = [t for t in tickers if t not in bad]
    if not tickers:
        return pd.DataFrame(), failures

    raw = None
    last_err = ""
    for attempt in range(retries):
        try:
            data = yf.download(tickers, start=start, interval="1d", auto_adjust=True,
                               progress=False, threads=True)
            if data is not None and not data.empty:
                raw = data["Close"]
                if isinstance(raw, pd.Series):  # single ticker
                    raw = raw.to_frame(tickers[0])
                break
            last_err = "Yahoo returned no data."
        except Exception as e:  # noqa: BLE001 - yfinance raises many types
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(pause * (attempt + 1))

    if raw is None:
        failures.update({t: f"Download failed after {retries} attempts ({last_err})" for t in tickers})
        return pd.DataFrame(), failures

    raw = raw.dropna(axis=1, how="all")
    for t in tickers:
        if t not in raw.columns:
            failures[t] = "No price history on Yahoo (ticker may be wrong, delisted or renamed)."
    return clean_native(raw), failures


def download_unit_trusts(tickers: list[str], retries: int = 3, pause: float = 2.0,
                         fetch=None) -> tuple[pd.DataFrame, dict[str, str]]:
    """Daily unit prices (cents) for UT:<ISIN> tickers from EasyEquities' public price feed, cleaned
    to weekly rand like everything else. The feed starts in mid-2021 and has no distributions added
    back. `fetch(url) -> dict` can be injected for tests."""
    import json
    import urllib.request

    def _get(url: str) -> dict:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Build-a-Fund Lab)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    fetch = fetch or _get
    series, failures = {}, {}
    for t in tickers:
        isin = t[len(UNIT_TRUST_PREFIX):]
        err = ""
        for attempt in range(retries):
            try:
                d = fetch(EE_PRICES.format(isin=isin))
                pts = d.get("Prices") or []
                if pts:
                    s = pd.Series({pd.Timestamp(p["ClosingDate"]): float(p["Price"]) for p in pts}).sort_index()
                    series[t] = s[~s.index.duplicated(keep="last")]
                else:
                    err = "EasyEquities returned no prices for this fund."
                break
            except Exception as e:  # noqa: BLE001 - network and JSON errors alike
                err = f"{type(e).__name__}: {e}"
                time.sleep(pause * (attempt + 1))
        if t not in series:
            failures[t] = err or "No prices."
    if not series:
        return pd.DataFrame(), failures
    return clean_native(pd.DataFrame(series)), failures


# ---- the store -------------------------------------------------------------------

@dataclass
class PriceStore:
    """Weekly prices with a bundled sample, a local cache and optional live fetching."""

    sample_path: Path = SAMPLE_PATH
    cache_path: Path = CACHE_PATH
    allow_live: bool = True
    history_from: dict[str, str] = field(default_factory=dict)  # ticker -> first usable date
    native: pd.DataFrame = field(default_factory=pd.DataFrame)
    source: dict[str, str] = field(default_factory=dict)  # ticker -> sample | cache | live
    failures: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        frames = []
        for path, label in ((self.sample_path, "sample"), (self.cache_path, "cache")):
            if Path(path).exists():
                df = pd.read_parquet(path)
                for t in df.columns:
                    if t not in self.source:
                        self.source[t] = label
                frames.append(df)
        if frames:
            native = frames[0]
            for df in frames[1:]:
                native = native.combine_first(df)
            native = native.sort_index()
            for t in native.columns:  # also repairs samples built before FX spikes were filtered
                if quote_unit(t) == "rate":
                    native[t] = remove_spikes(native[t], jump=0.08, calm=0.06)
            self.native = native

    @property
    def sample_date(self) -> str | None:
        if self.native.empty:
            return None
        return str(self.native.index.max().date())

    def has(self, ticker: str) -> bool:
        return ticker in self.native.columns and self.native[ticker].notna().any()

    def ensure(self, tickers: list[str]) -> dict[str, str]:
        """Make sure tickers are loaded, fetching missing ones live. Returns new failures."""
        missing = [t for t in dict.fromkeys(tickers) if not self.has(t) and t not in self.failures]
        needs_fx = any(quote_unit(t) == "USD" for t in tickers)
        if needs_fx and not self.has(USDZAR) and USDZAR not in missing:
            missing.append(USDZAR)
        if not missing:
            return {}
        if not self.allow_live:
            new = {t: "Not in the bundled dataset and live data is switched off." for t in missing}
            self.failures.update(new)
            return new
        fetched, new = download_native(missing)
        if not fetched.empty:
            self.native = self.native.combine_first(fetched) if not self.native.empty else fetched
            for t in fetched.columns:
                self.source[t] = "live"
            self._write_cache(fetched)
        self.failures.update(new)
        return new

    def _write_cache(self, fetched: pd.DataFrame) -> None:
        try:
            path = Path(self.cache_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            old = pd.read_parquet(path) if path.exists() else pd.DataFrame()
            merged = fetched.combine_first(old) if not old.empty else fetched
            merged.to_parquet(path)
        except OSError:
            pass  # a read-only filesystem (e.g. some hosts) just means no cache

    def prices_zar(self, tickers: list[str]) -> pd.DataFrame:
        """Weekly rand prices for the requested tickers (columns missing if unavailable)."""
        self.ensure(tickers)
        have = [t for t in dict.fromkeys(tickers) if self.has(t)]
        if not have:
            return pd.DataFrame()
        fx = self.native[USDZAR] if self.has(USDZAR) else pd.Series(dtype=float)
        native = self.native[have].copy()
        for t in have:
            if t in self.history_from:
                native.loc[native.index < pd.Timestamp(self.history_from[t]), t] = np.nan
        # ffill bridges short gaps (holidays); it never fills before a series' first price
        return to_zar(native.ffill(limit=2), fx)

    def first_dates(self, tickers: list[str]) -> dict[str, pd.Timestamp]:
        z = self.prices_zar(tickers)
        return {t: z[t].first_valid_index() for t in z.columns}
