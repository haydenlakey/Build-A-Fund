"""Explore diversifiers and side-by-side comparison: the maths, and both pages in the app."""
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from fundlab import analysis, data, diversifiers, estimators, risk
from fundlab.model import Fund, FundSettings, Holding

FRIDAYS = pd.date_range("2018-01-05", periods=300, freq="W-FRI")
SAMPLE = FundSettings(cov_method="sample", lookback_years=None)


def prices(seed=1):
    """A, B held; C moves against them, D with them, E is noisy; F lists late."""
    rng = np.random.default_rng(seed)
    m = rng.normal(0.002, 0.02, len(FRIDAYS))
    r = pd.DataFrame({
        "A": m + rng.normal(0, 0.01, len(FRIDAYS)), "B": m + rng.normal(0, 0.015, len(FRIDAYS)),
        "C": -0.5 * m + rng.normal(0.001, 0.01, len(FRIDAYS)), "D": 1.5 * m + rng.normal(0, 0.01, len(FRIDAYS)),
        "E": rng.normal(0.001, 0.05, len(FRIDAYS)), "F": m + rng.normal(0, 0.01, len(FRIDAYS)),
    }, index=FRIDAYS)
    px = 100 * (1 + r).cumprod()
    px.loc[:FRIDAYS[100], "F"] = np.nan
    return px


def test_exact_formula_matches_a_rebuilt_fund_and_ranks_by_volatility():
    px = prices()
    w = pd.Series({"A": 0.6, "B": 0.4})
    ex = diversifiers.explore(px, w, ["A", "C", "D", "E", "F"], FRIDAYS[0], FRIDAYS[-1], SAMPLE, 2_500, 10_000)
    assert list(ex.table.index[:1]) == ["C"] and "A" not in ex.table.index
    assert "F" in ex.skipped and "start" in ex.skipped["F"]
    assert ex.add_share == pytest.approx(0.2) and ex.n_weeks == len(FRIDAYS) - 1
    assert ex.table["d_vol"].is_monotonic_increasing
    cov = estimators.sample_cov(estimators.prices_to_returns(px[["A", "B", "C", "D", "E"]]))
    assert ex.vol_before == pytest.approx(risk.portfolio_vol(w, cov))
    for c in ("C", "D", "E"):
        w2 = pd.concat([0.8 * w, pd.Series({c: 0.2})])
        assert ex.table.loc[c, "vol_after"] == pytest.approx(risk.portfolio_vol(w2, cov), rel=1e-10)
    assert ex.table.loc["C", "corr"] < 0 < ex.table.loc["D", "corr"]
    assert ex.table.loc["C", "d_vol"] < 0 < ex.table.loc["D", "d_vol"]


def test_marginal_change_is_volatility_times_beta_minus_one():
    px = prices(2)
    w = pd.Series({"A": 0.5, "B": 0.5})
    tiny = diversifiers.explore(px, w, ["C", "D", "E"], FRIDAYS[0], FRIDAYS[-1], SAMPLE, 1.0, 1e6)
    t = tiny.table
    s = tiny.add_share
    assert (t["d_vol"] / s).to_numpy() == pytest.approx((tiny.vol_before * (t["beta"] - 1)).to_numpy(), rel=1e-3)


def test_compare_many_uses_one_window_and_matches_compare():
    px = prices(3)
    f1 = Fund("One", [Holding("A", "A", "jse_etf", 100), Holding("B", "B", "jse_etf", 100)], settings=SAMPLE)
    f2 = Fund("Two", [Holding("A", "A", "jse_etf", 100), Holding("F", "F", "jse_etf", 300)], settings=SAMPLE)
    mc = analysis.compare_many([f1, f2], px, SAMPLE)
    cmp = analysis.compare(f1, f2, px, SAMPLE)
    assert mc.est.report.start == FRIDAYS[101]  # F's first price cuts the window for both
    assert mc.stats[0].vol == pytest.approx(cmp.before.vol) and mc.stats[1].vol == pytest.approx(cmp.after.vol)
    assert mc.gaps[0] == pytest.approx(cmp.gap_before, abs=1e-6)
    assert len(mc.stats[0].port_returns) == len(mc.stats[1].port_returns)


pytestmark_app = pytest.mark.skipif(not data.SAMPLE_PATH.exists(), reason="bundled sample not built")
EXAMPLE = Fund("Example", [Holding("STX40.JO", "Satrix 40", "jse_etf", 10_000),
                           Holding("STX500.JO", "Satrix S&P 500", "jse_etf", 5_000),
                           Holding("GLD.JO", "NewGold Gold ETF", "jse_etf", 2_000)])


def app(page: str) -> AppTest:
    at = AppTest.from_file(str(data.ROOT / "app.py"), default_timeout=120)
    at.query_params.update({"fund": EXAMPLE.to_share_code()})
    at.run()
    at.switch_page(page).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@pytestmark_app
def test_explore_page_lists_candidates_and_makes_a_copy():
    at = app("views/explore.py")
    table = at.dataframe[0].value
    assert len(table) == 15 and table["Change in volatility"].is_monotonic_increasing
    assert not set(table["Ticker"]) & {"STX40.JO", "STX500.JO", "GLD.JO"}
    at.multiselect(key="ex_kinds").set_value(["us_etf"]).run()
    assert set(at.dataframe[0].value["Type"]) == {"US-listed ETF"}
    pick = at.selectbox(key="ex_pick").value
    next(b for b in at.button if b.label == "Make a copy with it").click().run()
    assert not at.exception
    funds = list(at.session_state.funds.values())
    assert len(funds) == 2 and funds[1].holding(pick) is not None and funds[0].holding(pick) is None
    assert at.session_state.active == funds[0].id

    at.switch_page("views/compare.py").run()
    assert not at.exception, [e.value for e in at.exception]
    side = at.dataframe[0].value
    assert list(side.columns) == [funds[0].name, funds[1].name] and "Volatility" in side.index
    assert side.loc["Holdings"].tolist() == ["3", "4"]


@pytestmark_app
def test_compare_page_with_one_fund_explains_what_to_do():
    at = app("views/compare.py")
    assert any("at least two funds" in i.value for i in at.info)


@pytestmark_app
def test_compare_keeps_each_funds_own_unit_trust_inputs():
    def fund(name, alloc):
        return Fund(name, [Holding("STX40.JO", "Satrix 40", "jse_etf", 1000),
                           Holding("UT:mine", "My balanced fund", "unit_trust", 3000, method="allocation_model",
                                   params={"allocation": alloc, "ter": 0.01})])
    calm, bold = fund("Calm", {"sa_cash": 1.0}), fund("Bold", {"global_equity": 1.0})
    at = AppTest.from_file(str(data.ROOT / "app.py"), default_timeout=120)
    at.query_params.update({"fund": calm.to_share_code()})
    at.run()
    funds = dict(at.session_state.funds)
    funds[bold.id] = bold
    at.session_state.funds = funds
    at.switch_page("views/compare.py").run()
    assert not at.exception, [e.value for e in at.exception]
    vol = at.dataframe[0].value.loc["Volatility"]
    assert vol.iloc[0] != vol.iloc[1]  # before the fix both funds used the last fund's allocation
