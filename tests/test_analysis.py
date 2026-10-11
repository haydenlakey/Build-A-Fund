import numpy as np
import pandas as pd
import pytest

from fundlab import analysis, verdict
from fundlab.model import Fund, FundSettings, Holding


@pytest.fixture(scope="module")
def prices():
    """Synthetic weekly rand prices.

    A and B move together (corr ~0.9, B is wilder); C is unrelated and calm;
    NEW lists two years before the end; TINY has only 30 weeks.
    """
    rng = np.random.default_rng(11)
    n = 600
    weeks = pd.date_range("2014-01-03", periods=n, freq="W-FRI")
    common = rng.normal(0.002, 0.03, n)
    r = pd.DataFrame({
        "A": common + rng.normal(0, 0.012, n),
        "B": 1.5 * common + rng.normal(0, 0.02, n),
        "C": rng.normal(0.0015, 0.015, n),
        "NEW": rng.normal(0.002, 0.03, n),
        "TINY": rng.normal(0.002, 0.03, n),
    }, index=weeks)
    p = 100 * (1 + r).cumprod()
    p.loc[weeks[: n - 104], "NEW"] = np.nan
    p.loc[weeks[: n - 30], "TINY"] = np.nan
    return p


def fund(**amounts):
    return Fund("T", [Holding(t, t, "jse_share", a) for t, a in amounts.items()])


SETTINGS = FundSettings(lookback_years=None, cov_method="sample", mean_shrinkage=0.0)


def test_history_window_rules(prices):
    rep = analysis.history_window(prices, ["A", "NEW", "TINY", "MISSING"], None)
    assert rep.included == ["A", "NEW"]
    assert "TINY" in rep.excluded and "29 weeks" in rep.excluded["TINY"]  # 30 prices = 29 returns
    assert "MISSING" in rep.excluded
    assert rep.limited_by == "NEW"
    assert rep.n_weeks == 103 and rep.is_short
    assert rep.short == {"NEW": 103}


def test_lookback_cuts_window(prices):
    rep = analysis.history_window(prices, ["A", "C"], lookback_years=3)
    assert 155 <= rep.n_weeks <= 157
    assert rep.limited_by is None


def test_fund_stats_coverage_excludes_unmeasurable(prices):
    est = analysis.estimate(prices, ["A", "TINY"], SETTINGS)
    st = analysis.fund_stats(fund(A=750, TINY=250), est, SETTINGS)
    assert st.coverage == pytest.approx(0.75)
    assert st.weights.sum() == pytest.approx(1.0)
    assert "TINY" in st.excluded
    assert st.risk_shares.sum() == pytest.approx(1.0)
    assert st.var_zar == pytest.approx(st.var * 750)  # VaR in rand covers only the measured R750


def test_compare_uses_common_window(prices):
    before, after = fund(A=1000), fund(A=1000, NEW=500)
    cmp = analysis.compare(before, after, prices, SETTINGS)
    assert len(cmp.est.returns) == 103  # the before fund is measured on NEW's shorter window too
    alone = analysis.fund_stats(before, analysis.estimate(prices, ["A"], SETTINGS), SETTINGS)
    assert cmp.before.vol != pytest.approx(alone.vol)


def test_before_stats_do_not_depend_on_the_candidate(prices):
    """Regression: shrinking toward the cross-sectional mean made 'before' move with the candidate."""
    s = FundSettings(lookback_years=None, mean_shrinkage=0.5)
    base = fund(A=1000)
    with_b = analysis.compare(base, fund(A=1000, B=500), prices, s)
    with_c = analysis.compare(base, fund(A=1000, C=500), prices, s)
    assert with_b.before.exp_return == pytest.approx(with_c.before.exp_return)
    assert with_b.before.vol == pytest.approx(with_c.before.vol, rel=1e-3)  # LW delta may differ slightly


def test_equal_sharpe_target_scales_with_vol(prices):
    from fundlab import estimators
    rets = prices[["A", "B", "C"]].pct_change().dropna()
    t = estimators.equal_sharpe_target(rets, 0.07, 0.3)
    sig = rets.std() * np.sqrt(52)
    assert np.allclose((t - 0.07) / sig, 0.3)
    assert t["B"] > t["A"] > t["C"]


def test_diversifier_moves_fund_toward_shared_frontier(prices):
    # with two assets every mix above the min-variance point is efficient, so use three
    cmp = analysis.compare(fund(A=1000, B=1000), fund(A=1000, B=1000, C=1000), prices, SETTINGS)
    assert cmp.gap_before > 0.005
    assert cmp.gap_after < cmp.gap_before
    assert "closer to the efficient frontier" in " ".join(verdict.explain(cmp, "C").details)


def test_empty_fund_has_no_stats(prices):
    cmp = analysis.compare(Fund("E"), fund(A=100), prices, SETTINGS)
    assert cmp.before is None and cmp.after is not None
    assert "first holding" in verdict.explain(cmp, "A").headline


def test_verdict_correlated_addition(prices):
    cmp = analysis.compare(fund(A=1000), fund(A=1000, B=1000), prices, SETTINGS)
    v = verdict.explain(cmp, "B")
    assert v.action == "add" and v.corr > 0.7
    assert "one for one" in v.headline


def test_verdict_diversifying_addition(prices):
    cmp = analysis.compare(fund(A=1000), fund(A=1000, C=1000), prices, SETTINGS)
    v = verdict.explain(cmp, "C")
    assert v.corr < 0.3 and cmp.delta("vol") < 0
    assert "low correlation" in v.headline and "risk falls" in v.headline


def test_verdict_removing_a_diversifier(prices):
    cmp = analysis.compare(fund(A=1000, C=1000), fund(A=1000), prices, SETTINGS)
    v = verdict.explain(cmp, "C")
    assert v.action == "remove" and v.headline.startswith("Removing C")
    assert "diversification work" in v.headline


def test_verdict_unmeasurable_holding(prices):
    cmp = analysis.compare(fund(A=1000), fund(A=1000, TINY=100), prices, SETTINGS)
    v = verdict.explain(cmp, "TINY")
    assert "can't be measured" in v.headline


def test_verdict_never_recommends(prices):
    words = ("should", "buy", "sell", "recommend")
    for t in ("B", "C"):
        v = verdict.explain(analysis.compare(fund(A=1000), fund(A=1000, **{t: 800}), prices, SETTINGS), t)
        text = (v.headline + " ".join(v.details)).lower()
        assert not any(w in text for w in words)
