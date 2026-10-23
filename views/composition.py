"""What kind of fund is it? Look-through composition, tilts, concentration, risk versus money."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from fundlab.factors import FACTORS, cluster, correlation
from fundlab.lookthrough import ASSET_LABELS, COUNTRY_NAMES, DOMINANT, EARNINGS_LABELS, TILTS, Composition
from fundlab.model import Fund
from ui import cached, charts, state
from ui import components as C

CHART_CONFIG = {"displayModeBar": False, "scrollZoom": False}

SECTOR_WHAT = """
The rings show what your rands end up owning once each ETF is **opened up** (a "look-through"
view). The inner ring is the asset class, the middle ring the sector, and the outer ring the
finer label the fund provider publishes (for example *Banks* and *Insurance* inside Financial
Services). The outer ring appears when you tap a sector to zoom in; tap the centre to zoom out.
Slices too thin to label still show their name when you hover or tap.

A single share counts fully toward its own sector. An ETF is split using the sector table on
its latest fact sheet, so a Satrix 40 holding spreads across mining, banks, Naspers and so on.

The bars underneath give the same sector totals as exact numbers.
"""

SECTOR_MATHS = r"""
For a breakdown category $c$ (a sector, country, currency...), the fund's share is the
rand-weighted average of each holding's own split:

$$B(c) = \sum_i w_i \, p_i(c), \qquad w_i = \frac{\text{R}_i}{\sum_j \text{R}_j}, \qquad \sum_c p_i(c) = 1.$$

For a share, $p_i$ puts all its weight on one category. For an ETF, $p_i(c)$ is the
percentage in the provider's fact sheet divided by 100 (rescaled to sum to one). Providers
label sectors differently (ICB, Morningstar, Bloomberg), so each label is mapped to one
common set of sectors in `data/lookthrough.yaml`.
"""

GEO_WHAT = """
**Country** is where each company is based. For an ETF the fact sheet's country split is used.
For a JSE equity ETF the top holdings' own countries are used (Anglo American, for instance, is
a UK company), and the rest counts as South African.

**Currency** is the currency the underlying assets are priced in before conversion to rand.
JSE-listed shares and JSE equity ETFs are priced in rand. Offshore funds take the currencies of
their countries, and gold and platinum count as US dollars because that's how they're priced.
The rand value of anything not priced in rand moves with the exchange rate.
"""

GEO_MATHS = r"""
Countries use the same weighted average as sectors, $B(c) = \sum_i w_i\,p_i(c)$.
For a JSE equity ETF with published top holdings $h$ (weights $v_h$, summing to $V \le 1$):

$$p(c) = \sum_{h:\,\text{country}(h)=c} v_h \;+\; (1 - V)\,\mathbf{1}[c = \text{ZA}].$$

Currencies map each country to its currency (euro-area countries to EUR) and add up.
"""

EARN_WHAT = """
This asks **where the companies make their money**, which matters more than where they are
listed. A JSE share like Richemont or British American Tobacco earns almost everything offshore,
so when the rand weakens its rand price tends to rise: South African investors call this a
**rand hedge**. Miners selling gold, platinum or coal in dollars have South African costs but
dollar revenue, which is a partial hedge.

Each JSE company's label is a curated judgement (see `data/universe.yaml`). Offshore funds and
commodities count as offshore. For JSE ETFs only the published top holdings can be classified,
so the rest shows as *Not classified*.
"""

EARN_MATHS = r"""
Labels per share: *sa*, *sa\_dollar*, *africa*, *mixed*, *global*. Fund shares are
$B(c) = \sum_i w_i\,p_i(c)$, as for sectors. The **rand hedge** tilt measures
$B(\text{global}) + B(\text{sa\_dollar})$.
"""

CONC_WHAT = """
**Top five** is the share of your rands in your five biggest holdings. **Effective holdings**
says how many equal-sized holdings the fund behaves like: ten holdings where one is 90% of the
money behave like about 1.2 holdings.

The table opens up your ETFs to show the **companies** you end up owning, adding together what
you hold directly and what you hold through funds. The same company can turn up in several of
your holdings: that overlap is easy to miss. Only each ETF's published top holdings (usually ten)
can be seen, so the *through funds* figures are a minimum.
"""

CONC_MATHS = r"""
$$\text{Top five} = \sum_{i \in \text{5 largest}} w_i, \qquad
N_{\text{eff}} = \frac{1}{\sum_i w_i^2}.$$

