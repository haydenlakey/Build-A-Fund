"""Look-through composition: data integrity, breakdown maths, overlap and tilts."""
import pandas as pd
import pytest

from fundlab.data import load_universe
from fundlab.lookthrough import TILTS, compose, load_lookthrough, profile


@pytest.fixture(scope="module")
def uni():
    return load_universe()


@pytest.fixture(scope="module")
def lt():
    return load_lookthrough()


def weights(**amounts) -> pd.Series:
    s = pd.Series({k.replace("_", ".") if k.endswith("_JO") else k: v for k, v in amounts.items()}, dtype=float)
    return s / s.sum()


# ---- data file ------------------------------------------------------------------

def test_every_universe_etf_has_lookthrough_data(uni, lt):
    etfs = [t for t, e in uni.entries.items() if e["kind"] in ("jse_etf", "us_etf")]
    assert etfs
    missing = [t for t in etfs if lt.resolve(t) is None]
    assert not missing


def test_use_targets_exist_and_have_an_asset_class(lt):
    for key, e in lt.entries.items():
        if "use" in e:
            assert e["use"] in lt.entries, key
        assert "asset" in lt.resolve(key), key


def test_every_split_and_holding_has_a_source_with_dates(lt):
    for key, raw in lt.entries.items():
        for field, src in (("sectors", "sectors_src"), ("holdings", "holdings_src")):
            if raw.get(field) and not key.startswith("index:Gold") and not key.startswith("index:Platinum"):
                s = lt.resolve(key).get(src)
                assert s and s.get("url", "").startswith("http") and s.get("as_of") and s.get("accessed"), (key, src)


def test_published_splits_sum_to_about_100(lt):
    for key in lt.entries:
        e = lt.resolve(key)
        for field in ("sectors", "countries"):
            if e.get(field):
                assert sum(e[field].values()) == pytest.approx(100, abs=1.0), (key, field)


def test_every_sector_label_is_mapped(lt):
    known = set(lt.sector_map.values())
    for key in lt.entries:
        for label in (lt.resolve(key).get("sectors") or {}):
            assert lt.map_sector(str(label)) in known, (key, label)


def test_jse_etfs_have_costs_and_an_index(uni):
    for t, e in uni.entries.items():
        if e["kind"] == "jse_etf":
            assert 0 < e["ter"] < 0.02, t
            assert e.get("tracks"), t


# ---- profiles -------------------------------------------------------------------

def test_profiles_sum_to_one(uni, lt):
    for t in ["STX40.JO", "STX500.JO", "GLD.JO", "STXGOV.JO", "ETFSWX.JO", "NPN.JO", "AAPL", "VT", "XYZ.JO"]:
        p = profile(t, uni.entries, lt)
        assert p.sectors["frac"].sum() == pytest.approx(1)
        for s in (p.countries, p.currencies, p.earnings):
            assert s.sum() == pytest.approx(1), t


def test_share_profile_is_itself(uni, lt):
    p = profile("NPN.JO", uni.entries, lt)
    assert not p.looked_through
    assert p.sectors.iloc[0]["sector"] == "Technology"
    assert p.currencies.to_dict() == {"ZAR": 1.0}
    assert p.earnings.to_dict() == {"global": 1.0}


def test_etf_inherits_index_but_keeps_own_holdings(uni, lt):
    a, b = profile("STX500.JO", uni.entries, lt), profile("SYG500.JO", uni.entries, lt)
    assert a.sectors.equals(b.sectors)  # same index record
    assert not a.companies.equals(b.companies)  # own fact sheets
    assert a.countries.to_dict() == {"US": 1.0} and a.currencies.to_dict() == {"USD": 1.0}
    # Alphabet's two share classes are merged into one company
    assert (a.companies["key"] == "GOOGL").sum() == 1


def test_jse_equity_etf_countries_use_top_holdings_domicile(uni, lt):
    p = profile("STX40.JO", uni.entries, lt)
    assert p.countries["GB"] == pytest.approx(0.0341 + 0.0791)  # Anglo American, AngloGold Ashanti plc
    assert p.currencies.to_dict() == {"ZAR": 1.0}


def test_etf_without_sector_split_falls_back_to_holdings(uni, lt):
    p = profile("ETFSWX.JO", uni.entries, lt)
    assert "Not disclosed" in set(p.sectors["sector"])


