"""Look-through composition: what a fund owns once each ETF is opened up.

Each holding gets a *profile*: how one rand in it splits by asset class, sector,
industry, country, currency and source of earnings, plus the companies it owns.
A share is its own one-line profile; an ETF's profile comes from
``data/lookthrough.yaml`` (published sector split, top holdings, countries).

The fund's breakdown along any dimension d is the rand-weighted mix of profiles,

    B_d(c) = sum_i w_i * p_{i,d}(c),

where w_i is holding i's share of the rands and p_{i,d} its profile (summing to 1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

LOOKTHROUGH_PATH = Path(__file__).resolve().parent.parent / "data" / "lookthrough.yaml"

ASSET_LABELS = {"equity": "Shares", "property": "Listed property", "bonds": "Bonds",
                "commodity": "Commodities", "cash": "Cash", "unlisted": "Unlisted"}
EARNINGS_LABELS = {
    "sa": "Mostly South Africa",
    "sa_dollar": "SA operations, dollar-priced output",
    "africa": "Africa outside SA",
    "mixed": "Mixed SA and offshore",
    "global": "Mostly offshore",
    "unclassified": "Not classified",
}
NOT_DISCLOSED = "Not disclosed"
UNCLASSIFIED = "unclassified"

# Tilt thresholds, as shares of the whole fund (see tilts()).
TILTS = {
    "tech": 0.25,         # Technology sector
    "resources": 0.25,    # Basic Materials + Energy
    "banks": 0.15,        # bank industry
    "property": 0.20,     # listed property
    "precious": 0.15,     # gold, platinum and precious-metal ETFs
    "rand_hedge": 0.50,   # earnings mostly offshore or in dollars
    "sa_focus": 0.80,     # earnings mostly South African
}
DOMINANT = 0.20  # one holding above this share of the rands is flagged


# ---- data -----------------------------------------------------------------------

@dataclass
class LookThroughData:
    entries: dict[str, dict]
    sector_map: dict[str, str]
    currency_of_country: dict[str, str]
    as_of: str = ""

    def resolve(self, key: str, _seen: tuple = ()) -> dict | None:
        """An entry with `use:` inheritance applied (own fields win)."""
        e = self.entries.get(key)
        if e is None or key in _seen:
            return None
        e = dict(e)
        parent = e.pop("use", None)
        if parent:
            base = self.resolve(parent, _seen + (key,)) or {}
            base.update(e)
            e = base
        return e

    def map_sector(self, label: str) -> str:
        return self.sector_map.get(label.upper(), label if label in self.sector_map.values() else "Other")

    def currency(self, country: str) -> str:
        return self.currency_of_country.get(country, "Other")


def load_lookthrough(path: Path | str = LOOKTHROUGH_PATH) -> LookThroughData:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    smap = {str(k).upper(): v for k, v in (raw.get("sector_map") or {}).items()}
    return LookThroughData(raw.get("entries") or {}, smap, raw.get("currency_of_country") or {},
                           str(raw.get("as_of", "")))


# ---- per-holding profiles -----------------------------------------------------------

@dataclass
class Profile:
    """How one rand in a holding splits. Every Series/frame sums to 1."""
    ticker: str
    sectors: pd.DataFrame  # columns asset, sector, industry, frac
    countries: pd.Series
    currencies: pd.Series
    earnings: pd.Series
    companies: pd.DataFrame  # columns key, name, frac (partial: top holdings only for ETFs)
    looked_through: bool  # False for a single share (it *is* its own holding)
    themes: set = field(default_factory=set)
    ter: float = 0.0
    tc: float = 0.0
    sources: dict = field(default_factory=dict)  # sectors_src, holdings_src, countries_src
    note: str = ""


def _norm(s: pd.Series) -> pd.Series:
    s = s[s > 0]
    return s / s.sum() if s.sum() > 0 else s


def _asset_of_share(entry: dict) -> str:
    return "property" if entry.get("sector") == "Real Estate" else "equity"


def _share_profile(ticker: str, entry: dict, lt: LookThroughData) -> Profile:
    country = entry.get("country") or ("ZA" if ticker.endswith(".JO") else "US")
    asset = _asset_of_share(entry)
    sector = entry.get("sector") or "Other"
    industry = entry.get("industry") or sector
    earnings = entry.get("exposure") or ("sa" if ticker.endswith(".JO") else "global")
    # A JSE listing is priced in rand whatever the company's domicile; the earnings
    # dimension carries the rand-hedge story.
    currency = "ZAR" if ticker.endswith(".JO") else lt.currency(country)
    return Profile(
        ticker=ticker,
        sectors=pd.DataFrame([{"asset": asset, "sector": sector, "industry": industry, "frac": 1.0}]),
        countries=pd.Series({country: 1.0}), currencies=pd.Series({currency: 1.0}),
        earnings=pd.Series({earnings: 1.0}),
        companies=pd.DataFrame([{"key": ticker, "name": entry.get("name", ticker), "frac": 1.0}]),
        looked_through=False, themes=set(entry.get("themes") or []),
    )


def _unknown_profile(ticker: str, name: str) -> Profile:
    """A ticker outside the curated universe: classify it only by where it lists."""
    jse = ticker.endswith(".JO")
    return Profile(
        ticker=ticker,
        sectors=pd.DataFrame([{"asset": "equity", "sector": "Other", "industry": "Not classified", "frac": 1.0}]),
        countries=pd.Series({"ZA" if jse else "US": 1.0}), currencies=pd.Series({"ZAR" if jse else "USD": 1.0}),
        earnings=pd.Series({UNCLASSIFIED: 1.0}),
        companies=pd.DataFrame([{"key": ticker, "name": name or ticker, "frac": 1.0}]),
        looked_through=False, note="Not in the curated list, so sector and earnings are not classified.",
    )


def _company_key(ticker, name: str) -> str:
    return ticker if ticker else f"name:{name}"


def _etf_profile(ticker: str, entry: dict, lt: LookThroughData, universe: dict[str, dict]) -> Profile:
    d = lt.resolve(ticker)
    if d is None:  # an ETF with no look-through data: one opaque block
        sector = {"Bonds": "Government bonds", "Property": "Real Estate", "Commodity": "Precious metals"}.get(
            entry.get("sector", ""), NOT_DISCLOSED)
        asset = {"Bonds": "bonds", "Property": "property", "Commodity": "commodity"}.get(entry.get("sector", ""), "equity")
        d = {"asset": asset, "sectors": {sector: 100}}
    asset = d.get("asset", "equity")
    holdings = [(h[0], str(h[1]), float(h[2])) for h in d.get("holdings") or []]

    # sectors: the published split; if none, the top holdings' own sectors plus a "not disclosed" rest
    rows = []
    if d.get("sectors"):
        for label, pct in d["sectors"].items():
            rows.append({"asset": asset, "sector": lt.map_sector(str(label)), "industry": str(label), "frac": float(pct)})
    else:
        for t, name, pct in holdings:
            e = universe.get(t) if t else None
            rows.append({"asset": asset, "sector": (e or {}).get("sector", "Other"),
                         "industry": (e or {}).get("industry", "Other"), "frac": pct})
        rest = 100 - sum(h[2] for h in holdings)
        if rest > 0:
            rows.append({"asset": asset, "sector": NOT_DISCLOSED, "industry": NOT_DISCLOSED, "frac": rest})
    sectors = pd.DataFrame(rows)
    sectors["frac"] = sectors["frac"] / sectors["frac"].sum()

    # countries: published split, refined with the top holdings' domiciles for JSE equity funds
    countries = pd.Series({str(k): float(v) for k, v in (d.get("countries") or {"Other": 100}).items()})
    countries = _norm(countries)
    earnings = _etf_earnings(asset, countries, holdings, universe)
    if set(countries.index) == {"ZA"} and asset == "equity" and holdings:
        refined = pd.Series(dtype=float)
        covered = 0.0
        for t, _, pct in holdings:
            e = universe.get(t) if t else None
            c = (e or {}).get("country", "ZA")
            refined[c] = refined.get(c, 0.0) + pct / 100
            covered += pct / 100
        refined["ZA"] = refined.get("ZA", 0.0) + max(1 - covered, 0.0)
        countries = _norm(refined)

    jse_listed = ticker.endswith(".JO")
    if asset == "commodity":
        currencies = pd.Series({"USD": 1.0})
    elif jse_listed and set(d.get("countries") or {"ZA": 1}) == {"ZA"}:
        currencies = pd.Series({"ZAR": 1.0})
    else:
        cur = pd.Series(dtype=float)
        for c, f in countries.items():
            k = lt.currency(c)
            cur[k] = cur.get(k, 0.0) + f
        currencies = _norm(cur)

    companies = pd.DataFrame([{"key": _company_key(t, n), "name": (universe.get(t) or {}).get("name", n) if t else n,
                               "frac": pct / 100} for t, n, pct in holdings], columns=["key", "name", "frac"])
    if not companies.empty:
        companies = companies.groupby("key", as_index=False).agg(name=("name", "first"), frac=("frac", "sum"))

    srcs = {k: d[k] for k in ("sectors_src", "holdings_src", "countries_src") if d.get(k)}
    return Profile(ticker=ticker, sectors=sectors, countries=countries, currencies=currencies, earnings=earnings,
                   companies=companies, looked_through=True, themes=set(entry.get("themes") or []),
                   ter=float(entry.get("ter") or 0.0), tc=float(entry.get("tc") or 0.0), sources=srcs,
                   note=str(d.get("note", "")))


def _etf_earnings(asset: str, countries: pd.Series, holdings: list, universe: dict[str, dict]) -> pd.Series:
    """Where the money is made: offshore funds and commodities are 'global'; SA funds use their
    top holdings' curated exposure and leave the rest unclassified (bonds and property: 'sa')."""
    if asset == "commodity":
        return pd.Series({"global": 1.0})
    if set(countries.index) != {"ZA"}:
        return pd.Series({"global": 1.0})
    if asset in ("bonds", "property") or not holdings:
        return pd.Series({"sa": 1.0})
    s = pd.Series(dtype=float)
    covered = 0.0
    for t, _, pct in holdings:
        e = universe.get(t) if t else None
        k = (e or {}).get("exposure", UNCLASSIFIED)
        s[k] = s.get(k, 0.0) + pct / 100
        covered += pct / 100
    s[UNCLASSIFIED] = s.get(UNCLASSIFIED, 0.0) + max(1 - covered, 0.0)
    return _norm(s)


