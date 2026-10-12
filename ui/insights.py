"""Insight pop-ups: a callout when a fund first trips a rule (until dismissed), and a list of all of them.

Dismissals are remembered per fund and rule for the session. A rule that stops tripping forgets its
dismissal, so tripping it again later shows the pop-up again.
"""
from __future__ import annotations

import streamlit as st

from fundlab import rules
from fundlab.model import Fund
from ui import cached


def _dismissed(fund: Fund) -> set:
    return st.session_state.setdefault("insights_dismissed", {}).setdefault(fund.id, set())


def _dismiss(fund_id: str, rule_id: str) -> None:
    st.session_state.setdefault("insights_dismissed", {}).setdefault(fund_id, set()).add(rule_id)


def current(fund: Fund) -> list[rules.Insight]:
    found = rules.evaluate(cached.insight_rules(), fund)
    dismissed = _dismissed(fund)
    dismissed &= {i.rule.id for i in found}
    return found


def _body(i: rules.Insight) -> None:
    lib = cached.library()
    st.markdown(f"**What I noticed.** {i.noticed}")
    st.markdown(f"**What history says.** {i.rule.history}")
    if i.rule.article in lib:
        st.page_link("views/library.py", label=f"Read more: {lib[i.rule.article].title}",
                     icon=":material/menu_book:", query_params={"article": i.rule.article})
    notes = [i.rule.threshold_note] if i.rule.threshold_note else []
    notes += [f"Source: [{s['title']}]({s['url']}) (accessed {s['accessed']})" for s in i.rule.sources]
    if notes:
        st.caption(" ".join(notes))


def popups(fund: Fund) -> None:
    """A dismissible callout for each tripped rule the visitor hasn't dismissed yet."""
    dismissed = _dismissed(fund)
    for i in current(fund):
        if i.rule.id in dismissed:
            continue
        with st.container(border=True, key=f"insight_{i.rule.id}"):
            icon = ":material/warning:" if i.rule.severity == "warning" else ":material/lightbulb:"
            st.markdown(f"{icon} **{i.rule.title}**")
            _body(i)
            st.button("Got it", key=f"dismiss_{i.rule.id}", on_click=_dismiss, args=(fund.id, i.rule.id),
                      help="Hide this pop-up. It stays in the Insights list.")


def panel(fund: Fund) -> None:
    """Every rule the fund trips, dismissed or not (for the sidebar)."""
    found = current(fund)
    with st.expander(f"Insights ({len(found)})", icon=":material/lightbulb:"):
        if not found:
            st.caption("Nothing to point out about this fund yet. Insights appear here when a change trips one "
                       "of the app's rules.")
        for i in found:
            st.markdown(f"**{i.rule.title}**")
            _body(i)
