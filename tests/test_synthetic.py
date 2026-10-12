"""Unit trusts without Yahoo prices: uploaded price files, allocation models, and the v2 data model."""
import json

import numpy as np
import pandas as pd
import pytest

from fundlab import PERIODS_PER_YEAR, analysis, synthetic
from fundlab.model import Fund, FundSettings, Holding

FRIDAYS = pd.date_range("2020-01-03", periods=200, freq="W-FRI")


def proxies(seed=0):
    rng = np.random.default_rng(seed)
    r = pd.DataFrame(rng.normal(0.002, 0.02, (len(FRIDAYS), 3)), index=FRIDAYS, columns=["STX40.JO", "STXGOV.JO", "VT"])
    return 100 * (1 + r).cumprod()


def test_allocation_model_is_the_weighted_proxy_return_less_fees():
    px = proxies()
    alloc = {"sa_equity": 0.6, "sa_bonds": 0.3, "sa_cash": 0.1}
    s = synthetic.allocation_prices(alloc, ter=0.0104, proxies=px, risk_free=0.07)
    r = s.pct_change().dropna()
    pr = px.pct_change().dropna()
    expect = 0.6 * pr["STX40.JO"] + 0.3 * pr["STXGOV.JO"] + 0.1 * 0.07 / PERIODS_PER_YEAR - 0.0104 / PERIODS_PER_YEAR
    pd.testing.assert_series_equal(r, expect, check_names=False, check_freq=False, atol=1e-12)
    assert s.iloc[0] == 100


def test_allocation_is_normalised_and_waits_for_the_latest_proxy():
    px = proxies()
    px.loc[:FRIDAYS[49], "VT"] = np.nan
    s = synthetic.allocation_prices({"sa_equity": 49.95, "global_equity": 49.95}, 0.0, px, 0.07)
    assert s.index[0] == FRIDAYS[50]
    assert synthetic.normalise_allocation({"sa_equity": 60, "sa_bonds": 39.9, "bogus": 5}) == pytest.approx(
        {"sa_equity": 60 / 99.9, "sa_bonds": 39.9 / 99.9})
    with pytest.raises(ValueError):
        synthetic.normalise_allocation({"sa_equity": 0})
    assert synthetic.normalise_allocation({"sa_bonds": 115, "sa_cash": -15}) == pytest.approx({"sa_bonds": 1.15, "sa_cash": -0.15})


def test_cash_only_fund_grows_at_the_risk_free_rate_less_fees():
    s = synthetic.allocation_prices({"sa_cash": 1.0}, 0.005, proxies(), 0.07)
    assert s.pct_change().dropna().std() < 1e-12
    assert s.pct_change().dropna().iloc[0] == pytest.approx((0.07 - 0.005) / 52)


def test_short_bonds_earn_cash_plus_a_quarter_of_the_bond_excess_return():
    px = proxies()
    s = synthetic.allocation_prices({"sa_short_bonds": 1.0}, 0.0, px, 0.07)
    r = s.pct_change().dropna()
    rf = 0.07 / PERIODS_PER_YEAR
    expect = rf + 0.25 * (px["STXGOV.JO"].pct_change().dropna() - rf)
    pd.testing.assert_series_equal(r, expect, check_names=False, check_freq=False, atol=1e-12)
    assert r.std() == pytest.approx(0.25 * px["STXGOV.JO"].pct_change().std())
    both = {"sa_short_bonds": 50, "sa_bonds": 50}
    assert synthetic.proxy_tickers(both) == ["STXGOV.JO"]
    assert synthetic.allocation_prices(both, 0.0, px, 0.07).index[0] == FRIDAYS[0]


@pytest.mark.parametrize("text", ids=["iso-daily", "dayfirst-semicolon-decimal-comma", "weekly-rand-thousands"], argvalues=[
    "Date,Price\n" + "\n".join(f"{d:%Y-%m-%d},{100 + i}" for i, d in enumerate(pd.date_range("2022-01-03", periods=400))),
    "\n".join(f"{d:%d/%m/%Y};{1000 + i},5" for i, d in enumerate(pd.date_range("2022-01-03", periods=400))),
    "\n".join(f"{d:%Y-%m-%d},\"R 1,{100 + i % 900:03d}.50\"" for i, d in enumerate(pd.date_range("2022-01-07", periods=60, freq="W-FRI"))),
])
def test_price_file_formats(text):
    s = synthetic.parse_price_file(text.encode())
    assert len(s) >= synthetic.MIN_UPLOAD_WEEKS
    assert (s.index.dayofweek == 4).all() and s.is_monotonic_increasing is not None
    assert (s > 0).all()