# app asset class (fundlab.synthetic.ASSET_CLASSES) -> (asset, sector, country, currency, earnings)
_CLASS_MAP = {
    "sa_equity": ("equity", NOT_DISCLOSED, "ZA", "ZAR", UNCLASSIFIED),
    "sa_property": ("property", "Real Estate", "ZA", "ZAR", "sa"),
    "sa_bonds": ("bonds", "Bonds", "ZA", "ZAR", "sa"),
    "sa_ilb": ("bonds", "Inflation-linked bonds", "ZA", "ZAR", "sa"),
    "sa_cash": ("cash", "Cash", "ZA", "ZAR", "sa"),
    "global_equity": ("equity", NOT_DISCLOSED, "Other", "Foreign", "global"),
    "global_bonds": ("bonds", "Bonds", "Other", "Foreign", "global"),
    "global_property": ("property", "Real Estate", "Other", "Foreign", "global"),
    "global_cash": ("cash", "Cash", "Other", "USD", "global"),
    "commodities": ("commodity", "Commodities", "Other", "USD", "global"),
}


def allocation_profile(ticker: str, allocation: dict[str, float], holdings: list | None = None,
                       universe: dict[str, dict] | None = None, ter: float = 0.0, tc: float = 0.0,
                       note: str = "") -> Profile:
    """Look-through for a unit trust from its published asset allocation (percent by app asset class).

    Offshore parts have no country split on most fact sheets, so they show as "Other"; SA shares'
    sector is "Not disclosed" except for the top holdings the sheet lists. Negative (derivative)
    weights are netted within each dimension and the result rescaled to sum to one.
    """
    universe = universe or {}
    a = {k: float(v) for k, v in allocation.items() if k in _CLASS_MAP and float(v) != 0}
    total = sum(a.values()) or 1.0
    rows, ctry, cur, earn = [], pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)
    for k, v in a.items():
        asset, sector, c, cu, e = _CLASS_MAP[k]
        rows.append({"asset": asset, "sector": sector, "industry": sector, "frac": v / total})
        ctry[c] = ctry.get(c, 0.0) + v / total
        cur[cu] = cur.get(cu, 0.0) + v / total
        earn[e] = earn.get(e, 0.0) + v / total
    sectors = pd.DataFrame(rows).groupby(["asset", "sector", "industry"], as_index=False)["frac"].sum()
    sectors = sectors[sectors["frac"] > 0]
    sectors["frac"] = sectors["frac"] / sectors["frac"].sum()
    comp = [{"key": _company_key(t, n), "name": (universe.get(t) or {}).get("name", n) if t else n,
             "frac": float(p) / 100} for t, n, p in (holdings or [])]
    companies = pd.DataFrame(comp, columns=["key", "name", "frac"])
    return Profile(ticker=ticker, sectors=sectors, countries=_norm(ctry), currencies=_norm(cur),
                   earnings=_norm(earn), companies=companies, looked_through=True, ter=ter, tc=tc or 0.0,
                   note=note or "From the fund's published asset allocation and top holdings.")


