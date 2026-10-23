import numpy as np
import pandas as pd
import pytest

from fundlab import analysis
from fundlab.model import Fund, FundSettings, Holding
from ui import charts


@pytest.fixture(scope="module")
def prices():
    rng = np.random.default_rng(5)
    n = 300
    weeks = pd.date_range("2018-01-05", periods=n, freq="W-FRI")
    r = pd.DataFrame({"A": rng.normal(0.002, 0.03, n), "B": rng.normal(0.001, 0.02, n),
                      "C": rng.normal(0.0015, 0.015, n)}, index=weeks)
    return 100 * (1 + r).cumprod()


SETTINGS = FundSettings(lookback_years=None, cov_method="sample", mean_shrinkage=0.0)


def fund(**amounts):
    return Fund("T", [Holding(t, t, "jse_share", a) for t, a in amounts.items()])


def test_label_moves_below_when_a_fund_marker_sits_on_it():
    xs, ys = [0.10, 0.30], [0.08, 0.12]
    pos = charts._label_positions(xs, ys, avoid=[(0.10, 0.085)], xspan=0.3, yspan=0.12)
    assert pos == ["bottom center", "top center"]
    # a marker both above and below: the label goes to the right
    pos = charts._label_positions([0.10], [0.08], avoid=[(0.10, 0.085), (0.10, 0.075)], xspan=0.3, yspan=0.12)
    assert pos == ["middle right"]


def test_labels_are_drawn_above_the_fund_markers(prices):
    cmp = analysis.compare(fund(A=1000, B=1000), fund(A=1000, B=1000, C=2000), prices, SETTINGS)
    fig = charts.risk_return(cmp, {}, moved=True)
    names = [t.name for t in fig.data]
    after = names.index("After")
    assert fig.data[-1].mode == "text" and len(fig.data) - 1 > after
    assert all(fr.traces == (after,) for fr in fig.frames)  # Replay still moves the fund marker
    assert "1px" in fig.data[-1].textfont.shadow


def test_small_move_gets_a_callout_instead_of_an_arrow(prices):
    big = charts.risk_return(analysis.compare(fund(A=1000), fund(A=1000, C=1000), prices, SETTINGS), {}, True)
    assert [a.text for a in big.layout.annotations] == [""]  # the arrow
    tiny = charts.risk_return(analysis.compare(fund(A=1000, C=1000), fund(A=1000, C=1003), prices, SETTINGS),
                              {}, True)
    (note,) = tiny.layout.annotations
    assert note.text.startswith("Barely moved<br>expected return ") and " pp" in note.text
    assert note.axref is None  # offset in pixels, not an arrow between data points
