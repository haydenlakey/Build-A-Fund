import numpy as np
import pandas as pd
import pytest

from fundlab import active, estimators, frontier, model, risk, var


@pytest.fixture(scope="module")
def returns():
    """Ten years of weekly returns for five assets with unequal correlations."""
    rng = np.random.default_rng(0)
    vols = np.array([0.03, 0.025, 0.04, 0.02, 0.035])
    corr = np.array([
        [1.0, 0.8, 0.3, 0.1, 0.5],
        [0.8, 1.0, 0.2, 0.0, 0.4],
        [0.3, 0.2, 1.0, -0.2, 0.6],
        [0.1, 0.0, -0.2, 1.0, 0.1],
        [0.5, 0.4, 0.6, 0.1, 1.0],
    ])
    cov = corr * np.outer(vols, vols)
    x = rng.multivariate_normal([0.002, 0.0015, 0.003, 0.001, 0.0025], cov, 520)
    return pd.DataFrame(x, columns=list("ABCDE"))


@pytest.fixture
def weights():
    return pd.Series([0.4, 0.3, 0.2, 0.1, 0.0], index=list("ABCDE"))


# ---- model ------------------------------------------------------------------

def make_fund():
    return model.Fund("Test", [
        model.Holding("A", "A", "jse_share", 1000.5),
        model.Holding("B", "B", "us_share", 2500, "USD"),
        model.Holding("C", "C", "jse_etf", 333.33),
    ])


def test_weights_sum_to_one_with_fractional_amounts():
    w = make_fund().weights()
    assert w.sum() == pytest.approx(1.0, abs=1e-12)
    assert w["B"] == pytest.approx(2500 / (1000.5 + 2500 + 333.33))


def test_duplicate_tickers_merge():
    f = make_fund()
    f.holdings.append(model.Holding("A", "A", "jse_share", 999.5))
    assert f.amounts()["A"] == pytest.approx(2000.0)
    assert f.weights().sum() == pytest.approx(1.0)


def test_edits_return_new_fund_and_zero_removes():
    f = make_fund()
    g = f.with_amount("A", 0)
    assert "A" not in g.weights().index
    assert "A" in f.weights().index  # original untouched
    assert f.with_amount("A", 50).amounts()["A"] == 50
    assert "D" in f.with_amount("D", 10, kind="us_share", currency="USD").weights().index


def test_negative_amount_rejected():
    with pytest.raises(ValueError):
        model.Holding("A", "A", "jse_share", -1)


def test_json_and_share_code_round_trip():
    f = make_fund()
    assert model.Fund.from_json(f.to_json()).to_dict() == f.to_dict()
    assert model.Fund.from_share_code(f.to_share_code()).to_dict() == f.to_dict()


def test_copy_gets_new_id():
    f = make_fund()
    assert f.copy().id != f.id
    assert f.copy(keep_id=True).id == f.id


# ---- estimators ---------------------------------------------------------------

def test_mean_shrinkage_preserves_average_and_bounds(returns):
    raw = estimators.mean_returns(returns)
    shrunk = estimators.mean_returns(returns, 0.5)
    assert shrunk.mean() == pytest.approx(raw.mean())
    assert shrunk.std() == pytest.approx(raw.std() * 0.5)
    assert np.allclose(estimators.mean_returns(returns, 1.0), raw.mean())
    with pytest.raises(ValueError):
        estimators.mean_returns(returns, 1.5)


def test_sample_cov_annualised(returns):
    assert np.allclose(estimators.sample_cov(returns), returns.cov() * 52)


@pytest.mark.parametrize("method", ["sample", "ledoit_wolf", "ewma"])
def test_covariances_are_symmetric_psd(returns, method):
    c = estimators.covariance(returns, method).to_numpy()
    assert np.allclose(c, c.T)
    assert np.linalg.eigvalsh(c).min() > 0


