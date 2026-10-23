"""Fact sheet: the fund on one page, in the style of a South African unit trust fact sheet."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from fundlab import factsheet
from ui import cached, charts, glossary, state
from ui import components as C
from ui.theme import palette

CHART_CONFIG = {"displayModeBar": False, "scrollZoom": False}

INTRO = """
South African unit trusts publish a one-page **fact sheet** (a *minimum disclosure document*) with the same
building blocks: objective, holdings, sector and country split, performance against a benchmark, risk numbers and
fees. This is that page for your fund. It is a **model fund**: nobody manages it and nobody can invest in it as a whole.
"""

GROWTH_WHAT = """
What R1 000 in your fund would have become over the price history used, next to the same R1 000 in the benchmark.
It is a **simulation**: today's holdings, in today's proportions, applied to past prices and topped back up to those
proportions every quarter. Your fund was put together today, knowing which shares have done well, so this flatters it
(hindsight bias). It is not a track record.
"""

GROWTH_MATHS = r"""
Simulated wealth $W_t$ starts at 1 and grows each week by the fund's return, with the holdings drifting apart until a
quarterly rebalance resets them to today's weights $w$ (`fundlab.backtest.run`, no trading costs; ETF and unit trust
charges are already inside their prices). The chart shows $1000\,W_t$. For a period of $n$ years ending at the last
week $T$, the table's yearly figure is

$$\left(\frac{W_T}{W_{T-52n}}\right)^{1/n} - 1,$$

