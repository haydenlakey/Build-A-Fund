"""Glossary tooltips: terms in explanatory text get a dotted underline; hover or tap shows the definition."""
from __future__ import annotations

import streamlit as st

from fundlab import glossary
from ui.theme import palette


@st.cache_data(show_spinner=False)
def _terms(stamp: int) -> list[glossary.Term]:
    return glossary.load_glossary()


def terms() -> list[glossary.Term]:
    """All glossary terms; re-read whenever content/glossary.yaml changes."""
    return _terms(glossary.GLOSSARY_PATH.stat().st_mtime_ns)


def style() -> None:
    """The tooltip CSS (once per page run). Colours are the theme's ink and surface, swapped."""
    p = palette()
    st.html(f"""<style>
.gl {{ border-bottom: 1px dotted currentColor; cursor: help; position: relative; outline: none; }}
.gl:hover::after, .gl:focus::after {{
  content: attr(data-def); position: absolute; left: 0; top: 1.5em; z-index: 1000;
  width: max-content; max-width: min(320px, 70vw); padding: 8px 10px; border-radius: 6px;
  background: {p['ink']}; color: {p['surface']}; font-size: 0.85rem; font-weight: 400; font-style: normal;
  line-height: 1.4; white-space: normal; text-align: left; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}}
.gl:focus {{ background: {p['grid']}; border-radius: 2px; }}
@media (max-width: 640px) {{  /* phones: the definition sits at the bottom of the screen, never off the edge */
  .gl:hover::after, .gl:focus::after {{
    position: fixed; left: 16px; right: 16px; bottom: 16px; top: auto; width: auto; max-width: none;
    font-size: 0.95rem; padding: 12px 14px;
  }}
}}
</style>""")


def mark(text: str) -> str:
    return glossary.annotate(text, terms())


def markdown(text: str, **kwargs) -> None:
    """st.markdown with the first mention of each glossary term marked."""
    st.markdown(mark(text), unsafe_allow_html=True, **kwargs)