def test_unknown_ticker_is_not_classified(uni, lt):
    p = profile("XYZ.JO", uni.entries, lt, name="Some company")
    assert p.earnings.to_dict() == {"unclassified": 1.0}
    assert p.companies.iloc[0]["name"] == "Some company"


# ---- fund breakdowns ---------------------------------------------------------------

def test_breakdowns_sum_to_one(uni, lt):
    c = compose(weights(STX40_JO=10_000, STX500_JO=5_000, CPI_JO=1_500, GLD_JO=2_000), uni.entries, lt)
    assert c.sectors["weight"].sum() == pytest.approx(1)
    for s in (c.by_asset, c.by_sector, c.by_country, c.by_currency, c.by_earnings):
        assert s.sum() == pytest.approx(1)


def test_breakdown_is_weighted_average_of_profiles(uni, lt):
    w = weights(STXRES_JO=1, STXFIN_JO=3)
    c = compose(w, uni.entries, lt)
    res, fin = (profile(t, uni.entries, lt) for t in ("STXRES.JO", "STXFIN.JO"))
    expected = 0.25 * res.sectors.groupby("sector")["frac"].sum().get("Financial Services", 0) \
        + 0.75 * fin.sectors.groupby("sector")["frac"].sum()["Financial Services"]
    assert c.by_sector["Financial Services"] == pytest.approx(expected)


def test_overlap_adds_direct_and_through_funds(uni, lt):
    c = compose(weights(NPN_JO=3_000, STX40_JO=5_000, STXIND_JO=2_000), uni.entries, lt)
    npn = c.companies.set_index("key").loc["NPN.JO"]
    assert npn["direct"] == pytest.approx(0.3)
    assert npn["via_funds"] == pytest.approx(0.5 * 0.0784 + 0.2 * 0.2310)
    assert npn["n_sources"] == 3
    assert c.companies.iloc[0]["key"] == "NPN.JO"


def test_concentration_numbers(uni, lt):
    c = compose(weights(STX40_JO=60, AAPL=10, MSFT=10, NVDA=10, KO=5, PG=5), uni.entries, lt)
    assert c.top5 == pytest.approx(0.95)
    assert c.largest == ("STX40.JO", pytest.approx(0.6))
    assert c.dominant


def test_weighted_costs(uni, lt):
    c = compose(weights(STX40_JO=1, NPN_JO=1), uni.entries, lt)
    assert c.weighted_ter == pytest.approx(0.5 * uni.get("STX40.JO")["ter"])
    assert c.lookthrough_share == pytest.approx(0.5)


# ---- tilts: one fund that trips each label, one that doesn't -------------------------

TILT_CASES = {
    "tech": ({"STXNDQ.JO": 1}, {"STXFIN.JO": 1}),
    "resources": ({"STXRES.JO": 1}, {"STXIND.JO": 1}),
    "banks": ({"STXFIN.JO": 1}, {"STXRES.JO": 1}),
    "property": ({"STXPRO.JO": 1}, {"STX40.JO": 1}),
    "precious": ({"GLD.JO": 1, "STX40.JO": 3}, {"STX40.JO": 1}),
    "rand_hedge": ({"STX500.JO": 1}, {"STXFIN.JO": 1}),
    "sa_focus": ({"STXGOV.JO": 1, "STXPRO.JO": 1}, {"STX500.JO": 1}),
}


@pytest.mark.parametrize("key", list(TILTS))
def test_each_tilt_fires_and_stays_quiet(uni, lt, key):
    yes, no = TILT_CASES[key]
    assert key in {t.key for t in compose(pd.Series(yes, dtype=float) / sum(yes.values()), uni.entries, lt).tilts}
    assert key not in {t.key for t in compose(pd.Series(no, dtype=float) / sum(no.values()), uni.entries, lt).tilts}


def test_tilt_text_never_advises(uni, lt):
    c = compose(weights(STXNDQ_JO=1, STXRES_JO=1, STXFIN_JO=1, GLD_JO=1), uni.entries, lt)
    for t in c.tilts:
        low = (t.label + " " + t.detail).lower()
        assert not any(w in low.split() for w in ("buy", "sell", "should", "recommend"))
