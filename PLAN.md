# PLAN: Build-a-Fund Lab

Living status document. Update whenever a phase finishes, a decision is made or
the plan changes. Full spec: [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md).

_Last updated: 2026-10-11 (Phase 4 done; Phase 2 steps 1–6 done; Phase 3 library parts 1–2 done: 22 articles)_

## Phase status

| # | Phase (from the spec) | Status |
|---|---|---|
| 1 | Fund builder and core risk maths | **Done** (2026-10-09). 72 tests pass. Browser-checked at desktop and phone (dark mode didn't actually switch until the Phase 2 config fix). |
| 2 | Composition, risk and reality-check views | **In progress.** Steps 1–6 done (ETF data, composition, sensitivities + clusters, active bets, risk detail, reality check); 320 tests pass. Next: step 7 (diversifier explorer, side-by-side comparison). |
| 3 | Library and insight pop-ups | **In progress (moved ahead at the user's request, 2026-10-09).** Library page + 22 sourced articles (every lesson group has at least one case file); 167 tests pass. Next: Phase 4. Glossary and pop-up rules engine still to do. |
| 4 | Due diligence, unit trusts and unlisted holdings | **Done** (2026-10-11). 281 tests pass. Browser-checked (desktop, phone, dark). |
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
- **Step 5 (2026-10-11): Risk in detail** (`views/risk.py`, between "Against a benchmark" and "Library").
  - *How sure can we be?*: expected return with its rough 95% range (±1.96 SE) as a warning callout; fund
    volatility under all three covariance estimates side by side (the one in use marked).
  - *VaR and ES three ways*: table of historical, parametric normal/t, Monte Carlo normal/t (+ a "whole fund, with
    unlisted" row from `unlisted.simulate_paths`) in % and rand; simulated rand-outcome histogram with the tail
    beyond VaR in orange, VaR/ES lines. Page-level "Shocks in the simulations" (normal / Student-t) and t degrees
    of freedom (default 5) drive the charts.
  - *Fan chart*: 5 000 paths over 1/3/5/10 years, 5–25–50–75–95 bands; whole fund (unlisted, buy and hold) when the
    fund has unlisted holdings.
  - *Stress tests* (`fundlab/stress.py`, episodes in editable `content/stress_tests.yaml`): buy-and-hold replay of
    the measured weights vs Top 40 index and S&P 500 in rand; bars + table (return, lowest point, measured share,
    weak estimates, whole fund with unlisted) + week-by-week chart per episode + holding table + library link.
  - *Falls from the top* (drawdown) and *Risk changes over time* (rolling vol, 13/26/52 weeks).
  - *Borrowing to invest* (`fundlab/leverage.py`): 1×/1.5×/2×/3×/4×, borrowing rate (default rf + 3 pp, labelled
    an assumption), margin-call level (default half the starting equity share). History replay chart with forced
    sales marked + 4 tiles; next-year table from 20 000 simulated years (wipe-out, margin call, median, 5th
    percentile, typical worst fall), no borrowing vs chosen multiple. Leverage is page-local (not saved in the fund).
  - `var.simulate_weekly` (paths kept; `simulate_paths` now compounds it, same draws as before), `var.fan`,
    `unlisted.simulate_paths` (`simulate` = its last column), cached wrappers in `ui/cached.py`, 7 charts in `ui/charts.py`.
  - Tests: `tests/test_risk_detail.py` (20), 3 AppTests (example fund incl. t shocks + 2× + episode switch, empty fund,
    unlisted fund rows). Browser check screenshots the page with 2× selected.
- **Step 6 (2026-10-11): Reality check** (`views/reality.py`, after "Risk in detail").
  - *Costs* (`fundlab/costs.py`, sourced defaults in `data/platform_costs.yaml`: EasyEquities ZAR & TFSA cost profile
    of 12 Feb 2026 + "Fees and costs" support page): editable buy/sell costs, FX fee for US holdings, unit trust
    platform fee, monthly account fee (Thrive R25, waivable). Tiles (fund charges inside prices, platform + account,
    one-off cost to buy, yearly drag), 20-year value lines (no costs / after fund costs / after all), 10- and 20-year
    rands lost split into fund charges vs platform, account and trading; costs by holding.
  - *Backtest* (`fundlab/backtest.py`): today's weights over the measured window, rebalanced never/yearly/quarterly/
    monthly/weekly at the previous week's close, trading costs on turnover; vs equal-weight version, Top 40 (STX40),
    S&P 500 in rand, balanced proxy (left out if its prices don't cover the window). Stats table + hindsight-bias note.
  - *Optimiser* (`frontier.optimise`, `frontier.resampled_weights`): same risk / same return / max Sharpe over the
    fund's own measured holdings (long only); weights vs yours with 10–90% whiskers from 200 seeded re-runs with
    each mean drawn from N(mu, SE²); Michaud (FAJ 1989, "estimation-error maximizers") cited.
  - Tests: `tests/test_reality.py` (14), 2 AppTests + reality page in the mixed-fund loop; browser check screenshot.

## Phase 2 plan

Pages: **What kind of fund is it?** (composition), **Risk detail**, **Reality check**, plus the diversifier
explorer and side-by-side comparison. In order:
1. ~~Research and add JSE ETF look-through data~~ Done (JSE `tracks` resolved; US `tracks: null` left: not verified).
2. ~~`fundlab/lookthrough.py` + composition page~~ Done.
3. ~~`fundlab/factors.py` + clustered correlation heatmap~~ Done.
4. ~~Active bets view~~ Done.
5. ~~Risk detail~~ Done (2026-10-11).
6. ~~Reality check~~ Done (2026-10-11).
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

### Phase 3: library part 2 (case-file batch 2, 2026-10-11)

- Written (7): situational-awareness, steinhoff, mti, woodford, sa-property-2018, march-2020, stocks-bonds-2022.
  Every source was re-read on 2026-10-11; figures from the app's data are labelled as such.
- `kind: points` charts take several named `lines:` (property: J253, Resilient, Growthpoint, Yahoo month ends rebased;
  MTI: 10%/month calculation vs Satrix 40); 2-point series allowed (Woodford fund size).
- Parser fix: the header split now only matches `---` on its own line (the WHO URL contains `---`).
- `scripts/browser_check.py` now covers the library index and three articles (each must show a chart).
- Left out because they couldn't be verified on a page read: Kent's £263m figure (one local report; the FT via
  interactive investor says about £250m, which is used); Woodford's wind-up details (only seen in search summaries);
  Steinhoff's pension-fund victims (not on the cited page); MTI recruitment-reward mechanics; a reason for the
  $20–24bn vs $45bn gap in Situational Awareness's reported size.
- **Resilient:** the FSCA closed both probes without findings of false statements (Nov 2019) or market abuse
  (Nov 2020); the article says so explicitly.

## Phase 4 plan (approved 2026-10-11)

User decisions (2026-10-11): an unlisted holding's return is **"the return if it goes to plan"**, and the app shows
the expected return after the chance of total loss; curate **6–8 unit trusts per risk level (24+ in total)**; the
bundled, dated company-fundamentals snapshot is fine for now.

**Step 1 done (2026-10-11):** `Holding.params` + schema v2 (`METHODS`; unlisted ⇔ `assumptions`), `fundlab/synthetic.py`
(upload parser: ISO/day-first dates, `;` files with decimal commas, rejects monthly/short/non-positive; allocation
model with proxies STX40, CSPROP (2011), STXGOV (May 2020), STXILB, cash at rf, VT/BND/VNQ in rand, GLD; `price_frame`
puts modelled series beside store prices), `fundlab/unlisted.py` (Assumptions, warnings, liquidity ladder, one-factor
whole-fund view, buy-and-hold simulation whose weekly sd compounds to exactly the stated annual sd, weekly failure
hazard). `ui/cached.compare`/active use `fund_prices`. 30 new tests (197 total).

**Steps 2–3 done (2026-10-11): unit trusts and unlisted holdings in the app.**
- `data/unit_trusts.yaml`: 28 EasyEquities unit trusts (8 low, 6 low–medium, 7 medium–high, 7 high), each with
  ASISA category, published risk label, benchmark, inception, size, TER/TC (EasyEquities class), allocation mapped to
  the app's asset classes, top holdings (tickers where in the universe), and the fact sheet used (url, as_of, host).
  **Sources (user's request, 2026-10-11): managers' own sites first** (Coronation, Nedgroup, Prescient, Discovery),
  then Discovery's platform library (current July/Aug 2026 copies of Allan Gray, M&G, Ninety One sheets), then
  EasyEquities' resource copies (older for some: Sanlam Mar 2025, Ninety One Managed May 2025, Steyn Oct 2025).
  Sygnia's site blocks scripts (Incapsula). Chart-only allocations were read by word coordinates (pdfplumber in the
  system Python, not the venv). Funds left out and why are listed in the file header.
- **Risk level rule:** the fund's own published label; "Medium" or no label resolved by ASISA category.
- **Prices:** `UT:<ISIN>` tickers from EasyEquities' public price feed
  (`pricing.easyequities.co.za/api/prices?ISINCode=…&period=0`, no key; daily unit prices in cents, mostly from
  mid-2021). **Distributions are not added back**, so low and low–medium funds default to the allocation model
  (money market prices are flat at R1.00). Bundled in the sample by `build_sample.py` (157 series now).
- Asset classes gain `global_cash` (USD in rand); allocations may hold negative (derivative) weights.
  `lookthrough.allocation_profile` / `unlisted_profile`, `compose(..., extra=)`, `unit_trusts.extra_profiles`.
- Build page: "What are you adding?" (Share or ETF | Unit trust | Unlisted investment). Unit trust picker by risk
  level (fund card: TER, size, label, category, allocation, dated source) with method choice (price history /
  model from allocation / upload a CSV) and "Describe your own". Unlisted picker with assumptions, derived numbers
  and warnings. **Illiquid sleeve and the whole fund** panel (share that can't be sold in a hurry, whole-fund
  expected return and volatility, seeded 1-year simulation VaR and P(loss > 20%), liquidity ladder, maths).
  Unlisted holdings get their own verdict. Holdings table shows "Measured by". VaR in rand now uses the measured
  share of the fund only.
- Known limitation, shown in the app: the SA bond proxy is the whole government bond market (long duration), so
  modelled short-dated income funds look more volatile than they are.
- Tests: `test_unit_trusts.py` (62), 3 AppTests (unit trust by allocation, unlisted with warning and sleeve, mixed
  fund through every page). 262 pass. Browser check covers the mixed fund (build + composition).

**Step 4 done (2026-10-11): due-diligence checklists.**
- `content/due_diligence.yaml` (editable): company (7 items), fund/ETF (7), unlisted (8), each with why it matters,
  auto/manual, library "read more" slug and links (FSCA register and warnings pages, checked live 2026-10-11; the
  older `Fais/Search_FSP.htm` links quoted in news articles now 404).
- `fundlab/fundamentals.py` + `scripts/build_fundamentals.py` -> `data/sample/fundamentals.json` (78 shares, Yahoo
  info + annual income/cash flow + dividends; added to the weekly GitHub Action). Ad-hoc tickers are fetched live.
- `fundlab/diligence.py` fills findings with rule-of-thumb flags (stated in the text): net debt > 3x EBITDA,
  cash from operations < 0.8x profit, any loss year or shrinking sales, P/E > 1.5x the app's sector peers (app
  sectors) or (US shares only) its own year-end P/E median, missed dividends or 2+ yearly cuts, ISS overall >= 8,
  commodity sectors; funds: TER+TC > 1.5%, 3+ top holdings already owned; unlisted: promised return >= 20%,
  lock-in >= 5 years, guarantee-like or no-loss inputs. Banks get a capital-ratio note instead of debt ratios.
- **Decision:** no P/E-vs-own-history for JSE shares: Yahoo's per-share history mixes cents and rand and ignores
  splits (Naspers' share count jumps 187m -> 855m). Dividend "cuts" are calendar-year totals, caveated.
- `ui/diligence.py`: "Before you add it: due-diligence checklist (n worth a closer look)" expander on the Build page
  for every holding type, with session-only "Done" ticks and library deep links (`st.page_link` with
  `?article=`; the library now lets the link's query param win over session state).
- Tests: `test_diligence.py` (fires/stays-quiet per flag, content neutral, every universe share builds), 1 AppTest.


Finding: Yahoo's search returns no SA unit trusts (tried Allan Gray, Coronation, Ninety One, PSG; `0P…` Morningstar
codes 404). So "price history" for a unit trust is best-effort (a Yahoo code the user types in); upload and the
allocation model will be the usual routes.

1. **Model and maths (pure Python).** `Holding.params` (optional dict), schema v2 (v1 files still load).
   `fundlab/synthetic.py`: weekly rand series for (a) an uploaded CSV (date, price; daily or weekly; cents check;
   ≥ 52 weeks) and (b) an allocation model = Σ weight × proxy return (SA equity STX40/^J200, SA property STXPRO,
   SA bonds STXGOV, cash at risk-free, global equity STXWDM, global bonds via an ETF proxy, gold) − TER/52. Series
   enter the price frame under `UT:<id>`, so every existing page works unchanged; the method is labelled everywhere.
   `fundlab/unlisted.py`: assumptions (return if it goes to plan, low/high range → vol, lock-in years, chance of total
   loss, correlation with the listed sleeve, default 0.5); implied expected return after the loss chance; one-factor
   covariance with the listed sleeve (always PSD); Monte Carlo with a total-loss jump; illiquid share (unlisted +
   anything locked longer than the horizon). Unlisted holdings never get a fake history: history-based numbers cover
   the listed part (coverage shown), the "whole fund" numbers come from the stated assumptions.
2. **Unit trusts.** `data/unit_trusts.yaml`: a few popular SA unit trusts sold on EasyEquities, each with ASISA
   category, benchmark, TER/TIC, asset allocation, top holdings, manager/inception/size, fact-sheet URL and date
   (researched; only what the sheets say). Build page gains a "Unit trust" tab: pick a curated fund or describe
   your own, choose the method. Look-through and overlap reuse `lookthrough.py` (allocation → asset/sector/country,
   top holdings → overlap).
3. **Unlisted.** "Unlisted investment" tab with the assumption inputs and explanations; an **illiquid sleeve** panel
   (amounts, lock-ins, share of the fund that can't be sold in a hurry); whole-fund expected return, volatility and
   Monte Carlo VaR (seeded) including it; a warning when the promised return is far above what listed markets pay,
   linking to MTI and Woodford.
4. **Due diligence.** `content/due_diligence.yaml` (items per type: company, fund/ETF, unlisted; each with why it
   matters and an optional auto-fill key) + `fundlab/diligence.py`. Auto-fill: funds/ETFs from universe/lookthrough/
   unit-trust data (TER, benchmark, top holdings, overlap with your fund); companies from a dated fundamentals
   snapshot bundled by `build_sample.py` (yfinance: margins, debt, P/E vs own history and sector peers, dividends),
   live for ad-hoc tickers; unlisted from the stated assumptions (scam flags). Items that need judgement (auditor
   changes, licence check on the FSCA register) are explained, not auto-filled. Shown as an expander before Add.
5. Tests for each step (model round trip, upload parsing, allocation maths, unlisted maths incl. MC convergence and
   loss frequency, checklist auto-fill, AppTests for adding each type); browser check; commit after each step.

## Architecture (as it exists)

```
Build A Fund/
├── app.py                 # entry: page config, st.navigation, sidebar (fund manager + settings)
├── views/                 # pages (not pages/, to avoid Streamlit's legacy auto-pages)
│   ├── build.py           # Build your fund (centrepiece)
│   ├── composition.py     # What kind of fund is it? (look-through, tilts, concentration, risk vs money, betas, clusters)
│   ├── active_bets.py     # Against a benchmark (active weights, TE, TE budget, rules of thumb)
│   ├── risk.py            # Risk in detail (estimate uncertainty, VaR/ES 3 ways, fan, stress tests, drawdown, leverage)
│   ├── reality.py         # Reality check (costs, backtest with rebalancing, optimiser + resampling)
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
│   ├── var.py             # parametric (normal/t), historical, Monte Carlo VaR/ES, weekly sims, fan bands
│   ├── stress.py          # stress-test episodes, buy-and-hold replay, two-factor proxies for missing history
│   ├── leverage.py        # borrowing to invest: margin calls, forced sales, wipe-outs
│   ├── costs.py           # fund charges, platform/account fees, trading costs, rands lost over n years
│   ├── backtest.py        # rebalanced backtests with trading costs
│   ├── frontier.py        # long-only frontier (warm-started SLSQP), efficiency_gap, optimise goals, resampling
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

Made during Phase 2 step 6 (2026-10-11):
- **Costs are layered:** TER/TC are already inside ETF and unit-trust prices (so history-based numbers are after
  them; shown, not deducted again); platform/account fees and trading costs are not in prices and are applied only
  on the Reality check page. Growth before costs is a labelled assumption (default 10%), not the app's expected return.
- **STT (0.25%) only on JSE share purchases**: the cost profile says "purchases of shares"; whether it applies to ETF
  units was **not verified** (no source found). The input's help text says to add 0.25 if it does.
- **US shares:** only the EasyFX transfer fee (0.5%) is included; no published USD-account cost profile was found.
- **Backtest trades at the previous week's close**, so weekly rebalancing without costs reproduces `port_returns`.
- **Optimiser uncertainty uses unshrunk standard errors** σᵢ/√years (uncertainty about the true mean).

Made during Phase 2 step 5 (2026-10-11):
- **Stress windows** come from the app's own weekly data (Top 40 index peak 16 May 2008 → trough 21 Nov 2008, −47%)
  or the matching library case file's dates (Nenegate 4–11 Dec 2015, Covid 14 Feb–20 Mar 2020, 2022 calendar year);
  July 2026 = 26 Jun–31 Jul 2026 (Micron −27% in rand). Episode text only states what the data or article supports.
- **Stress replays are buy and hold** from the episode start. A holding without prices in the episode is
  **estimated** by OLS on the Top 40 *price index* (^J200.JO, the only Top 40 series back to 2008) and SPY in rand,
  intercept dropped; R² < 0.3 is flagged *weak*. Unlisted holdings follow the listed part at β = ρσᵤ/σ_S.
- **Leverage model:** fixed debt (not rebalanced), interest accrues weekly, weekly margin check; a call sells back to
  the starting equity share 1/L; E ≤ 0 = wiped out. With normal shocks, wipe-outs are near impossible (calls
  de-lever first); Student-t shows them. The page says so.
- **Simulated weekly fund returns are floored at −100%** (fat-tailed t draws with low df could go below).

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

1. ~~Phase 3 case-file batch 2~~ Done (2026-10-11).
2. ~~Phase 4~~ Done (2026-10-11).
3. ~~Phase 2 step 5 (Risk in detail)~~ Done (2026-10-11); it reuses `unlisted.simulate_paths` for the
   whole-fund VaR row and fan chart, and moves unlisted holdings with the listed part in stress tests.
4. ~~Phase 2 step 6 (Reality check)~~ Done (2026-10-11). Next in Phase 2: step 7 (diversifier explorer,
   side-by-side comparison).
5. Phase 4 follow-ups: a "can't sell in a hurry" pop-up rule (Phase 3 rules engine) using
   `unlisted.illiquid_share`; refresh the older unit-trust sheets (Sanlam 2025, Ninety One Managed 2025, Steyn 2025)
   from managers' sites; consider a short-duration SA bond proxy for income funds.
6. Later: remaining case files (44 approved; a 2008 case file would give the 2008 stress test a library link),
   glossary tooltips and the pop-up rules engine (Phase 3, incl. "leverage switched on" once leverage is saved
   in the fund, if wanted).

Phase 2, step 7 (next in Phase 2): "Explore diversifiers" (from the preset universe, which holdings would historically
have lowered the fund's risk most per rand added, framed as exploration) and side-by-side comparison of saved funds.
