"""Plotly figures."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from fundlab.analysis import Comparison

from .theme import FONT, base_layout, palette

N_FRAMES = 14


def _short(ticker: str, names: dict[str, str] | None = None) -> str:
    """Chart label: the ticker without .JO; unit trusts (UT:...) have no readable ticker, so a short name."""
    if ":" in ticker:
        name = (names or {}).get(ticker, ticker.split(":", 1)[1])
        return name if len(name) <= 16 else name[:15].rstrip() + "…"
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
        text=[_short(t, names) for t in tick], textposition="top center",
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


# ---- active bets -------------------------------------------------------------------

def active_bars(active, names: dict[str, str]) -> go.Figure:
    """Active weights: overweights (blue) right of zero, underweights (red) left, labelled with signs."""
    p = palette()
    s = active.sort_values()
    labels = [names.get(t, t) for t in s.index]
    fig = go.Figure(go.Bar(
        x=s.values, y=labels, orientation="h",
        marker=dict(color=[p["div_neg"] if v > 0 else p["div_pos"] for v in s.values], cornerradius=4),
        text=[f"{v:+.1%}" for v in s.values], textposition="outside", cliponaxis=False,
        textfont=dict(color=p["ink2"], size=12),
        customdata=["more than the benchmark" if v > 0 else "less than the benchmark" for v in s.values],
        hovertemplate="<b>%{y}</b><br>%{x:+.1%}: %{customdata}<extra></extra>",
    ))
    layout = base_layout(p, height=max(180, 60 + 34 * len(s)), showlegend=False, margin=dict(l=8, r=56, t=8, b=8),
                         bargap=0.35)
    lim = max(abs(s.min()), abs(s.max()), 0.01) * 1.25
    layout["xaxis"] = dict(layout["xaxis"], tickformat="+.0%", range=[-lim, lim], zeroline=True,
                           zerolinecolor=p["axis"], zerolinewidth=1)
    layout["yaxis"] = dict(layout["yaxis"], showgrid=False, automargin=True, tickfont=dict(color=p["ink2"]))
    fig.update_layout(**layout)
    return fig


def budget_bars(budget, names: dict[str, str]) -> go.Figure:
    """Each bet's share of the tracking-error budget (can be negative: the bet offsets others)."""
    p = palette()
    s = budget.sort_values()
    fig = go.Figure(go.Bar(
        x=s.values, y=[names.get(t, t) for t in s.index], orientation="h",
        marker=dict(color=[p["series"][1] if v >= 0 else p["muted"] for v in s.values], cornerradius=4),
        text=[f"{v:.0%}" for v in s.values], textposition="outside", cliponaxis=False,
        textfont=dict(color=p["ink2"], size=12),
        hovertemplate="<b>%{y}</b><br>%{x:.1%} of the tracking-error budget<extra></extra>",
    ))
    layout = base_layout(p, height=max(180, 60 + 34 * len(s)), showlegend=False, margin=dict(l=8, r=56, t=8, b=8),
                         bargap=0.35)
    layout["xaxis"] = dict(layout["xaxis"], tickformat=".0%", zeroline=True, zerolinecolor=p["axis"])
    layout["yaxis"] = dict(layout["yaxis"], showgrid=False, automargin=True, tickfont=dict(color=p["ink2"]))
    fig.update_layout(**layout)
    return fig


# ---- library -----------------------------------------------------------------------

def history_lines(df, names: dict[str, str], y_title: str, log: bool = False) -> go.Figure:
    """One line per column over time, in fixed categorical order; direct labels at the line ends."""
    p = palette()
    fig = go.Figure()
    for i, c in enumerate(df.columns):
        s = df[c].dropna()
        colour = p["series"][i % len(p["series"])]
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, mode="lines+markers" if len(s) < 30 else "lines", name=names.get(c, c),
            line=dict(color=colour, width=2), marker=dict(size=8, color=colour, line=dict(width=2, color=p["surface"])),
            hovertemplate=f"<b>{names.get(c, c)}</b><br>%{{x|%d %b %Y}}<br>%{{y:,.2f}}<extra></extra>",
        ))
    layout = base_layout(p, height=380, margin=dict(l=8, r=8, t=40, b=8), showlegend=len(df.columns) > 1)
    layout["yaxis"] = dict(layout["yaxis"], title=y_title, type="log" if log else "linear")
    layout["xaxis"] = dict(layout["xaxis"], showgrid=False)
    fig.update_layout(**layout)
    return fig


