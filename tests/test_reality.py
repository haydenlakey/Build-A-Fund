"""Reality check: costs, backtests with rebalancing, and the optimiser."""
import numpy as np
import pandas as pd
import pytest

from fundlab import backtest, costs, frontier, risk
from fundlab.model import Fund, Holding


# ---- costs -------------------------------------------------------------------------

def test_platform_costs_file_is_sourced_and_sane():
    pc = costs.load_platform_costs()
    assert pc["source"].startswith("https://") and pc["accessed"] and pc["as_of"]
    assert 0 < pc["broker_commission"] < 0.01 and pc["vat"] == pytest.approx(0.15)


def test_trading_costs_from_the_cost_profile():
    pc = costs.load_platform_costs()
    t = costs.TradingCosts.from_platform(pc)
    vatable = (0.0025 + 0.000795 + 0.0000031) * 1.15
    assert t.buy_other == pytest.approx(vatable)
    assert t.buy_share == pytest.approx(vatable + 0.0025)  # STT on share purchases
    assert t.sell == pytest.approx(vatable)
    assert t.buy_cost("us_share") == pytest.approx(vatable + 0.005)
    assert t.buy_cost("unit_trust") == 0 and t.sell_cost("unlisted") == 0


def _fund():
    return Fund("C", [Holding("STX40.JO", "S", "jse_etf", 6000), Holding("CPI.JO", "C", "jse_share", 2000),
                      Holding("UT:x", "U", "unit_trust", 2000, method="allocation_model",
                              params={"allocation": {"sa_equity": 100}, "ter": 0.015})])


def test_summary_weights_costs_by_amount():
    t = costs.TradingCosts(0.006, 0.004, 0.004, 0.005)
    s = costs.summarise(_fund(), {"STX40.JO": 0.001, "UT:x": 0.015}, {"STX40.JO": 0.0003}, t, 0.0025, 25.0)
    assert s.total_zar == 10_000
    assert s.fund_costs == pytest.approx(0.6 * 0.0013 + 0.2 * 0.015)
    assert s.platform == pytest.approx(0.2 * 0.0025)
    assert s.account == pytest.approx(300 / 10_000)
    assert s.buy == pytest.approx(0.6 * 0.004 + 0.2 * 0.006)
    assert s.yearly == pytest.approx(s.fund_costs + s.platform + s.account)


def test_projection_matches_a_year_by_year_loop():
    t = costs.TradingCosts(0.006, 0.004, 0.004, 0.0)
    s = costs.summarise(_fund(), {"UT:x": 0.015}, {}, t, 0.0025, 25.0)
    g, n = 0.09, 12
    v = s.total_zar * (1 - s.buy)
    r = g - s.fund_costs - s.platform
    for _ in range(n):
        v = v * (1 + r) - 300
    pj = costs.project(s.total_zar, g, s, 25.0, n)
    assert pj.after_all == pytest.approx(v * (1 - s.sell))
    assert pj.no_costs == pytest.approx(10_000 * 1.09 ** 12)
    assert pj.lost == pytest.approx(pj.lost_fund + pj.lost_other)
    assert pj.no_costs > pj.after_fund_costs > pj.after_all


def test_no_costs_means_nothing_lost():
    s = costs.summarise(Fund("Z", [Holding("A.JO", "A", "jse_share", 1000)]), {}, {},
                        costs.TradingCosts(0, 0, 0, 0), 0.0, 0.0)
    pj = costs.project(1000, 0.08, s, 0.0, 20)
    assert pj.lost == pytest.approx(0.0)
    assert costs.value_paths(1000, 0.08, s, 0.0, 20).shape == (21, 3)


# ---- backtest ----------------------------------------------------------------------

def _returns(n=160, seed=3):
    idx = pd.date_range("2022-01-07", periods=n, freq="W-FRI")
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.normal(0.002, [0.03, 0.01, 0.02], (n, 3)), index=idx, columns=list("ABC"))


def test_rebalance_weeks():
    idx = pd.date_range("2022-01-07", periods=110, freq="W-FRI")
    assert backtest.rebalance_weeks(idx, "never").sum() == 0
    assert backtest.rebalance_weeks(idx, "weekly").sum() == 109
    m = backtest.rebalance_weeks(idx, "monthly")
    assert not m[0] and all(idx[i].month != idx[i - 1].month for i in np.flatnonzero(m))
    assert backtest.rebalance_weeks(idx, "yearly").sum() == 2  # into 2023 and 2024


