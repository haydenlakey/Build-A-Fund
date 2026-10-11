"""Risk detail: weekly simulation, fan bands, leverage and margin calls, stress-test replays."""
import re

import numpy as np
import pandas as pd
import pytest

from fundlab import leverage, stress, unlisted, var
from fundlab.model import Fund, Holding

ADVICE = re.compile(r"\b(you should|we recommend|recommended|should (buy|sell|invest)|buy now|sell now)\b", re.I)


def _two_assets():
    idx = ["A", "B"]
    mu = pd.Series([0.10, 0.06], index=idx)
    cov = pd.DataFrame([[0.04, 0.006], [0.006, 0.01]], index=idx, columns=idx)
    w = pd.Series([0.6, 0.4], index=idx)
    return mu, cov, w


# ---- simulation --------------------------------------------------------------------

@pytest.mark.parametrize("dist", ["normal", "t"])
def test_simulate_paths_is_compounded_weekly(dist):
    mu, cov, w = _two_assets()
    weekly = var.simulate_weekly(mu, cov, w, 8, 500, dist, 5.0, seed=7)
    assert weekly.shape == (500, 8)
    total = var.simulate_paths(mu, cov, w, 8, 500, dist, 5.0, seed=7)
    np.testing.assert_allclose(total, np.prod(1 + weekly, axis=1) - 1)


def test_weekly_sims_match_moments():
    mu, cov, w = _two_assets()
    weekly = var.simulate_weekly(mu, cov, w, 52, 4000, seed=1)
    port_sd = float(np.sqrt(w @ cov @ w))
    assert weekly.mean() * 52 == pytest.approx(float(w @ mu), abs=0.01)
    assert weekly.std() * np.sqrt(52) == pytest.approx(port_sd, rel=0.02)


def test_fan_bands_are_ordered_and_start_at_one():
    rng = np.random.default_rng(0)
    paths = np.concatenate([np.ones((2000, 1)), np.cumprod(1 + rng.normal(0.002, 0.03, (2000, 104)), axis=1)], axis=1)
    bands = var.fan(paths)
    assert list(bands.columns) == [5, 25, 50, 75, 95]
    assert (bands.iloc[0] == 1).all()
    assert (bands.diff(axis=1).iloc[:, 1:] >= 0).all().all()
    assert bands[95].iloc[-1] - bands[5].iloc[-1] > bands[95].iloc[10] - bands[5].iloc[10]  # widens


def test_unlisted_paths_end_where_simulate_does():
    f = Fund("U", [Holding("STX40.JO", "S", "jse_etf", 8000),
                   Holding("UNL:farm", "Farm", "unlisted", 2000, method="assumptions",
                           params={"exp_return": 0.15, "low": -0.1, "high": 0.4, "lockin_years": 5, "p_loss": 0.05})])
    paths = unlisted.simulate_paths(f, 0.10, 0.18, 26, 3000, seed=3)
    assert paths.shape == (3000, 27) and (paths[:, 0] == 1).all()
    np.testing.assert_allclose(unlisted.simulate(f, 0.10, 0.18, 26, 3000, seed=3), paths[:, -1] - 1)


# ---- leverage ----------------------------------------------------------------------

def test_no_borrowing_is_just_the_fund():
    r = np.array([0.02, -0.05, 0.03, -0.01])
    mp = leverage.margin_paths(r, 1.0, 0.10)
    np.testing.assert_allclose(mp.equity[0], np.concatenate([[1], np.cumprod(1 + r)]))
    assert mp.n_calls[0] == 0 and not mp.wiped[0]


def test_leverage_multiplies_a_small_move_and_charges_interest():
    mp = leverage.margin_paths(np.array([0.01]), 2.0, 0.052)
    # assets 2 * 1.01 = 2.02, debt 1 * 1.001 = 1.001
    assert mp.equity[0, 1] == pytest.approx(2.02 - 1.001)


