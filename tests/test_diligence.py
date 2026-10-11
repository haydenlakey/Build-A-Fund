"""Due-diligence checklists: content is complete and neutral; each auto-filled flag fires and stays quiet."""
import re

import pandas as pd
import pytest

from fundlab import data, diligence, fundamentals
from fundlab.content import load_library
from fundlab.unlisted import Assumptions

CONTENT = diligence.load_content()
LIB = load_library()
ADVICE = re.compile(r"\b(you should|we recommend|recommended|should (buy|sell|invest)|buy now|sell now|avoid)\b", re.I)


def company(**kw):
    base = {"currency": "ZAR", "sector": "Industrials", "summary": "Makes things. Sells them. Third sentence.",
            "total_debt": 100e6, "total_cash": 50e6, "ebitda": 100e6, "trailing_pe": 10.0, "price_to_book": 1.5,
            "iss_overall": 3, "dividends_by_year": {str(y): 100.0 for y in range(2015, 2027)},
            "annual": [{"year_end": f"{y}-12-31", "revenue": 1e9 * 1.05 ** i, "net_income": 1e8,
                        "op_cash_flow": 1.2e8, "eps": 1.0} for i, y in enumerate(range(2022, 2026))]}
    base.update(kw)
    return base


PEERS = {f"P{i}.JO": {"sector": "Industrials", "trailing_pe": 10.0} for i in range(4)}


def check(f, ticker="X.JO", entry=None, price=None):
    return diligence.company_checklist(CONTENT, ticker, entry or {"sector": f.get("sector")}, f, PEERS, price)


@pytest.mark.parametrize("kind", ["company", "fund", "unlisted"])
def test_content_is_complete_and_neutral(kind):
    sec = CONTENT[kind]
    ids = [i["id"] for i in sec["items"]]
    assert len(ids) == len(set(ids)) and sec["title"]
    for i in sec["items"]:
        assert i["question"] and i["why"]
        assert not i.get("read") or i["read"] in LIB, i["read"]
        for k in i.get("links", []):
            assert CONTENT["links"][k]["url"].startswith("https://")
        assert not ADVICE.search(i["question"] + " " + i["why"])


def test_quiet_company_has_no_flags():
    cl = check(company())
    assert cl.flags == 0, [(i.id, i.finding) for i in cl.items if i.flag]
    assert "Makes things. Sells them." in cl.item("business").finding
    assert "Third" not in cl.item("business").finding


@pytest.mark.parametrize("item, kw", [
    ("debt", dict(total_debt=500e6, total_cash=0.0)),
    ("earnings", dict(annual=[{"year_end": "2024-12-31", "revenue": 1e9, "net_income": -1e7, "op_cash_flow": 1e7},
                              {"year_end": "2025-12-31", "revenue": 1e9, "net_income": 1e8, "op_cash_flow": 1e8}])),
    ("earnings", dict(annual=[{"year_end": "2024-12-31", "revenue": 1e9, "net_income": 1e8, "op_cash_flow": 2e7},
                              {"year_end": "2025-12-31", "revenue": 1.1e9, "net_income": 1e8, "op_cash_flow": 2e7}])),
    ("valuation", dict(trailing_pe=30.0)),
    ("dividends", dict(dividends_by_year={str(y): (100.0 if y % 3 else 0.0) for y in range(2015, 2027)})),
    ("governance", dict(iss_overall=9)),
    ("dependence", dict(sector="Basic Materials")),
])
def test_each_company_flag_fires(item, kw):
    f = company(**kw)
    entry = {"sector": f["sector"]}
    peers = {**PEERS, **{f"Q{i}.JO": {"sector": "Basic Materials", "trailing_pe": 10.0} for i in range(4)}}
    cl = diligence.company_checklist(CONTENT, "X.JO", entry, f, peers)
    assert cl.item(item).flag, cl.item(item).finding


def test_banks_get_no_debt_ratio_and_us_shares_get_pe_history():
    cl = check(company(sector="Financial Services", total_debt=9e12))
    assert "raw material" in cl.item("debt").finding and not cl.item("debt").flag
    price = pd.Series([10.0, 12.0, 14.0, 16.0], index=pd.to_datetime(["2022-12-30", "2023-12-29", "2024-12-27", "2025-12-26"]))
    cl = check(company(trailing_pe=40.0), ticker="XYZ", price=price)
    assert "own price-to-earnings" in cl.item("valuation").finding and cl.item("valuation").flag


def test_no_fundamentals_is_handled():
    cl = diligence.company_checklist(CONTENT, "ZZZ.JO", None, None, {})
    assert "No company figures" in cl.note and cl.flags == 0


def test_fund_checklist_overlap_and_fees():
    cand = pd.DataFrame([{"key": "NPN.JO", "name": "Naspers", "frac": 0.2}, {"key": "SBK.JO", "name": "Standard Bank", "frac": 0.1},
                         {"key": "FSR.JO", "name": "FirstRand", "frac": 0.05}, {"key": "AAPL", "name": "Apple", "frac": 0.05}])
    mine = pd.DataFrame([{"key": k, "name": k, "total": 0.1} for k in ("NPN.JO", "SBK.JO", "FSR.JO")])
    cl = diligence.fund_checklist(CONTENT, "F", asisa="SA Equity", ter=0.017, tc=0.001,
                                  candidate_companies=cand, fund_companies=mine)
    assert cl.item("overlap").flag and "3 of its 4" in cl.item("overlap").finding
    assert cl.item("fees").flag and "R180 a year" in cl.item("fees").finding
    cl = diligence.fund_checklist(CONTENT, "F", tracks="Top 40", ter=0.001, candidate_companies=cand.tail(1),
                                  fund_companies=mine)
    assert not cl.item("overlap").flag and not cl.item("fees").flag
    assert "index tracker" in cl.item("mandate").finding


@pytest.mark.parametrize("kw, flags", [
    (dict(exp_return=0.6, low=0.58, high=0.62, p_loss=0.0, lockin_years=1), {"realistic", "scam_signs"}),
    (dict(exp_return=0.10, lockin_years=7), {"withdrawal"}),
    (dict(exp_return=0.10, lockin_years=1), set()),
])
def test_unlisted_checklist_flags(kw, flags):
    cl = diligence.unlisted_checklist(CONTENT, Assumptions.from_params(kw))
    assert {i.id for i in cl.items if i.flag} == flags


SNAP = fundamentals.load_snapshot()["companies"]


@pytest.mark.skipif(not SNAP, reason="fundamentals snapshot not built")
def test_every_universe_share_builds_a_checklist():
    uni = data.load_universe()
    for t, e in uni.entries.items():
        if e["kind"] in ("jse_share", "us_share"):
            cl = diligence.company_checklist(CONTENT, t, e, SNAP.get(t), SNAP)
            assert cl.item("business").finding, t
            for it in cl.items:
                assert not ADVICE.search(it.finding), (t, it.id)
