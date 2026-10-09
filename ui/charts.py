"""Plotly figures."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from fundlab.analysis import Comparison

from .theme import FONT, base_layout, palette

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


# ---- composition ------------------------------------------------------------------

ASSET_ORDER = ["equity", "property", "bonds", "commodity", "cash"]


def sector_sunburst(sectors, asset_labels: dict[str, str]) -> go.Figure:
    """Asset class -> sector -> published industry label, sized by share of the fund.

    Colour follows the asset class only (<= 5 hues); rings are separated by surface-coloured borders.
    """
    p = palette()
    colours = {a: p["series"][i] for i, a in enumerate(ASSET_ORDER)}
    ids, labels, parents, values, cols = [], [], [], [], []
    for a, g in sectors.groupby("asset", sort=False):
        aid = f"a:{a}"
        ids.append(aid); labels.append(asset_labels.get(a, a)); parents.append(""); values.append(g["weight"].sum())
        cols.append(colours.get(a, p["muted"]))
        for s, gs in g.groupby("sector", sort=False):
            sid = f"{aid}/s:{s}"
            ids.append(sid); labels.append(s); parents.append(aid); values.append(gs["weight"].sum())
            cols.append(colours.get(a, p["muted"]))
            if len(gs) > 1 or gs["industry"].iloc[0] != s:
                for _, r in gs.iterrows():
                    ids.append(f"{sid}/i:{r['industry']}"); labels.append(r["industry"]); parents.append(sid)
                    values.append(r["weight"]); cols.append(colours.get(a, p["muted"]))
    fig = go.Figure(go.Sunburst(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
        marker=dict(colors=cols, line=dict(color=p["surface"], width=2)),
        insidetextorientation="radial", textfont=dict(family=FONT),
        hovertemplate="<b>%{label}</b><br>%{value:.1%} of the fund<br>%{percentParent:.0%} of %{parent}<extra></extra>",
        maxdepth=2,
    ))
    fig.update_layout(**base_layout(p, height=460, margin=dict(l=4, r=4, t=8, b=4),
                                    uniformtext=dict(minsize=11, mode="hide")))
    return fig


def share_bars(s, name: str, colour_idx: int = 0, height_per_bar: int = 30) -> go.Figure:
    """Horizontal bars of shares (fractions), largest on top, value labels at the bar ends."""
    p = palette()
    s = s[s > 0.0005].sort_values()
    fig = go.Figure(go.Bar(
        x=s.values, y=list(s.index), orientation="h", name=name,
        marker=dict(color=p["series"][colour_idx], line=dict(width=0), cornerradius=4),
        text=[f"{v:.1%}" for v in s.values], textposition="outside", cliponaxis=False,
        textfont=dict(color=p["ink2"], size=12),
        hovertemplate="<b>%{y}</b><br>%{x:.1%} of the fund<extra></extra>",
    ))
    layout = base_layout(p, height=max(140, 60 + height_per_bar * len(s)), showlegend=False,
                         margin=dict(l=8, r=48, t=8, b=8), bargap=0.35)
    layout["xaxis"] = dict(layout["xaxis"], tickformat=".0%", rangemode="tozero", showgrid=True)
    layout["yaxis"] = dict(layout["yaxis"], showgrid=False, automargin=True, tickfont=dict(color=p["ink2"]))
    fig.update_layout(**layout)
    return fig


def risk_vs_money(rands, risk, names: dict[str, str]) -> go.Figure:
    """Paired horizontal bars: each holding's share of the rands and share of the risk."""
    p = palette()
    order = rands.sort_values().index
    labels = [names.get(t, t) for t in order]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=[risk.get(t, float("nan")) for t in order], orientation="h", name="Share of risk",
        marker=dict(color=p["series"][1], cornerradius=4),
        text=[f"{risk.get(t, float('nan')):.0%}" for t in order], textposition="outside", cliponaxis=False,
        textfont=dict(color=p["ink2"], size=11),
        hovertemplate="<b>%{y}</b><br>Share of risk %{x:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=labels, x=[rands[t] for t in order], orientation="h", name="Share of rands",
        marker=dict(color=p["series"][0], cornerradius=4), text=[f"{rands[t]:.0%}" for t in order],
        textposition="outside", cliponaxis=False, textfont=dict(color=p["ink2"], size=11),
        hovertemplate="<b>%{y}</b><br>Share of rands %{x:.1%}<extra></extra>",
    ))
    layout = base_layout(p, height=max(200, 90 + 52 * len(order)), barmode="group", bargap=0.3, bargroupgap=0.08,
                         margin=dict(l=8, r=48, t=40, b=8))
    layout["xaxis"] = dict(layout["xaxis"], tickformat=".0%", rangemode="tozero")
    layout["yaxis"] = dict(layout["yaxis"], showgrid=False, automargin=True, tickfont=dict(color=p["ink2"]))
    layout["legend"] = dict(layout["legend"], traceorder="reversed")
    fig.update_layout(**layout)
    return fig


