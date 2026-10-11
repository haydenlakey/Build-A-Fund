"""Unlisted holdings: stated assumptions, whole-fund maths, simulation and illiquidity."""
import numpy as np
import pytest

from fundlab import unlisted
from fundlab.model import Fund, Holding
from fundlab.unlisted import Assumptions


def ul(ticker, amount, **kw):
    return Holding(ticker, ticker, "unlisted", amount, method="assumptions", params=kw)


def test_derived_quantities():
    a = Assumptions(exp_return=0.15, low=-0.1, high=0.4, lockin_years=5, p_loss=0.05)
    assert a.vol_if_survives == pytest.approx(0.5 / (2 * 1.645))
    assert a.expected_return == pytest.approx(0.95 * 1.15 - 1)
    # brute-force variance of the mixture
    rng = np.random.default_rng(1)
    n = 2_000_000
    r = np.where(rng.random(n) < 0.05, -1.0, 0.15 + a.vol_if_survives * rng.standard_normal(n))
    assert a.total_vol == pytest.approx(r.std(), rel=0.01)
    assert a.p_lost_over(5) == pytest.approx(1 - 0.95 ** 5)


@pytest.mark.parametrize("kw", [dict(exp_return=0.5, low=0.0, high=0.3), dict(p_loss=1.0), dict(corr=1.5),
                                dict(low=-1.2), dict(lockin_years=-1)])
def test_invalid_assumptions_are_rejected(kw):
    with pytest.raises(ValueError):
        Assumptions.from_params(kw)


def test_whole_fund_one_factor_maths():
    f = Fund("F", [Holding("STX40.JO", "S", "jse_etf", 600), ul("UL:a", 300, corr=0.5), ul("UL:b", 100, corr=0.2)])
    wf = unlisted.whole_fund(f, listed_mu=0.10, listed_vol=0.18)
    a, b = Assumptions.from_params({"corr": 0.5}), Assumptions.from_params({"corr": 0.2})
    assert list(wf.weights) == pytest.approx([0.6, 0.3, 0.1])
    assert wf.exp_return == pytest.approx(0.6 * 0.10 + 0.3 * a.expected_return + 0.1 * b.expected_return)
    assert wf.cov.loc["Listed", "UL:a"] == pytest.approx(0.5 * a.total_vol * 0.18)
    assert wf.cov.loc["UL:a", "UL:b"] == pytest.approx(0.5 * 0.2 * a.total_vol * b.total_vol)
    assert np.linalg.eigvalsh(wf.cov.to_numpy()).min() > -1e-12
    assert wf.listed_share == pytest.approx(0.6)


def test_whole_fund_without_unlisted_is_the_listed_sleeve():
    f = Fund("F", [Holding("STX40.JO", "S", "jse_etf", 600)])
    wf = unlisted.whole_fund(f, 0.1, 0.2)
    assert wf.exp_return == pytest.approx(0.1) and wf.vol == pytest.approx(0.2)
    assert unlisted.whole_fund(f, float("nan"), float("nan")) is None


def test_simulation_matches_the_assumptions():
    f = Fund("F", [ul("UL:a", 100, exp_return=0.12, low=-0.05, high=0.29, p_loss=0.0)])
    sims = unlisted.simulate(f, 0.0, 0.0, 52, n_sims=40_000, seed=3)
    a = Assumptions.from_params({"exp_return": 0.12, "low": -0.05, "high": 0.29, "p_loss": 0.0})
    assert sims.mean() == pytest.approx(0.12, abs=0.004)
    assert sims.std() == pytest.approx(a.vol_if_survives, rel=0.05)


def test_simulated_total_loss_frequency_matches_p():
    f = Fund("F", [ul("UL:a", 100, p_loss=0.1)])
    sims = unlisted.simulate(f, 0.0, 0.0, 104, n_sims=40_000, seed=7)
    assert (sims == -1.0).mean() == pytest.approx(1 - 0.9 ** 2, abs=0.01)


def test_simulation_is_reproducible_with_the_seed_and_mixes_the_sleeves():
    f = Fund("F", [Holding("STX40.JO", "S", "jse_etf", 500), ul("UL:a", 500, p_loss=0.0)])
    a = unlisted.simulate(f, 0.1, 0.2, 26, n_sims=5000, seed=42)
    b = unlisted.simulate(f, 0.1, 0.2, 26, n_sims=5000, seed=42)
    assert np.array_equal(a, b)
    assert a.mean() == pytest.approx(0.5 * 0.05 + 0.5 * (1.12 ** 0.5 - 1), abs=0.01)


def test_liquidity_ladder_and_illiquid_share():
    f = Fund("F", [Holding("STX40.JO", "S", "jse_etf", 500), ul("UL:a", 200, lockin_years=0),
                   ul("UL:b", 200, lockin_years=3), ul("UL:c", 100, lockin_years=10)])
    lad = unlisted.liquidity_ladder(f)
    assert lad.tolist() == [700, 0, 200, 100]
    assert unlisted.illiquid_share(f) == pytest.approx(0.5)


@pytest.mark.parametrize("kw, fires", [
    (dict(exp_return=0.6, low=0.58, high=0.62, p_loss=0.0, lockin_years=1), 3),
    (dict(exp_return=0.25), 2),  # high return + 5-year default lock-in
    (dict(exp_return=0.10, lockin_years=2), 0),
])
def test_warnings_fire_and_stay_quiet(kw, fires):
    assert len(Assumptions.from_params(kw).warnings()) == fires