def test_ledoit_wolf_shrinks_partially_when_target_is_wrong(returns):
    cov, delta = estimators.ledoit_wolf_cov(returns)
    assert 0.0 < delta < 0.5
    # variances are untouched by the constant-correlation target (up to n/(n-1))
    assert np.allclose(np.diag(cov), (returns.var(ddof=1) * 52).to_numpy())


def test_ledoit_wolf_shrinks_more_with_few_observations(returns):
    _, d_full = estimators.ledoit_wolf_cov(returns)
    _, d_short = estimators.ledoit_wolf_cov(returns.iloc[:30])
    assert d_short > d_full


def test_ewma_with_lambda_near_one_approaches_sample(returns):
    e = estimators.ewma_cov(returns, lam=0.999999)
    assert np.allclose(e, estimators.sample_cov(returns), rtol=1e-3)


# ---- risk -----------------------------------------------------------------------

def test_risk_contributions_sum_to_total_risk(returns, weights):
    cov = estimators.covariance(returns)
    rc = risk.risk_contributions(weights, cov)
    assert rc.sum() == pytest.approx(risk.portfolio_vol(weights, cov), rel=1e-12)
    assert risk.risk_shares(weights, cov).sum() == pytest.approx(1.0)
    assert rc["E"] == 0.0


def test_vol_ignores_column_order(returns, weights):
    cov = estimators.covariance(returns)
    shuffled = cov.loc[list("EDCBA"), list("EDCBA")]
    assert risk.portfolio_vol(weights, shuffled) == pytest.approx(risk.portfolio_vol(weights, cov))


def test_diversification_measures(returns, weights):
    cov = estimators.covariance(returns)
    assert risk.diversification_ratio(weights, cov) >= 1.0
    assert risk.effective_holdings(pd.Series([0.25] * 4)) == pytest.approx(4.0)
    assert risk.effective_holdings(pd.Series([1.0])) == pytest.approx(1.0)


def test_max_drawdown_known_path():
    r = pd.Series([0.10, -0.50, 0.20, 0.50])  # 1.1 -> 0.55 -> 0.66 -> 0.99
    assert risk.max_drawdown(r) == pytest.approx(-0.5)


def test_average_correlation_of_identical_assets():
    c = pd.DataFrame(0.04, index=list("AB"), columns=list("AB"))
    assert risk.average_correlation(pd.Series([0.5, 0.5], index=list("AB")), c) == pytest.approx(1.0)


# ---- VaR -------------------------------------------------------------------------

def _one_asset(mu=0.08, vol=0.18):
    return (pd.Series(mu, index=["X"]), pd.DataFrame([[vol**2]], index=["X"], columns=["X"]),
            pd.Series([1.0], index=["X"]))


def test_mc_var_converges_to_parametric_normal():
    mu, cov, w = _one_asset()
    p_var, p_es = var.parametric_var_es(0.08, 0.18, 1, 0.95)
    sims = var.simulate_paths(mu, cov, w, h_weeks=1, n_sims=400_000, seed=1)
    m_var, m_es = var.mc_var_es(sims, 0.95)
    assert m_var == pytest.approx(p_var, rel=0.01)
    assert m_es == pytest.approx(p_es, rel=0.01)


def test_mc_var_converges_to_parametric_t():
    mu, cov, w = _one_asset()
    p_var, p_es = var.parametric_var_es(0.08, 0.18, 1, 0.99, dist="t", df=5)
    sims = var.simulate_paths(mu, cov, w, 1, 400_000, dist="t", df=5, seed=2)
    m_var, m_es = var.mc_var_es(sims, 0.99)
    assert m_var == pytest.approx(p_var, rel=0.02)
    assert m_es == pytest.approx(p_es, rel=0.03)


def test_multi_asset_mc_matches_parametric(returns, weights):
    mu = estimators.mean_returns(returns)
    cov = estimators.covariance(returns)
    p_var, _ = var.parametric_var_es(risk.portfolio_return(weights, mu), risk.portfolio_vol(weights, cov), 1)
    m_var, _ = var.mc_var_es(var.simulate_paths(mu, cov, weights, 1, 300_000, seed=3))
    assert m_var == pytest.approx(p_var, rel=0.015)