def test_margin_call_restores_starting_share():
    # 2x, margin call below 25%: a 40% fall leaves A = 1.2, D = 1, E = 0.2 (16.7% of assets) -> sell
    mp = leverage.margin_paths(np.array([-0.40]), 2.0, 0.0, maintenance=0.25)
    E, A = mp.equity[0, 1], mp.assets[0, 1]
    assert E == pytest.approx(0.2)
    assert E / A == pytest.approx(0.5)
    assert mp.sold[0, 0] == pytest.approx(1.2 - 2 * 0.2)
    assert mp.n_calls[0] == 1 and not mp.wiped[0]


def test_a_big_enough_fall_wipes_you_out_and_stays_at_zero():
    mp = leverage.margin_paths(np.array([0.05, -0.30, 0.50]), 4.0, 0.0)
    assert mp.wiped[0] and mp.wiped_at[0] == 2
    assert mp.equity[0, 2] == 0 and mp.equity[0, 3] == 0
    assert mp.max_drawdown[0] == pytest.approx(-1.0)


def test_leverage_rejects_bad_inputs():
    with pytest.raises(ValueError):
        leverage.margin_paths(np.zeros(3), 0.5, 0.0)
    with pytest.raises(ValueError):
        leverage.margin_paths(np.zeros(3), 2.0, 0.0, maintenance=0.6)


def test_more_leverage_means_more_margin_calls_and_wipe_outs():
    rng = np.random.default_rng(42)
    weekly = rng.normal(0.08 / 52, 0.25 / np.sqrt(52), (5000, 52))
    calls = [leverage.summarise(leverage.margin_paths(weekly, L, 0.10)).p_call for L in (1.5, 2.0, 4.0)]
    assert calls[0] < calls[1] < calls[2]
    # wipe-outs need a single week that falls by more than the cushion: rare with normal shocks, not with fat tails
    mu, cov, w = _two_assets()
    fat = var.simulate_weekly(mu, cov * 2, w, 52, 20_000, "t", 3.0, seed=1)
    wiped = [leverage.summarise(leverage.margin_paths(fat, L, 0.10)).p_wiped for L in (1.0, 2.0, 4.0)]
    assert wiped[0] <= wiped[1] < wiped[2] and fat.min() >= -1


def test_history_frame_lines_up_with_returns():
    idx = pd.date_range("2024-01-05", periods=5, freq="W-FRI")
    r = pd.Series([0.01, -0.2, 0.05, -0.3, 0.1], index=idx)
    h = leverage.history(r, 3.0, 0.08)
    assert len(h) == 6 and h.index[1] == idx[0]
    assert h["unlevered"].iloc[-1] == pytest.approx(float(np.prod(1 + r)))
    assert (h["sold"] >= 0).all()


# ---- stress tests ------------------------------------------------------------------

def test_episodes_load_and_text_is_neutral():
    eps = stress.load_episodes()
    assert len(eps) >= 5
    assert {e.key for e in eps} >= {"gfc_2008", "nenegate_2015", "covid_2020", "rates_2022", "ai_2026"}
    for e in eps:
        assert e.start.dayofweek == 4 and e.end.dayofweek == 4  # Friday week-ends like the price data
        assert not ADVICE.search(e.what)


def test_episode_articles_exist():
    from fundlab import content
    lib = content.load_library()
    for e in stress.load_episodes():
        assert e.article is None or e.article in lib, e.article