def test_weekly_rebalancing_without_costs_is_the_fund_series():
    r = _returns()
    w = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
    run = backtest.run(r, w, "weekly")
    # the first week has no rebalance, but weights start at target, so it's still w'r every week
    expected = np.concatenate([[1.0], np.cumprod(1 + risk.portfolio_returns(w, r).to_numpy())])
    np.testing.assert_allclose(run.wealth.to_numpy(), expected)
    assert run.costs == 0 and len(run.wealth) == len(r) + 1


def test_never_rebalancing_is_buy_and_hold():
    r = _returns()
    w = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
    run = backtest.run(r, w, "never", 0.01, 0.01)
    expected = float((w * (1 + r).prod()).sum())
    assert run.wealth.iloc[-1] == pytest.approx(expected)
    assert run.turnover == 0 and run.costs == 0


def test_trading_costs_lower_the_result_and_grow_with_frequency():
    r = _returns()
    w = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
    free = backtest.run(r, w, "monthly").wealth.iloc[-1]
    paid = backtest.run(r, w, "monthly", 0.005, 0.005)
    assert paid.wealth.iloc[-1] < free and paid.costs > 0 and paid.turnover > 0
    weekly = backtest.run(r, w, "weekly", 0.005, 0.005)
    assert weekly.costs > paid.costs


def test_backtest_stats():
    idx = pd.date_range("2020-01-03", periods=105, freq="W-FRI")
    wealth = pd.Series(np.linspace(1, 1.21, 105), index=idx)
    s = backtest.stats(wealth, 0.0)
    assert s["total"] == pytest.approx(0.21)
    assert s["cagr"] == pytest.approx(1.21 ** (52 / 104) - 1)
    assert s["worst"] == pytest.approx(0.0)


# ---- optimiser ---------------------------------------------------------------------

def _mu_cov():
    idx = list("ABCD")
    mu = pd.Series([0.14, 0.10, 0.07, 0.06], index=idx)
    sd = np.array([0.25, 0.18, 0.10, 0.05])
    corr = np.full((4, 4), 0.3)
    np.fill_diagonal(corr, 1.0)
    return mu, pd.DataFrame(np.outer(sd, sd) * corr, index=idx, columns=idx)


def test_optimiser_beats_the_fund_on_its_goal():
    mu, cov = _mu_cov()
    w0 = pd.Series(0.25, index=mu.index)
    r0, v0 = risk.portfolio_return(w0, mu), risk.portfolio_vol(w0, cov)
    w = frontier.optimise(mu, cov, "same_risk", target_vol=v0)
    assert w.sum() == pytest.approx(1) and (w >= -1e-9).all()
    assert risk.portfolio_vol(w, cov) <= v0 + 1e-6 and risk.portfolio_return(w, mu) >= r0 - 1e-9
    w = frontier.optimise(mu, cov, "same_return", target_ret=r0)
    assert risk.portfolio_return(w, mu) >= r0 - 1e-6 and risk.portfolio_vol(w, cov) <= v0 + 1e-9


def test_max_sharpe_is_at_least_any_frontier_point():
    mu, cov = _mu_cov()
    w = frontier.optimise(mu, cov, "max_sharpe", rf=0.04)
    best = risk.sharpe(risk.portfolio_return(w, mu), risk.portfolio_vol(w, cov), 0.04)
    fr = frontier.efficient_frontier(mu, cov, 25)
    assert best >= max((r - 0.04) / v for r, v in zip(fr.rets, fr.vols)) - 1e-4


def test_resampling_spreads_the_weights():
    mu, cov = _mu_cov()
    se = pd.Series(0.2 / np.sqrt(5), index=mu.index)
    draws = frontier.resampled_weights(mu, se, cov, "max_sharpe", 60, seed=1, rf=0.04)
    assert draws.shape[1] == 4 and len(draws) > 50
    np.testing.assert_allclose(draws.sum(axis=1), 1.0, atol=1e-6)
    assert (draws.quantile(0.9) - draws.quantile(0.1)).max() > 0.3
    again = frontier.resampled_weights(mu, se, cov, "max_sharpe", 60, seed=1, rf=0.04)
    pd.testing.assert_frame_equal(draws, again)  # seeded


def test_unknown_goal_raises():
    mu, cov = _mu_cov()
    with pytest.raises(ValueError):
        frontier.optimise(mu, cov, "moon")