def unlisted_profile(ticker: str, name: str, category: str = "Other", country: str = "ZA") -> Profile:
    """An unlisted holding is its own asset class; its sector is the category the user picked."""
    return Profile(
        ticker=ticker,
        sectors=pd.DataFrame([{"asset": "unlisted", "sector": "Unlisted", "industry": category, "frac": 1.0}]),
        countries=pd.Series({country: 1.0}), currencies=pd.Series({"ZAR" if country == "ZA" else "Foreign": 1.0}),
        earnings=pd.Series({"sa" if country == "ZA" else "global": 1.0}),
        companies=pd.DataFrame([{"key": ticker, "name": name or ticker, "frac": 1.0}]),
        looked_through=False, note="Unlisted: described by your own assumptions.",
    )


def profile(ticker: str, universe: dict[str, dict], lt: LookThroughData, name: str = "") -> Profile:
    entry = universe.get(ticker)
    if entry is None:
        return _unknown_profile(ticker, name)
    if entry.get("kind") in ("jse_etf", "us_etf"):
        return _etf_profile(ticker, entry, lt, universe)
    return _share_profile(ticker, entry, lt)


# ---- the fund -----------------------------------------------------------------------

@dataclass
class Tilt:
    key: str
    label: str
    value: float
    threshold: float
    detail: str


