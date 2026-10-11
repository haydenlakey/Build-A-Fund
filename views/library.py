"""The library: finance history and theory anyone can read, no fund needed."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from fundlab.content import GROUPS, SECTIONS, Article, by_section
from ui import cached, charts
from ui import components as C

CHART_CONFIG = {"displayModeBar": False, "scrollZoom": False}
INTRO = ("Stories and ideas behind investing: why shares exist, how bubbles form and burst, what went wrong (and "
         "right) in real episodes, and the theory the rest of this app uses. Every figure links to its source.")


def open_article(slug: str) -> None:
    st.session_state.article = slug
    st.query_params["article"] = slug


def close_article() -> None:
    st.session_state.article = None
    st.query_params.pop("article", None)


def points_frame(c: dict, default_name: str) -> pd.DataFrame:
    """Sourced values from the file: one `points` series, or several named `lines`, one column each."""
    lines = c.get("lines") or {c.get("series", default_name): c["points"]}
    cols = [pd.DataFrame(pts, columns=["date", name]).assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")
            for name, pts in lines.items()]
    return pd.concat(cols, axis=1).sort_index()


def chart(a: Article) -> None:
    c = a.chart
    if not c:
        return
    if c.get("kind") == "points":
        fig = charts.history_lines(points_frame(c, a.title), {}, c.get("unit", ""), log=bool(c.get("log")))
        source = c.get("source", "")
    else:
        tickers = list(c["tickers"])
        px = cached.prices(tickers).loc[str(c.get("start", "1990")):str(c.get("end", "2100")), :]
        px = px[[t for t in tickers if t in px.columns]].dropna(how="all")
        if px.empty:
            return
        rebased = px / px.apply(lambda s: s.dropna().iloc[0]) * 100
        names = dict(c.get("names") or {})
        names = {t: names.get(t, cached.name_of(t)) for t in rebased.columns}
        fig = charts.history_lines(rebased, names, "Value (start = 100)", log=bool(c.get("log")))
        source = c.get("source") or ("Weekly closes from Yahoo Finance (the app's price data), rebased to 100; "
                                     "US prices converted to rand at USD/ZAR where noted.")
    if c.get("title"):
        st.markdown(f"**{c['title']}**")
    st.plotly_chart(fig, config=CHART_CONFIG, key=f"chart_{a.slug}")
    if source:
        st.caption(f"Chart: {source}")


def article_view(a: Article, articles: dict[str, Article]) -> None:
    st.button("← Back to the library", on_click=close_article)
    st.title(a.title)
    meta = " · ".join(x for x in [SECTIONS[a.section], a.group, a.years] if x)
    st.caption(meta)
    if a.lesson:
        st.info(f"**The lesson for a fund builder:** {a.lesson}", icon=":material/school:")
    st.markdown(a.body)
    chart(a)
    rel = [articles[r] for r in a.related if r in articles]
    if rel:
        st.markdown("**Related reading**")
        cols = st.columns(min(3, len(rel)))
        for i, r in enumerate(rel):
            cols[i % len(cols)].button(r.title, key=f"rel_{r.slug}", on_click=open_article, args=(r.slug,),
                                       width="stretch")
    if a.sources:
        st.markdown("**Sources**")
        st.markdown("\n".join(f"{i}. [{s['title']}]({s['url']}) (accessed {s['accessed']})"
                              for i, s in enumerate(a.sources, 1)))
    C.disclaimer()


def card(a: Article) -> None:
    with st.container(border=True):
        st.markdown(f"**{a.title}**" + (f"  \n:gray[{a.years}]" if a.years else ""))
        if a.summary:
            st.caption(a.summary)
        st.button("Read", key=f"open_{a.slug}", on_click=open_article, args=(a.slug,))


def grid(items: list[Article], per_row: int = 3) -> None:
    for i in range(0, len(items), per_row):
        cols = st.columns(per_row)
        for col, a in zip(cols, items[i:i + per_row]):
            with col:
                card(a)


def index_view(articles: dict[str, Article]) -> None:
    st.title("Library")
    C.disclaimer()
    st.markdown(INTRO)
    q = st.text_input("Search the library", placeholder="e.g. leverage, rand, Steinhoff", key="lib_q").strip().lower()
    if q:
        hits = [a for a in articles.values() if q in (a.title + " " + a.summary + " " + a.body + " " + a.group).lower()]
        st.caption(f"{len(hits)} article{'s' if len(hits) != 1 else ''} mention “{q}”.")
        grid(sorted(hits, key=lambda a: a.title))
        return
    present = [s for s in SECTIONS if by_section(articles, s)]
    section = st.segmented_control("Section", present, format_func=SECTIONS.get, default=present[0] if present else None,
                                   key="lib_section") or (present[0] if present else None)
    if section is None:
        st.info("No articles yet.")
        return
    items = by_section(articles, section)
    if section == "case":
        st.caption("Real episodes, grouped by the lesson they teach. Each covers what happened, why, who was hurt, "
                   "and what it means for someone building a fund.")
        for g in GROUPS + sorted({a.group for a in items} - set(GROUPS)):
            gi = [a for a in items if a.group == g]
            if gi:
                st.subheader(g)
                grid(gi)
    else:
        grid(items)


# ---------------------------------------------------------------------------------

articles = cached.library()
slug = st.query_params.get("article") or st.session_state.get("article")  # a link's ?article= wins
if slug and slug in articles:
    article_view(articles[slug], articles)
else:
    index_view(articles)
