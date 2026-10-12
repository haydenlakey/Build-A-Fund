"""Insight rules: the rules file is valid and sourced, every rule trips at its bounds, measures are right,
and the pop-ups behave (a change pops, a loaded fund doesn't, dismissal sticks)."""
import re
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from fundlab import content, data, lookthrough, rules
from fundlab.model import Fund, Holding

RULES = rules.load_rules()
LIB = content.load_library()
EPS = 1e-6


def fund_with_unlisted(listed: float, unl: float, exp_return: float = 0.1) -> Fund:
    return Fund("F", [Holding("STX40.JO", "Satrix 40", "jse_etf", listed),
                      Holding("UL:farm", "A farm", "unlisted", unl, method="assumptions",
                              params={"lockin_years": 7, "exp_return": exp_return, "low": -0.3,
                                      "high": max(0.3, exp_return + 0.2)})])


def values_at(rule: rules.Rule, inside: bool) -> dict:
    """Measures just inside every condition (inside=True) or with the first one just outside."""
    v = {}
    for i, (m, c) in enumerate(rule.when.items()):
        lo, hi = c.get("above"), c.get("below")
        x = (lo + EPS) if lo is not None else (hi - EPS)
        if not inside and i == 0:
            x = lo if lo is not None else hi  # on the bound: strict inequalities don't trip
        v[m] = x
    for k in re.findall(r"\{(\w+)\}", rule.noticed + rule.history):  # text-only names
        v.setdefault(k, "X") if k not in ("value", "threshold") else None
    return v


def test_rules_file_is_complete_and_sourced():
    assert len(RULES) >= 16
    for r in RULES:
        assert r.article in LIB, f"{r.id}: no library article {r.article!r}"
        assert r.title and r.noticed and r.history and r.threshold_note
        advice = r"\b(should|recommend\w*|(buy|sell) (it|this|that|now|more))\b"
        assert not re.search(advice, " ".join((r.title, r.noticed, r.history)), re.I), r.id
        a = LIB[r.article]
        sourced = " ".join([a.summary, a.lesson, a.body] + [s["title"] for s in r.sources])
        for num in re.findall(r"\d[\d.,]*\d|\d", r.history):
            assert num in sourced or r.sources, f"{r.id}: {num} isn't in {r.article} and has no source"
        for s in r.sources:
            assert s["url"].startswith("https://") and re.fullmatch(r"20\d\d-\d\d-\d\d", s["accessed"])


def test_every_lesson_group_has_a_rule():
    groups = {LIB[r.article].group for r in RULES if LIB[r.article].group}
    assert set(content.GROUPS) <= groups, set(content.GROUPS) - groups


@pytest.mark.parametrize("rule", RULES, ids=[r.id for r in RULES])
def test_rule_trips_inside_its_bounds_only(rule):
    found, checked = rules.evaluate([rule], values_at(rule, inside=True))
    assert [i.rule.id for i in found] == [rule.id] and checked == {rule.id}
    assert "{" not in found[0].noticed and "{" not in found[0].history
    quiet, checked = rules.evaluate([rule], values_at(rule, inside=False))
    assert quiet == [] and checked == {rule.id}
    missing = values_at(rule, inside=True)
    missing.pop(next(iter(rule.when)))
    assert rules.evaluate([rule], missing) == ([], set())  # not measurable: skipped, not tripped


def test_illiquid_and_promise_measures():
    v = rules.measures(fund_with_unlisted(7_000, 3_000, exp_return=0.6))
    assert v["illiquid_share"] == pytest.approx(0.3)
    assert v["max_promised"] == pytest.approx(0.6) and v["max_promised_name"] == "A farm"
    found, _ = rules.evaluate(RULES, v)
    assert {i.rule.id for i in found} == {"cant_sell_in_a_hurry", "unlisted_promise"}
    assert rules.evaluate(RULES, rules.measures(fund_with_unlisted(9_000, 1_000)))[0] == []
    assert rules.measures(Fund("Empty")) == {}


def test_stats_measures_risk_gap_needs_a_big_ratio():
    fund = Fund("F", [Holding("A", "Alpha", "jse_share", 50), Holding("B", "Beta", "jse_share", 30),
                      Holding("C", "Gamma", "jse_share", 20)])
    w = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
    stats = SimpleNamespace(weights=w, risk_shares=pd.Series({"A": 0.62, "B": 0.08, "C": 0.30}),
                            avg_corr=0.7, max_drawdown=-0.35)
    v = rules.measures(fund, stats=stats)
    assert v["risk_gap"] == 0.0  # A: +12 pp but only 1.24x; C: 1.5x but only +10 pp
    stats.risk_shares = pd.Series({"A": 0.45, "B": 0.10, "C": 0.45})
    v = rules.measures(fund, stats=stats)
    assert v["risk_gap"] == pytest.approx(0.25) and v["risk_gap_name"] == "Gamma"
    assert v["worst_fall"] == pytest.approx(0.35) and v["n_measured"] == 3
    ids = {i.rule.id for i in rules.evaluate(RULES, v)[0]}
    assert {"risk_gap", "deep_fall", "one_bet"} <= ids