@dataclass
class Composition:
    weights: pd.Series
    sectors: pd.DataFrame  # asset, sector, industry, weight (sums to 1)
    by_asset: pd.Series
    by_sector: pd.Series
    by_country: pd.Series
    by_currency: pd.Series
    by_earnings: pd.Series
    companies: pd.DataFrame  # key, name, direct, via_funds, total, n_sources (sorted by total)
    profiles: dict[str, Profile]
    tilts: list[Tilt]
    top5: float
    largest: tuple[str, float]
    weighted_ter: float
    weighted_tc: float
    bank_share: float
    lookthrough_share: float  # share of rands held through ETFs

    @property
    def dominant(self) -> bool:
        return self.largest[1] > DOMINANT


def _mix(weights: pd.Series, parts: dict[str, pd.Series]) -> pd.Series:
    out = pd.Series(dtype=float)
    for t, w in weights.items():
        for k, f in parts[t].items():
            out[k] = out.get(k, 0.0) + w * f
    return out.sort_values(ascending=False)


def _is_bank(industry: str) -> bool:
    i = industry.lower()
    return i == "banks" or i.startswith("banks ") or i.startswith("banks-") or i.startswith("banks -")


def compose(weights: pd.Series, universe: dict[str, dict], lt: LookThroughData,
            names: dict[str, str] | None = None, extra: dict[str, Profile] | None = None) -> Composition:
    """Look-through breakdowns of a fund given its weights (fractions summing to one).

    `extra` supplies ready-made profiles (unit trusts, unlisted holdings) by ticker.
    """
    names, extra = names or {}, extra or {}
    w = weights[weights > 0]
    profs = {t: extra.get(t) or profile(t, universe, lt, names.get(t, "")) for t in w.index}

    frames = []
    for t, wt in w.items():
        f = profs[t].sectors.copy()
        f["weight"] = f.pop("frac") * wt
        f["holding"] = t
        frames.append(f)
    sectors = (pd.concat(frames).groupby(["asset", "sector", "industry"], as_index=False)["weight"].sum()
               if frames else pd.DataFrame(columns=["asset", "sector", "industry", "weight"]))
    sectors = sectors.sort_values("weight", ascending=False, ignore_index=True)
    by_asset = sectors.groupby("asset")["weight"].sum().sort_values(ascending=False)
    by_sector = sectors.groupby("sector")["weight"].sum().sort_values(ascending=False)
    bank_share = float(sectors.loc[sectors["industry"].map(_is_bank), "weight"].sum()) if len(sectors) else 0.0

    by_country = _mix(w, {t: p.countries for t, p in profs.items()})
    by_currency = _mix(w, {t: p.currencies for t, p in profs.items()})
    by_earnings = _mix(w, {t: p.earnings for t, p in profs.items()})

    companies = _companies(w, profs)
    top5 = float(w.sort_values(ascending=False).head(5).sum())
    big = w.idxmax() if len(w) else ""
    comp = Composition(
        weights=w, sectors=sectors, by_asset=by_asset, by_sector=by_sector, by_country=by_country,
        by_currency=by_currency, by_earnings=by_earnings, companies=companies, profiles=profs, tilts=[],
        top5=top5, largest=(big, float(w.max()) if len(w) else 0.0),
        weighted_ter=float(sum(w[t] * profs[t].ter for t in w.index)),
        weighted_tc=float(sum(w[t] * profs[t].tc for t in w.index)),
        bank_share=bank_share,
        lookthrough_share=float(sum(w[t] for t in w.index if profs[t].looked_through)),
    )
    comp.tilts = tilts(comp)
    return comp


