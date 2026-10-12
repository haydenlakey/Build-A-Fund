"""The curated unit trusts in data/unit_trusts.yaml (no Streamlit).

A unit trust holding uses one of three methods (Holding.method):
    price_history     unit prices from EasyEquities' feed (ticker UT:<ISIN>)
    uploaded          a price file the user supplied (Holding.params["prices"])
    allocation_model  the fund's published asset allocation, run through proxy series
                      (fundlab.synthetic.allocation_prices), less its TER
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .data import UNIT_TRUST_PREFIX

UNIT_TRUSTS_PATH = Path(__file__).resolve().parent.parent / "data" / "unit_trusts.yaml"
RISK_ORDER = ["low", "low_medium", "medium_high", "high"]
CUSTOM_PREFIX = UNIT_TRUST_PREFIX + "custom-"


@dataclass
class UnitTrust:
    ticker: str
    code: str
    name: str
    manager: str
    risk: str
    risk_label: str
    asisa: str
    benchmark: str
    inception: str
    size: str
    ter: float
    tc: float | None
    fees_src: str
    allocation: dict[str, float]
    method: str
    sheet: dict
    holdings: list = field(default_factory=list)
    allocation_note: str = ""
    performance_fee: str = ""

    @property
    def isin(self) -> str:
        return self.ticker[len(UNIT_TRUST_PREFIX):]

    def params(self, method: str | None = None) -> dict:
        """Holding.params for this fund (allocation and fees travel with saved files and share links)."""
        return {"allocation": dict(self.allocation), "ter": self.ter, "curated": self.code,
                **({"holdings": [list(h) for h in self.holdings]} if self.holdings else {})}


@dataclass
class UnitTrustList:
    funds: dict[str, UnitTrust]
    levels: dict[str, dict]
    meta: dict

    def by_risk(self, risk: str) -> list[UnitTrust]:
        return sorted((f for f in self.funds.values() if f.risk == risk), key=lambda f: f.name)

    def get(self, ticker: str) -> UnitTrust | None:
        return self.funds.get(ticker)


def load_unit_trusts(path: Path | str = UNIT_TRUSTS_PATH) -> UnitTrustList:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    known = set(UnitTrust.__dataclass_fields__)
    funds = {}
    for d in raw["funds"]:
        d = {k: v for k, v in d.items() if k in known}
        d["inception"] = str(d.get("inception", ""))
        d["sheet"] = {**d["sheet"], **{k: str(d["sheet"][k]) for k in ("as_of", "accessed") if k in d["sheet"]}}
        d["allocation"] = {k: float(v) for k, v in d["allocation"].items()}
        f = UnitTrust(**d)
        if f.risk not in RISK_ORDER:
            raise ValueError(f"{f.code}: unknown risk level {f.risk!r}")
        funds[f.ticker] = f
    meta = {k: v for k, v in raw.items() if k not in ("funds", "risk_levels")}
    return UnitTrustList(funds, raw.get("risk_levels", {}), meta)


def is_unit_trust_ticker(ticker: str) -> bool:
    return ticker.upper().startswith(UNIT_TRUST_PREFIX)


def extra_profiles(fund, universe: dict[str, dict], uts: UnitTrustList) -> dict:
    """Look-through profiles for a fund's unit trusts (from their allocation) and unlisted holdings."""
    from . import lookthrough, unlisted

    out = {}
    for h in fund.holdings:
        if h.kind == "unlisted":
            a = unlisted.assumptions_of(h)
            out[h.ticker] = lookthrough.unlisted_profile(h.ticker, h.name, a.category, h.params.get("country", "ZA"))
        elif h.kind == "unit_trust":
            ut = uts.get(h.ticker)
            alloc = h.params.get("allocation") or (ut.allocation if ut else None)
            if alloc:
                out[h.ticker] = lookthrough.allocation_profile(
                    h.ticker, alloc, h.params.get("holdings") or (ut.holdings if ut else []), universe,
                    ter=float(h.params.get("ter", ut.ter if ut else 0.0) or 0.0), tc=float((ut.tc if ut else 0.0) or 0.0))
    return out
