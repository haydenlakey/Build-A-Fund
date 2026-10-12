"""Insight pop-ups: a callout when a change first trips a rule (until dismissed), and a list of all of them.

Rules a fund already trips when this session first sees it (opened from a link, a file or the example)
go straight to the Insights list: only a change pops up. Dismissals are remembered per fund and rule
for the session. A rule that was checked and stopped tripping forgets its dismissal, so tripping it
again later shows the pop-up again. A rule that couldn't be checked here (e.g. leverage, known only
on the Risk page) keeps its state.
"""
from __future__ import annotations

import re

import streamlit as st

from fundlab import rules
from fundlab.model import Fund
from ui import cached

MAX_POPUPS = 2  # more than this at once would bury the page; the rest wait in the Insights list


def _dismissed(fund: Fund) -> set:
    return st.session_state.setdefault("insights_dismissed", {}).get(fund.id, set())


def _dismiss(fund_id: str, rule_id: str) -> None:
    st.session_state.setdefault("insights_dismissed", {}).setdefault(fund_id, set()).add(rule_id)


def current(fund: Fund, extra: dict | None = None) -> list[rules.Insight]:
    values = {**cached.rule_measures(fund), **(extra or {})}
    found, checked = rules.evaluate(cached.insight_rules(), values)
    by_fund = st.session_state.setdefault("insights_dismissed", {})
    if fund.id not in by_fund:  # first sight of this fund: what it already trips isn't news
        by_fund[fund.id] = {i.rule.id for i in found}
    by_fund[fund.id] -= checked - {i.rule.id for i in found}
    return found


def _body(i: rules.Insight, compact: bool = False) -> None:
    lib = cached.library()
    if compact:  # the sidebar: what was noticed and where to read more
        st.caption(i.noticed)
    else:
        st.markdown(f"**What I noticed.** {i.noticed}")
        st.markdown(f"**What history says.** {i.history}")
    if i.rule.article in lib:
        st.page_link("views/library.py", label=f"Read more: {lib[i.rule.article].title}",
                     icon=":material/menu_book:", query_params={"article": i.rule.article})
    if compact:
        return
    notes = [i.rule.threshold_note] if i.rule.threshold_note else []
    notes += [f"Source: [{s['title']}]({s['url']}) (accessed {s['accessed']})" for s in i.rule.sources]
    if not i.rule.sources and re.search(r"\d", i.rule.history):
        notes.append("Figures from the library article, which lists its sources.")
    if notes:
        st.caption(" ".join(notes))


def popups(fund: Fund, extra: dict | None = None, only: set[str] | None = None) -> None:
    """Dismissible callouts for tripped rules the visitor hasn't dismissed yet (at most MAX_POPUPS)."""
    dismissed = _dismissed(fund)
    waiting = [i for i in current(fund, extra) if i.rule.id not in dismissed and (only is None or i.rule.id in only)]
    for i in waiting[:MAX_POPUPS]:
        with st.container(border=True, key=f"insight_{i.rule.id}"):
            icon = ":material/warning:" if i.rule.severity == "warning" else ":material/lightbulb:"
            st.markdown(f"{icon} **{i.rule.title}**")
            _body(i)
            st.button("Got it", key=f"dismiss_{i.rule.id}", on_click=_dismiss, args=(fund.id, i.rule.id),
                      help="Hide this pop-up. It stays in the Insights list in the sidebar.")
    if len(waiting) > MAX_POPUPS:
        st.caption(f"{len(waiting) - MAX_POPUPS} more in **Insights** in the sidebar.")


def panel(fund: Fund) -> None:
    """Every rule the fund trips, dismissed or not (for the sidebar)."""
    found = current(fund)
    with st.expander(f"Insights ({len(found)})", icon=":material/lightbulb:"):
        if not found:
            st.caption("Nothing to point out about this fund yet. Insights appear here when a change trips one "
                       "of the app's rules.")
        for i in found:
            st.markdown(f"**{i.rule.title}**")
            _body(i, compact=True)