Exposure to company $k$: $E_k = w_k^{\text{direct}} + \sum_{f\,\in\,\text{ETFs}} w_f\,v_{f,k}$,
where $v_{f,k}$ is $k$'s weight in fund $f$'s published top holdings.
A holding above """ + f"{DOMINANT:.0%}" + r""" of the rands is flagged as dominant.
"""

RISK_WHAT = """
Blue bars show each holding's share of your **rands**. Orange bars show its share of the
fund's **risk** (volatility). They differ because a holding that swings a lot, or moves in step
with everything else you own, adds more risk than its size suggests. A steady holding that
zigs when the rest zags can take up less risk than money, and occasionally less than zero (it
reduces the fund's risk).

When an orange bar is much longer than its blue bar, that holding drives the fund's ups and downs.
"""

RISK_MATHS = r"""
With weights $w$ and covariance matrix $\Sigma$ (weekly returns, annualised), fund volatility is
$\sigma_p = \sqrt{w^\top\Sigma w}$. Each holding's **Euler risk contribution** is

$$RC_i = \frac{w_i\,(\Sigma w)_i}{\sigma_p}, \qquad \sum_i RC_i = \sigma_p,$$

and its share of risk is $RC_i / \sigma_p$. These shares add to 100%. Holdings left out of the
statistics for lack of history get no risk bar.
"""

BETA_WHAT = """
A **beta** says how much your fund has tended to move when something else moves. A beta of
1.2 to the JSE Top 40 means that in a week the Top 40 rose 1%, your fund rose about 1.2% on
average; a beta of 0 means no consistent link.

The **US dollar in rand** row is the rand-hedge test: a positive beta means your fund has
tended to *gain* in rand when the rand weakened. Gold and commodities show how much the fund
rides on those prices.

Each dot is the best estimate and the whisker its **95% confidence interval**: the range of
betas consistent with the data. A whisker crossing zero means the history can't rule out *no*
link. Each row is a separate regression on the same weeks, so the rows overlap: a fund full of
JSE miners will show betas to the Top 40, gold *and* commodities at once.
"""

BETA_MATHS = r"""
For each factor $f$, ordinary least squares on weekly rand returns over the statistics window:

$$r_{\text{fund},t} = a + \beta\, f_t + \varepsilon_t .$$

Standard errors are **Newey-West (HAC)**, robust to autocorrelation and changing volatility,
with $L = \lfloor 4 (n/100)^{2/9} \rfloor$ lags:

$$\widehat{V}(\hat b) = (X^\top X)^{-1}\Big[\sum_t \hat u_t^2 x_t x_t^\top + \sum_{l=1}^{L}\Big(1-\tfrac{l}{L+1}\Big)
\sum_t \hat u_t \hat u_{t-l}\big(x_t x_{t-l}^\top + x_{t-l} x_t^\top\big)\Big](X^\top X)^{-1}\cdot\frac{n}{n-k}.$$

The interval is $\hat\beta \pm t_{0.975,\,n-2}\,\mathrm{se}(\hat\beta)$. $R^2$ is the share of the fund's
weekly variance the factor explains. Factors: Satrix 40 (Top 40 with dividends), SPY × USD/ZAR,
USD/ZAR, gold futures × USD/ZAR, and the Invesco DBC commodity ETF × USD/ZAR (a proxy: Yahoo has no
Bloomberg Commodity index).
"""

CORR_WHAT = """
Each square is the **correlation** between two holdings' weekly returns: +1 (red) means they
always move together, 0 (gray) no relationship, −1 (blue) they move in opposite directions.

The holdings are **reordered** so that ones that move alike sit next to each other, which makes
blocks of red stand out: each block is, in effect, one bet held several times over. Owning ten
holdings that all correlate at 0.9 diversifies much less than owning three that don't.
"""

CORR_MATHS = r"""
Correlations come from the covariance estimate chosen in *Assumptions and settings*:
$\rho_{ij} = \Sigma_{ij} / \sqrt{\Sigma_{ii}\Sigma_{jj}}$.

Ordering: hierarchical clustering with **average linkage** on the distance
$d_{ij} = \sqrt{(1-\rho_{ij})/2}$ (0 for perfectly correlated, 1 for perfectly opposite), with
optimal leaf ordering. Groups are cut at $d = \sqrt{(1-0.7)/2}$, so holdings in a group have an
average correlation of roughly 0.7 or more.
"""


def character(comp: Composition) -> None:
    st.subheader("Its character")
    if comp.tilts:
        st.markdown(" ".join(f":blue-badge[{t.label}]" for t in comp.tilts))
        for t in comp.tilts:
            st.markdown(f"- **{t.label}.** {t.detail}")
    else:
        st.markdown("No strong tilt by the measures used here: no sector, region or theme dominates.")
    asset = " · ".join(f"{ASSET_LABELS.get(a, a)} {v:.0%}" for a, v in comp.by_asset.items())
    st.caption(f"Asset mix: {asset}. {comp.lookthrough_share:.0%} of the rands sit in ETFs and are looked through.")
    with st.expander("How are these labels decided?"):
        rows = {"tech": "Technology sector", "resources": "Basic Materials + Energy", "banks": "Banks",
                "property": "Listed property", "precious": "Gold and platinum (the metals themselves)",
                "rand_hedge": "Earned offshore or in dollars", "sa_focus": "Earned mainly in South Africa"}
        st.markdown("Each label appears when its share of the whole fund reaches a threshold. The thresholds "
                    "are rules of thumb chosen for this app, not industry standards.")
        st.dataframe(pd.DataFrame([{"Label": k.replace("_", " "), "Measures": rows[k], "Threshold": f"{v:.0%}"}
                                   for k, v in TILTS.items()]), hide_index=True, width="stretch")
        st.caption("Banks are only separable where the fact sheet splits Financials into banks and insurers "
                   "(Satrix's ICB sector tables do; the 10X and Satrix Momentum sheets don't), so the bank share "
                   "can be understated.")


def what_it_owns(comp: Composition) -> None:
    st.subheader("What it owns, looked through")
    view = st.segmented_control("Break down by", ["Sector", "Country and currency", "Where earnings come from"],
                                default="Sector", key="comp_view") or "Sector"
    if view == "Sector":
        st.plotly_chart(charts.sector_sunburst(comp.sectors, ASSET_LABELS), config=CHART_CONFIG, key="sunburst")
        st.plotly_chart(charts.share_bars(comp.by_sector, "Sector"), config=CHART_CONFIG, key="sector_bars")
        C.chart_notes(SECTOR_WHAT, SECTOR_MATHS, "sector")
    elif view == "Country and currency":
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Country**")
            s = comp.by_country.rename(index=lambda c: COUNTRY_NAMES.get(c, c))
            st.plotly_chart(charts.share_bars(s, "Country"), config=CHART_CONFIG, key="country_bars")
        with c2:
            st.markdown("**Currency of the underlying assets**")
            st.plotly_chart(charts.share_bars(comp.by_currency, "Currency", colour_idx=1), config=CHART_CONFIG,
                            key="currency_bars")
        C.chart_notes(GEO_WHAT, GEO_MATHS, "geo")
    else:
        s = comp.by_earnings.rename(index=lambda k: EARNINGS_LABELS.get(k, k))
        st.plotly_chart(charts.share_bars(s, "Earnings"), config=CHART_CONFIG, key="earn_bars")
        C.chart_notes(EARN_WHAT, EARN_MATHS, "earn")


def concentration(comp: Composition, fund: Fund) -> None:
    st.subheader("Concentration")
    big, big_w = comp.largest
    c1, c2, c3 = st.columns(3)
    with c1.container(border=True, height="stretch"):
        st.metric("Top five holdings", C.pct(comp.top5, 0), help="Share of your rands in your five biggest holdings.")
    with c2.container(border=True, height="stretch"):
        n = 1 / float((comp.weights ** 2).sum())
        st.metric("Effective holdings", f"{n:.1f}", help="How many equal-sized holdings the fund behaves like.")
        st.caption(f"from {len(comp.weights)} actual holding{'s' if len(comp.weights) != 1 else ''}")
    with c3.container(border=True, height="stretch"):
        st.metric("Largest holding", C.pct(big_w, 0))
        st.caption(cached.name_of(big, fund))
    if comp.dominant:
        kind = "an ETF that spreads it further" if comp.profiles[big].looked_through else "a single company"
        st.warning(f"**{cached.name_of(big, fund)}** is {big_w:.0%} of the fund, more than {DOMINANT:.0%}. "
                   f"It is {kind}, so the fund's fortunes lean heavily on it.", icon=":material/balance:")

    co = comp.companies
    shown = co[co["total"] >= 0.005].head(15)
    if len(shown):
        st.markdown("**The companies you end up owning**")
        df = pd.DataFrame({
            "Company": shown["name"].values,
            "Total": shown["total"].values * 100,
            "Directly": shown["direct"].values * 100,
            "Through funds": shown["via_funds"].values * 100,
            "In how many of your holdings": shown["n_sources"].values,
        })
        top = max(float(df["Total"].max()), 1.0)
        st.dataframe(df, hide_index=True, width="stretch", column_config={
            "Total": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=top),
            "Directly": st.column_config.NumberColumn(format="%.1f%%"),
            "Through funds": st.column_config.NumberColumn(format="%.1f%%", help="A minimum: only each ETF's "
                                                           "published top holdings are visible."),
        })
        overlap = shown[(shown["n_sources"] > 1)]
        if len(overlap):
            names = ", ".join(overlap["name"].head(3))
            st.caption(f"Overlap: {names} {'appears' if len(overlap) == 1 else 'appear'} in more than one of your holdings.")
    C.chart_notes(CONC_WHAT, CONC_MATHS, "conc")


def risk_vs_money(fund: Fund) -> None:
    st.subheader("Risk versus money")
    if len(fund.weights()) < 2:
        st.caption("With one holding, it carries all the money and all the risk.")
        return
    with st.spinner("Estimating risk…"):
        cmp = cached.compare(fund, fund)
    stats = cmp.after
    if stats is None:
        st.info("Not enough price history to measure risk for these holdings yet.")
        return
    w = fund.weights()
    risk = stats.risk_shares * stats.coverage
    names = {t: cached.name_of(t, fund) for t in w.index}
    st.plotly_chart(charts.risk_vs_money(w, risk, names), config=CHART_CONFIG, key="rvm")
    gaps = (risk - w.reindex(risk.index)).dropna().sort_values(ascending=False)
    if len(gaps) and gaps.iloc[0] > 0.05:
        t = gaps.index[0]
        st.caption(f"**{names[t]}** carries {risk[t]:.0%} of the risk with {w[t]:.0%} of the rands.")
    for t, why in stats.excluded.items():
        st.caption(f"{names.get(t, t)} has no risk bar: {why}")
    C.chart_notes(RISK_WHAT, RISK_MATHS, "rvm")


def sensitivities(fund: Fund, comp: Composition) -> None:
    st.subheader("Sensitivities")
    with st.spinner("Running regressions…"):
        res = cached.sensitivities(fund)
    if not res or not res[0]:
        st.info("Not enough shared price history to estimate sensitivities (at least a year of weekly returns).")
        return
    single, joint, r2, n = res
    st.plotly_chart(charts.beta_forest(single), config=CHART_CONFIG, key="betas")
    by = {b.key: b for b in single}
    notes = []
    if "usdzar" in by:
        b = by["usdzar"]
        if b.significant:
            notes.append(f"In weeks the rand weakened 1% against the dollar, the fund tended to move {b.beta:+.2f}% "
                         f"in rand ({'it behaved like a rand hedge' if b.beta > 0 else 'the opposite of a rand hedge'}).")
            if b.beta < 0 and any(t.key == "rand_hedge" for t in comp.tilts):
                notes.append("That sits oddly with the *Rand hedge* label above, and both are true. The label is about "
                             "where the companies earn their money, which pays off over years as the rand drifts. "
                             "Week to week, the rand and South African shares often fall together when global "
                             "investors pull money out of emerging markets, so the short-run link can point the other way.")
        else:
            notes.append("No clear link to the rand–dollar exchange rate over this window.")
    best = max(single, key=lambda b: b.r2)
    notes.append(f"The {best.label} explains the most of the fund's weekly swings (R² {best.r2:.0%}).")
    for t in notes:
        st.caption(t)
    if st.toggle("Show as a table", key="beta_table"):
        st.dataframe(pd.DataFrame([{"Factor": b.label, "Beta": b.beta, "95% low": b.lo, "95% high": b.hi,
                                    "R²": b.r2 * 100, "Correlation": b.corr, "Weeks": b.n} for b in single]),
                     hide_index=True, width="stretch", column_config={
                         "Beta": st.column_config.NumberColumn(format="%.2f"),
                         "95% low": st.column_config.NumberColumn(format="%.2f"),
                         "95% high": st.column_config.NumberColumn(format="%.2f"),
                         "R²": st.column_config.NumberColumn(format="%.0f%%"),
                         "Correlation": st.column_config.NumberColumn(format="%.2f")})
    C.chart_notes(BETA_WHAT, BETA_MATHS, "beta")
    if len(joint) and st.session_state.get("maths_beta"):
        st.markdown(f"**All factors at once** (one regression, {n} weeks, R² {r2:.0%}). Each beta now holds the "
                    "other factors fixed, so overlapping factors share the credit and intervals widen.")
        jt = joint.rename(index={k: FACTORS[k][1] for k in joint.index})
        st.dataframe(jt.rename(columns={"beta": "Beta", "se": "Std error (HAC)", "lo": "95% low", "hi": "95% high"}),
                     width="stretch", column_config={c: st.column_config.NumberColumn(format="%.2f")
                                                     for c in ["Beta", "Std error (HAC)", "95% low", "95% high"]})


def moves_together(fund: Fund) -> None:
    st.subheader("Which holdings move together")
    if len(fund.weights()) < 2:
        st.caption("Add a second holding to see how your holdings move relative to each other.")
        return
    cmp = cached.compare(fund, fund)
    cov = cmp.est.cov
    if cov.shape[0] < 2:
        st.info("Not enough shared price history to compare holdings yet.")
        return
    cl = cluster(correlation(cov))
    names = {t: cached.name_of(t, fund) for t in cl.order}
    st.plotly_chart(charts.corr_heatmap(cl.corr, names), config=CHART_CONFIG, key="corr")
    if cl.groups:
        for g in cl.groups:
            sub = cl.corr.loc[g, g].to_numpy()
            avg = (sub.sum() - len(g)) / (len(g) * (len(g) - 1))
            share = fund.weights()[g].sum()
            st.caption(f"Move together (average correlation {avg:.2f}, {share:.0%} of the rands): "
                       + ", ".join(names[t] for t in g))
    else:
        st.caption("No group of holdings moves closely together (no average correlation of 0.7 or more).")
    C.chart_notes(CORR_WHAT, CORR_MATHS, "corr")


def sources(comp: Composition, fund: Fund) -> None:
    rows = []
    for t, p in comp.profiles.items():
        if not p.looked_through:
            continue
        e = cached.universe().get(t) or {}
        links = []
        for k, label in (("sectors_src", "sectors"), ("holdings_src", "top holdings"), ("countries_src", "countries")):
            s = p.sources.get(k)
            if s:
                links.append(f"[{label}]({s['url']}) as at {s['as_of']}")
        cost = f"TER {p.ter:.2%}" + (f", transaction costs {p.tc:.2%}" if p.tc else "") if p.ter else "no TER on file"
        rows.append(f"- **{cached.name_of(t, fund)}** ({t}), tracks {e.get('tracks') or 'no index'}; {cost}. "
                    + ("; ".join(links) if links else "No look-through sources.") + (f" {p.note}" if p.note else ""))
    with st.expander("Where these numbers come from"):
        if rows:
            st.markdown("\n".join(rows))
        st.caption("Shares use the curated sector, country and earnings labels in `data/universe.yaml`. ETF data "
                   "comes from each provider's fact sheet (Minimum Disclosure Document), copied on "
                   f"{cached.lookthrough_data().as_of}. Fact sheets lag by one to ten months, and holdings drift "
                   "between them.")
        if comp.weighted_ter:
            st.caption(f"Weighted ETF costs across the fund: TER {comp.weighted_ter:.2%} a year, plus transaction "
                       f"costs {comp.weighted_tc:.2%}. Brokerage and platform fees are extra (see *Reality check*, "
                       "coming next).")


# ---------------------------------------------------------------------------------

fund = state.active()
st.title("What kind of fund is it?")
C.disclaimer()

if not fund.holdings:
    st.info("This fund is empty. Add holdings on the **Build your fund** page, or open the example fund there.",
            icon=":material/lightbulb:")
    st.stop()

comp = cached.compose(fund)
st.caption(f"**{fund.name}** · {C.rand(fund.total_zar)} across {len(comp.weights)} "
           f"holding{'s' if len(comp.weights) != 1 else ''}")
character(comp)
what_it_owns(comp)
concentration(comp, fund)
risk_vs_money(fund)
sensitivities(fund, comp)
moves_together(fund)
sources(comp, fund)