and a calendar year's return is $W$ at its last week divided by $W$ at the last week of the year before, minus one.
The benchmark is rebased to the fund's value in the week its prices start.
"""

SECTOR_WHAT = """
What your rands end up owning by sector once each ETF and unit trust is opened up (a look-through view). The six
largest are shown; the rest are grouped as *Other*. *What kind of fund is it?* has the full breakdown.
"""

SECTOR_MATHS = r"""
For each sector $c$, $B(c) = \sum_i w_i\,p_i(c)$: the rand weight $w_i$ of each holding times the share $p_i(c)$
of that holding in the sector (1 or 0 for a single share, the fact-sheet split for a fund).
"""

COUNTRY_WHAT = """
Where the companies you own through the fund are based, looked through in the same way. A company's base is not
the same as where it earns its money: *What kind of fund is it?* shows earnings exposure separately.
"""

COUNTRY_MATHS = SECTOR_MATHS.replace("sector $c$", "country $c$").replace("in the sector", "based there")


def html_table(rows: list[tuple], header: tuple | None = None, text_cols: int = 1) -> None:
    """A compact table that wraps long values instead of cutting them off (dataframes clip on narrow columns).
    The first `text_cols` columns are left-aligned text; the rest are right-aligned values."""
    p = palette()
    css = (f"<style>.fs-t{{width:100%;border-collapse:collapse;font-size:0.9rem;margin-bottom:0.6rem}}"
           f".fs-t td,.fs-t th{{padding:0.3rem 0.4rem;border-bottom:1px solid {p['grid']};vertical-align:top;"
           f"text-align:right}}.fs-t th{{color:{p['muted']};font-weight:500}}.fs-t .l{{text-align:left}}</style>")

    def cells(row, tag):
        return "".join(f"<{tag}{' class=l' if i < text_cols else ''}>{html.escape(str(c))}</{tag}>"
                       for i, c in enumerate(row))
    head = f"<tr>{cells(header, 'th')}</tr>" if header else ""
    body = "".join(f"<tr>{cells(r, 'td')}</tr>" for r in rows)
    st.markdown(f"{css}<table class='fs-t'>{head}{body}</table>", unsafe_allow_html=True)


def edit_objective(fund) -> None:
    text = st.text_area("Objective", fund.objective, max_chars=400, key=f"objective_{fund.id}",
                        placeholder="In a sentence or two: what is this fund for, and for how long?",
                        help="Real fact sheets open with the fund's objective. Yours is saved with the fund.")
    if text != fund.objective:
        f = fund.copy(keep_id=True)
        f.objective = text.strip()
        state.put(f)
        st.rerun()


def performance_section(sheet: factsheet.FactSheet) -> None:
    perf = sheet.performance
    st.subheader("Performance (simulated)")
    if perf is None:
        st.caption("No performance: none of the holdings has enough price history.")
        return
    lines = {"Your fund": perf.growth["fund"] / 1000}
    if "benchmark" in perf.growth:
        lines[sheet.benchmark] = perf.growth["benchmark"].dropna() / 1000
    st.plotly_chart(charts.backtest_lines(lines, 1000.0), config=CHART_CONFIG, key="fs_growth")
    C.chart_notes(GROWTH_WHAT, GROWTH_MATHS, "fs_growth")
    header = ("", "Your fund", sheet.benchmark)
    for title, df in [("Yearly return over each period", perf.periods), ("Calendar years", perf.calendar)]:
        if len(df):
            st.caption(title)
            html_table([(k, factsheet.pct(r["fund"]), factsheet.pct(r["benchmark"])) for k, r in df.iterrows()], header)


def insights_section(sheet: factsheet.FactSheet) -> None:
    st.subheader("Top insights")
    if not sheet.insights:
        st.caption("None of the app's insight rules is tripped by this fund.")
    for i in sheet.insights:
        with st.container(border=True):
            icon = ":material/warning:" if i.severity == "warning" else ":material/lightbulb:"
            st.markdown(f"{icon} **{i.title}**")
            st.caption(i.noticed)
            st.page_link("views/library.py", label=f"Read more: {i.article_title}", icon=":material/menu_book:",
                         query_params={"article": i.article})


# ---------------------------------------------------------------------------------

fund = state.active()
st.title("Fact sheet")
C.disclaimer()
glossary.markdown(INTRO)

if not fund.holdings:
    st.info("This fund is empty. Add holdings on the **Build your fund** page, or open the example fund there.",
            icon=":material/lightbulb:")
    st.stop()

with st.expander("Objective and benchmark", icon=":material/edit:", expanded=not fund.objective):
    edit_objective(fund)
    C.pick_benchmark(fund)

with st.spinner("Putting the fact sheet together…"):
    sheet = cached.fact_sheet(state.active())

with st.container(border=True):
    st.header(sheet.name, divider="gray")
    when = f"Prices to {sheet.as_of:%d %B %Y}. " if sheet.as_of is not None else ""
    st.caption(f"Model fund fact sheet. {when}{factsheet.DISCLAIMER}")
    if sheet.objective:
        st.markdown(f"**Objective.** {sheet.objective}")

    left, right = st.columns([3, 2], gap="large")
    with right:
        st.subheader("Fund details")
        html_table(sheet.details)
        st.caption("Risk level: the app's own bands on volatility (under 4%, 7%, 9%, 12% a year), on the five-step "
                   "scale SA fact sheets use. Managers set their labels with more than volatility.")
        if sheet.risk:
            st.subheader("Risk")
            html_table(sheet.risk)
        if sheet.fees:
            st.subheader("Fees")
            html_table(sheet.fees)
            st.caption("TER and TC are already inside ETF and unit trust prices. Platform, account and buying costs "
                       "use EasyEquities' published defaults (see *Reality check*).")
        st.subheader("Asset classes")
        html_table([(k, factsheet.pct(v)) for k, v in sheet.by_asset.items()])
    with left:
        performance_section(sheet)
        st.subheader("Top holdings")
        html_table([(r["name"], r["type"], factsheet.pct(r["weight"])) for _, r in sheet.holdings.iterrows()],
                   ("Holding", "Type", "Share"), text_cols=2)

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.subheader("Sectors")
        st.plotly_chart(charts.share_bars(sheet.by_sector, "Sector"), config=CHART_CONFIG, key="fs_sector")
        C.chart_notes(SECTOR_WHAT, SECTOR_MATHS, "fs_sector")
    with c2:
        st.subheader("Countries")
        st.plotly_chart(charts.share_bars(sheet.by_country, "Country"), config=CHART_CONFIG, key="fs_country")
        C.chart_notes(COUNTRY_WHAT, COUNTRY_MATHS, "fs_country")

    insights_section(sheet)
    for note in sheet.notes:
        st.caption(note)