def test_composition_measures_themes_fees_and_companies():
    uni = data.load_universe()
    fund = Fund("F", [Holding("NVDA", "NVIDIA", "us_share", 4_000), Holding("SMH", "Semis", "us_etf", 4_000),
                      Holding("STX40.JO", "Satrix 40", "jse_etf", 2_000)])
    comp = lookthrough.compose(fund.weights(), uni.entries, lookthrough.load_lookthrough())
    v = rules.measures(fund, comp=comp)
    assert v["theme_name"] in ("artificial intelligence", "chips (semiconductors)") and v["theme_share"] >= 0.8
    assert v["largest_company_name"] == "NVIDIA" and v["largest_company"] > 0.4
    assert v["fee_cost"] == pytest.approx(1 - (1 - v["fee"]) ** 20)
    assert v["tech_share"] > 0.25 and "one_theme" in {i.rule.id for i in rules.evaluate(RULES, v)[0]}


def test_sharp_rise_counts_only_big_enough_holdings():
    idx = pd.date_range("2024-01-05", periods=60, freq="W-FRI")
    px = pd.DataFrame({"A": np.linspace(100, 300, 60), "B": np.linspace(100, 110, 60)}, index=idx)
    big = Fund("F", [Holding("A", "Rocket", "jse_share", 10), Holding("B", "Steady", "jse_share", 90)])
    v = rules.measures(big, prices=px)
    assert v["max_rise_name"] == "Rocket" and v["max_rise"] > 1.0
    small = Fund("F", [Holding("A", "Rocket", "jse_share", 4), Holding("B", "Steady", "jse_share", 96)])
    assert rules.measures(small, prices=px)["max_rise_name"] == "Steady"


def test_bad_rules_are_rejected(tmp_path):
    base = ("rules:\n  - {id: x, title: T, when: {%s: {above: 0.1}}, severity: %s, noticed: '{value}', "
            "history: H, article: woodford}\n")
    for meas, sev in (("nope", "info"), ("illiquid_share", "loud")):
        p = tmp_path / "r.yaml"
        p.write_text(base % (meas, sev))
        with pytest.raises(ValueError):
            rules.load_rules(p)


app_only = pytest.mark.skipif(not data.SAMPLE_PATH.exists(), reason="bundled sample not built")


def run_app(fund: Fund | None = None) -> AppTest:
    at = AppTest.from_file(str(data.ROOT / "app.py"), default_timeout=120)
    if fund:
        at.query_params.update({"fund": fund.to_share_code()})
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def dismiss_buttons(at) -> list[str]:
    return [b.key for b in at.button if str(b.key).startswith("dismiss_")]


def insight_count(at) -> int:
    return int(next(e.label for e in at.expander if e.label.startswith("Insights (")).split("(")[1].rstrip(")"))


@app_only
def test_a_loaded_fund_lists_insights_without_popping_up():
    at = run_app(fund_with_unlisted(7_000, 3_000, exp_return=0.6))
    assert dismiss_buttons(at) == []
    text = " ".join(m.value for m in at.markdown)
    assert "can't be sold in a hurry" in text and "unusually high return" in text and insight_count(at) >= 2


@app_only
def test_a_change_pops_up_until_dismissed():
    at = run_app(fund_with_unlisted(9_000, 1_000))
    before = insight_count(at)  # a Top 40 tracker alone is bank-heavy, so not necessarily 0
    assert dismiss_buttons(at) == []
    at.segmented_control(key="add_kind").set_value("unlisted").run()
    at.text_input(key="ul_name_0___new__").set_value("Coffee shop").run()
    at.number_input(key="ul_r_0___new__").set_value(60.0).run()
    at.number_input(key="ul_hi_0___new__").set_value(80.0).run()
    at.number_input(key="amt_0_UL:coffee-shop").set_value(3000.0).run()
    next(b for b in at.button if b.label == "Add it").click().run()
    assert not at.exception
    # three rules trip (the coffee shop is also one business at 23% of the fund); two pop up at a time
    assert dismiss_buttons(at) == ["dismiss_cant_sell_in_a_hurry", "dismiss_unlisted_promise"]
    assert any("1 more in" in c.value for c in at.caption)
    next(b for b in at.button if b.key == "dismiss_unlisted_promise").click().run()
    assert dismiss_buttons(at) == ["dismiss_cant_sell_in_a_hurry", "dismiss_one_company"]
    assert insight_count(at) == before + 3


@app_only
def test_leverage_pops_up_on_the_risk_page():
    at = run_app(Fund("F", [Holding("STX40.JO", "Satrix 40", "jse_etf", 10_000)]))
    at.switch_page("views/risk.py").run()
    assert "dismiss_leverage_on" not in dismiss_buttons(at)
    at.segmented_control(key="lev").set_value(2.0).run()
    assert not at.exception, [e.value for e in at.exception]
    assert "dismiss_leverage_on" in dismiss_buttons(at)
