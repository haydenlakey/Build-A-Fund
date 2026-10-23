"""Fund and holding data model, plus save/load and share-link encoding."""
from __future__ import annotations

import base64
import copy
import json
import uuid
import zlib
from dataclasses import asdict, dataclass, field

import pandas as pd

SCHEMA_VERSION = 2  # 2 added Holding.params (version 1 files still load)

METHODS = {
    "price_history": "Price history",
    "uploaded": "Uploaded prices",
    "allocation_model": "Modelled from its asset allocation",
    "assumptions": "Your stated assumptions (no price history)",
}

HOLDING_KINDS = {
    "jse_share": "JSE share",
    "jse_etf": "JSE-listed ETF",
    "us_share": "US share",
    "us_etf": "US-listed ETF",
    "unit_trust": "Unit trust",
    "unlisted": "Unlisted investment",
}


@dataclass
class Holding:
    ticker: str
    name: str
    kind: str
    amount_zar: float
    currency: str = "ZAR"  # currency the price is quoted in (before conversion to rand)
    method: str = "price_history"  # a key of METHODS
    # method-specific inputs: allocation_model {allocation, ter}, uploaded {prices: [[date, price], ...]},
    # assumptions {exp_return, low, high, lockin_years, p_loss, corr, category}; empty for listed holdings
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in HOLDING_KINDS:
            raise ValueError(f"unknown holding kind {self.kind!r}")
        if self.method not in METHODS:
            raise ValueError(f"unknown method {self.method!r}")
        if (self.kind == "unlisted") != (self.method == "assumptions"):
            raise ValueError("unlisted holdings, and only they, use stated assumptions")
        self.params = dict(self.params or {})
        self.amount_zar = float(self.amount_zar)
        if self.amount_zar < 0:
            raise ValueError("amount must be zero or positive")


@dataclass
class FundSettings:
    lookback_years: float = 5.0
    cov_method: str = "ledoit_wolf"
    mean_shrinkage: float = 0.5
    prior_sharpe: float = 0.3  # user assumption: shrinkage target is rf + prior_sharpe * asset vol
    risk_free: float = 0.07  # user assumption, annual, in rand
    var_alpha: float = 0.95
    var_horizon_weeks: int = 4
    seed: int = 42
    benchmark: str = "top40"  # a key of universe.yaml benchmarks (older files: a ticker, read as top40)


@dataclass
class Fund:
    name: str
    holdings: list[Holding] = field(default_factory=list)
    objective: str = ""
    settings: FundSettings = field(default_factory=FundSettings)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # ---- derived quantities -------------------------------------------------
    @property
    def total_zar(self) -> float:
        return float(sum(h.amount_zar for h in self.holdings))

    def weights(self) -> pd.Series:
        """Weights derived from rand amounts. Holdings with the same ticker are merged."""
        amounts = self.amounts()
        total = amounts.sum()
        if total <= 0:
            return pd.Series(dtype=float)
        return amounts / total

    def amounts(self) -> pd.Series:
        s = pd.Series({}, dtype=float)
        for h in self.holdings:
            s[h.ticker] = s.get(h.ticker, 0.0) + h.amount_zar
        return s[s > 0]

    def holding(self, ticker: str) -> Holding | None:
        return next((h for h in self.holdings if h.ticker == ticker), None)

    def unlisted(self) -> list[Holding]:
        return [h for h in self.holdings if h.kind == "unlisted" and h.amount_zar > 0]

    # ---- edits (all return a new Fund so before/after can be compared) -----
    def with_amount(self, ticker: str, amount: float, *, name: str = "", kind: str | None = None,
                    currency: str = "ZAR", method: str = "price_history", params: dict | None = None) -> "Fund":
        """Add, resize or (amount 0) remove a holding. `params`, if given, replaces a held holding's inputs.

        Adding a new holding needs its `kind` (there is no safe default: an ETF is not a share).
        """
        new = self.copy(keep_id=True)
        h = new.holding(ticker)
        if h is None:
            if amount > 0:
                if kind is None:
                    raise ValueError(f"adding {ticker} needs its kind (one of {', '.join(HOLDING_KINDS)})")
                new.holdings.append(Holding(ticker, name or ticker, kind, amount, currency, method, params or {}))
        elif amount <= 0:
            new.holdings = [x for x in new.holdings if x.ticker != ticker]
        else:
            h.amount_zar = float(amount)
            if params is not None:
                h.params = dict(params)
        return new

    def without(self, ticker: str) -> "Fund":
        return self.with_amount(ticker, 0.0)

    def copy(self, keep_id: bool = False, name: str | None = None) -> "Fund":
        new = copy.deepcopy(self)
        if not keep_id:
            new.id = uuid.uuid4().hex[:8]
        if name is not None:
            new.name = name
        return new

    # ---- serialisation -----------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema_version"] = SCHEMA_VERSION
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Fund":
        d = dict(d)
        version = d.pop("schema_version", 1)
        if version > SCHEMA_VERSION:
            raise ValueError("This fund file was made by a newer version of the app.")
        settings_d = d.pop("settings", {}) or {}
        known = set(FundSettings.__dataclass_fields__)
        settings = FundSettings(**{k: v for k, v in settings_d.items() if k in known})
        hk = set(Holding.__dataclass_fields__)
        holdings = [Holding(**{k: v for k, v in h.items() if k in hk}) for h in d.pop("holdings", [])]
        return cls(name=d.get("name", "Untitled fund"), holdings=holdings,
                   objective=d.get("objective", ""), settings=settings,
                   id=d.get("id") or uuid.uuid4().hex[:8])

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, s: str | bytes) -> "Fund":
        return cls.from_dict(json.loads(s))

    def to_share_code(self) -> str:
        """Compact URL-safe encoding of the fund for ?fund=... links."""
        raw = json.dumps(self.to_dict(), separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode().rstrip("=")

    @classmethod
    def from_share_code(cls, code: str) -> "Fund":
        pad = "=" * (-len(code) % 4)
        raw = zlib.decompress(base64.urlsafe_b64decode(code + pad))
        return cls.from_json(raw)
