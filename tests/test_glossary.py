"""Glossary: the terms file is complete and neutral, and annotation marks terms safely."""
import re

import pytest
from streamlit.testing.v1 import AppTest

from fundlab import content, data, glossary

TERMS = glossary.load_glossary()
LIB = content.load_library()


def marked(html_text: str) -> list[str]:
    return re.findall(r'<span class="gl"[^>]*>([^<]+)</span>', html_text)


def test_terms_are_complete_neutral_and_unambiguous():
    assert len(TERMS) >= 40
    spellings = {}
    for t in TERMS:
        assert t.definition and len(t.definition) < 300, t.term
        assert not re.search(r"\b(should|recommend\w*)\b", t.definition, re.I), t.term
        assert not t.article or t.article in LIB, f"{t.term}: no article {t.article}"
        for s in (t.term, *t.aliases):
            assert s.lower() not in spellings, f"{s!r} is in both {spellings.get(s.lower())} and {t.term}"
            spellings[s.lower()] = t.term


@pytest.mark.parametrize("term", ["expected return", "volatility", "Sharpe ratio", "drawdown", "value at risk",
                                  "expected shortfall", "diversification ratio", "effective holdings",
                                  "efficient frontier", "tracking error", "information ratio", "beta", "TER",
                                  "leverage", "rand hedge", "look-through", "unit trust", "ETF"])
def test_the_app_s_core_terms_are_defined(term):
    assert glossary.lookup(TERMS, term) is not None


def test_first_mention_only_with_plurals_and_longest_match():
    out = glossary.annotate("The diversification ratio rises with diversification. ETFs and an ETF. "
                            "Volatility, then volatility.", TERMS)
    assert marked(out) == ["diversification ratio", "diversification", "ETFs", "Volatility"]


def test_acronyms_match_their_case_only():
    assert marked(glossary.annotate("var and es are words; VaR and ES are measures.", TERMS)) == ["VaR", "ES"]


def test_maths_links_code_and_html_are_left_alone():
    text = ("See [volatility](https://x.org/volatility), `beta`, $\beta$ and $$\sigma = volatility$$ "
            "and <b title='beta'>x</b>; then beta.")
    out = glossary.annotate(text, TERMS)
    assert marked(out) == ["beta"] and out.endswith('beta</span>.')
    assert "[volatility](https://x.org/volatility)" in out and "$$\sigma = volatility$$" in out


def test_definitions_are_escaped_and_used_is_shared():
    out = glossary.annotate("Sharpe ratio", TERMS)
    assert "data-def=\"" in out and "'" not in out.split("data-def=")[1].split('">')[0]
    used = set()
    first = glossary.annotate("beta here", TERMS, used)
    second = glossary.annotate("beta there", TERMS, used)
    assert marked(first) == ["beta"] and marked(second) == []


@pytest.mark.skipif(not data.SAMPLE_PATH.exists(), reason="bundled sample not built")
def test_library_glossary_section_and_marked_articles():
    at = AppTest.from_file(str(data.ROOT / "app.py"), default_timeout=120).run()
    at.switch_page("views/library.py").run()
    at.segmented_control(key="lib_section").set_value("glossary").run()
    assert not at.exception, [e.value for e in at.exception]
    assert any(m.value == "**Sharpe ratio**" for m in at.markdown)
    at.query_params["article"] = "diversification"
    at.switch_page("views/library.py").run()
    assert not at.exception
    assert any('class="gl"' in m.value for m in at.markdown)