# ---- risk detail -------------------------------------------------------------------

def _rgba(hex_colour: str, alpha: float) -> str:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _axes(layout: dict, x: dict | None = None, y: dict | None = None) -> dict:
    layout["xaxis"] = dict(layout["xaxis"], **(x or {}))
    layout["yaxis"] = dict(layout["yaxis"], **(y or {}))
    return layout


def _legend_line(fig: go.Figure, name: str, colour: str, dash: str = "solid", width: float = 1.5) -> None:
    """A legend entry for a reference line drawn as a shape (shapes have no legend of their own)."""
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name=name, hoverinfo="skip",
                             line=dict(color=colour, width=width, dash=dash)))


def _signed_pct(v: float) -> str:
    return "0%" if abs(v) < 0.005 else f"{v:+.0%}"


def outcome_hist(gains, var_zar: float, es_zar: float, alpha: float) -> go.Figure:
    """Simulated rand gains and losses; the tail beyond VaR in orange, VaR and ES marked."""
    p = palette()
    gains = np.asarray(gains)
    lo, hi = np.percentile(gains, [0.2, 99.8])
    size = (hi - lo) / 60 if hi > lo else 1.0
    bins = dict(start=lo - size, end=hi + size, size=size)
    fig = go.Figure()
    for mask, name, colour in [(gains > -var_zar, "Other outcomes", p["series"][0]),
                               (gains <= -var_zar, f"Worst {1 - alpha:.1%}".replace(".0%", "%"), p["series"][1])]:
        fig.add_trace(go.Histogram(
            x=gains[mask], xbins=bins, name=name, marker=dict(color=colour, line=dict(width=1, color=p["surface"])),
            hovertemplate="Gain or loss about R%{x:,.0f}<br>%{y} of the simulations<extra></extra>"))
    for x, text, dash in [(-var_zar, "VaR", "solid"), (-es_zar, "ES (average of the worst)", "dash")]:
        fig.add_vline(x=x, line=dict(color=p["ink2"], width=1.5, dash=dash))
        _legend_line(fig, f"{text}: R{-x:,.0f}".replace(",", " "), p["ink2"], dash)
    layout = base_layout(p, height=380, barmode="overlay", bargap=0, margin=dict(l=8, r=8, t=64, b=8))
    fig.update_layout(**_axes(layout, dict(title="Gain or loss in rand over the horizon", tickprefix="R",
                                           tickformat=",.0f"), dict(title="Simulations", showgrid=True)))
    return fig


def fan_chart(bands, start_amount: float, invested: float) -> go.Figure:
    """Percentile bands (5-95, 25-75) and median of simulated rand values, by years from now."""
    p = palette()
    blue = p["series"][0]
    yrs = bands.index / 52
    fig = go.Figure()
    for lo, hi, a, name in [(5, 95, 0.14, "5th to 95th percentile"), (25, 75, 0.30, "25th to 75th percentile")]:
        fig.add_trace(go.Scatter(x=yrs, y=bands[hi] * start_amount, mode="lines", line=dict(width=0),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=yrs, y=bands[lo] * start_amount, mode="lines", line=dict(width=0),
                                 fill="tonexty", fillcolor=_rgba(blue, a), name=name, hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=yrs, y=bands[50] * start_amount, mode="lines", name="Middle outcome (median)", line=dict(color=blue, width=2),
        customdata=np.column_stack([bands[q] * start_amount for q in (5, 25, 75, 95)]),
        hovertemplate="<b>After %{x:.1f} years</b><br>95th percentile R%{customdata[3]:,.0f}"
                      "<br>75th R%{customdata[2]:,.0f}<br>Median R%{y:,.0f}<br>25th R%{customdata[1]:,.0f}"
                      "<br>5th R%{customdata[0]:,.0f}<extra></extra>"))
    fig.add_hline(y=invested, line=dict(color=p["muted"], width=1, dash="dot"))
    _legend_line(fig, "What you put in", p["muted"], "dot", 1)
    layout = base_layout(p, height=420, hovermode="x", margin=dict(l=8, r=8, t=64, b=8))
    fig.update_layout(**_axes(layout, dict(title="Years from now", rangemode="tozero"),
                              dict(title="Fund value in rand", tickprefix="R", tickformat=",.0f")))
    return fig