def _frame():
    idx = pd.date_range("2018-01-05", periods=200, freq="W-FRI")
    rng = np.random.default_rng(5)
    f1 = rng.normal(0.002, 0.03, len(idx))
    f2 = rng.normal(0.002, 0.025, len(idx))
    fac = pd.DataFrame({"^J200.JO": 100 * np.cumprod(1 + f1), "SPY": 100 * np.cumprod(1 + f2)}, index=idx)
    a = 50 * np.cumprod(1 + 1.2 * f1 + 0.3 * f2 + rng.normal(0, 0.005, len(idx)))
    b = pd.Series(10 * np.cumprod(1 + rng.normal(0.001, 0.01, len(idx))), index=idx)
    late = pd.Series(0.5 * f1 + 0.8 * f2 + rng.normal(0, 0.004, len(idx)), index=idx)
    late_px = 20 * (1 + late).cumprod()
    late_px[:120] = np.nan  # lists after the episode
    return idx, fac, pd.DataFrame({"A": a, "B": b, "LATE": late_px}, index=idx)


def test_fit_proxy_recovers_betas():
    idx, fac, px = _frame()
    p = stress.fit_proxy(px["A"].pct_change(), fac.pct_change())
    assert p.betas["^J200.JO"] == pytest.approx(1.2, abs=0.05)
    assert p.betas["SPY"] == pytest.approx(0.3, abs=0.05)
    assert p.r2 > 0.9


def test_replay_is_buy_and_hold_when_everything_is_measured():
    idx, fac, px = _frame()
    ep = stress.Episode("x", "X", idx[20], idx[40], "test")
    w = pd.Series({"A": 0.7, "B": 0.3})
    r = stress.replay(w, px, fac, ep)
    exp = 0.7 * px["A"][idx[40]] / px["A"][idx[20]] + 0.3 * px["B"][idx[40]] / px["B"][idx[20]] - 1
    assert r.fund_return == pytest.approx(exp)
    assert r.measured_share == pytest.approx(1.0)
    assert r.worst <= min(r.fund_return, 0) + 1e-12
    assert r.benchmarks.iloc[0].eq(1).all()


def test_replay_estimates_a_holding_that_listed_later():
    idx, fac, px = _frame()
    ep = stress.Episode("x", "X", idx[30], idx[50], "test")
    r = stress.replay(pd.Series({"A": 0.5, "LATE": 0.5}), px, fac, ep)
    assert r.by_holding.loc["LATE", "method"] == "Estimated"
    assert r.measured_share == pytest.approx(0.5)
    f = fac.loc[idx[30]:idx[50]].pct_change().iloc[1:]
    p = stress.fit_proxy(px["LATE"].pct_change(), fac.pct_change())
    exp = float(np.prod(1 + f @ p.betas) - 1)
    assert r.by_holding.loc["LATE", "return"] == pytest.approx(exp)


def test_one_week_episode_works():
    idx, fac, px = _frame()
    r = stress.replay(pd.Series({"A": 1.0}), px, fac, stress.Episode("w", "W", idx[60], idx[61], "one week"))
    assert r.fund_return == pytest.approx(px["A"][idx[61]] / px["A"][idx[60]] - 1)


def test_replay_none_before_factor_data():
    idx, fac, px = _frame()
    ep = stress.Episode("old", "Old", pd.Timestamp("2008-05-16"), pd.Timestamp("2008-11-21"), "before the data")
    assert stress.replay(pd.Series({"A": 1.0}), px, fac, ep) is None


def test_whole_fund_return_moves_unlisted_with_listed():
    f = Fund("U", [Holding("STX40.JO", "S", "jse_etf", 8000),
                   Holding("UNL:x", "X", "unlisted", 2000, method="assumptions",
                           params={"exp_return": 0.1, "low": 0.0, "high": 0.2, "lockin_years": 1, "p_loss": 0.0,
                                   "corr": 0.5})])
    a = unlisted.assumptions_of(f.holdings[1])
    beta = 0.5 * a.total_vol / 0.2
    assert stress.whole_fund_return(f, -0.3, 0.2) == pytest.approx(0.8 * -0.3 + 0.2 * beta * -0.3)
    plain = Fund("P", [Holding("STX40.JO", "S", "jse_etf", 1000)])
    assert stress.whole_fund_return(plain, -0.3, 0.2) == -0.3
