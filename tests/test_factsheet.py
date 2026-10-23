import math
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from fundlab import PERIODS_PER_YEAR, factsheet, rules
from fundlab.model import Fund, Holding

WEEKS = pd.date_range("2020-01-03", "2026-10-16", freq="W-FRI")


def wealth(r: float, index=WEEKS) -> pd.Series:
    return pd.Series((1 + r) ** np.arange(len(index)), index=index)


@pytest.mark.parametrize("vol, level", [(0.0, "Low"), (0.0399, "Low"), (0.04, "Low to medium"), (0.08, "Medium"),
                                        (0.09, "Medium to high"), (0.12, "High"), (0.30, "High"),
                                        (float("nan"), "–")])
def test_risk_level_bands(vol, level):
    assert factsheet.risk_level(vol) == level


def test_pct_has_no_negative_zero():
    assert factsheet.pct(-0.0002) == "0.0%" and factsheet.pct(-0.0002, signed=True) == "+0.0%"
    assert factsheet.pct(-0.012) == "-1.2%" and factsheet.pct(float("nan")) == "–"


def test_constant_growth_gives_the_same_yearly_return_for_every_period():
    r = 0.002
    p = factsheet.performance(wealth(r), wealth(0.001))
    yearly = (1 + r) ** PERIODS_PER_YEAR - 1
    assert list(p.periods.index) == ["1 year", "3 years", "5 years", "Whole window (6.8 years)"]
    assert p.periods["fund"].tolist() == pytest.approx([yearly] * 4)
    assert p.periods["benchmark"].tolist() == pytest.approx([(1.001) ** PERIODS_PER_YEAR - 1] * 4)
    assert p.best_12m == pytest.approx(yearly) and p.worst_12m == pytest.approx(yearly)
    assert p.growth["fund"].iloc[0] == 1000 and p.growth["benchmark"].iloc[0] == 1000


def test_calendar_years_are_complete_years_plus_the_year_to_date():
    p = factsheet.performance(wealth(0.002))
    # 2020 has no value at the end of 2019, so the first complete year is 2021
    assert list(p.calendar.index) == ["2021", "2022", "2023", "2024", "2025", "2026 to 16 Oct"]
    weeks_2022 = sum(WEEKS.year == 2022)
    assert p.calendar.loc["2022", "fund"] == pytest.approx(1.002 ** weeks_2022 - 1)
    assert p.calendar["benchmark"].isna().all()  # no benchmark given


def test_benchmark_with_a_shorter_history_is_shown_only_where_it_has_prices():
    bench = wealth(0.001)
    bench[bench.index < "2023-01-01"] = np.nan
    p = factsheet.performance(wealth(0.002), bench)
    assert math.isfinite(p.periods.loc["1 year", "benchmark"])
    assert math.isnan(p.periods.loc["5 years", "benchmark"])
    first = bench.first_valid_index()
    assert p.growth.loc[first, "benchmark"] == pytest.approx(p.growth.loc[first, "fund"])  # starts level with the fund


def test_short_window_has_no_long_periods():
    p = factsheet.performance(wealth(0.002, WEEKS[-80:]))
    assert list(p.periods.index) == ["1 year", "Whole window (1.5 years)"]


def test_holdings_table_shows_the_top_ten_then_the_rest():
    f = Fund("Many", [Holding(f"T{i}.JO", f"Share {i}", "jse_share", 100 + i) for i in range(14)])
    t = factsheet.holdings_table(f, {})
    assert len(t) == 11 and t["weight"].sum() == pytest.approx(1.0)
    assert t["name"].iloc[0] == "T13.JO" and t["name"].iloc[-1] == "Other (4 holdings)"
    assert t["type"].iloc[0] == "JSE share"


def _insight(rid: str, severity: str) -> rules.Insight:
    r = rules.Rule(id=rid, title=rid.title(), when={"x": {"above": 0}}, severity=severity, noticed="n {value}",
                   history="h", article=f"art-{rid}")
    return rules.Insight(r, {"x": 1.0})


def test_top_insights_put_warnings_first_then_file_order():
    tripped = [_insight("a", "info"), _insight("b", "warning"), _insight("c", "info"), _insight("d", "warning")]
    top = factsheet.top_insights(tripped, {"art-b": "Article B"})
    assert [i.title for i in top] == ["B", "D", "A"]
    assert top[0].article_title == "Article B" and top[1].article_title == "art-d"


def test_build_with_nothing_measured_still_makes_a_sheet():
    f = Fund("Only unlisted", [Holding("UL:x", "Coffee shop", "unlisted", 5000, method="assumptions",
                                       params={"exp_return": 0.2})], objective="Learn.")
    sheet = factsheet.build(f, names={"UL:x": "Coffee shop"}, illiquid=1.0)
    assert sheet.performance is None and sheet.risk == [] and sheet.fees == []
    assert any("No performance" in n for n in sheet.notes)
    assert dict(sheet.details)["Can't be sold in a hurry"] == "100%"
    assert sheet.holdings["name"].tolist() == ["Coffee shop"] and sheet.objective == "Learn."


