"""Curated unit trusts: the data file is complete and sourced, and look-through and price fetching work."""
import re

import pandas as pd
import pytest

from fundlab import data, lookthrough, synthetic, unit_trusts
from fundlab.model import Fund, Holding

UTS = unit_trusts.load_unit_trusts()
UNI = data.load_universe()


def test_every_risk_level_has_six_to_eight_funds():
    counts = {r: len(UTS.by_risk(r)) for r in unit_trusts.RISK_ORDER}
    assert all(6 <= n <= 8 for n in counts.values()), counts
    assert set(UTS.levels) == set(unit_trusts.RISK_ORDER)


@pytest.mark.parametrize("ticker", sorted(UTS.funds))
def test_fund_entry_is_complete_and_sourced(ticker):
    f = UTS.get(ticker)
    assert re.fullmatch(r"UT:ZAE\d{9}", f.ticker), f.ticker
    assert f.name and f.manager and f.asisa and f.risk_label and f.benchmark
    assert 0 < f.ter < 0.03 and (f.tc is None or 0 <= f.tc < 0.02)
    assert f.method in ("price_history", "allocation_model")
    assert f.sheet["url"].startswith("https://") and f.sheet["host"] in ("manager", "discovery", "momentum", "easyequities")
    assert re.fullmatch(r"20\d\d-\d\d-\d\d", f.sheet["as_of"])
    assert re.fullmatch(r"20\d\d-\d\d-\d\d", f.sheet.get("accessed", "2026-01-01"))
    assert set(f.allocation) <= set(synthetic.ASSET_CLASSES)
    assert sum(f.allocation.values()) == pytest.approx(100, abs=1.0)
    for t, name, pct in f.holdings:
        assert t is None or t in UNI.entries, f"{t} ({name}) is not in universe.yaml"
        assert 0 < pct < 100


def test_income_funds_default_to_the_allocation_model():
    for f in UTS.by_risk("low") + UTS.by_risk("low_medium"):
        assert f.method == "allocation_model", f.code


def test_short_dated_bonds_use_the_short_bond_class():
    for code, short in (("SIAB4", 34.65), ("SEYB1", 38.40)):
        f = next(f for f in UTS.funds.values() if f.code == code)
        assert f.allocation["sa_short_bonds"] == pytest.approx(short), code
        p = lookthrough.allocation_profile(f.ticker, f.allocation)
        assert p.sectors.set_index("sector").loc["Short-term bonds", "frac"] == pytest.approx(short / 100, abs=1e-3)


def test_short_bond_class_lowers_a_bond_funds_modelled_volatility():
    f = next(f for f in UTS.funds.values() if f.code == "SEYB1")
    px = data.PriceStore(allow_live=False).prices_zar(synthetic.proxy_tickers(f.allocation))
    old = {**f.allocation, "sa_bonds": f.allocation["sa_bonds"] + f.allocation["sa_short_bonds"], "sa_short_bonds": 0}
    vol = {k: synthetic.allocation_prices(a, f.ter, px, 0.07).pct_change().std()
           for k, a in (("new", f.allocation), ("old", old))}
    assert vol["new"] < 0.8 * vol["old"]


def test_every_proxy_is_in_the_bundled_prices():
    store = data.PriceStore(allow_live=False)
    for f in UTS.funds.values():
        for t in synthetic.proxy_tickers(f.allocation):
            assert store.has(t), (f.code, t)


@pytest.mark.parametrize("ticker", sorted(UTS.funds))
def test_allocation_profile_sums_to_one(ticker):
    f = UTS.get(ticker)
    p = lookthrough.allocation_profile(f.ticker, f.allocation, f.holdings, UNI.entries, f.ter, f.tc or 0)
    assert p.sectors["frac"].sum() == pytest.approx(1)
    for s in (p.countries, p.currencies, p.earnings):
        assert s.sum() == pytest.approx(1) and (s >= 0).all()


def test_unit_trust_overlap_and_unlisted_in_composition():
    ag = UTS.get("UT:ZAE000177341")  # Allan Gray Equity: AB InBev 5.5%
    fund = Fund("F", [Holding("ANH.JO", "AB InBev", "jse_share", 500),
                      Holding(ag.ticker, ag.name, "unit_trust", 1000, method="price_history", params=ag.params()),
                      Holding("UL:farm", "A farm", "unlisted", 500, method="assumptions", params={"category": "Other"})])
    extra = unit_trusts.extra_profiles(fund, UNI.entries, UTS)
    c = lookthrough.compose(fund.weights(), UNI.entries, lookthrough.load_lookthrough(), extra=extra)
    row = c.companies.set_index("key").loc["ANH.JO"]
    assert row["direct"] == pytest.approx(0.25) and row["via_funds"] == pytest.approx(0.5 * 0.055)
    assert c.by_asset["unlisted"] == pytest.approx(0.25)
    assert c.weighted_ter == pytest.approx(0.5 * ag.ter)


def test_custom_unit_trust_params_drive_its_profile():
    fund = Fund("F", [Holding("UT:custom-x", "X", "unit_trust", 100, method="allocation_model",
                              params={"allocation": {"sa_equity": 60, "global_bonds": 40}, "ter": 0.01})])
    p = unit_trusts.extra_profiles(fund, UNI.entries, UTS)["UT:custom-x"]
    assert p.earnings.to_dict() == pytest.approx({"unclassified": 0.6, "global": 0.4})


def test_unit_trust_prices_are_fetched_and_cleaned():
    calls = []

    def fake(url):
        calls.append(url)
        if "ZAE000000001" in url:
            return {"Prices": [{"ClosingDate": f"{d:%Y-%m-%d}T00:00:00", "Price": 1000 + i}
                               for i, d in enumerate(pd.bdate_range("2024-01-01", periods=30))]}
        return {"Prices": []}

    df, fail = data.download_unit_trusts(["UT:ZAE000000001", "UT:ZAE000000002"], fetch=fake, pause=0)
    assert list(df.columns) == ["UT:ZAE000000001"] and "UT:ZAE000000002" in fail
    assert df.iloc[0, 0] == pytest.approx(10.04)  # cents -> rand, Friday close of the first week
    assert "ISINCode=ZAE000000001" in calls[0]
    assert data.quote_unit("UT:ZAE000000001") == "ZAc"