def _companies(w: pd.Series, profs: dict[str, Profile]) -> pd.DataFrame:
    """Each underlying company's share of the fund, held directly and through funds.

    Fund holdings only cover each ETF's published top holdings, so via_funds is a lower bound.
    """
    rows = []
    for t, wt in w.items():
        p = profs[t]
        for _, r in p.companies.iterrows():
            rows.append({"key": r["key"], "name": r["name"], "direct": wt * r["frac"] if not p.looked_through else 0.0,
                         "via_funds": wt * r["frac"] if p.looked_through else 0.0, "source": t})
    if not rows:
        return pd.DataFrame(columns=["key", "name", "direct", "via_funds", "total", "n_sources"])
    df = pd.DataFrame(rows)
    out = df.groupby("key", as_index=False).agg(name=("name", "first"), direct=("direct", "sum"),
                                                via_funds=("via_funds", "sum"), n_sources=("source", "nunique"))
    out["total"] = out["direct"] + out["via_funds"]
    return out.sort_values("total", ascending=False, ignore_index=True)


def tilts(c: Composition) -> list[Tilt]:
    """Plain-language tilt labels. Each fires when its share of the fund passes TILTS[key].

    tech = Technology sector; resources = Basic Materials + Energy; banks = bank industry;
    property = Real Estate sector; precious = Precious metals; rand_hedge = earnings 'global'
    + 'sa_dollar'; sa_focus = earnings 'sa' (incl. SA bonds and property).
    """
    s, e = c.by_sector, c.by_earnings
    vals = {
        "tech": s.get("Technology", 0.0),
        "resources": s.get("Basic Materials", 0.0) + s.get("Energy", 0.0),
        "banks": c.bank_share,
        "property": s.get("Real Estate", 0.0),
        "precious": s.get("Precious metals", 0.0),
        "rand_hedge": e.get("global", 0.0) + e.get("sa_dollar", 0.0),
        "sa_focus": e.get("sa", 0.0),
    }
    text = {
        "tech": ("Tech-heavy", "{v} of the fund is in technology companies."),
        "resources": ("Resources-heavy", "{v} is in mining, chemicals and energy, whose profits follow commodity prices."),
        "banks": ("Bank-heavy", "{v} is in banks."),
        "property": ("Property-heavy", "{v} is in listed property."),
        "precious": ("Precious-metals-heavy", "{v} is in gold or platinum held directly."),
        "rand_hedge": ("Rand hedge", "{v} earns its money offshore or in US dollars, so it tends to gain in rand when the rand weakens."),
        "sa_focus": ("Mostly South African", "{v} earns its money mainly in South Africa."),
    }
    out = []
    for k, v in vals.items():
        if v >= TILTS[k]:
            label, detail = text[k]
            out.append(Tilt(k, label, float(v), TILTS[k], detail.format(v=f"{v:.0%}")))
    return sorted(out, key=lambda t: -t.value)