# ---- sensitivities and correlation --------------------------------------------------

def beta_forest(betas) -> go.Figure:
    """Each factor's beta as a dot with its confidence interval as a whisker; zero line for reference."""
    p = palette()
    betas = list(reversed(betas))
    y = [b.label for b in betas]
    fig = go.Figure()
    fig.add_vline(x=0, line=dict(color=p["axis"], width=1))
    fig.add_trace(go.Scatter(
        x=[b.beta for b in betas], y=y, mode="markers+text", name="Beta",
        marker=dict(size=11, color=p["series"][0], line=dict(width=2, color=p["surface"])),
        error_x=dict(type="data", symmetric=False, array=[b.hi - b.beta for b in betas],
                     arrayminus=[b.beta - b.lo for b in betas], color=p["series"][0], thickness=2, width=6),
        text=[f"{b.beta:.2f}" for b in betas], textposition="top center", textfont=dict(color=p["ink2"], size=12),
        customdata=[[b.lo, b.hi, b.r2, b.n] for b in betas],
        hovertemplate="<b>%{y}</b><br>Beta %{x:.2f}<br>95% interval %{customdata[0]:.2f} to %{customdata[1]:.2f}"
                      "<br>R² %{customdata[2]:.0%} · %{customdata[3]} weeks<extra></extra>",
    ))
    layout = base_layout(p, height=max(220, 70 + 56 * len(betas)), showlegend=False, margin=dict(l=8, r=16, t=16, b=8))
    layout["xaxis"] = dict(layout["xaxis"], title="Beta (change in the fund per 1 unit change in the factor)",
                           zeroline=False)
    layout["yaxis"] = dict(layout["yaxis"], showgrid=False, automargin=True, tickfont=dict(color=p["ink2"]))
    fig.update_layout(**layout)
    return fig


def corr_heatmap(corr, names: dict[str, str]) -> go.Figure:
    """Clustered correlation matrix, diverging blue (-1) <-> gray (0) <-> red (+1)."""
    p = palette()
    labels = [names.get(t, t) for t in corr.index]
    n = len(labels)
    z = corr.to_numpy()
    fig = go.Figure(go.Heatmap(
        z=z, x=labels, y=labels, zmin=-1, zmax=1, xgap=2, ygap=2,
        colorscale=[[0, p["div_neg"]], [0.5, p["div_mid"]], [1, p["div_pos"]]],
        text=[[f"{v:.2f}" for v in row] for row in z], texttemplate="%{text}" if n <= 12 else None,
        textfont=dict(size=11),
        colorbar=dict(title=dict(text="Correlation", side="right"), thickness=10, tickvals=[-1, -0.5, 0, 0.5, 1],
                      outlinewidth=0, tickfont=dict(color=p["muted"])),
        hovertemplate="<b>%{y}</b> and <b>%{x}</b><br>correlation %{z:.2f}<extra></extra>",
    ))
    side = max(280, 120 + 38 * n)
    layout = base_layout(p, height=side, margin=dict(l=8, r=8, t=8, b=8))
    layout["xaxis"] = dict(layout["xaxis"], showgrid=False, tickangle=-40, automargin=True, side="bottom")
    layout["yaxis"] = dict(layout["yaxis"], showgrid=False, autorange="reversed", automargin=True,
                           tickfont=dict(color=p["ink2"]))
    fig.update_layout(**layout)
    return fig
