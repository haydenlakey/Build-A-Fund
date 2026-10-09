# PLAN: Build-a-Fund Lab

Living status document. Update whenever a phase finishes, a decision is made or
the plan changes. Full spec: [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md).

_Last updated: 2026-10-09 (Phase 2, steps 1–3 done)_

## Phase status

| # | Phase (from the spec) | Status |
|---|---|---|
| 1 | Fund builder and core risk maths | **Done** (2026-10-09). 72 tests pass. Browser-checked at desktop and phone (dark mode didn't actually switch until the Phase 2 config fix). |
| 2 | Composition, risk and reality-check views | **In progress.** Steps 1–3 done (ETF data, composition page, sensitivities + correlation clusters); 111 tests pass. Next: step 4. |
| 3 | Library and insight pop-ups | Not started |
| 4 | Due diligence, unit trusts and unlisted holdings | Not started |
| 5 | Fact sheet and polish | Not started |

### Phase 1: what was delivered

- `fundlab/` (pure Python): estimators, risk, VaR/ES (3 ways), frontier, active bets, model, data, analysis, verdict
- `data/universe.yaml` (125 holdings + 8 factors) and `data/sample/prices_native.parquet` (129 series × 1 658 weeks, 1995-01-06 → 2026-10-09)
- `scripts/build_sample.py` and a weekly GitHub Action to refresh the sample (untested until the repo is on GitHub)
- App: `app.py` (navigation + sidebar: fund picker, New/Copy/Delete, save to file, open file, share link,
  assumptions and settings including a visible seed), `views/build.py`, `views/about.py`
- Build page: search the universe or any JSE/US ticker → rand amount → live preview with **verdict**,
  **before/after metric cards** (change highlighted, rounding-to-zero shown neutral), **risk-return chart**
  (holdings, shared efficient frontier, hollow "before", orange "after", arrow, **▶ Replay the move** animation),
  "What am I looking at?" + "Show me the maths" (LaTeX), history-window notes and warnings, holdings table with
  share of rands vs share of risk. Nothing changes until the user presses Add/Apply.
- Tests: `test_maths.py` (30), `test_data.py` (22), `test_analysis.py` (13), `test_app.py` (7, headless AppTest)
- `scripts/browser_check.py`: Playwright screenshots at 3 viewports + console-error check + animation check

### Moved from phase 1 to phase 2 (as in the original plan table)

- Compare funds side by side (funds can already be duplicated, saved and loaded)
- "Explore diversifiers" from the preset universe

### Phase 2: delivered so far

- **Step 1 (ETF research):** all 31 JSE ETFs now have `tracks`, `ter`, `tc` in `universe.yaml` (sources by provider
  in its header). New `data/lookthrough.yaml`: per ETF/index sector split (published labels + `sector_map` to the
  app's Morningstar sectors), top holdings with tickers (for overlap), countries, `currency_of_country`, and a
  `{url, as_of, accessed}` source on every block. `use:` lets an ETF inherit from the index it tracks.
  Covers the 16 US ETFs too (yfinance `funds_data`).
- **Step 2:** `fundlab/lookthrough.py` (profiles per holding → fund breakdowns by asset/sector/industry, country,
  currency, earnings exposure; company overlap direct + through funds; tilts; concentration; weighted TER/TC)
  and `views/composition.py` "What kind of fund is it?": tilt badges + explanation, sunburst (asset → sector,
  tap for industry) + sector bars, country and currency bars, earnings-exposure bars, concentration tiles +
  dominance warning + "companies you end up owning" table, risk-vs-money paired bars, sources expander.
- **Step 3:** `fundlab/factors.py`: single-factor betas (OLS, Newey-West HAC errors, t intervals, R²) to Top 40
  (STX40.JO), S&P 500 in rand, USD/ZAR, gold in rand, DBC in rand; a joint regression (shown under "Show me the
  maths"); correlation clustering (average linkage on sqrt((1-ρ)/2), optimal leaf order, groups at ρ ≈ 0.7).
  Composition page gains **Sensitivities** (dot-and-whisker chart + table toggle + rand-hedge reading) and
  **Which holdings move together** (clustered heatmap, diverging blue/gray/red tokens in `ui/theme.py`).
- **Data fix (affects Phase 1 numbers):** Yahoo's ZAR=X has isolated bad ticks (14.86 on 15 Nov 2024 between
  17.28 and 18.10; 15.43 on 17 Jan 2025). `data.remove_spikes` now repairs FX series daily on download and weekly
  on load. USD/ZAR vol for 2024–25 dropped from ~28% to ~10% a year; STX500 vs SPY-in-rand correlation 0.56 → 0.83.
- Tests: `tests/test_factors.py` (10, incl. simulated CI coverage with AR(1) errors), 3 spike tests in `test_data.py`.
- Tests: `tests/test_lookthrough.py` (25, incl. a fires/stays-quiet fund per tilt), 2 new AppTests.
  `scripts/browser_check.py` now also screenshots the composition page (3 views) via a share link.

## Phase 2 plan

Pages: **What kind of fund is it?** (composition), **Risk detail**, **Reality check**, plus the diversifier
explorer and side-by-side comparison. In order:
1. ~~Research and add JSE ETF look-through data~~ Done (JSE `tracks` resolved; US `tracks: null` left: not verified).
2. ~~`fundlab/lookthrough.py` + composition page~~ Done.
3. ~~`fundlab/factors.py` + clustered correlation heatmap~~ Done.
4. Active bets view: benchmark picker, active weights, TE, TE budget, rule-of-thumb comparisons (maths already in `active.py`).
5. Risk detail: VaR/ES 3 ways side by side, simulated rand distribution, fan chart, stress tests
   (2008, Dec 2015, Mar 2020, 2022, Jul 2026), drawdown and rolling vol, leverage toggle.
6. Reality check: costs drag (TER + editable brokerage, R lost over 10/20 years), backtest vs Top 40,
   S&P 500 in rand, balanced proxy, equal-weight, with rebalancing; optimiser comparison with caveats.
7. Explore diversifiers; side-by-side fund comparison.

## Architecture (as it exists)

```
Build A Fund/
├── app.py                 # entry: page config, st.navigation, sidebar (fund manager + settings)
├── views/                 # pages (not pages/, to avoid Streamlit's legacy auto-pages)
│   ├── build.py           # Build your fund (centrepiece)
│   ├── composition.py     # What kind of fund is it? (look-through, tilts, concentration, risk vs money)
│   └── about.py           # About and data
├── ui/                    # Streamlit-only helpers
│   ├── state.py           # session funds, active fund, example fund, share-link parse/build
│   ├── cached.py          # cached universe/PriceStore, labels, cached compare()
│   ├── charts.py          # risk_return() Plotly figure with frames + Replay button
│   ├── components.py      # disclaimer, chart_notes (what/maths), metric_panel, rand/pct formatting
│   └── theme.py           # light/dark palette (reference data-viz palette), base Plotly layout
├── fundlab/               # pure Python, never imports Streamlit
│   ├── __init__.py        # PERIODS_PER_YEAR = 52
│   ├── estimators.py      # returns, mean (+ target shrinkage, equal_sharpe_target, SE), sample/LW/EWMA cov
│   ├── risk.py            # vol, Euler RCs, risk shares, Sharpe, div ratio, eff. holdings, drawdown, avg corr
│   ├── var.py             # parametric (normal/t), historical, Monte Carlo VaR/ES
│   ├── frontier.py        # long-only frontier (warm-started SLSQP), efficiency_gap
│   ├── active.py          # active weights, TE, TE budget, pairwise bet, rule of thumb
│   ├── model.py           # Holding, FundSettings, Fund, JSON + share codes
│   ├── data.py            # Universe, quote units, cleaning, weekly resample, FX, download, PriceStore
│   ├── analysis.py        # history_window, estimate, FundStats, compare (shared window + frontier)
│   ├── lookthrough.py     # ETF look-through profiles, breakdowns, overlap, tilts, concentration
│   └── verdict.py         # plain-language verdict
├── data/universe.yaml, data/lookthrough.yaml, data/sample/{prices_native.parquet, meta.json}, data/cache/ (git-ignored)
├── scripts/build_sample.py, scripts/browser_check.py
├── tests/ (test_maths, test_data, test_analysis, test_app), pytest.ini
├── .streamlit/config.toml # theme primaryColor blue
├── .github/workflows/refresh-data.yml
└── requirements.txt (pinned), requirements-dev.txt (+ playwright)
```

Not yet created: `content/` (library Markdown, glossary.yaml, rules.yaml), further views.

## Data model

- **Holding**: `ticker, name, kind, amount_zar, currency="ZAR", method="price_history"`.
  `kind` ∈ jse_share, jse_etf, us_share, us_etf, unit_trust, unlisted. `method` ∈
  price_history, uploaded, allocation_model, assumptions. Negative amounts are rejected.
- **FundSettings**: `lookback_years=5, cov_method="ledoit_wolf", mean_shrinkage=0.5, prior_sharpe=0.3,
  risk_free=0.07, var_alpha=0.95, var_horizon_weeks=4, seed=42, benchmark="STX40.JO"`.
  Unknown keys in a loaded file are ignored; missing keys take defaults.
- **Fund**: `name, holdings, objective, settings, id`. `weights()`/`amounts()` merge duplicate tickers, drop zeros.
  Edits return new Funds. JSON with `schema_version = 1`. Share code = zlib + URL-safe base64 (`?fund=`).
- **Universe entry** (`universe.yaml`): ticker, name, sector, industry/region, country, exposure
  (sa / sa_dollar / africa / mixed / global), themes, optional `history_from`, `tracks`, `ter`.
  `kind` and `currency` are added on load.
- Still to add (phase 4): unlisted parameters (`exp_return, low, high, lockin_years, p_total_loss, assumed_corr`).

## Decisions made

Agreed with the user (2026-10-08):
- Stack: Streamlit + Plotly, pure-Python `fundlab` core, Streamlit Community Cloud. Zero cost.
- Case-file list approved (44 files, 10 groups; below).
- Situational Awareness: report the conflicting figures as a sourced range (about $20bn vs about $45bn AUM; about $16bn
  public book sold to Citadel at roughly a 10% discount), not a single "$45bn→$10bn" figure.
- A weekly GitHub Action refreshes the bundled data. The repo will be public.
- A new "Liquidity and locked money" lesson group (for the "can't sell in a hurry" rule).

Accepted with the plan:
- **Weekly returns** (JSE/US close at different times, which biases daily cross-market correlations).
- **Short-history rule**: shared window; exclude a holding with < 52 weekly returns in it; warn if the window is
  < 156 weeks. Before/after use the window of the union of both versions. (The planned "override to include
  a short holding" is **not built yet**.)
- Benchmark proxies: Top 40 = STX40.JO (or ^J200.JO for long history); S&P 500 in rand = SPY × USDZAR;
  balanced = transparent ETF mix, labelled as a proxy.
- Unlisted correlation with listed equity user-set, default 0.5.
- Bundled data is primary on Streamlit Cloud; live fetching is a bonus.
- Fact-sheet PDF: fpdf2 + matplotlib. Glossary tooltips must open on tap.

Made during build (2026-10-09):
- **Data pipeline:** daily closes resampled to Friday week-ends (Yahoo's weekly bars use inconsistent anchors);
  store native units after cleaning (JSE ÷100); USD→ZAR on load; indices are points; total-return prices.
- **Mean shrinkage toward an equal-Sharpe prior** rf + S·σᵢ (S = 0.3, a = 0.5, both editable). Shrinking toward the
  cross-sectional mean made the "before" fund move with the previewed candidate (12.9% vs 21.6%).
- **Efficiency gap against one shared frontier** (union of before and after holdings). Per-fund frontiers made every
  addition look like a move away from efficient. `compare()` skips the per-fund frontiers (7 s → 1.1 s).
- Universe sectors use Yahoo/Morningstar names for JSE and US alike; JSE rows curated (Naspers/Prosus = Technology).
- Commodity factor = DBC in rand (no ^BCOM on Yahoo). Gold = GC=F in rand.
- Ad-hoc tickers: only JSE (.JO) and US-listed (`data.is_supported`).
- Verdict wording describes, never recommends (a test bans buy/sell/should/recommend).
- Pages live in `views/` and are registered with `st.navigation`.
- Theme primary colour is blue (#2a78d6), so neutral progress bars don't read as alarms.
- VaR on the Build page is parametric normal, with the horizon/confidence from settings; historical VaR is computed
  (`FundStats.var_hist`) but only shown in Phase 2's risk page.
- *(inferred)* Ledoit-Wolf shrinks toward the constant-correlation target; EWMA λ = 0.97 weekly; MC rebalances weekly,
  t innovations share one chi-square draw; risk-free 7% is a placeholder assumption.

Made in Phase 2 (2026-10-09):
- **Look-through lives in `data/lookthrough.yaml`** (not inline in `universe.yaml`, which keeps one line per
  holding); costs stay on the universe line. ETFs inherit from index records via `use:`.
- **Offshore index sector splits use US-listed ETF proxies** (SPY, QQQ, URTH, EEM, MCHI, EWJ, FEZ; MSCI USA uses
  SPY) via yfinance, so every sector label is Morningstar like the rest of the app. Fund sheets use mixed schemes
  (10X uses Bloomberg BICS, which lumps healthcare into "consumer non-cyclical").
- **TER = 1-year figure** where a sheet gives 1-year and 3-year. **Sygnia offshore ETFs: "Broker/Other platform"
  TER** (what an EasyEquities buyer pays), not the cheaper Sygnia Alchemy figure. NewGold: "annual sales charge";
  1nvest Gold: 0.25% management fee ex VAT (no TER published).
- **Country** = where a company is based (top holdings refine JSE ETFs); **currency** = what the underlying is
  priced in (JSE-listed shares and SA ETFs = ZAR; gold/platinum = USD); **earnings** (curated `exposure`) carries
  the rand-hedge story. The SA ETF remainder beyond top holdings is "Not classified" rather than guessed.
- **Tilt thresholds** (share of the whole fund): tech ≥ 25%, resources (Basic Materials + Energy) ≥ 25%,
  banks ≥ 15%, property ≥ 20%, precious metals ≥ 15%, rand hedge (global + sa_dollar earnings) ≥ 50%,
  mostly SA ≥ 80%; dominant holding > 20%. App rules of thumb, shown to the user as such (`lookthrough.TILTS`).
- **Sunburst shows two rings** (asset → sector); the industry ring appears on tap. Colour = asset class only (≤ 5 hues).
  Other breakdowns are single-hue horizontal bars (dataviz guidance: part-to-whole with many classes → bars).
- **Dark mode fix:** `.streamlit/config.toml` uses `[theme.light]`/`[theme.dark]` primaryColor. A top-level
  `[theme] primaryColor` made Streamlit build one custom light theme and ignore the visitor's dark setting.
- **Betas are single-factor regressions** (one per factor, easiest to read); the joint regression is extra detail.
  Factor series need ≥ 52 overlapping weeks. The Top 40 factor is STX40.JO (total return, from 2009).
- **FX spike rule:** a point > 8% (weekly; 5% daily) from both neighbours in the same direction while the
  neighbours are within 6% (2% daily) is interpolated. FX only: volatile shares (Micron, gold miners) genuinely
  jump and reverse, and a share-level filter flagged dozens of real weeks.
- When the *Rand hedge* tilt (earnings) and a negative USD/ZAR beta (weekly co-movement) disagree, the page explains
  why both can be true instead of hiding one.
- The browser check ignores Streamlit's own 404 probes of `<page>/_stcore/*` on deep links (benign; it falls back).

## Research done so far

- **Top 40** (41 lines incl. Investec Ltd + PLC) as at 8 Oct 2026, from https://satrix.co.za/products/product-details?id=44
  (accessed 2026-10-08). STX40 TER 0.10% on the same page.
- **Situational Awareness** and the **July 2026 AI sell-off** confirmed 2026-10-08. Sources: Quartz
  (qz.com/situational-awareness-hedge-fund-margin-call-citadel-fire-sale-073126), Yahoo Finance, CNBC 5 Aug 2026
  and 21 Aug 2026, Crypto Briefing, SpotGamma, NBC News (Nasdaq-100 correction 28 Jul), CNBC 29 Jul (chip
  sell-off), Bloomberg 28 Jul, XTB 7 Jul. Copy the full URLs into the case files when writing them.
- US sector/industry/country and US ETF expense ratios: Yahoo Finance via yfinance (accessed 2026-10-09).
- **JSE ETF fact sheets (2026-10-09):** Satrix MDDs (`satrix.co.za/fund/mdd/<code>`, 31 Aug 2026) and product-page
  sector tables (`product-details?id=N`; ids in `lookthrough.yaml`); Sygnia via iTransact (31 Jul 2026); 10X via
  `assetmanagement.10x.co.za/wp-content/uploads/2026/08/` (31 Jul 2026); 1nvest, NewGold and SYGEU via
  EasyEquities' resource site (Oct–Dec 2025: **older**, because etfsa.co.za returns 403 to scripts and the
  1nvest/NewGold sites block them). MSCI EM country weights: MSCI factsheet, 30 Sep 2026.
  Tip: `pdftotext -raw` reads Satrix/Sygnia/10X sheets; 1nvest needs word coordinates (pdfplumber).

## Approved case-file list (44)

- **Bubbles and manias:** Tulip mania 1637 (with Goldgar's revisionist view) · Mississippi Bubble 1720 · South Sea 1720 · Railway Mania 1840s · 1929 · Nifty Fifty 1972–74 · Japan 1989 · Dot-com 2000 · Crypto 2021–22 · July 2026 AI chip sell-off (still unfolding)
- **Leverage and forced selling:** LTCM · 2008 · Volmageddon/XIV 2018 · Archegos · UK LDI 2022 · Situational Awareness 2026
- **Inflation and rates:** 1970s stagflation · Volcker shock · 2022 stock-and-bond sell-off
- **Currency and country:** 1997 Asian crisis · 1998 Russia default and rand crisis · 2001 rand collapse · Dec 2015 Nenegate · Zimbabwe · Argentina 2001 · Russia 2022
- **Fraud and governance:** Enron · Madoff · Wirecard · Steinhoff · Tongaat Hulett · MTI · Sharemax
- **Banks and credit:** Lehman · SA small-bank crisis 2002 · African Bank 2014 · VBS 2018 · SVB and Credit Suisse 2023
- **Sector collapses:** SA listed property 2018 · Commodity slump 2014–16 · Platinum's decline · Telecoms bust 2000–02 · Negative oil April 2020
- **Shocks:** 1987 · 2010 Flash Crash · March 2020
- **Liquidity and locked money:** Woodford 2019 · UK property fund suspensions 2016/2020
- **Counterexamples:** Century of US equities · Long-run JSE real returns · Buffett's bet · First index fund and SPIVA SA · Buying through 2008–09

## Known bugs and issues

- **Cold start is slow on this machine:** importing the stack takes about 20 s on the first run (probably antivirus
  scanning the venv). Each interaction then takes about 1.5 s. Check on Streamlit Cloud.
- **Fund marker can hide a holding's label** on the risk-return chart when they coincide (e.g. "STX500" on a phone).
  Phase 5 polish.
- **The arrow is invisible for very small moves** (markers overlap); Replay still shows the motion.
- **Holdings table on phones:** Ticker/Type scroll off to the right (by design: key columns first).
- `Fund.with_amount` defaults `kind="jse_share"`; the Build page passes the universe kind, but other callers must too.
- **Data limits:** USD/ZAR from Dec 2003 only; JSE shares from 2000 at the earliest; STX40.JO from 2009; STXGOV.JO
  (SA bonds) from May 2020; short JSE listings (CFR 2023, BHG 2022, NPH 2021, SSW 2020, PRX 2019); CRWV from 2025.
  OUT.JO before 2011-03-18 is a predecessor company (cut via `history_from`). Six ETF tickers return nothing
  (STXSWX, SYGSW4, DIVTRX, NFEMOM, NFTRCI, PTXTEN).
- The GitHub Action and Streamlit Cloud deployment are untested (no GitHub repo yet).
- CRLF warnings on commit (Windows). Harmless; add `.gitattributes` if they get annoying.
- **Stale ETF sheets:** 1nvest (ETFT40, ETFSWX, ETF500, ETFGLD), NewGold (GLD, NGPLT) and SYGEU data date from
  Oct–Dec 2025. Refresh by hand from etfsa.co.za when a browser is available.
- ETFSWX has no published sector table (chart only): its sector view uses top holdings + "Not disclosed".
- Bank share is understated for ETFs whose sheets only give ICB industries (CTOP50, STXMMT: "Financials").
- VT, VEA, VWO, SMH have no sourced country split (shown as "Other or global").

## Open questions

- Risk-free default (7%): replace with a sourced current SA 91-day T-bill yield (with date), or keep it as a labelled assumption.
- A longer free SA government bond series for the balanced benchmark (STXGOV.JO starts 2020).
- Should a user be able to force-include a holding with < 52 weeks of history (planned override, not built)?
- GitHub repo name/visibility, and when to deploy to Streamlit Community Cloud (needs the user's GitHub account).

## Next step

Phase 2, step 4: active bets view (benchmark picker: Top 40, balanced proxy, global; active weights, tracking
error, each bet's share of the TE budget, rule-of-thumb versions beside the exact calculation; maths already in
`fundlab/active.py`). Benchmarks need look-through weights for overlap (e.g. Top 40 holdings vs a fund's shares).