STRESS_SERIES = [("fund", "Your fund"), ("bench_j200", "Top 40 index"), ("bench_spy", "S&P 500 in rand")]


def stress_bars(rows) -> go.Figure:
    """Grouped bars per episode: your fund, the Top 40 index and the S&P 500 in rand (episode returns)."""
    p = palette()
    fig = go.Figure()
    labels = [r["episode"] for r in rows][::-1]
    for i, (key, name) in reversed(list(enumerate(STRESS_SERIES))):
        vals = [r[key] for r in rows][::-1]
        fig.add_trace(go.Bar(
            x=vals, y=labels, orientation="h", name=name, marker=dict(color=p["series"][i], cornerradius=4),
            text=[_signed_pct(v) for v in vals], textposition="outside", cliponaxis=False,
            textfont=dict(color=p["ink2"], size=11),
            hovertemplate=f"<b>%{{y}}</b><br>{name}: %{{x:+.1%}}<extra></extra>"))
    layout = base_layout(p, height=max(260, 70 + 78 * len(rows)), barmode="group", bargap=0.25, bargroupgap=0.06,
                         margin=dict(l=8, r=56, t=40, b=8))
    layout["legend"] = dict(layout["legend"], traceorder="reversed")
    fig.update_layout(**_axes(layout, dict(tickformat="+.0%", zeroline=True, zerolinecolor=p["axis"]),
                              dict(showgrid=False, automargin=True, tickfont=dict(color=p["ink2"]))))
    return fig


def stress_path(rep) -> go.Figure:
    """One episode week by week, everything rebased to 100 at the start."""
    p = palette()
    fig = go.Figure()
    series = [(rep.path, "Your fund"), (rep.benchmarks["^J200.JO"], "Top 40 index"),
              (rep.benchmarks["SPY"], "S&P 500 in rand")]
    for i, (s, name) in enumerate(series):
        colour = p["series"][i]
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values * 100, mode="lines+markers" if len(s) < 30 else "lines", name=name,
            line=dict(color=colour, width=2), marker=dict(size=8, color=colour, line=dict(width=2, color=p["surface"])),
            hovertemplate=f"<b>{name}</b><br>%{{x|%d %b %Y}}<br>%{{y:.1f}}<extra></extra>"))
    fig.add_hline(y=100, line=dict(color=p["axis"], width=1))
    layout = base_layout(p, height=360)
    fig.update_layout(**_axes(layout, dict(showgrid=False), dict(title="Value (start = 100)")))
    return fig


def drawdown_chart(dd) -> go.Figure:
    """Fall from the previous high, week by week (0 = at a new high)."""
    p = palette()
    fig = go.Figure(go.Scatter(
        x=dd.index, y=dd.values, mode="lines", fill="tozeroy", line=dict(color=p["series"][0], width=1.5),
        fillcolor=_rgba(p["series"][0], 0.2), name="Fall from the previous high",
        hovertemplate="%{x|%d %b %Y}<br>%{y:.1%} below the previous high<extra></extra>"))
    worst = dd.idxmin()
    fig.add_annotation(x=worst, y=dd.min(), text=f"Worst: {dd.min():.0%}", showarrow=True, arrowhead=0, ax=36,
                       ay=0, xanchor="left", font=dict(color=p["ink"], size=12), arrowcolor=p["ink2"],
                       bgcolor=p["surface"])
    layout = base_layout(p, height=320, showlegend=False, margin=dict(l=8, r=8, t=16, b=8))
    fig.update_layout(**_axes(layout, dict(showgrid=False), dict(tickformat=".0%", title="Below the previous high")))
    return fig


