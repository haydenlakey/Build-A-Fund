import io
import re
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

pypdf = pytest.importorskip("pypdf")  # dev requirement: reads the PDF back

from fundlab import factsheet, rules  # noqa: E402
from fundlab.model import Fund, Holding  # noqa: E402
from ui import factsheet_pdf  # noqa: E402

WEEKS = pd.date_range("2020-01-03", "2026-10-16", freq="W-FRI")
LONG = "An extraordinarily long holding name that goes on and on, Limited (Proprietary) Class B Shares"
ADVICE = re.compile(r"\b(buy|sell|should|recommend)\b", re.I)
SHARE = "https://example.streamlit.app/?fund=" + "x" * 600


def stats(vol=0.12):
    return SimpleNamespace(vol=vol, coverage=1.0, eff_holdings=7.5, max_drawdown=-0.31, sharpe=0.41, var=0.06)


def comp(n_sectors=12, n_countries=12):
    return SimpleNamespace(weighted_ter=0.0042, weighted_tc=0.0011, by_asset=pd.Series({"equity": 0.8, "bonds": 0.2}),
                           by_sector=pd.Series({f"Sector number {i}": 1 / n_sectors for i in range(n_sectors)}),
                           by_country=pd.Series({f"C{i}": 1 / n_countries for i in range(n_countries)}))


def insight(i: int, severity="info") -> rules.Insight:
    r = rules.Rule(id=f"r{i}", title=f"A long insight title number {i} " * 4, when={"x": {"above": 0}},
                   severity=severity, noticed=("Something long was noticed about this fund. " * 12) + "{value}",
                   history="h", article="diversification")
    return rules.Insight(r, {"x": 0.5})


def sheet(fund: Fund, **kw) -> factsheet.FactSheet:
    rng = np.random.default_rng(1)
    w = pd.Series(np.cumprod(1 + rng.normal(0.002, 0.02, len(WEEKS))), index=WEEKS)
    args = dict(names={}, stats=stats(), comp=comp(), benchmark="Global shares (MSCI World)", fund_wealth=w,
                bench_wealth=w * 0.9, cost_summary=SimpleNamespace(platform=0.0025, account=0.012, buy=0.006,
                                                                   total_zar=fund.total_zar),
                tripped=[insight(0), insight(1, "warning"), insight(2), insight(3)],
                articles={"diversification": "Diversification"}, as_of=WEEKS[-1], var_label="1-month VaR (95%)")
    args.update(kw)
    return factsheet.build(fund, **args)


def read(pdf: bytes):
    r = pypdf.PdfReader(io.BytesIO(pdf))
    return r, " ".join(pg.extract_text() for pg in r.pages)


def links(r) -> list[str]:
    return [a.get_object()["/A"]["/URI"] for a in r.pages[0].get("/Annots", []) if "/A" in a.get_object()]


BIG = Fund(LONG, [Holding(f"T{i}.JO", f"{LONG} {i}", "jse_share", 1000 + i) for i in range(40)],
           objective="To grow over a very long time. " * 20)


@pytest.mark.parametrize("case", ["big", "unlisted_only", "short_history", "no_benchmark"])
def test_every_case_fits_on_one_page(case):
    if case == "big":
        s = sheet(BIG)
    elif case == "unlisted_only":
        f = Fund("Coffee", [Holding("UL:x", "Coffee shop", "unlisted", 5000, method="assumptions",
                                    params={"exp_return": 0.2})])
        s = factsheet.build(f, names={"UL:x": "Coffee shop"}, illiquid=1.0, benchmark="JSE Top 40",
                            whole=SimpleNamespace(vol=0.3))
    elif case == "short_history":
        s = sheet(BIG, fund_wealth=pd.Series(np.linspace(1, 1.1, 60), index=WEEKS[-60:]))
    else:
        s = sheet(BIG, bench_wealth=None, active_report=None)
    r, text = read(factsheet_pdf.render(s, SHARE, lambda a: f"https://example.streamlit.app/library?article={a}"))
    assert len(r.pages) == 1
    assert "Model fund fact sheet" in text and "not a real unit trust" in text


def test_pdf_contents_links_and_qr_code():
    s = sheet(Fund("Short name", [Holding("A.JO", "Alpha", "jse_share", 600), Holding("B.JO", "Beta", "jse_etf", 400)],
                   objective="Learn how a fund behaves."), names={"A.JO": "Alpha", "B.JO": "Beta"})
    share = "https://example.streamlit.app/?fund=abc"
    r, text = read(factsheet_pdf.render(s, share, lambda a: f"https://example.streamlit.app/library?article={a}"))
    for part in ["Short name", "Objective: Learn how a fund behaves.", "Top holdings", "Alpha", "60.0%",
                 "Fund details", "Risk", "Fees", "Total investment charge", "Top insights", "Warning:",
                 "Sectors (looked through)", "Countries (looked through)", "Performance (simulated)"]:
        assert part in text, part
    assert share in links(r) and "https://example.streamlit.app/library?article=diversification" in links(r)
    assert len(r.pages[0].images) == 4  # growth, sectors, countries, QR code
    assert not ADVICE.search(text), ADVICE.search(text)


def test_no_qr_code_for_a_very_long_link_or_none():
    s = sheet(BIG)
    r, _ = read(factsheet_pdf.render(s, "https://x.app/?fund=" + "y" * 2500))
    assert len(r.pages[0].images) == 3
    r, _ = read(factsheet_pdf.render(s))
    assert len(r.pages[0].images) == 3 and links(r) == []


@pytest.mark.parametrize("url, root", [
    ("http://localhost:8501/factsheet?fund=abc", "http://localhost:8501"),
    ("http://localhost:8501/", "http://localhost:8501"),
    ("https://build-a-fund.streamlit.app/compare", "https://build-a-fund.streamlit.app"),
    ("https://build-a-fund.streamlit.app", "https://build-a-fund.streamlit.app"),
    ("", ""),
])
def test_app_url_drops_the_page_and_query(monkeypatch, url, root):
    from ui import state
    monkeypatch.setattr(state, "st", SimpleNamespace(context=SimpleNamespace(url=url)))
    assert state.app_url() == root
