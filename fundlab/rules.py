"""Insight rules: conditions on measures of the fund, read from content/rules.yaml.

`measures()` turns a fund and what the app already computed about it into a flat dict of named
numbers (and a few names for the text). A rule trips when every one of its conditions holds:

    measure > above    and/or    measure < below

A rule whose measures aren't all available (no price history, no benchmark report, leverage only
known on the Risk page) is skipped, not tripped. Evaluation is pure: the UI decides which tripped
rules are new (pop-up) and which the visitor has already dismissed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from . import PERIODS_PER_YEAR, lookthrough, unlisted
from .model import Fund

RULES_PATH = Path(__file__).resolve().parent.parent / "content" / "rules.yaml"
SEVERITIES = ("info", "warning")
FEE_YEARS = 20
RISE_MIN_WEIGHT = 0.05  # only holdings at least this share of the fund count for "rose very sharply"
RISK_RATIO = 1.5  # risk_gap only counts holdings whose share of the risk is at least this multiple of their money

# themes that describe a market, not a story, so they don't count as "one theme"
BROAD_THEMES = {"offshore_equity", "sa_equity", "sa_bonds", "offshore_bonds"}
THEME_NAMES = {
    "ai": "artificial intelligence", "us_tech": "US technology", "semiconductors": "chips (semiconductors)",
    "mining": "mining", "bank": "banks", "gold": "gold", "pgm": "platinum-group metals",
    "listed_property": "listed property", "sa_retail": "SA retail", "oil": "oil", "insurance": "insurance",
    "pharma": "pharmaceuticals", "copper": "copper", "china_tech": "Chinese technology", "tencent": "Tencent",
    "telecoms": "telecoms", "software": "software", "beverages": "beverages", "tobacco": "tobacco",
    "luxury": "luxury goods", "inflation_linked": "inflation-linked bonds",
}

# measures that aren't fractions of the fund: how to show them in the text (default: whole percent)
FORMATS = {"avg_corr": "{:.2f}", "n_measured": "{:.0f}", "leverage": "{:.1f}×", "fee": "{:.2%}", "te": "{:.1%}"}

# every measure a rule may use (rules.yaml is checked against this list)
MEASURES = {
    "illiquid_share", "tech_share", "resources_share", "bank_share", "property_share", "sa_share",
    "equity_share", "bond_share", "cushion_share", "largest_company", "theme_share",
    "avg_corr", "n_measured", "worst_fall", "risk_gap", "fee", "fee_cost", "te_top_share",
    "max_rise", "max_promised", "leverage",
}


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    when: dict  # measure -> {"above": x} and/or {"below": y}
    severity: str
    noticed: str
    history: str
    article: str
    threshold_note: str = ""
    sources: list = field(default_factory=list)

    @property
    def first(self) -> tuple[str, float]:
        m, c = next(iter(self.when.items()))
        return m, c.get("above", c.get("below"))


@dataclass(frozen=True)
class Insight:
    rule: Rule
    values: dict

    @property
    def value(self) -> float:
        return self.values[self.rule.first[0]]

    @property
    def noticed(self) -> str:
        return fill(self.rule.noticed, self.values, self.rule)

    @property
    def history(self) -> str:
        return fill(self.rule.history, self.values, self.rule)


def fmt(name: str, v) -> str:
    if isinstance(v, str):
        return v
    return FORMATS.get(name, "{:.0%}").format(v)


def fill(text: str, values: dict, rule: Rule) -> str:
    m, bound = rule.first
    shown = {k: fmt(k, v) for k, v in values.items()}
    return text.format(value=shown.get(m, ""), threshold=fmt(m, bound), **shown)


def load_rules(path: Path | str = RULES_PATH) -> list[Rule]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    rules, seen = [], set()
    for d in raw.get("rules", []):
        sources = [{**s, "accessed": str(s.get("accessed", ""))} for s in d.get("sources", [])]
        when = {m: {k: float(v) for k, v in c.items()} for m, c in (d.get("when") or {}).items()}
        r = Rule(**{**d, "when": when, "sources": sources})
        if not when:
            raise ValueError(f"rule {r.id}: no conditions")
        for m, c in when.items():
            if m not in MEASURES:
                raise ValueError(f"rule {r.id}: unknown measure {m!r}")
            if not c or set(c) - {"above", "below"}:
                raise ValueError(f"rule {r.id}: a condition needs 'above' and/or 'below'")
        if r.severity not in SEVERITIES:
            raise ValueError(f"rule {r.id}: unknown severity {r.severity!r}")
        if r.id in seen:
            raise ValueError(f"duplicate rule id {r.id!r}")
        seen.add(r.id)
        rules.append(r)
    return rules


def _ok(v) -> bool:
    return v is not None and not isinstance(v, str) and not (isinstance(v, float) and math.isnan(v))


def evaluate(rules: list[Rule], values: dict) -> tuple[list[Insight], set[str]]:
    """(tripped rules in file order, ids of every rule whose measures were all available)."""
    out, checked = [], set()
    for r in rules:
        if not all(_ok(values.get(m)) for m in r.when):
            continue
        checked.add(r.id)
        if all(("above" not in c or values[m] > c["above"]) and ("below" not in c or values[m] < c["below"])
               for m, c in r.when.items()):
            out.append(Insight(r, values))
    return out, checked


def measures(fund: Fund, stats=None, comp: lookthrough.Composition | None = None, active=None,
             prices: pd.DataFrame | None = None, names: dict[str, str] | None = None) -> dict:
    """Named measures of the fund for the rules (fractions unless FORMATS says otherwise).

    stats: analysis.FundStats; comp: look-through Composition; active: active.ActiveReport;
    prices: weekly rand prices of the holdings; names: ticker -> display name. Any may be None,
    which leaves the measures that need it out.
    """
    names = names or {}
    nm = lambda t: names.get(t) or ((h := fund.holding(t)) and h.name) or t  # noqa: E731
    v: dict = {}
    if not fund.holdings or fund.total_zar <= 0:
        return v
    w = fund.weights()
    v["illiquid_share"] = unlisted.illiquid_share(fund)

    promised = {h.ticker: float(h.params.get("exp_return", 0.0)) for h in fund.unlisted() if h.amount_zar > 0}
    if promised:
        t = max(promised, key=promised.get)
        v["max_promised"], v["max_promised_name"] = promised[t], nm(t)

    if comp is not None:
        tv = lookthrough.tilt_values(comp)
        v.update(tech_share=tv["tech"], resources_share=tv["resources"], bank_share=tv["banks"],
                 property_share=tv["property"], sa_share=tv["sa_focus"])
        a = comp.by_asset
        v["equity_share"] = float(a.get("equity", 0.0))
        v["bond_share"] = float(a.get("bonds", 0.0))
        v["cushion_share"] = float(a.get("commodity", 0.0) + a.get("cash", 0.0))
        if not comp.companies.empty:
            top = comp.companies.iloc[0]
            v["largest_company"], v["largest_company_name"] = float(top["total"]), str(top["name"])
        themes: dict[str, float] = {}
        for t, wt in comp.weights.items():
            p = comp.profiles.get(t)
            for th in (p.themes if p else set()) - BROAD_THEMES:
                themes[th] = themes.get(th, 0.0) + float(wt)
        if themes:
            th = max(themes, key=themes.get)
            v["theme_share"], v["theme_name"] = themes[th], THEME_NAMES.get(th, th.replace("_", " "))
        fee = float(comp.weighted_ter + comp.weighted_tc)
        v["fee"], v["fee_cost"] = fee, 1 - (1 - fee) ** FEE_YEARS

    if stats is not None:
        v["n_measured"] = float(len(stats.weights))
        v["avg_corr"] = stats.avg_corr
        v["worst_fall"] = -stats.max_drawdown
        rs, wm = stats.risk_shares, stats.weights.reindex(stats.risk_shares.index)
        gap = (rs - wm)[rs >= RISK_RATIO * wm].dropna()
        if len(rs) > 1:
            v["risk_gap"] = float(gap.max()) if len(gap) else 0.0
            if len(gap):
                t = gap.idxmax()
                v["risk_gap_name"], v["risk_gap_risk"], v["risk_gap_money"] = nm(t), float(rs[t]), float(wm[t])

    if active is not None and not active.budget.empty:
        t, share = active.top_bet
        a = float(active.active.get(t, 0.0))
        v["te_top_share"], v["te_top_name"], v["te"] = share, nm(t), float(active.te)
        v["te_top_bet"] = f"holding {'more' if a > 0 else 'less'} of {nm(t)} than the benchmark does ({a:+.0%})"

    if prices is not None and not prices.empty:
        rises = {}
        for t in w.index[w >= RISE_MIN_WEIGHT]:
            if t in prices.columns:
                s = prices[t].dropna()
                if len(s) > PERIODS_PER_YEAR:
                    rises[t] = float(s.iloc[-1] / s.iloc[-1 - PERIODS_PER_YEAR] - 1)
        if rises:
            t = max(rises, key=rises.get)
            v["max_rise"], v["max_rise_name"] = rises[t], nm(t)
    return v