def rolling_vol_chart(rv, full_vol: float, window: int) -> go.Figure:
    """Rolling annualised volatility with the whole-window figure as a reference line."""
    p = palette()
    rv = rv.dropna()
    fig = go.Figure(go.Scatter(
        x=rv.index, y=rv.values, mode="lines", line=dict(color=p["series"][0], width=2),
        name=f"Volatility over the previous {window} weeks",
        hovertemplate="%{x|%d %b %Y}<br>%{y:.1%} a year<extra></extra>"))
    fig.add_hline(y=full_vol, line=dict(color=p["muted"], width=1, dash="dot"))
    _legend_line(fig, f"Whole window: {full_vol:.0%}", p["muted"], "dot", 1)
    layout = base_layout(p, height=320)
    fig.update_layout(**_axes(layout, dict(showgrid=False),
                              dict(tickformat=".0%", rangemode="tozero", title="Volatility, % a year")))
    return fig


def leverage_chart(hist, lev: float, amount: float) -> go.Figure:
    """Your own money with and without borrowing, forced sales marked."""
    p = palette()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist["unlevered"] * amount, mode="lines", name="Without borrowing",
        line=dict(color=p["series"][0], width=2),
        hovertemplate="%{x|%d %b %Y}<br>Without borrowing R%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist["equity"] * amount, mode="lines", name=f"Your money, borrowing to hold {lev:g}×",
        line=dict(color=p["series"][1], width=2),
        hovertemplate="%{x|%d %b %Y}<br>Your money R%{y:,.0f}<extra></extra>"))
    calls = hist[hist["sold"] > 0]
    if len(calls):
        fig.add_trace(go.Scatter(
            x=calls.index, y=calls["equity"] * amount, mode="markers", name="Forced sale (margin call)",
            marker=dict(symbol="x-thin", size=11, color=p["ink"], line=dict(width=2, color=p["ink"])),
            customdata=calls["sold"] * amount,
            hovertemplate="%{x|%d %b %Y}<br>Lender sold R%{customdata:,.0f} of the investments<extra></extra>"))
    fig.add_hline(y=amount, line=dict(color=p["muted"], width=1, dash="dot"))
    _legend_line(fig, "What you put in", p["muted"], "dot", 1)
    layout = base_layout(p, height=400)
    fig.update_layout(**_axes(layout, dict(showgrid=False),
                              dict(title="Your money in rand", tickprefix="R", tickformat=",.0f", rangemode="tozero")))
    return fig


# ---- reality check -----------------------------------------------------------------

def cost_paths(df) -> go.Figure:
    """Fund value year by year with no costs, after fund costs and after all costs."""
    p = palette()
    styles = {"No costs": (p["muted"], "dot"), "After fund costs": (p["series"][0], "solid"),
              "After all costs": (p["series"][1], "solid")}
    fig = go.Figure()
    for c in df.columns:
        colour, dash = styles[c]
        fig.add_trace(go.Scatter(
            x=df.index, y=df[c], mode="lines", name=c, line=dict(color=colour, width=2, dash=dash),
            hovertemplate=f"<b>{c}</b><br>Year %{{x}}: R%{{y:,.0f}}<extra></extra>"))
    layout = base_layout(p, height=380, hovermode="x unified")
    fig.update_layout(**_axes(layout, dict(title="Years from now", dtick=5, showgrid=False),
                              dict(title="Fund value in rand", tickprefix="R", tickformat=",.0f")))
    return fig


