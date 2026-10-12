"""Insight rules: the rules file is valid and sourced, evaluation trips at the threshold, and the pop-ups work."""
import re

import pytest
from streamlit.testing.v1 import AppTest

from fundlab import content, data, rules
from fundlab.model import Fund, Holding

RULES = rules.load_rules()
LIB = content.load_library()


def fund_with_unlisted(listed: float, unl: float) -> Fund:
    return Fund("F", [Holding("STX40.JO", "Satrix 40", "jse_etf", listed),
                      Holding("UL:farm", "A farm", "unlisted", unl, method="assumptions", params={"lockin_years": 7})])


def test_rules_file_is_complete_and_sourced():
    assert RULES
    for r in RULES:
        assert r.article in LIB, f"{r.id}: no library article {r.article!r}"
        assert r.title and r.noticed and r.history and 0 <= r.above <= 1
        assert "{value}" in r.noticed
        advice = r"\b(should|recommend\w*|(buy|sell) (it|this|that|now|more))\b"
        assert not re.search(advice, " ".join((r.title, r.noticed, r.history)), re.I), r.id
        if re.search(r"\d", r.history):
            assert r.sources, f"{r.id}: figures in history need a source"
        for s in r.sources:
            assert s["url"].startswith("https://") and re.fullmatch(r"20\d\d-\d\d-\d\d", s["accessed"])


def test_illiquid_rule_trips_above_the_threshold_only():
    tripped = rules.evaluate(RULES, fund_with_unlisted(7_000, 3_000))
    assert [i.rule.id for i in tripped] == ["cant_sell_in_a_hurry"]
    assert tripped[0].value == pytest.approx(0.3)
    assert tripped[0].noticed.startswith("30% of your fund's rands")
    assert "Woodford" in tripped[0].rule.history
    assert rules.evaluate(RULES, fund_with_unlisted(9_000, 1_000)) == []
    assert rules.evaluate(RULES, fund_with_unlisted(8_000, 2_000)) == []  # exactly 20%: not above it
    assert rules.evaluate(RULES, Fund("Empty")) == []


def test_bad_rules_are_rejected(tmp_path):
    base = ("rules:\n  - {id: x, title: T, trigger: %s, above: 0.1, severity: %s, noticed: '{value}', "
            "history: H, article: woodford}\n")
    for trig, sev in (("nope", "info"), ("illiquid_share", "loud")):
        p = tmp_path / "r.yaml"
        p.write_text(base % (trig, sev))
        with pytest.raises(ValueError):
            rules.load_rules(p)


@pytest.mark.skipif(not data.SAMPLE_PATH.exists(), reason="bundled sample not built")
def test_popup_shows_until_dismissed_and_stays_in_the_list():
    def run(fund):
        at = AppTest.from_file(str(data.ROOT / "app.py"), default_timeout=120)
        at.query_params.update({"fund": fund.to_share_code()})
        return at.run()

    at = run(fund_with_unlisted(7_000, 3_000))
    assert not at.exception
    assert any(b.key == "dismiss_cant_sell_in_a_hurry" for b in at.button)
    assert any(e.label == "Insights (1)" for e in at.expander)
    next(b for b in at.button if b.key == "dismiss_cant_sell_in_a_hurry").click().run()
    assert not any(b.key == "dismiss_cant_sell_in_a_hurry" for b in at.button)
    assert any(e.label == "Insights (1)" for e in at.expander)

    quiet = run(fund_with_unlisted(9_000, 1_000))
    assert not quiet.exception
    assert not any(b.key == "dismiss_cant_sell_in_a_hurry" for b in quiet.button)
    assert any(e.label == "Insights (0)" for e in quiet.expander)