def test_mc_is_reproducible_with_seed():
    mu, cov, w = _one_asset()
    a = var.simulate_paths(mu, cov, w, 4, 1000, seed=7)
    b = var.simulate_paths(mu, cov, w, 4, 1000, seed=7)
    assert np.array_equal(a, b)


def test_t_tails_fatter_than_normal_at_99():
    n_var, n_es = var.parametric_var_es(0.08, 0.18, 4, 0.99)
    t_var, t_es = var.parametric_var_es(0.08, 0.18, 4, 0.99, dist="t", df=4)
    assert t_var > n_var and t_es > n_es


def test_es_exceeds_var(returns, weights):
    pr = risk.portfolio_returns(weights, returns)
    h_var, h_es = var.historical_var_es(pr, 4)
    assert h_es >= h_var > 0


# ---- frontier --------------------------------------------------------------------

def test_frontier_is_efficient_and_long_only(returns, weights):
    mu = estimators.mean_returns(returns)
    cov = estimators.covariance(returns)
    fr = frontier.efficient_frontier(mu, cov, 15)
    assert len(fr.rets) >= 10
    assert np.all(np.diff(fr.rets) >= -1e-10)
    assert np.all(np.diff(fr.vols) >= -1e-6)  # upper branch: more return costs more risk
    for w in fr.weights:
        assert w.min() >= -1e-9 and w.sum() == pytest.approx(1.0)
    r, v = risk.portfolio_return(weights, mu), risk.portfolio_vol(weights, cov)
    assert frontier.efficiency_gap(r, v, fr) >= 0
    assert frontier.efficiency_gap(fr.rets[3], fr.vols[3], fr) == pytest.approx(0, abs=1e-6)


# ---- active bets ---------------------------------------------------------------

def test_pairwise_bet_spec_example():
    """Spec: TE 1%, vols 21% and 8%, correlation -0.01 -> bet ~4.4%, shares ~87% / 13%."""
    b = active.pairwise_bet(0.01, 0.21, 0.08, -0.01)
    assert b["bet_size"] == pytest.approx(0.0443, abs=5e-4)
    assert b["share_long"] == pytest.approx(0.87, abs=0.005)
    assert b["share_short"] == pytest.approx(0.13, abs=0.005)
    assert b["share_long"] + b["share_short"] == pytest.approx(1.0)


def test_te_budget_matches_pairwise_and_te_hits_target():
    b = active.pairwise_bet(0.01, 0.21, 0.08, -0.01)
    a = pd.Series([b["bet_size"], -b["bet_size"]], index=["A", "B"])
    cross = -0.01 * 0.21 * 0.08
    cov = pd.DataFrame([[0.21**2, cross], [cross, 0.08**2]], index=["A", "B"], columns=["A", "B"])
    assert active.tracking_error(a, cov) == pytest.approx(0.01)
    assert np.allclose(active.te_budget(a, cov), [b["share_long"], b["share_short"]])


def test_rule_of_thumb_exact_for_equal_vol_equal_corr():
    s, r = 0.2, 0.4
    cov = pd.DataFrame(s**2 * (r + (1 - r) * np.eye(4)), index=list("ABCD"), columns=list("ABCD"))
    a = pd.Series([0.03, -0.01, -0.01, -0.01], index=list("ABCD"))
    assert active.te_rule_of_thumb(a, s, r) == pytest.approx(active.tracking_error(a, cov))


def test_active_weights_union_of_indexes():
    a = active.active_weights(pd.Series({"A": 0.6, "B": 0.4}), pd.Series({"B": 0.5, "C": 0.5}))
    assert a.to_dict() == pytest.approx({"A": 0.6, "B": -0.1, "C": -0.5})
    assert a.sum() == pytest.approx(0.0)
