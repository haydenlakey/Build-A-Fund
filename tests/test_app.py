"""Headless smoke tests of the Streamlit app (no browser, no network: bundled data only)."""
import pytest
from streamlit.testing.v1 import AppTest

from fundlab import data
from fundlab.model import Fund, Holding

pytestmark = pytest.mark.skipif(not data.SAMPLE_PATH.exists(), reason="bundled sample not built")
TIMEOUT = 120


def fresh(query: dict | None = None) -> AppTest:
    at = AppTest.from_file(str(data.ROOT / "app.py"), default_timeout=TIMEOUT)
    if query:
        at.query_params.update(query)
    return at.run()


def no_errors(at: AppTest):
    assert not at.exception, [e.value for e in at.exception]


def test_empty_start_offers_example():
    at = fresh()
    no_errors(at)
    assert any("Open the example fund" in b.label for b in at.button)


def test_example_fund_shows_metrics_and_chart():
    at = fresh()
    next(b for b in at.button if b.label == "Open the example fund").click().run()
    no_errors(at)
    labels = [m.label for m in at.metric]
    assert "Expected return" in labels and "Volatility" in labels
    assert at.get("plotly_chart")


def test_preview_and_apply_an_addition():
    at = fresh()
    next(b for b in at.button if b.label == "Open the example fund").click().run()
    at.selectbox(key="pick").set_value("NPN.JO").run()
    no_errors(at)
    at.number_input(key="amt_NPN.JO").set_value(4000.0).run()
    no_errors(at)
    assert any("What does this change do?" in s.value for s in at.subheader)
    vol = next(m for m in at.metric if m.label == "Volatility")
    assert vol.delta is not None
    next(b for b in at.button if b.label == "Add it").click().run()
    no_errors(at)
    fund = at.session_state.funds[at.session_state.active]
    assert fund.amounts()["NPN.JO"] == pytest.approx(4000.0)


def test_share_link_opens_fund():
    f = Fund("Shared", [Holding("STX40.JO", "Satrix 40", "jse_etf", 5000), Holding("AAPL", "Apple", "us_share", 2500, "USD")])
    at = fresh({"fund": f.to_share_code()})
    no_errors(at)
    fund = at.session_state.funds[at.session_state.active]
    assert fund.name == "Shared" and fund.total_zar == pytest.approx(7500)


def test_bad_share_link_warns():
    at = fresh({"fund": "not-a-real-code"})
    no_errors(at)
    assert any("couldn't be read" in w.value for w in at.warning)


def test_short_history_holding_is_flagged():
    f = Fund("Short", [Holding("STX40.JO", "Satrix 40", "jse_etf", 5000), Holding("CRWV", "CoreWeave", "us_share", 1000, "USD")])
    at = fresh({"fund": f.to_share_code()})
    no_errors(at)
    text = " ".join(w.value for w in at.warning)
    assert "under three years" in text


def test_about_page_renders():
    at = fresh()
    at.switch_page("views/about.py").run()
    no_errors(at)
    assert any("About and data" in t.value for t in at.title)


def test_composition_page_with_example_fund():
    at = fresh()
    next(b for b in at.button if b.label == "Open the example fund").click().run()
    at.switch_page("views/composition.py").run()
    no_errors(at)
    assert any("What kind of fund is it?" in t.value for t in at.title)
    labels = [m.label for m in at.metric]
    assert "Top five holdings" in labels and "Effective holdings" in labels
    assert len(at.get("plotly_chart")) >= 3  # sunburst, sector bars, risk vs money
    for view in ["Country and currency", "Where earnings come from"]:
        at.segmented_control(key="comp_view").set_value(view).run()
        no_errors(at)


def test_composition_page_empty_fund():
    at = fresh()
    at.switch_page("views/composition.py").run()
    no_errors(at)
    assert any("This fund is empty" in i.value for i in at.info)