@pytest.mark.parametrize("text, why", ids=["one-col", "no-dates", "short", "monthly", "negative"], argvalues=[
    ("just one column\n1\n2\n", "two columns"),
    ("a,b\nx,y\nz,w\n", "dates"),
    ("\n".join(f"{d:%Y-%m-%d},{i}" for i, d in enumerate(pd.date_range("2024-01-01", periods=30), 1)), "weeks"),
    ("\n".join(f"{d:%Y-%m-%d},{i}" for i, d in enumerate(pd.date_range("2018-01-31", periods=80, freq="ME"), 1)), "monthly"),
    ("\n".join(f"{d:%Y-%m-%d},{i - 5}" for i, d in enumerate(pd.date_range("2024-01-01", periods=400))), "above zero"),
])
def test_price_file_errors_are_explained(text, why):
    with pytest.raises(ValueError, match=why):
        synthetic.parse_price_file(text)


def test_uploaded_and_modelled_holdings_flow_through_the_statistics():
    px = proxies()
    up = synthetic.parse_price_file("\n".join(f"{d:%Y-%m-%d},{v}" for d, v in (px["VT"] * 3).items()))
    fund = Fund("UT", [
        Holding("STX40.JO", "Satrix 40", "jse_etf", 1000),
        Holding("UT:up", "My uploaded fund", "unit_trust", 1000, method="uploaded",
                params={"prices": synthetic.series_to_params(up)}),
        Holding("UT:bal", "A balanced fund", "unit_trust", 1000, method="allocation_model",
                params={"allocation": {"sa_equity": 0.6, "sa_bonds": 0.4}, "ter": 0.01}),
    ])
    assert synthetic.needed_tickers([fund]) == ["STX40.JO", "STXGOV.JO"]
    frame = synthetic.price_frame([fund], lambda ts: px[[t for t in ts if t in px.columns]], 0.07)
    assert {"STX40.JO", "UT:up", "UT:bal"} <= set(frame.columns)
    cmp = analysis.compare(fund, fund, frame, FundSettings(lookback_years=None))
    assert set(cmp.after.weights.index) == {"STX40.JO", "UT:up", "UT:bal"}
    assert cmp.after.risk_shares.sum() == pytest.approx(1.0)


def test_unlisted_holding_gets_no_price_column_and_a_clear_reason():
    px = proxies()
    fund = Fund("U", [Holding("STX40.JO", "Satrix 40", "jse_etf", 1000),
                      Holding("UL:farm", "A farm", "unlisted", 500, method="assumptions", params={})])
    frame = synthetic.price_frame([fund], lambda ts: px[[t for t in ts if t in px.columns]], 0.07)
    assert "UL:farm" not in frame.columns
    st = analysis.compare(fund, fund, frame, FundSettings(lookback_years=None)).after
    assert st.coverage == pytest.approx(1000 / 1500)
    assert st.excluded["UL:farm"] == analysis.UNLISTED_REASON


def test_model_v2_round_trip_and_v1_files_still_load():
    f = Fund("F", [Holding("UL:x", "X", "unlisted", 10, method="assumptions", params={"exp_return": 0.1}),
                   Holding("UT:y", "Y", "unit_trust", 5, method="allocation_model", params={"allocation": {"sa_cash": 1}})])
    g = Fund.from_share_code(f.to_share_code())
    assert g.holdings[0].params == {"exp_return": 0.1} and g.holdings[1].method == "allocation_model"
    v1 = {"name": "Old", "schema_version": 1, "holdings": [
        {"ticker": "NPN.JO", "name": "Naspers", "kind": "jse_share", "amount_zar": 5, "currency": "ZAR",
         "method": "price_history"}]}
    old = Fund.from_json(json.dumps(v1))
    assert old.holdings[0].params == {}
    with pytest.raises(ValueError):
        Holding("UL:z", "Z", "unlisted", 1)  # unlisted needs the assumptions method
    with pytest.raises(ValueError):
        Holding("NPN.JO", "N", "jse_share", 1, method="assumptions")


def test_with_amount_keeps_or_replaces_params():
    f = Fund("F").with_amount("UL:x", 100, name="X", kind="unlisted", method="assumptions", params={"p_loss": 0.1})
    assert f.holding("UL:x").params == {"p_loss": 0.1}
    g = f.with_amount("UL:x", 200)
    assert g.holding("UL:x").params == {"p_loss": 0.1} and g.holding("UL:x").amount_zar == 200
    h = f.with_amount("UL:x", 200, params={"p_loss": 0.2})
    assert h.holding("UL:x").params == {"p_loss": 0.2} and f.holding("UL:x").params == {"p_loss": 0.1}
