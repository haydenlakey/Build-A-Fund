"""Library content: every article parses, is sourced, links resolve and never gives advice."""
import re

import pytest

from fundlab import data
from fundlab.content import GROUPS, SECTIONS, load_library

LIB = load_library()
ADVICE = re.compile(r"\b(you should|we recommend|i recommend|recommended|should (buy|sell|invest)|buy now|sell now)\b", re.I)


def test_library_has_every_section_except_planned_ones():
    assert LIB
    assert {"basics", "bubbles", "case", "counter", "theory"} <= {a.section for a in LIB.values()}


@pytest.mark.parametrize("slug", sorted(LIB))
def test_article_is_sourced_and_well_formed(slug):
    a = LIB[slug]
    assert a.section in SECTIONS and a.title and a.body and a.summary
    assert a.sources, "every article needs at least one source"
    for s in a.sources:
        assert s["url"].startswith("https://"), s
        assert s.get("title") and str(s.get("accessed", "")).startswith("20"), s
    for r in a.related:
        assert r in LIB, f"related link {r!r} does not exist"
    assert not ADVICE.search(a.body + " " + a.lesson + " " + a.summary)


@pytest.mark.parametrize("slug", sorted(s for s, a in LIB.items() if a.section == "case"))
def test_case_files_have_group_lesson_and_chart(slug):
    a = LIB[slug]
    assert a.group in GROUPS and a.lesson and a.years
    assert a.chart and a.chart["kind"] in ("prices", "points")


@pytest.mark.parametrize("slug", sorted(s for s, a in LIB.items() if a.chart))
def test_charts_have_data(slug):
    c = LIB[slug].chart
    if c["kind"] == "points":
        assert len(c["points"]) >= 3 and c.get("source")
        dates = [str(d) for d, _ in c["points"]]
        assert dates == sorted(dates)
    else:
        store = data.PriceStore(allow_live=False)
        for t in c["tickers"]:
            assert store.has(t), f"{t} is not in the bundled prices"
            s = store.native[t].loc[str(c["start"]):str(c["end"])].dropna()
            assert len(s) >= 3, t
