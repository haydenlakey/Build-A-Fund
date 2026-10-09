"""Chart colours and chrome for light and dark mode (reference data-viz palette)."""
from __future__ import annotations

import streamlit as st

LIGHT = {
    "surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
    "grid": "#e1e0d9", "axis": "#c3c2b7",
    "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
}
DARK = {
    "surface": "#1a1a19", "ink": "#ffffff", "ink2": "#c3c2b7", "muted": "#898781",
    "grid": "#2c2c2a", "axis": "#383835",
    "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
}
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def palette() -> dict:
    try:
        return DARK if st.context.theme.type == "dark" else LIGHT
    except Exception:  # noqa: BLE001 - theme is unavailable in tests and very old browsers
        return LIGHT


def base_layout(p: dict, **overrides) -> dict:
    layout = dict(
        paper_bgcolor=p["surface"], plot_bgcolor=p["surface"],
        font=dict(family=FONT, color=p["ink2"], size=13),
        margin=dict(l=8, r=8, t=40, b=8),
        hoverlabel=dict(bgcolor=p["surface"], font=dict(family=FONT, color=p["ink"]), bordercolor=p["axis"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=p["ink2"])),
        xaxis=dict(gridcolor=p["grid"], zeroline=False, linecolor=p["axis"], tickfont=dict(color=p["muted"]),
                   title_font=dict(color=p["ink2"])),
        yaxis=dict(gridcolor=p["grid"], zeroline=False, linecolor=p["axis"], tickfont=dict(color=p["muted"]),
                   title_font=dict(color=p["ink2"])),
    )
    layout.update(overrides)
    return layout
