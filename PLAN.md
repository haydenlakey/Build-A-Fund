# PLAN: Build-a-Fund Lab

Living status document. Update whenever a phase finishes, a decision is made or
the plan changes. Full spec: [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md).

_Last updated: 2026-10-11 (Phase 2 steps 1–4 done; Phase 3 library part 1 done)_

## Phase status

| # | Phase (from the spec) | Status |
|---|---|---|
| 1 | Fund builder and core risk maths | **Done** (2026-10-09). 72 tests pass. Browser-checked at desktop and phone (dark mode didn't actually switch until the Phase 2 config fix). |
| 2 | Composition, risk and reality-check views | **In progress.** Steps 1–4 done (ETF data, composition, sensitivities + clusters, active bets); 118 tests pass. Next: step 5. |
| 3 | Library and insight pop-ups | **In progress (moved ahead at the user's request, 2026-10-09).** Library page + 15 sourced articles done; 145 tests pass. Next: case-file batch 2, then Phase 4. Glossary and pop-up rules engine still to do. |
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
- **Step 4:** `benchmarks:` section in `universe.yaml` (Top 40 = STX40, MSCI World = STXWDM, S&P 500 = SPY in rand,
  balanced proxy = 50/25/25 STX40/STXWDM/STXGOV). `active.analyse()` → `ActiveReport` (exact TE, TE budget, beta to
  benchmark, expected active return, IR, |a|-weighted rule-of-thumb TE). New page `views/active_bets.py`
  "Against a benchmark": benchmark picker (saved in `FundSettings.benchmark`, now a key; old ticker values fall
  back to top40), 4 metric tiles, active-weight diverging bars, TE-budget bars + table, one-bet warning, pairwise
  rule for biggest over vs under with a TE-target slider, maths for both rules of thumb.
- **Picker fix (user-reported):** after Add the search box kept the stock with no amount box, so holdings couldn't be
  resized. Widget keys now carry `picker_gen` (bumped in `apply()`); new holdings start with an empty amount (no
  R1000 default preview); held ones prefill their amount.
- Tests: `tests/test_factors.py` (10, incl. simulated CI coverage with AR(1) errors), 3 spike tests in `test_data.py`.
- Tests: `tests/test_lookthrough.py` (25, incl. a fires/stays-quiet fund per tilt), 2 new AppTests.
  `scripts/browser_check.py` now also screenshots the composition page (3 views) via a share link.

## Phase 2 plan

Pages: **What kind of fund is it?** (composition), **Risk detail**, **Reality check**, plus the diversifier
explorer and side-by-side comparison. In order:
1. ~~Research and add JSE ETF look-through data~~ Done (JSE `tracks` resolved; US `tracks: null` left: not verified).
2. ~~`fundlab/lookthrough.py` + composition page~~ Done.
3. ~~`fundlab/factors.py` + clustered correlation heatmap~~ Done.
4. ~~Active bets view~~ Done.
5. Risk detail: VaR/ES 3 ways side by side, simulated rand distribution, fan chart, stress tests
   (2008, Dec 2015, Mar 2020, 2022, Jul 2026), drawdown and rolling vol, leverage toggle.
6. Reality check: costs drag (TER + editable brokerage, R lost over 10/20 years), backtest vs Top 40,
   S&P 500 in rand, balanced proxy, equal-weight, with rebalancing; optimiser comparison with caveats.
7. Explore diversifiers; side-by-side fund comparison.

### Phase 3: delivered so far (library part 1, commit a29b29e)

- `content/library/*.md`: YAML header (title, section, group, order, years, summary, lesson, related, chart,
  sources [{title, url, accessed}]) + Markdown body. Loaded by `fundlab/content.py` (no Streamlit).
- `views/library.py` "Library": search, sections (Why we invest, How bubbles work, Case files grouped by the 9 lesson
  groups, When patience paid, Sector histories, Theory), article view with lesson callout, chart, related links,
  numbered dated sources. `?article=<slug>` deep links. Charts: `kind: prices` (bundled sample, rebased to 100) or
  `kind: points` (sourced values baked into the file, for pre-2003 or delisted series).
- Written (15): why-we-invest, five-phases, diversification, efficient-frontier, risk-contribution, tracking-error,
  information-ratio, leverage, fees, estimation-error, dot-com, ltcm, african-bank, nenegate, buffett-bet.
- `tests/test_content.py`: every article sourced (https + accessed date), related links resolve, case files have
  group/lesson/years/chart, chart data present, no advice phrasing. 2 AppTests for the library.
- Content rule kept: only figures read on a fetched page (or computed from the app's data, labelled so) go in.
  Two drafts had unsupported sentences; they were cut or re-sourced. Many news sites (Reuters, BBC, FT, CNBC,
  etfsa, IOL) block fetching; Fin24 links redirect to the News24 home page, so avoid citing them.

### Research gathered for case-file batch 2 (not yet written; all accessed 2026-10-09)

- **Situational Awareness (Leverage, 2026):** Quartz via Yahoo, 31 Jul 2026
  https://finance.yahoo.com/markets/stocks/articles/leopold-aschenbrenners-ai-hedge-fund-174426079.html : peaked $45bn
  start of July, ~$10bn after; up to 400% leverage; margin calls, prime brokers BofA, Goldman, JPMorgan; Citadel bought
  public positions below market; long AI infrastructure / short software (Adobe); Nebius, SanDisk, Micron, CoreWeave
  each −35%+ in July; >1,000% since July 2024 inception (WSJ). Crypto Briefing 3 Aug 2026 (via Fortune)
  https://cryptobriefing.com/situational-awareness-67-percent-loss-citadel-sale/ : −67% in July, ~$16bn book sold at
  ~10% discount. Yahoo/CNBC 30 Jul 2026
  https://finance.yahoo.com/markets/stocks/articles/situational-awareness-sells-public-equities-140824582.html :
  "roughly $20 billion to $24 billion vehicle"; 439% net through 30 Jun (FT). Present size as a range (decision).
  Chart idea: kind prices [MU, CRWV, NVDA] May–Sep 2026 (in rand).
- **Steinhoff (Fraud):** https://en.wikipedia.org/wiki/Steinhoff_International : Jooste resigned 5 Dec 2017; shares lost
  almost 90% within two weeks; −96% by Mar 2019 (~$15bn market value); PwC: fictitious/irregular transactions over
  €6.5bn 2009–2017; 90+ lawsuits; ~R25bn retail settlement pot; delisted Oct 2023. No Yahoo prices (delisted): use a
  points chart indexed to 100 from those reported falls, clearly labelled.
- **MTI (Fraud):** CFTC release 8696-23 https://www.cftc.gov/PressRoom/PressReleases/8696-23 (order 24 Apr 2023):
  ≥29,421 BTC worth >$1.73bn (end Mar 2021) from ≥23,000 US individuals and more worldwide; all misappropriated;
  the "bot" was false; $1.73bn restitution + same penalty, largest CFTC penalty; Steynberg detained in Brazil since
  Dec 2021. Finance Magnates 1 Jan 2021
  https://www.financemagnates.com/cryptocurrency/news/south-african-bitcoin-trader-mti-enters-liquidation-ceo-on-run/ :
  promised "at least 10 percent monthly return"; FSCA: "illegal operation, misleading clients"; ~R9.45bn from ~28,000
  investors (estimate). Chart idea: points of what 10%/month compounding would imply (a calculation, labelled).
- **Woodford (Liquidity):** FCA press release 5 Aug 2025
  https://www.fca.org.uk/news/press-releases/fca-fines-over-woodford-equity-income-fund/printable/print :
  £10.1bn (May 2017) → £3.6bn before the June 2019 suspension; only 8% sellable within 7 days; sold liquid, bought less
  liquid; fines £40m WIM, £5,888,800 Woodford (referred to Upper Tribunal); £230m redress from Link. Trigger: £237m Kent
  County Council redemption (ii.co.uk / Trustnet; fetch one before citing). Chart: points (fund size).
- **SA listed property 2018 (Sector collapses):** Morningstar via FAnews, 17 Jan 2019
  https://www.fanews.co.za/article/investments/8/general/1133/sa-property-sector-what-happened-and-where-to-from-here/26034 :
  the Resilient group was >40% of SAPY before the collapse; asset class −25.2% in 2018. Yahoo: ^J253.JO 694.7
  (29 Dec 2017) → 478.2 (31 Dec 2018), price only; RES.JO 12638.6c → 5312.9c (−58%). Regenerate monthly points
  2017–2020 with yfinance. FSCA probe from Mar 2018 (BusinessLive 14 Dec 2018; verify before citing).
- **March 2020 (Shocks):** WHO 11 Mar 2020
  https://www.who.int/news-room/speeches/item/who-director-general-s-opening-remarks-at-the-media-briefing-on-covid-19---11-march-2020
  ("can be characterized as a pandemic"). App data (weekly): ^J200 −30.3% 14 Feb → 20 Mar; USD/ZAR 14.90 → 19.10
  peak (24 Apr); SPY in rand −21% at worst; TLT in rand +28.5% by 20 Mar; gold ETF in rand +11% by 20 Mar. Chart:
  kind prices [^J200.JO, SPY, TLT, GLD.JO, ZAR=X] 2020-02-14 to 2020-06-26.
- **2022 stock-and-bond sell-off (Inflation and rates):** BLS https://www.bls.gov/news.release/archives/cpi_07132022.htm
  (CPI +9.1% y/y June 2022, largest since Nov 1981); Fed
  https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm (16 Mar 2022: 1/4–1/2%) and
  https://www.federalreserve.gov/newsevents/pressreleases/monetary20221214a.htm (14 Dec 2022: 4-1/4–4-1/2%).
  Yahoo USD total returns 2022: SPY −18.2%, TLT −31.2%, AGG −13.0%. In rand (app data): SPY −12.9%, TLT −26.8%,
  STX40 ~0%, STXGOV −2.8%.
- Code TODO for these: let `kind: points` charts take several named lines (`lines: {name: [[date, value], ...]}`)
  for the property chart; allow 2-point series (Woodford) in `test_charts_have_data`.

## Architecture (as it exists)

```
Build A Fund/
├── app.py                 # entry: page config, st.navigation, sidebar (fund manager + settings)
├── views/                 # pages (not pages/, to avoid Streamlit's legacy auto-pages)
│   ├── build.py           # Build your fund (centrepiece)
│   ├── composition.py     # What kind of fund is it? (look-through, tilts, concentration, risk vs money, betas, clusters)
│   ├── active_bets.py     # Against a benchmark (active weights, TE, TE budget, rules of thumb)
│   ├── library.py         # Library (articles from content/library)
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
│   ├── factors.py         # OLS + Newey-West betas, correlation clustering
│   ├── content.py         # library article loader (YAML header + Markdown)
│   └── verdict.py         # plain-language verdict
├── content/library/*.md (library articles)
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
- **Active bets are measured per holding against the benchmark's components** (no look-through into Top 40
  constituents: that would cut the history window to 2023, when Richemont listed on the JSE). It is exact for TE because
  r_F − r_B = a'r. A fund's own Satrix 40 nets against a Top 40 benchmark; direct Naspers is a bet on top of the index.
- Rule-of-thumb inputs: |a|-weighted average vol and |a_i a_j|-weighted average pairwise correlation.
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

1. Phase 3 case-file batch 2 from the research above (Situational Awareness, Steinhoff, MTI, Woodford, SA property
   2018, March 2020, 2022), so every lesson group has at least one file. Commit.
2. **Phase 4** (the user asked for it next): due-diligence checklists by holding type; unit trusts (price history,
   upload, or allocation model; look-through and overlap); unlisted holdings (stated assumptions, illiquid sleeve,
   included in Monte Carlo/scenarios, illiquid share). See spec sections 8 and 9.
3. Later: remaining case files (44 approved), glossary tooltips and the pop-up rules engine (Phase 3), then Phase 2
   steps 5–7.

Phase 2, step 5 (when resumed): Risk detail page: VaR/ES three ways side by side (historical, parametric, Monte Carlo
normal/t; maths in `fundlab/var.py`), simulated rand distribution, fan chart, stress tests (2008, Dec 2015, Mar 2020,
2022, Jul 2026; use ^J200.JO for long history), drawdown and rolling vol, leverage toggle (2x/4x: drawdowns,
chance of wipe-out, forced selling).
