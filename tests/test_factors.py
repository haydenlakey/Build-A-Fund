"""Factor betas (OLS with Newey-West errors) and correlation clustering."""
import numpy as np
import pandas as pd
import pytest

from fundlab.factors import cluster, correlation, joint_betas, newey_west_lags, ols_hac, single_betas


def test_newey_west_lag_rule():
    assert newey_west_lags(100) == 4
    assert newey_west_lags(260) == 4
    assert newey_west_lags(1000) == 6


def test_ols_coefficients_match_least_squares():
    rng = np.random.default_rng(42)
    X = np.column_stack([np.ones(300), rng.normal(size=(300, 2))])
    y = X @ [0.1, 0.8, -0.3] + rng.normal(scale=0.5, size=300)
    res = ols_hac(y, X)
    np.testing.assert_allclose(res.coef, np.linalg.lstsq(X, y, rcond=None)[0])
    assert 0 < res.r2 < 1


def test_hac_with_no_lags_is_white_hc1():
    rng = np.random.default_rng(1)
    n = 200
    X = np.column_stack([np.ones(n), rng.normal(size=n)])
    y = X @ [0.0, 1.0] + rng.normal(size=n) * (1 + np.abs(X[:, 1]))  # heteroskedastic
    res = ols_hac(y, X, lags=0)
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ b
    inv = np.linalg.inv(X.T @ X)
    hc1 = inv @ (X.T * u**2) @ X @ inv * n / (n - 2)
    np.testing.assert_allclose(res.se, np.sqrt(np.diag(hc1)))


@pytest.mark.parametrize("phi", [0.0, 0.5])
def test_confidence_interval_coverage(phi):
    """95% intervals should contain the true beta about 95% of the time, also with AR(1) errors and regressor."""
    rng = np.random.default_rng(7)
    n, sims, true_b, hits = 260, 400, 1.5, 0
    for _ in range(sims):
        e, x = rng.normal(size=n), rng.normal(size=n)
        for t in range(1, n):  # autocorrelated regressor and errors make plain OLS errors too small
            e[t] += phi * e[t - 1]
            x[t] += phi * x[t - 1]
        y = 0.002 + true_b * x + e
        res = ols_hac(y, np.column_stack([np.ones(n), x]))
        lo, hi = res.ci(0.95)
        hits += lo[1] <= true_b <= hi[1]
    assert 0.90 <= hits / sims <= 0.985


def test_single_betas_recover_exact_relationship():
    rng = np.random.default_rng(3)
    idx = pd.date_range("2020-01-03", periods=156, freq="W-FRI")
    fac = pd.DataFrame({"top40": rng.normal(0, 0.02, 156), "usdzar": rng.normal(0, 0.015, 156)}, index=idx)
    port = 0.001 + 2.0 * fac["top40"]
    betas = {b.key: b for b in single_betas(port, fac)}
    assert betas["top40"].beta == pytest.approx(2.0)
    assert betas["top40"].r2 == pytest.approx(1.0)
    assert betas["top40"].significant
    assert betas["usdzar"].lo < 0 < betas["usdzar"].hi or abs(betas["usdzar"].beta) < 0.5
    table, r2, n = joint_betas(port, fac)
    assert table.loc["top40", "beta"] == pytest.approx(2.0) and n == 156


def test_single_betas_need_a_year_of_overlap():
    idx = pd.date_range("2020-01-03", periods=40, freq="W-FRI")
    fac = pd.DataFrame({"gold": np.linspace(-0.01, 0.01, 40)}, index=idx)
    assert single_betas(fac["gold"] * 2, fac) == []


def test_cluster_finds_blocks_and_keeps_them_adjacent():
    rng = np.random.default_rng(5)
    a, b = rng.normal(size=500), rng.normal(size=500)
    rets = pd.DataFrame({
        "A1": a + 0.2 * rng.normal(size=500), "B1": b + 0.2 * rng.normal(size=500),
        "A2": a + 0.2 * rng.normal(size=500), "C": rng.normal(size=500),
        "B2": b + 0.2 * rng.normal(size=500), "A3": a + 0.2 * rng.normal(size=500),
    })
    cl = cluster(correlation(rets.cov()))
    groups = sorted(sorted(g) for g in cl.groups)
    assert groups == [["A1", "A2", "A3"], ["B1", "B2"]]
    pos = [cl.order.index(t) for t in ["A1", "A2", "A3"]]
    assert max(pos) - min(pos) == 2  # contiguous
    assert list(cl.corr.index) == cl.order


def test_correlation_has_unit_diagonal():
    cov = pd.DataFrame([[0.04, 0.01], [0.01, 0.09]], index=["x", "y"], columns=["x", "y"])
    c = correlation(cov)
    assert np.allclose(np.diag(c), 1) and c.loc["x", "y"] == pytest.approx(0.01 / 0.06)