def backtest_lines(lines: dict, amount: float) -> go.Figure:
    """Growth of the fund's rands under each line; the fund first and thickest, fixed colour order."""
    p = palette()
    fig = go.Figure()
    for i, (name, w) in enumerate(lines.items()):
        colour = p["series"][i % len(p["series"])]
        fig.add_trace(go.Scatter(
            x=w.index, y=w.values * amount, mode="lines", name=name,
            line=dict(color=colour, width=2.5 if i == 0 else 1.5),
            hovertemplate=f"<b>{name}</b><br>%{{x|%d %b %Y}}<br>R%{{y:,.0f}}<extra></extra>"))
    fig.add_hline(y=amount, line=dict(color=p["muted"], width=1, dash="dot"))
    layout = base_layout(p, height=420)
    fig.update_layout(**_axes(layout, dict(showgrid=False),
                              dict(title="Value in rand", tickprefix="R", tickformat=",.0f")))
    return fig


def weights_compare(current, optimised, lo, hi, names: dict[str, str]) -> go.Figure:
    """Your weights next to the optimiser's, with the 10th-90th percentile range of the optimiser's weight
    when expected returns are varied within their uncertainty."""
    p = palette()
    order = current.sort_values().index
    labels = [names.get(t, t) for t in order]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=[optimised[t] for t in order], orientation="h", name="Optimiser",
        marker=dict(color=p["series"][1], cornerradius=4),
        error_x=dict(type="data", symmetric=False, array=[hi[t] - optimised[t] for t in order],
                     arrayminus=[optimised[t] - lo[t] for t in order], color=p["ink2"], thickness=1.5, width=5),
        customdata=[[lo[t], hi[t]] for t in order],
        hovertemplate="<b>%{y}</b><br>Optimiser %{x:.1%}<br>Re-runs: %{customdata[0]:.0%} to %{customdata[1]:.0%}"
                      "<extra></extra>"))
    fig.add_trace(go.Bar(
        y=labels, x=[current[t] for t in order], orientation="h", name="Your fund",
        marker=dict(color=p["series"][0], cornerradius=4), text=[f"{current[t]:.0%}" for t in order],
        textposition="outside", cliponaxis=False, textfont=dict(color=p["ink2"], size=11),
        hovertemplate="<b>%{y}</b><br>Your fund %{x:.1%}<extra></extra>"))
    layout = base_layout(p, height=max(220, 90 + 56 * len(order)), barmode="group", bargap=0.3, bargroupgap=0.08,
                         margin=dict(l=8, r=48, t=40, b=8))
    layout["legend"] = dict(layout["legend"], traceorder="reversed")
    fig.update_layout(**_axes(layout, dict(tickformat=".0%", range=[0, 1.05]),
                              dict(showgrid=False, automargin=True, tickfont=dict(color=p["ink2"]))))
    return fig


# ---- explore diversifiers and compare funds ----------------------------------------

def diversifier_bars(table, names: dict[str, str]) -> go.Figure:
    """Change in fund volatility from adding each candidate: falls in blue, rises in red, biggest fall on top."""
    p = palette()
    t = table.iloc[::-1]
    labels = [f"{names.get(i, i)} ({_short(i)})" for i in t.index]
    fig = go.Figure(go.Bar(
        y=labels, x=t["d_vol"] * 100, orientation="h",
        marker=dict(color=[p["div_neg"] if v < 0 else p["div_pos"] for v in t["d_vol"]], cornerradius=4),
        text=[f"{v * 100:+.2f} pp" for v in t["d_vol"]], textposition="outside", cliponaxis=False,
        textfont=dict(color=p["ink2"], size=11),
        customdata=t[["vol", "corr", "vol_after", "d_ret"]].to_numpy(),
        hovertemplate="<b>%{y}</b><br>Fund volatility %{customdata[2]:.1%} (%{x:+.2f} pp)<br>Its own volatility "
                      "%{customdata[0]:.1%}<br>Correlation with your fund %{customdata[1]:.2f}<br>Expected return "
                      "change %{customdata[3]:+.2%}<extra></extra>"))
    lo = min(0.0, float(t["d_vol"].min()) * 100)
    hi = max(0.0, float(t["d_vol"].max()) * 100)
    pad = 0.25 * (hi - lo or 1.0)
    layout = base_layout(p, height=max(240, 70 + 30 * len(t)), margin=dict(l=8, r=8, t=16, b=8), showlegend=False)
    fig.update_layout(**_axes(layout, dict(tickformat="+.1f", range=[lo - pad, hi + pad], zeroline=True,
                                           zerolinecolor=p["axis"], title="Change in fund volatility, % points"),
                              dict(showgrid=False, automargin=True, tickfont=dict(color=p["ink2"]))))
    return fig