def test_build_uses_whole_fund_volatility_for_the_risk_level():
    f = Fund("F", [Holding("A.JO", "A", "jse_share", 1000)])
    stats = SimpleNamespace(vol=0.05, coverage=0.5, eff_holdings=1.0, max_drawdown=-0.1, sharpe=0.4, var=0.03)
    sheet = factsheet.build(f, names={}, stats=stats, whole=SimpleNamespace(vol=0.15),
                            fund_wealth=wealth(0.002), benchmark="JSE Top 40")
    assert sheet.risk_level == "High"
    assert dict(sheet.risk)["Whole fund volatility (with unlisted)"] == "15.0% a year"
    assert any("cover the 50%" in n for n in sheet.notes)


def test_sheet_text_never_advises():
    words = r"\b(buy|sell|should|recommend)\b"
    import re
    assert not re.search(words, factsheet.DISCLAIMER, re.I)
    f = Fund("F", [Holding("A.JO", "A", "jse_share", 1000)])
    stats = SimpleNamespace(vol=0.05, coverage=1.0, eff_holdings=1.0, max_drawdown=-0.1, sharpe=0.4, var=0.03)
    cost = SimpleNamespace(platform=0.0, account=0.003, buy=0.006, total_zar=1000.0)
    sheet = factsheet.build(f, names={}, stats=stats, fund_wealth=wealth(0.002), cost_summary=cost,
                            comp=SimpleNamespace(weighted_ter=0.001, weighted_tc=0.0, by_asset=pd.Series({"equity": 1.0}),
                                                 by_sector=pd.Series({"Technology": 1.0}),
                                                 by_country=pd.Series({"ZA": 1.0})))
    text = " ".join(f"{k} {v}" for k, v in sheet.details + sheet.risk + sheet.fees)
    assert not re.search(words, text, re.I)
    assert sheet.by_country.index.tolist() == ["South Africa"] and sheet.by_asset.index.tolist() == ["Shares"]


# ---- the page -------------------------------------------------------------------------------

from streamlit.testing.v1 import AppTest  # noqa: E402

from fundlab import data  # noqa: E402

app_only = pytest.mark.skipif(not data.SAMPLE_PATH.exists(), reason="bundled sample not built")
EXAMPLE = Fund("Example", [Holding("STX40.JO", "Satrix 40", "jse_etf", 10_000),
                           Holding("STX500.JO", "Satrix S&P 500", "jse_etf", 5_000),
                           Holding("NPN.JO", "Naspers", "jse_share", 4_000),
                           Holding("GLD.JO", "NewGold Gold ETF", "jse_etf", 2_000)])


def page(fund: Fund) -> AppTest:
    at = AppTest.from_file(str(data.ROOT / "app.py"), default_timeout=120)
    at.query_params.update({"fund": fund.to_share_code()})
    at.run()
    at.switch_page("views/factsheet.py").run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@app_only
def test_fact_sheet_page_shows_every_block():
    at = page(EXAMPLE)
    heads = [h.value for h in at.subheader]
    for h in ["Fund details", "Risk", "Fees", "Asset classes", "Performance (simulated)", "Top holdings",
              "Sectors", "Countries", "Top insights"]:
        assert h in heads
    assert at.header[0].value == "Example"
    assert len(at.get("plotly_chart")) == 3
    assert sum(t.label == "Show me the maths" for t in at.toggle) >= 3  # every chart has its notes
    holdings = next(m.value for m in at.markdown if "<th class=l>Holding</th>" in m.value)
    assert holdings.index("Satrix 40") < holdings.index("Naspers")  # largest first


@app_only
def test_objective_and_benchmark_are_saved_with_the_fund():
    at = page(EXAMPLE)
    fid = at.session_state.active
    at.text_area(key=f"objective_{fid}").input("Growth over ten years or more.").run()
    assert not at.exception
    assert at.session_state.funds[fid].objective == "Growth over ten years or more."
    assert any("Growth over ten years" in m.value for m in at.markdown)
    at.selectbox[0].select("sp500").run()
    assert at.session_state.funds[fid].settings.benchmark == "sp500"
    details = next(m.value for m in at.markdown if "Fund size" in m.value)
    assert ">US shares (S&amp;P 500 in rand)</td>" in details  # values are escaped


@app_only
def test_fact_sheet_for_an_empty_and_an_unlisted_fund():
    at = AppTest.from_file(str(data.ROOT / "app.py"), default_timeout=120)
    at.run()
    at.switch_page("views/factsheet.py").run()
    assert not at.exception and any("empty" in i.value for i in at.info)
    unl = Fund("Side business", [Holding("STX40.JO", "Satrix 40", "jse_etf", 3_000),
                                 Holding("UL:shop", "Coffee shop", "unlisted", 6_000, method="assumptions",
                                         params={"exp_return": 0.25, "lockin_years": 5, "p_loss": 0.05})])
    at = page(unl)
    risk = next(m.value for m in at.markdown if "<td class=l>Volatility</td>" in m.value)
    assert "<td class=l>Whole fund volatility (with unlisted)</td>" in risk
    assert any("cover the 33%" in c.value for c in at.caption)
