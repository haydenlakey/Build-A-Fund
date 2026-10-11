"""What a fund costs: fund charges inside the price, platform and account fees, and trading costs.

Three layers (all as fractions):
    fund costs      TER + TC of ETFs and unit trusts. Already inside their prices, so every
                    history-based number in the app is after them; shown so you can see the price.
    platform/account a yearly fee on unit trusts plus a fixed monthly account fee F (rand),
                    which as a share of the fund is 12 F / V.
    trading         a one-off cost to buy (and sell): broker commission, settlement and levy
                    (plus VAT), securities transfer tax on share purchases, an FX fee for US holdings.

Rands lost over n years, with growth g a year before costs, starting amount A:
    no costs            V0 = A (1 + g)^n
    after fund costs    V1 = A (1 + g - c_f)^n
    after everything    V2 = [A (1 - b)(1 + r)^n - 12 F ((1 + r)^n - 1) / r] (1 - s),   r = g - c_f - c_p
where b and s are the buy and sell costs as fractions of the amount, c_p the platform fee share.
Fees are taken from returns in one step a year (a close approximation of monthly deductions).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from .model import Fund

COSTS_PATH = Path(__file__).resolve().parent.parent / "data" / "platform_costs.yaml"
LISTED_KINDS = {"jse_share", "jse_etf", "us_share", "us_etf"}


def load_platform_costs(path: Path = COSTS_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@dataclass
class TradingCosts:
    """Costs per trade as fractions of the amount traded."""
    buy_share: float  # JSE share purchase (includes STT)
    buy_other: float  # other listed purchase (ETF, US)
    sell: float
    fx: float  # extra on US holdings (rand to dollars)

    @classmethod
    def from_platform(cls, pc: dict) -> "TradingCosts":
        vatable = (pc["broker_commission"] + pc["settlement"] + pc["investor_protection_levy"]) * (1 + pc["vat"])
        return cls(vatable + pc["stt_on_share_purchases"], vatable, vatable, pc["easyfx_transfer_fee"])

    def buy_cost(self, kind: str) -> float:
        """Cost to buy one rand of a holding of this kind (unit trusts and unlisted: none here)."""
        if kind == "jse_share":
            return self.buy_share
        if kind == "jse_etf":
            return self.buy_other
        if kind in ("us_share", "us_etf"):
            return self.buy_other + self.fx
        return 0.0

    def sell_cost(self, kind: str) -> float:
        return self.sell if kind in LISTED_KINDS else 0.0


@dataclass
class CostSummary:
    by_holding: pd.DataFrame  # ticker -> amount, kind, ter, tc, platform, buy, sell (fractions)
    total_zar: float
    fund_costs: float  # weighted TER + TC, a year
    platform: float  # weighted unit trust platform fee, a year
    account: float  # 12 F / V, a year
    buy: float  # weighted one-off cost to buy
    sell: float  # weighted one-off cost to sell
    notes: list[str] = field(default_factory=list)

    @property
    def yearly(self) -> float:
        return self.fund_costs + self.platform + self.account


def summarise(fund: Fund, ter: dict[str, float], tc: dict[str, float], trading: TradingCosts,
              ut_platform_fee: float, monthly_fee: float) -> CostSummary:
    """Per-holding and weighted costs. `ter`/`tc` map ticker -> fraction a year (missing = 0)."""
    rows = []
    for h in fund.holdings:
        if h.amount_zar <= 0:
            continue
        rows.append({"ticker": h.ticker, "amount": h.amount_zar, "kind": h.kind,
                     "ter": ter.get(h.ticker, 0.0) or 0.0, "tc": tc.get(h.ticker, 0.0) or 0.0,
                     "platform": ut_platform_fee if h.kind == "unit_trust" else 0.0,
                     "buy": trading.buy_cost(h.kind), "sell": trading.sell_cost(h.kind)})
    df = pd.DataFrame(rows, columns=["ticker", "amount", "kind", "ter", "tc", "platform", "buy", "sell"])
    df = df.groupby("ticker", sort=False).agg({"amount": "sum", "kind": "first", "ter": "first", "tc": "first",
                                              "platform": "first", "buy": "first", "sell": "first"})
    total = float(df["amount"].sum())
    w = df["amount"] / total if total > 0 else df["amount"] * 0
    notes = []
    if any(k == "unlisted" for k in df["kind"]):
        notes.append("Unlisted holdings have no listed fund charges or trading costs here; their own fees are part of "
                     "the return you assumed for them.")
    return CostSummary(df, total, float(w @ (df["ter"] + df["tc"])), float(w @ df["platform"]),
                       12 * monthly_fee / total if total > 0 else 0.0, float(w @ df["buy"]), float(w @ df["sell"]),
                       notes)


@dataclass
class Projection:
    years: int
    no_costs: float
    after_fund_costs: float
    after_all: float

    @property
    def lost(self) -> float:
        return self.no_costs - self.after_all

    @property
    def lost_fund(self) -> float:
        return self.no_costs - self.after_fund_costs

    @property
    def lost_other(self) -> float:
        return self.after_fund_costs - self.after_all


def project(amount: float, growth: float, s: CostSummary, monthly_fee: float, years: int) -> Projection:
    """The three values in the module docstring after `years` years."""
    v0 = amount * (1 + growth) ** years
    v1 = amount * (1 + growth - s.fund_costs) ** years
    r = growth - s.fund_costs - s.platform
    g = (1 + r) ** years
    annuity = years if abs(r) < 1e-12 else (g - 1) / r
    v2 = (amount * (1 - s.buy) * g - 12 * monthly_fee * annuity) * (1 - s.sell)
    return Projection(years, float(v0), float(v1), float(max(v2, 0.0)))


def value_paths(amount: float, growth: float, s: CostSummary, monthly_fee: float, years: int) -> pd.DataFrame:
    """Year-by-year values with no costs, after fund costs, and after everything (sold at that year)."""
    rows = [project(amount, growth, s, monthly_fee, n) for n in range(years + 1)]
    return pd.DataFrame({"No costs": [p.no_costs for p in rows], "After fund costs": [p.after_fund_costs for p in rows],
                         "After all costs": [p.after_all for p in rows]}, index=pd.Index(range(years + 1), name="year"))