def diversifier_scatter(table, names: dict[str, str], highlight: list[str]) -> go.Figure:
    """Every candidate: correlation with the fund against the change in fund volatility."""
    p = palette()
    fig = go.Figure()
    rest = table.drop(index=highlight, errors="ignore")
    top = table.loc[[t for t in highlight if t in table.index]]
    for df, name, colour, size, text in ((rest, "Other holdings", p["muted"], 7, False),
                                         (top, "Listed in the table", p["series"][0], 10, True)):
        fig.add_trace(go.Scatter(
            x=df["corr"], y=df["d_vol"], mode="markers+text" if text else "markers", name=name,
            text=[_short(t) for t in df.index] if text else None, textposition="top center",
            textfont=dict(size=10, color=p["ink2"]),
            marker=dict(size=size, color=colour, line=dict(width=1, color=p["surface"])),
            customdata=[[names.get(t, t), v] for t, v in zip(df.index, df["vol"])],
            hovertemplate="<b>%{customdata[0]}</b><br>Correlation %{x:.2f}<br>Fund volatility %{y:+.2%}<br>"
                          "Its own volatility %{customdata[1]:.1%}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=p["axis"], width=1))
    layout = base_layout(p, height=420)
    fig.update_layout(**_axes(layout, dict(title="Correlation with your fund (weekly returns)", range=[-0.5, 1.0]),
                              dict(title="Change in fund volatility", tickformat="+.1%")))
    return fig


def funds_risk_return(mc, fund_names: list[str], names: dict[str, str]) -> go.Figure:
    """Each fund as a coloured dot against the frontier of all their holdings, holdings in grey."""
    p = palette()
    est = mc.est
    fig = go.Figure()
    tick = list(est.mu.index)
    if tick:
        fig.add_trace(go.Scatter(
            x=np.sqrt(np.diag(est.cov.loc[tick, tick])), y=est.mu.values, mode="markers+text", name="Holdings",
            text=[_short(t, names) for t in tick], textposition="top center", textfont=dict(size=10, color=p["muted"]),
            marker=dict(size=7, color=p["muted"], line=dict(width=1, color=p["surface"])),
            customdata=[names.get(t, t) for t in tick],
            hovertemplate="<b>%{customdata}</b><br>Expected return %{y:.1%}<br>Volatility %{x:.1%}<extra></extra>"))
    fr = mc.frontier
    if len(fr.vols) > 1:
        fig.add_trace(go.Scatter(x=fr.vols, y=fr.rets, mode="lines", name="Efficient frontier",
                                 line=dict(color=p["muted"], width=1.5, dash="dot"), hoverinfo="skip"))
    for i, (s, name) in enumerate(zip(mc.stats, fund_names)):
        if s is None:
            continue
        colour = p["series"][i % len(p["series"])]
        fig.add_trace(go.Scatter(
            x=[s.vol], y=[s.exp_return], mode="markers", name=name,
            marker=dict(size=16, color=colour, line=dict(width=2, color=p["surface"])),
            hovertemplate=f"<b>{name}</b><br>Expected return %{{y:.1%}}<br>Volatility %{{x:.1%}}<extra></extra>"))
    layout = base_layout(p, height=460)
    fig.update_layout(**_axes(layout, dict(title="Volatility (risk), % a year", tickformat=".0%", rangemode="tozero"),
                              dict(title="Expected return, % a year", tickformat=".0%")))
    return fig
