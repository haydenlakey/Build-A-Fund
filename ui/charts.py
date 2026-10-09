"""Plotly figures."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from fundlab.analysis import Comparison

from .theme import base_layout, palette

N_FRAMES = 14


def _short(ticker: str) -> str:
    return ticker.removesuffix(".JO")


def risk_return(cmp: Comparison, names: dict[str, str], moved: bool) -> go.Figure:
    """Holdings, the shared efficient frontier, and the fund before/after.

    The 'after' marker starts at its final position (so a static view shows the
    result); the Replay button animates it from the 'before' position.
    """
    p = palette()
    blue, orange = p["series"][0], p["series"][1]
    est = cmp.est
    fig = go.Figure()

    # 0: individual holdings
    tick = list(est.mu.index)
    vols = np.sqrt(np.diag(est.cov.loc[tick, tick])) if tick else []
    fig.add_trace(go.Scatter(
        x=vols, y=est.mu.values, mode="markers+text", name="Individual holdings",
        text=[_short(t) for t in tick], textposition="top center",
        textfont=dict(size=11, color=p["muted"]),
        marker=dict(size=8, color=p["muted"], line=dict(width=2, color=p["surface"])),
        customdata=[names.get(t, t) for t in tick],
        hovertemplate="<b>%{customdata}</b><br>Expected return %{y:.1%}<br>Volatility %{x:.1%}<extra></extra>",
    ))
    # 1: frontier
    fr = cmp.frontier
    if len(fr.vols) > 1:
        fig.add_trace(go.Scatter(
            x=fr.vols, y=fr.rets, mode="lines", name="Efficient frontier",
            line=dict(color=blue, width=2), hovertemplate="Frontier<br>Return %{y:.1%}<br>Volatility %{x:.1%}<extra></extra>",
        ))
    b, a = cmp.before, cmp.after
    if moved and b is not None:
        fig.add_trace(go.Scatter(
            x=[b.vol], y=[b.exp_return], mode="markers", name="Before",
            marker=dict(size=14, color=p["surface"], line=dict(width=2, color=p["ink2"])),
            hovertemplate="<b>Before</b><br>Return %{y:.1%}<br>Volatility %{x:.1%}<extra></extra>",
        ))
    if a is not None:
        fig.add_trace(go.Scatter(
            x=[a.vol], y=[a.exp_return], mode="markers", name="After" if moved else "Your fund",
            marker=dict(size=16, color=orange, line=dict(width=2, color=p["surface"])),
            hovertemplate=f"<b>{'After' if moved else 'Your fund'}</b><br>Return %{{y:.1%}}<br>Volatility %{{x:.1%}}<extra></extra>",
        ))
    layout = base_layout(
        p, height=440,
        xaxis=dict(base_layout(p)["xaxis"], title="Volatility (risk), % a year", tickformat=".0%", rangemode="tozero"),
        yaxis=dict(base_layout(p)["yaxis"], title="Expected return, % a year", tickformat=".0%"),
    )
    fig.update_layout(**layout)

    if moved and b is not None and a is not None:
        fig.add_annotation(x=a.vol, y=a.exp_return, ax=b.vol, ay=b.exp_return,
                           xref="x", yref="y", axref="x", ayref="y", showarrow=True,
                           arrowhead=3, arrowsize=1.2, arrowwidth=1.5, arrowcolor=p["ink2"], standoff=9, text="")
        after_idx = len(fig.data) - 1
        frames = []
        for k in range(N_FRAMES + 1):
            t = k / N_FRAMES
            t = t * t * (3 - 2 * t)  # ease in-out
            frames.append(go.Frame(
                data=[go.Scatter(x=[b.vol + t * (a.vol - b.vol)], y=[b.exp_return + t * (a.exp_return - b.exp_return)])],
                traces=[after_idx], name=str(k)))
        fig.frames = frames
        fig.update_layout(updatemenus=[dict(
            type="buttons", direction="left", x=1, xanchor="right", y=-0.26, yanchor="top",
            bgcolor=p["surface"], bordercolor=p["axis"], font=dict(color=p["ink2"]), showactive=False,
            buttons=[dict(label="▶ Replay the move", method="animate",
                          args=[[str(k) for k in range(N_FRAMES + 1)],
                                dict(frame=dict(duration=45, redraw=False), transition=dict(duration=0),
                                     fromcurrent=False, mode="immediate")])],
        )], margin=dict(l=8, r=8, t=40, b=120), height=480)
    return fig
