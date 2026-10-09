import numpy as np
import pandas as pd
import pytest

from fundlab import data


# ---- conventions --------------------------------------------------------------

@pytest.mark.parametrize("ticker, unit", [
    ("NPN.JO", "ZAc"), ("STX40.JO", "ZAc"), ("^J200.JO", "points"), ("ZAR=X", "rate"),
    ("AAPL", "USD"), ("BRK-B", "USD"), ("GC=F", "USD"),
])
def test_quote_unit(ticker, unit):
    assert data.quote_unit(ticker) == unit


@pytest.mark.parametrize("ticker, ok", [
    ("NPN.JO", True), ("AAPL", True), ("BRK-B", True), ("VOD.L", False), ("", False), ("A B", False),
])
def test_is_supported(ticker, ok):
    assert data.is_supported(ticker) is ok


# ---- cleaning -------------------------------------------------------------------

def test_repair_hundredfold_fixes_a_stretch_quoted_in_rand():
    true_cents = pd.Series(np.linspace(10_000, 12_000, 20))
    glitched = true_cents.copy()
    glitched.iloc[5:9] /= 100  # four days reported in rand instead of cents
    assert np.allclose(data.repair_hundredfold(glitched), true_cents)


def test_repair_leaves_real_crashes_alone():
    s = pd.Series([100.0, 98, 40, 35, 36])  # a 59% one-week crash is real, not a unit switch
    assert np.allclose(data.repair_hundredfold(s), s)


def test_to_weekly_aligns_any_anchor_to_friday():
    days = pd.bdate_range("2024-01-01", "2024-02-29")
    df = pd.DataFrame({"A": np.arange(len(days), dtype=float)}, index=days)
    w = data.to_weekly(df)
    assert set(w.index.dayofweek) == {4}
    assert w.loc["2024-01-05", "A"] == 4.0  # Friday close of the first week


def test_clean_native_divides_jse_cents():
    days = pd.bdate_range("2024-01-01", periods=10)
    raw = pd.DataFrame({"NPN.JO": 70_000.0, "AAPL": 200.0, "^J200.JO": 90_000.0}, index=days)
    out = data.clean_native(raw)
    assert out["NPN.JO"].iloc[-1] == pytest.approx(700.0)
    assert out["AAPL"].iloc[-1] == pytest.approx(200.0)
    assert out["^J200.JO"].iloc[-1] == pytest.approx(90_000.0)  # indices are points, not cents


def test_to_zar_converts_usd_only_and_leaves_gaps_before_fx():
    weeks = pd.date_range("2003-11-07", periods=6, freq="W-FRI")
    native = pd.DataFrame({"AAPL": 10.0, "NPN.JO": 50.0}, index=weeks)
    fx = pd.Series([np.nan, np.nan, 8.0, 8.0, 9.0, 9.0], index=weeks)
    z = data.to_zar(native, fx)
    assert z["AAPL"].isna().iloc[:2].all()
    assert z["AAPL"].iloc[-1] == pytest.approx(90.0)
    assert (z["NPN.JO"] == 50.0).all()


# ---- store ----------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    weeks = pd.date_range("2010-01-01", periods=200, freq="W-FRI")
    rng = np.random.default_rng(0)
    native = pd.DataFrame({
        "AAA.JO": 100 * np.exp(np.cumsum(rng.normal(0, 0.03, 200))),
        "BBB": 50 * np.exp(np.cumsum(rng.normal(0, 0.03, 200))),
        "ZAR=X": 15.0,
    }, index=weeks)
    native.loc[weeks[:50], "BBB"] = np.nan  # listed later
    path = tmp_path / "sample.parquet"
    native.to_parquet(path)
    return data.PriceStore(sample_path=path, cache_path=tmp_path / "cache.parquet", allow_live=False,
                           history_from={"AAA.JO": str(weeks[20].date())})


def test_store_converts_and_reports_missing(store):
    z = store.prices_zar(["AAA.JO", "BBB", "NOPE.JO"])
    assert list(z.columns) == ["AAA.JO", "BBB"]
    assert z["BBB"].iloc[-1] == pytest.approx(store.native["BBB"].iloc[-1] * 15.0)
    assert "NOPE.JO" in store.failures
    assert store.source["AAA.JO"] == "sample"


def test_store_respects_history_from_and_late_listings(store):
    first = store.first_dates(["AAA.JO", "BBB"])
    assert first["AAA.JO"] == store.native.index[20]
    assert first["BBB"] == store.native.index[50]


# ---- universe and bundled sample ---------------------------------------------------

def test_universe_loads_and_searches():
    u = data.load_universe()
    assert len([e for e in u.entries.values() if e["kind"] == "jse_share"]) == 41
    assert u.search("naspers")[0]["ticker"] == "NPN.JO"
    assert u.search("NPN")[0]["ticker"] == "NPN.JO"
    assert u.kind_of("AAPL") == "us_share" and u.kind_of("STX40.JO") == "jse_etf"
    assert u.get("AAPL")["currency"] == "USD"
    assert u.history_limits()["OUT.JO"] == "2011-03-18"
    for e in u.entries.values():
        assert {"ticker", "name", "sector", "kind"} <= set(e)


@pytest.mark.skipif(not data.SAMPLE_PATH.exists(), reason="bundled sample not built")
def test_bundled_sample_is_sane():
    u = data.load_universe()
    s = data.PriceStore(allow_live=False, history_from=u.history_limits())
    assert set(s.native.index.dayofweek) == {4}
    missing = [t for t in u.all_tickers() if not s.has(t)]
    assert not missing, missing
    z = s.prices_zar(["STX40.JO", "AAPL", "ZAR=X"])
    last = z.dropna().iloc[-1]
    assert 20 < last["STX40.JO"] < 1_000  # rand, not cents
    assert 5 < last["ZAR=X"] < 40
    assert last["AAPL"] > 1_000  # dollars converted to rand
    weekly = z.pct_change(fill_method=None)
    assert weekly.abs().max().max() < 1.5  # no leftover 100x glitches in these


def test_remove_spikes_interpolates_isolated_fx_ticks():
    idx = pd.date_range("2024-11-01", periods=5, freq="W-FRI")
    s = pd.Series([17.60, 17.28, 14.86, 18.10, 18.08], index=idx)  # Yahoo ZAR=X, Nov 2024
    out = data.remove_spikes(s, jump=0.08, calm=0.06)
    assert out.iloc[2] == pytest.approx((17.28 + 18.10) / 2, rel=1e-3)
    assert out.drop(idx[2]).equals(s.drop(idx[2]))


def test_remove_spikes_keeps_real_moves_and_edges():
    idx = pd.date_range("2020-02-28", periods=5, freq="W-FRI")
    crash = pd.Series([15.47, 15.59, 16.56, 17.34, 17.30], index=idx)  # a real, persistent move
    assert data.remove_spikes(crash, jump=0.08, calm=0.06).equals(crash)
    edge = pd.Series([10.0, 10.1, 10.0, 10.1, 13.0], index=idx)  # last point has no right neighbour
    assert data.remove_spikes(edge, jump=0.08, calm=0.06).equals(edge)


def test_store_cleans_fx_spikes_on_load():
    store = data.PriceStore(allow_live=False)
    z = store.native[data.USDZAR]
    assert z.loc["2024-11-15"] > 17.0 and z.loc["2025-01-17"] > 18.0
