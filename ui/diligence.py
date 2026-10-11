"""The 'Before you add it' due-diligence checklist on the Build page."""
from __future__ import annotations

import streamlit as st

from fundlab import diligence, fundamentals, lookthrough
from fundlab.diligence import Checklist
from fundlab.model import Fund
from fundlab.unlisted import Assumptions
from ui import cached

ICONS = {"flag": (":material/search:", "Worth a closer look"), "auto": (":material/info:", "From the data"),
         "manual": (":material/edit_note:", "For you to check")}


@st.cache_resource
def content() -> dict:
    return diligence.load_content()


@st.cache_resource
def snapshot() -> dict:
    return fundamentals.load_snapshot()


@st.cache_data(ttl=24 * 3600, show_spinner="Fetching company figures from Yahoo…", max_entries=64)
def live_fundamentals(ticker: str) -> dict | None:
    return fundamentals.fetch(ticker)


def build(fund: Fund, ticker: str, spec: dict) -> Checklist | None:
    kind = spec.get("kind")
    c = content()
    if kind == "unlisted":
        return diligence.unlisted_checklist(c, Assumptions.from_params(spec.get("params", {})))
    have = cached.compose(fund).companies if fund.holdings else None
    if kind == "unit_trust":
        ut = cached.unit_trust_list().get(ticker)
        p = spec.get("params", {})
        hold = p.get("holdings") or (ut.holdings if ut else [])
        prof = lookthrough.allocation_profile(ticker, p.get("allocation") or {"sa_cash": 1}, hold, cached.universe().entries)
        if ut:
            return diligence.fund_checklist(c, ut.name, asisa=ut.asisa, benchmark=ut.benchmark, ter=ut.ter, tc=ut.tc,
                                            performance_fee=ut.performance_fee, manager=ut.manager,
                                            inception=ut.inception, size=ut.size, sheet=ut.sheet,
                                            candidate_companies=prof.companies if hold else None,
                                            fund_companies=have, kind_label="unit trust")
        return diligence.fund_checklist(c, spec.get("name", ticker), ter=p.get("ter"), fund_companies=have,
                                        kind_label="unit trust")
    uni = cached.universe()
    e = uni.get(ticker)
    if kind in ("jse_etf", "us_etf"):
        prof = lookthrough.profile(ticker, uni.entries, cached.lookthrough_data(), spec.get("name", ""))
        src = (cached.lookthrough_data().resolve(ticker) or {}).get("holdings_src") or {}
        return diligence.fund_checklist(c, spec.get("name", ticker), tracks=(e or {}).get("tracks") or "",
                                        ter=(e or {}).get("ter"), tc=(e or {}).get("tc"),
                                        sheet={"url": src.get("url"), "as_of": str(src.get("as_of", ""))} if src else None,
                                        candidate_companies=prof.companies if len(prof.companies) else None,
                                        fund_companies=have, kind_label="ETF")
    snap = snapshot()
    f = snap["companies"].get(ticker) or live_fundamentals(ticker)
    store = cached.store()
    price = store.native[ticker] if store.has(ticker) else None
    sector_of = {t: x.get("sector") for t, x in uni.entries.items()}
    return diligence.company_checklist(c, ticker, e, f, snap["companies"], price, sector_of=sector_of)


def show(cl: Checklist, key: str) -> None:
    n = cl.flags
    label = "Before you add it: due-diligence checklist" + (f" ({n} worth a closer look)" if n else "")
    with st.expander(label, icon=":material/checklist:"):
        st.caption(cl.intro + " Ticks are just for you; nothing is saved.")
        for it in cl.items:
            icon, tip = ICONS["flag" if it.flag else "auto" if it.auto and it.finding else "manual"]
            with st.container(border=True):
                c1, c2 = st.columns([12, 2], vertical_alignment="top")
                c1.markdown(f"{icon} **{it.question}**", help=tip)
                c2.checkbox("Done", key=f"dd_{key}_{it.id}", help="Mark this as looked at (not saved).")
                if it.finding:
                    st.markdown(it.finding)
                st.caption(it.why)
                for ln in it.links:
                    st.markdown(f"[{ln['title']}]({ln['url']}) (accessed {ln['accessed']})")
                if it.read and it.read in cached.library():
                    st.page_link("views/library.py", label=f"Read more: {cached.library()[it.read].title}",
                                 icon=":material/menu_book:", query_params={"article": it.read})
        if cl.note:
            st.caption(cl.note)
