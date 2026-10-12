"""Insight rules: each one compares a measure of the fund with a threshold (content/rules.yaml).

A rule trips when trigger(fund) > above. Evaluation is pure: the UI decides which tripped rules are
new (pop-up) and which the visitor has already dismissed.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import unlisted
from .model import Fund

RULES_PATH = Path(__file__).resolve().parent.parent / "content" / "rules.yaml"
SEVERITIES = ("info", "warning")

# trigger name -> measure of the fund (a fraction)
TRIGGERS: dict[str, Callable[[Fund], float]] = {
    "illiquid_share": unlisted.illiquid_share,
}


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    trigger: str
    above: float
    severity: str
    noticed: str
    history: str
    article: str
    threshold_note: str = ""
    sources: list = field(default_factory=list)


@dataclass(frozen=True)
class Insight:
    rule: Rule
    value: float

    @property
    def noticed(self) -> str:
        return self.rule.noticed.format(value=_pct(self.value), threshold=_pct(self.rule.above))


def _pct(x: float) -> str:
    return f"{x:.0%}"


def load_rules(path: Path | str = RULES_PATH) -> list[Rule]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    rules, seen = [], set()
    for d in raw.get("rules", []):
        sources = [{**s, "accessed": str(s.get("accessed", ""))} for s in d.get("sources", [])]
        r = Rule(**{**d, "above": float(d["above"]), "sources": sources})
        if r.trigger not in TRIGGERS:
            raise ValueError(f"rule {r.id}: unknown trigger {r.trigger!r}")
        if r.severity not in SEVERITIES:
            raise ValueError(f"rule {r.id}: unknown severity {r.severity!r}")
        if r.id in seen:
            raise ValueError(f"duplicate rule id {r.id!r}")
        seen.add(r.id)
        rules.append(r)
    return rules


def evaluate(rules: list[Rule], fund: Fund) -> list[Insight]:
    """The rules this fund trips, in file order. Each trigger is computed at most once."""
    values: dict[str, float] = {}
    out = []
    for r in rules:
        if r.trigger not in values:
            values[r.trigger] = float(TRIGGERS[r.trigger](fund))
        if values[r.trigger] > r.above:
            out.append(Insight(r, values[r.trigger]))
    return out
