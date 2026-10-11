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
    at.selectbox(key="pick_0").set_value("NPN.JO").run()
    no_errors(at)
    assert at.number_input(key="amt_0_NPN.JO").value is None  # no amount until the user types one
    assert not any("What does this change do?" in s.value for s in at.subheader)
    at.number_input(key="amt_0_NPN.JO").set_value(4000.0).run()
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
    assert len(at.get("plotly_chart")) >= 5  # sunburst, sector bars, risk vs money, betas, correlation
    assert {"Sensitivities", "Which holdings move together"} <= {s.value for s in at.subheader}
    for view in ["Country and currency", "Where earnings come from"]:
        at.segmented_control(key="comp_view").set_value(view).run()
        no_errors(at)


def test_composition_page_empty_fund():
    at = fresh()
    at.switch_page("views/composition.py").run()
    no_errors(at)
    assert any("This fund is empty" in i.value for i in at.info)


def test_picker_resets_after_a_change_and_can_resize():
    """Regression: after Add, the picker kept showing the stock with no amount box, so it couldn't be changed."""
    at = fresh()
    next(b for b in at.button if b.label == "Open the example fund").click().run()
    at.selectbox(key="pick_0").set_value("NPN.JO").run()
    at.number_input(key="amt_0_NPN.JO").set_value(2500.0).run()
    next(b for b in at.button if b.label == "Add it").click().run()
    no_errors(at)
    assert at.selectbox(key="pick_1").value is None  # a fresh, empty picker
    at.selectbox(key="pick_1").set_value("NPN.JO").run()
    box = at.number_input(key="amt_1_NPN.JO")
    assert box.value == pytest.approx(2500.0)  # prefilled with what you hold
    box.set_value(6000.0).run()
    next(b for b in at.button if b.label == "Apply the increase").click().run()
    no_errors(at)
    fund = at.session_state.funds[at.session_state.active]
    assert fund.amounts()["NPN.JO"] == pytest.approx(6000.0)


def test_active_bets_page_and_benchmark_switch():
    at = fresh()
    next(b for b in at.button if b.label == "Open the example fund").click().run()
    at.switch_page("views/active_bets.py").run()
    no_errors(at)
    labels = [m.label for m in at.metric]
    assert "Tracking error" in labels and "Rule-of-thumb estimate" in labels
    assert len(at.get("plotly_chart")) >= 2
    at.selectbox[0].set_value("balanced").run()
    no_errors(at)
    fund = at.session_state.funds[at.session_state.active]
    assert fund.settings.benchmark == "balanced"


def test_old_benchmark_ticker_in_saved_file_still_works():
    f = Fund("Old", [Holding("STX40.JO", "Satrix 40", "jse_etf", 5000), Holding("NPN.JO", "Naspers", "jse_share", 2000)])
    f.settings.benchmark = "STX40.JO"
    at = fresh({"fund": f.to_share_code()})
    at.switch_page("views/active_bets.py").run()
    no_errors(at)
    assert any(m.label == "Tracking error" for m in at.metric)


def test_library_index_and_article():
    at = fresh()
    at.switch_page("views/library.py").run()
    no_errors(at)
    assert any(t.value == "Library" for t in at.title)
    next(b for b in at.button if b.key == "open_why-we-invest").click().run()
    no_errors(at)
    assert any("Why we invest" in t.value for t in at.title)
    next(b for b in at.button if "Back to the library" in b.label).click().run()
    no_errors(at)
    at.segmented_control(key="lib_section").set_value("case").run()
    no_errors(at)
    next(b for b in at.button if b.key == "open_nenegate").click().run()
    no_errors(at)
    assert at.get("plotly_chart")  # the case file's chart from bundled prices


def test_library_search():
    at = fresh()
    at.switch_page("views/library.py").run()
    at.text_input(key="lib_q").set_value("leverage").run()
    no_errors(at)
    assert any(b.key == "open_ltcm" for b in at.button)


def test_add_a_unit_trust_by_allocation_model():
    at = fresh()
    next(b for b in at.button if b.label == "Open the example fund").click().run()
    at.segmented_control(key="add_kind").set_value("unit_trust").run()
    at.segmented_control(key="ut_level_0").set_value("low_medium").run()
    at.selectbox(key="ut_pick_0_low_medium").set_value("UT:ZAE000177366").run()  # Allan Gray Stable
    no_errors(at)
    assert at.radio(key="ut_method_0_UT:ZAE000177366").value == "allocation_model"
    at.number_input(key="amt_0_UT:ZAE000177366").set_value(5000.0).run()
    no_errors(at)
    assert any("What does this change do?" in s.value for s in at.subheader)
    next(b for b in at.button if b.label == "Add it").click().run()
    no_errors(at)
    h = at.session_state.funds[at.session_state.active].holding("UT:ZAE000177366")
    assert h.kind == "unit_trust" and h.method == "allocation_model" and h.params["allocation"]


def test_add_an_unlisted_holding_shows_the_illiquid_sleeve():
    at = fresh()
    next(b for b in at.button if b.label == "Open the example fund").click().run()
    at.segmented_control(key="add_kind").set_value("unlisted").run()
    at.text_input(key="ul_name_0___new__").set_value("Coffee shop").run()
    at.number_input(key="ul_r_0___new__").set_value(60.0).run()
    at.number_input(key="ul_hi_0___new__").set_value(80.0).run()
    no_errors(at)
    assert any("far beyond" in w.value for w in at.warning)  # promised-return warning
    at.number_input(key="amt_0_UL:coffee-shop").set_value(3000.0).run()
    no_errors(at)
    assert any("Illiquid sleeve" in s.value for s in at.subheader)
    illiquid = next(m for m in at.metric if m.label == "Can't be sold in a hurry")
    assert illiquid.value == "14.0%"  # R3 000 of R21 500
    next(b for b in at.button if b.label == "Add it").click().run()
    no_errors(at)
    fund = at.session_state.funds[at.session_state.active]
    assert fund.holding("UL:coffee-shop").params["exp_return"] == pytest.approx(0.6)


def test_unlisted_and_unit_trust_fund_from_link_renders_everywhere():
    f = Fund("Mixed", [Holding("STX40.JO", "Satrix 40", "jse_etf", 5000),
                       Holding("UT:custom-own", "Own balanced", "unit_trust", 2000, method="allocation_model",
                               params={"allocation": {"sa_equity": 60, "sa_bonds": 30, "sa_cash": 10}, "ter": 0.01}),
                       Holding("UL:farm", "Farm", "unlisted", 1000, method="assumptions", params={"lockin_years": 7})])
    at = fresh({"fund": f.to_share_code()})
    no_errors(at)
    assert any("Illiquid sleeve" in s.value for s in at.subheader)
    for page in ("views/composition.py", "views/active_bets.py"):
        at.switch_page(page).run()
        no_errors(at)
