# PLAN: Build-a-Fund Lab

Living status document. Update whenever a phase finishes, a decision is made or
the plan changes. Full spec: [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md).

_Last updated: 2026-10-23 (**Phase 5 steps 1–3 done** (polish, fact-sheet data, Fact sheet page), 580 tests; Phase 3 done 2026-10-22: all approved case files written, 61 library articles, 551 tests; batch 4 and batch 5 (27 files) done 2026-10-22; batch 3 part 2 done 2026-10-13; Phase 3 rules + glossary + commodity case file done 2026-10-12; Phase 2 done; Phase 4 follow-ups (a)-(c) done; Phase 4 done; Phase 2 steps 1–6 done; Phase 3 library parts 1–2 done: 22 articles)_

## Phase status

| # | Phase (from the spec) | Status |
|---|---|---|
| 1 | Fund builder and core risk maths | **Done** (2026-10-09). 72 tests pass. Browser-checked at desktop and phone (dark mode didn't actually switch until the Phase 2 config fix). |
| 2 | Composition, risk and reality-check views | **Done** (2026-10-12). Steps 1–7 (ETF data, composition, sensitivities + clusters, active bets, risk detail, reality check, diversifier explorer + side-by-side comparison); 332 tests pass. Browser-checked (desktop, phone, dark). |
| 3 | Library and insight pop-ups | **Done (2026-10-22).** Library page + 22 sourced articles (every lesson group has at least one case file); 167 tests pass. Next: Phase 4. **Rules done (2026-10-12): 16 pop-up rules, every lesson group covered.** **Glossary done (2026-10-12): 52 terms, hover/tap tooltips.** **Commodity slump case file + resources-heavy rule done (17 rules).** **Batch 3 part 2 (2026-10-13): 2008, 1987, Enron, 2001 rand, VBS, Japan.** **Batch 4 (2026-10-22): Madoff, Tongaat, Asian crisis, UK LDI, Lehman, US century.** **Done (2026-10-22): every item on the approved list is written (46 case files + 5 counterexamples, 61 articles); 551 tests pass; browser-checked.** |
| 4 | Due diligence, unit trusts and unlisted holdings | **Done** (2026-10-11). 281 tests pass. Browser-checked (desktop, phone, dark). |
| 5 | Fact sheet and polish | **In progress.** Plan approved 2026-10-23. Steps 1–3 done 2026-10-23 (polish, fact-sheet data, page), 580 tests. |

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

- Compare funds side by side: done in Phase 2 step 7
- "Explore diversifiers" from the preset universe: done in Phase 2 step 7

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

- **Step 7 (2026-10-12): Explore diversifiers and Compare funds** (two pages after "Reality check").
  - `fundlab/diversifiers.py` `explore()`: every universe holding not in the fund, x rands added as new money
    (s = x/(T+x) of the measured fund), exact σ' from one covariance estimated on the fund's window for the fund and
    all candidates together (so "now" can differ from the Build page in the 2nd decimal under Ledoit-Wolf); also
    correlation and beta to the fund (dσ/ds = σ(β−1) at the margin); candidates without prices for the whole window
    are skipped and listed. ~0.25 s for 117 candidates.
  - `views/explore.py`: amount (default ~10% of the fund), type filter, top N; tiles; bars of the change in volatility
    (pp, blue falls / red rises); table; scatter of correlation vs change for all candidates; "Make a copy with it"
    (adds a copy beside the fund, active fund unchanged, link to Compare); skipped list; links to diversification and
    2022 case file. Framed as exploration; text avoids unsourced history (only the 2022 case file is cited).
  - `analysis.compare_many()` (union window, shared frontier, gaps) + `views/compare.py`: pick 2–4 session funds;
    assumptions from the active fund; metrics table (incl. ± range, extra risk vs frontier, look-through shares,
    largest holding, fund charges, illiquid share); risk-return chart with each fund + holdings + dotted frontier;
    R1 000 growth over the shared window (weekly rebalanced); holdings matrix. Duplicate fund names get an id suffix.
  - `components.table_height()` so long tables show without an inner scroll bar. Charts: `diversifier_bars`,
    `diversifier_scatter`, `funds_risk_return`.
  - Tests: `tests/test_explore_compare.py` (5: exact formula vs rebuilt fund, marginal beta rule, compare_many window,
    2 AppTests incl. copy → compare); explore added to the mixed-fund AppTest loop; browser check screenshots both
    pages (makes a copy on Explore and follows the link to Compare).

## Phase 2 plan

Pages: **What kind of fund is it?** (composition), **Risk detail**, **Reality check**, plus the diversifier
explorer and side-by-side comparison. In order:
1. ~~Research and add JSE ETF look-through data~~ Done (JSE `tracks` resolved; US `tracks: null` left: not verified).
2. ~~`fundlab/lookthrough.py` + composition page~~ Done.
3. ~~`fundlab/factors.py` + clustered correlation heatmap~~ Done.
4. ~~Active bets view~~ Done.
5. ~~Risk detail~~ Done (2026-10-11).
6. ~~Reality check~~ Done (2026-10-11).
7. ~~Explore diversifiers; side-by-side fund comparison~~ Done (2026-10-12).

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

### Phase 3: pop-up rules (2026-10-12)

- `content/rules.yaml` now has **16 rules** with `when:` conditions on named measures (all must hold; `above`/`below`),
  `threshold_note` on each (every line is labelled as the app's own choice), and text placeholders for any measure.
  One per spec starter rule except resources-heavy (waits for a commodity case file); lesson groups all covered:
  Bubbles (tech_heavy, sharp_rise), Leverage (leverage_on, one_theme), Inflation (bonds_only_cushion), Currency
  (all_sa), Fraud (one_company, unlisted_promise), Banks (bank_heavy), Sector collapses (property_heavy), Shocks
  (deep_fall), Liquidity (cant_sell_in_a_hurry); theory: one_bet (avg corr > 0.6, ≥ 3 holdings), risk_gap (risk share
  ≥ 1.5× and > 10 pp above money share), te_one_bet (one bet > 50% of TE, with direction), high_fees (> 1%, with the
  20-year cost (1 − fee)^20, exact when the charge comes off the fund's value yearly).
- **Figures in a rule's history text come from its linked article's summary** (a test checks every number appears in
  the article, unless the rule lists its own sources). The pop-up then says the figures come from the article.
- `fundlab/rules.py`: `measures(fund, stats, comp, active, prices, names)` (pure; any input may be None),
  `evaluate(rules, values)` → (tripped, checked). Tilt measures reuse `lookthrough.tilt_values()` (same thresholds as
  the composition labels); themes exclude broad market tags; largest company is looked through (an unlisted holding
  counts as one business). `ui/cached.rule_measures(fund)` caches the measures from the app's cached results.
- **Pop-up behaviour:** only a *change* pops up. Rules a fund already trips when the session first sees it (link, file,
  example, copy) go straight to the sidebar **Insights (n)** list (compact: what was noticed + read more). At most 2
  pop-ups at once ("n more in Insights"). A rule that was checked and stopped tripping forgets its dismissal; one that
  couldn't be checked keeps it. **Leverage** pops up on Risk in detail when the multiple is above 1 (`extra=`).
- Tests: `tests/test_rules.py` (26: file sourced and neutral, every group covered, each rule trips just inside its bounds
  and not on them, skipped when a measure is missing, measures for illiquid/promise/risk gap/themes/fees/sharp rise,
  AppTests: loaded fund lists without popping, a change pops 2 + "1 more", dismissal, leverage on the Risk page).
  Browser check: insights listed for the mixed fund, leverage pop-up at 2×.

### Phase 3: glossary (2026-10-12)

- `content/glossary.yaml`: 52 terms (term, aliases, def, optional article, `case: true` for acronyms like VaR/ES/TER/ETF
  that are also ordinary words). Definitions are plain concepts: no figures or history.
- `fundlab/glossary.py`: `load_glossary`, `annotate(text, terms, used=None)` wraps the **first mention** of each term
  (plurals matched, longest term first, acronyms case-sensitive) in `<span class="gl" tabindex="0" data-def="…">`;
  LaTeX, code, Markdown links, HTML tags and URLs are never touched. `lookup()`.
- `ui/glossary.py`: tooltip CSS from `ui/theme.py` (ink on surface, swapped), injected once per run in `app.py`;
  definition shows on `:hover` and on `:focus` (**tap** focuses the span on phones). **On screens ≤ 640 px the
  definition is pinned to the bottom of the screen** (16 px gutters) so it never runs off the edge; tapping elsewhere
  closes it. `glossary.markdown()` is used for page intros (Against a benchmark, Risk, Reality check, Explore,
  Compare), every chart's "What am I looking at?" (via `components.chart_notes`) and library article bodies.
- Library: a **Glossary** section (cards with read-more links) and search that also matches glossary terms.
- Tests: `tests/test_glossary.py` (24: terms neutral and unambiguous, the app's core terms defined, first mention only,
  plurals, longest match, acronym case, protected maths/links/HTML, escaping, shared `used`, AppTest for the Library
  section and a marked article). Browser check: every checked library article must have marked terms. Checked by hand:
  hover (light, dark), phone tap (bottom sheet, no sideways scroll), inside expanders.
- Seen twice in Playwright right after a server restart: a Streamlit `stDialog` overlay briefly intercepting clicks
  during the ~20 s cold start; not reproducible on a warm server. Watch for it on Streamlit Cloud.

### Phase 3: case-file batch 3, part 1 (2026-10-12)

- **Commodity slump 2014–16** (`commodity-slump-2014-16.md`, Sector collapses). Sources fetched 2026-10-12: World Bank
  press releases of 26 Jan 2016 (oil −47%, metals −21% in 2015) and 26 Apr 2016 (oil and metals 50–70% below early-2011
  peaks); Glencore RNS 7 Sep 2015 via Investegate (measures "up to US$10.2 billion", equity up to US$2.5bn, dividend
  suspended, net debt to "the low US$20s billion" by end-2016); The Citizen/Moneyweb 9 Dec 2015 (Anglo: dividend
  suspended H2 2015 and 2016, ~60% fewer assets, workforce 135,000 → 50,000). App-data figures labelled as such:
  Anglo −81% and Glencore −73% in rand (Jul 2014 → Jan 2016), then +253% / +160% to end-2016; Top 40 index −14%;
  DBC in rand −34%; USD/ZAR 10.63 → 16.52. Chart: `kind: prices` from the bundled sample.
- Left out (not verified on a page read): "largest job cuts in the industry's history"; a general claim that heavy
  borrowers fell most (rewritten as the mechanism, tied to the sourced Glencore/Anglo actions).
- **resources_heavy** rule added (25%, links to the new case file); all 17 rules' figures pass the article check.
- **Bug fixed: two "$<digit>" in one Markdown paragraph render as LaTeX in Streamlit** (seen on the new article's
  Glencore line). Currency in prose is now written `US\$10`; LTCM, MTI and Situational Awareness escaped too; a content
  test fails on any paragraph with two unescaped `$<digit>` (table rows exempt).
- fees.md: "Reality check page (coming)" → it exists now.

### Phase 3: case-file batch 3, part 2 (2026-10-13)

- Written (6), all sources fetched 2026-10-13:
  - **gfc-2008** (Leverage): Fed History essays (Rich; Duca), FCIC Conclusions pp. xv–xx (40 to 1, <3% wipes out,
    Bear Stearns overnight borrowing, GSEs 75 to 1, 26 million, US\$11 trillion), HISTORY.com for Lehman (US\$639bn,
    15 Sep 2008). App data: Top 40 −47% (May–Nov 2008, back to May 2008 level Feb 2012), BAC −93% (USD), FSR −51%,
    SBK −46%, SPY −55% USD / −30% ZAR (Oct 2007–Mar 2009), TLT +26% USD. **Linked from the 2008 stress test**
    (`content/stress_tests.yaml`).
  - **crash-1987** (Shocks): Fed History essay (Bernhardt and Eckblad); chart = ^GSPC from yfinance (points). The
    "24 standard deviations" figure is the app's own calculation (daily sd 0.85%, Jan 1985–Sep 1987), labelled so.
  - **enron** (Fraud): CRS RS21135 (Feb 2002) via EveryCRSReport, DOJ press release 23 Oct 2006. FBI page 403s.
    Yahoo has no Enron prices, so the chart is CRS's 2 points (>US\$80 Jan 2001, <70c Jan 2002), labelled.
  - **rand-2001** (Currency): 2002 Budget Review ch. 2 (37.4% vs USD; possible causes; 1985/1998/2001 table),
    Mail & Guardian 10 May 2002 (Deloitte, KPMG findings before the Myburgh report). **FRED DEXSFUS** (free CSV,
    no key) gives USD/ZAR before 2003; used for the chart and for SPY/Top 40 in rand vs dollars in 2001–02.
    Explains 37% vs 59% (quoting direction). Myburgh final findings left out (only seen in search summaries;
    polity.org.za 403s).
  - **vbs** (Banks): Motau report "The Great Bank Heist" (Corruption Watch copy; SARB page blocks scripts),
    BusinessTech. R1 894 923 674 to 53 persons (Mar 2015–Jun 2018); reported deposits R285m → R1.55bn chart.
  - **japan-1989** (Bubbles): Okina, Shirakawa and Shiratsuka (BoJ IMES, 2001); Nikkei from yfinance (peak
    38,915.87 on 29 Dec 1989, low 7,054.98 on 10 Mar 2009, first close above on 22 Feb 2024).
- Tips: FCIC PDFs drop their old-style digits in `pdftotext`; render pages with `pdftoppm -png` and read the image.
- `scripts/browser_check.py` also checks gfc-2008 and vbs.

### Phase 3: case-file batch 4 (2026-10-22)

- Written (6), all sources fetched 2026-10-22:
  - **madoff** (Fraud): SDNY sentencing release (29 Jun 2009; US\$170.8bn forfeiture), SEC OIG-509 executive summary
    (six complaints; Markopolos 3 vs 26 down months; DTC: <US\$18m vs US\$2.5bn claimed), madofftrustee.com
    (US\$15.494bn recovered, US\$14.799bn distributed, as of 29 Sep 2026). Chart: S&P 500 vs an app-drawn steady 15%
    line (Barron's figure via OIG), labelled as an illustration. Principal-lost % left out (sources disagree).
  - **tongaat-hulett** (Fraud): BizNews (board's PwC summary), The Herald/Business Day 11 Dec 2019 (R11.886bn; equity
    R62m vs R12bn reported), BusinessTech 12 Oct 2026 (**delisting on 3 Nov 2026**, no value for shareholders).
    JSE SENS PDFs and Engineering News block scripts; Yahoo has no TON.JO. Chart: 2-point write-down estimate.
  - **asian-crisis-1997** (Currency): Fed History (Carson and Clark), IMF Issues Brief 00/05; FRED DEXTHUS/DEXKOUS/
    DEXMAUS chart; KOSPI/KLCI/JKSE falls from Yahoo. Thailand's 1998 GDP left out (the IMF brief gives −6% and −10.2%).
  - **uk-ldi-2022** (Leverage): Cunliffe letter 5 Oct 2022, BoE Quarterly Bulletin 2023 (£19.3bn); daily GLTL.L,
    INXG.L, ISF.L from Yahoo.
  - **lehman** (Banks): Valukas examiner report vol. 1 (Stanford mirror; Repo 105 ~US\$50bn, net leverage 12.1 vs 13.9),
    SEC 2009-104 (Reserve Primary, US\$785m Lehman paper), Treasury HP-1147. Chart: BAC/JPM/XLF/SPY in rand
    (JPM ended H2 2008 up 6% in rand, so the text says not every bank fell).
  - **us-century** (Counterexamples, section `counter`): Damodaran histretSP (1928–2025) deflated by FRED CPIAUCNS
    (Dec–Dec); first **`log: true`** chart. All statistics are the app's calculation, labelled.
- Next batch suggestion: Tulip mania, South Sea 1720, 1929, 1970s stagflation, Wirecard, Long-run JSE real returns.

### Phase 3: case-file batch 5, the rest of the list (2026-10-22)

- **Count fix:** the approved list has 53 items, not 44. All are now covered: 1720 Mississippi + South Sea are one
  article (`bubbles-1720`, the research treats them as linked); the July 2026 AI chip sell-off is covered by
  `situational-awareness`; Lehman got its own file (Repo 105, Reserve Primary Fund).
- Written (27): tulip-mania, bubbles-1720, railway-mania, crash-1929, nifty-fifty, crypto-2021-22, volmageddon-2018,
  archegos, stagflation-1970s, volcker-1979, flash-crash-2010, uk-property-funds, russia-rand-1998, zimbabwe,
  argentina-2001, russia-2022, wirecard, sharemax, sa-small-banks-2002, svb-credit-suisse-2023, negative-oil-2020,
  platinum, telecoms-bust, jse-long-run, index-funds-spiva, buying-through-2008 (plus lehman etc. in batch 4).
- **New: `chart: {kind: none, reason: ...}`** for case files with no sourced series (tulip-mania, sharemax). The library
  shows "No chart: <reason>"; the content test requires a reason; the browser check covers tulip-mania.
- Data sources used beyond the app's bundle: yfinance live (^GSPC from 1927, ^N225, ^VIX, SVXY, BTC/ETH, CL=F/BZ=F, PL=F,
  GLTL/INXG/ISF/IUKP.L, BIDU/TME/IQ, WRCDF, ^MERV, ARS=X, RUB=X, KRE, VFINX); FRED CSV (DEXSFUS, DEXTHUS/KOUS/MAUS,
  FEDFUNDS, GS10, CPIAUCNS, ZAFCPIALLMINMEI); Damodaran histretSP (1928–2025).
- Left out (couldn't verify on a fetched page): Garber/Thompson tulip price index (paywalled); Yale 1720 dataset (licence
  forbids redistribution); Hanke's Zimbabwe peak estimate (Cato blocks fetching; IMF's 500 billion % official figure
  used); SPIVA 2025 figures (spglobal.com 403; 2015 inaugural figures used); Myburgh's final findings; FTX conviction and
  Hwang conviction (DOJ pages block fetching; regulators' allegations used and labelled as such); Credit Suisse AT1
  court annulment (Oct 2025, only seen in search summaries).
- Many sites block scripts (DOJ, FBI, Cato, spglobal, JSE SENS, polity, Britannica). Workarounds that worked: university
  mirrors (UCEMA for the IMF IEO report, Stanford for Valukas), EveryCRSReport, SEC/Fed/BIS/FINMA/IMF direct.

## Phase 5 plan (approved 2026-10-23)

User decisions (2026-10-23): take every recommendation in the proposal. **Push to GitHub after each step** (pull and
rebase first: the weekly bot pushes to `master`); **deploy to Streamlit Community Cloud after step 1** (the user
does the deploy and sends the URL); **QR code on the PDF** (free `qrcode` package); **no ASISA-style category** on the
fact sheet (it would need sourced ASISA rules; the sheet shows a labelled risk level instead).

1. ~~**Polish**~~ Done (2026-10-23):
   - Risk-return charts (Build and Compare): holding labels are their own text layer drawn after the fund markers, with
     a background-coloured halo (`textfont.shadow`); a label moves below, then right of its dot when a fund marker sits
     where it would be drawn (`charts._label_positions`).
   - Moves shorter than ~3% of the plotted range (`charts.SMALL_MOVE`) get a two-line "Barely moved" callout with the
     changes in pp (≈ 0 under 0.005 pp), pointing into the side of the chart with more room, instead of a hidden arrow.
     The browser check finds the "After" trace by name.
   - `synthetic.distinct_versions()`: Compare gives each differently modelled copy of a unit trust its own ticker
     (`UT:x~2`, named "<name> (<fund>'s inputs)"); store-priced copies keep the plain ticker.
   - `Fund.with_amount` raises if a *new* holding has no `kind` (no `jse_share` default).
   - Glossary: **market capitalisation** and **delisting** (54 terms); a test checks every article marks a term.
2. ~~**Fact-sheet data**~~ Done (2026-10-23). `fundlab/factsheet.py` (pure): header, objective, details, top 10 holdings + other, look-through
   sector and country, simulated performance vs benchmark (1/3/5 y, best/worst calendar year, growth of R1 000), risk
   statistics, TER/TC/TIC + platform costs, top 3 insights (warnings first, then `rules.yaml` order). Risk level on the
   SA five-step scale from volatility, thresholds labelled as the app's own: **under 4 / 7 / 9 / 12% a year** = Low,
   Low to medium, Medium, Medium to high, High. Calibration (2026-10-23, 5-year weekly prices): 17 of the 27 measurable
   curated unit trusts land on their own published level, the other 10 one step away. The whole-fund volatility
   (with unlisted) sets the level when the fund has unlisted holdings. Performance = today's weights, rebalanced
   quarterly, no trading costs (`factsheet.SCHEDULE`); the benchmark is rebased to the fund where its prices start and
   shown only where it has prices at both ends of a period. `ui/cached.fact_sheet(fund)` assembles it (insights via
   `rules.evaluate` directly, so building the sheet never changes pop-up state). `COUNTRY_NAMES` moved to
   `fundlab.lookthrough`.
3. ~~**Fact sheet page**~~ Done (2026-10-23). `views/factsheet.py` after Compare: "Objective and benchmark" expander
   (objective saved in the fund; the benchmark picker moved to `components.pick_benchmark`, shared with Against a
   benchmark), then the sheet in a bordered box: header + disclaimer, performance (growth chart, period and calendar
   tables), top holdings, fund details, risk, fees, asset classes, sector and country bars, top 3 insights with library
   links. 3 charts, each with `chart_notes`. Tables are small HTML tables (`html_table`, border colour from
   `ui/theme.py`) because dataframes clipped long values in the narrow column and on phones. 21 tests (18 pure, 3
   AppTests); browser check screenshots the example and mixed funds' sheets.
4. **PDF** (fpdf2 + matplotlib, one A4 page, DejaVu Sans from matplotlib, light palette from `ui/theme.py`, built on
   demand): share link + QR code; "model fund for learning, not a real unit trust" on the page; tests for one page in
   stress cases and no advice words; browser check downloads it and renders it with `pdftoppm`.
   **Why:** pure-Python wheels that install on Streamlit Cloud from `requirements.txt` alone. Kaleido 1.x needs Chrome;
   WeasyPrint/wkhtmltopdf need system libraries; browser print varies by device and includes the sidebar.
5. **Deployment readiness:** clean Python 3.10 install from `requirements.txt` (pytest moves to dev), memory and
   first-load timing, README, `browser_check.py --url` against the live app.
6. Wrap-up: PLAN.md, tests, browser check.

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
│   ├── explore.py         # Explore diversifiers (each universe holding added in turn)
│   ├── compare.py         # Compare funds side by side (shared window)
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
│   ├── analysis.py        # history_window, estimate, FundStats, compare / compare_many (shared window + frontier)
│   ├── diversifiers.py    # explore(): volatility change from adding each candidate
│   ├── rules.py           # insight rules (content/rules.yaml) evaluation
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

`content/`: library/*.md, rules.yaml, glossary.yaml, due_diligence.yaml, stress_tests.yaml.

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

## Approved case-file list (53 items; the old heading said 44, a miscount)

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
- On a phone the "Barely moved" callout can cover a nearby holding's label (seen: GLD in the example fund).
- A "Page not found" toast showed once on a deep link to `/factsheet` straight after a server start (cold start, like
  the `stDialog` overlay noted in Phase 3); not reproducible on a warm server.
- **Holdings table on phones:** Ticker/Type scroll off to the right (by design: key columns first).
- **Data limits:** USD/ZAR from Dec 2003 only; JSE shares from 2000 at the earliest; STX40.JO from 2009; STXGOV.JO
  (SA bonds) from May 2020; short JSE listings (CFR 2023, BHG 2022, NPH 2021, SSW 2020, PRX 2019); CRWV from 2025.
  OUT.JO before 2011-03-18 is a predecessor company (cut via `history_from`). Six ETF tickers return nothing
  (STXSWX, SYGSW4, DIVTRX, NFEMOM, NFTRCI, PTXTEN).
- **GitHub:** repo `haydenlakey/Build-A-Fund` exists; the weekly Action ran (bot commit "Refresh bundled price data
  (2026-10-17)"). Streamlit Cloud deployment still untested (Phase 5 step 5).
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
- Repo visibility not confirmed (no `gh` CLI here). Deploy after Phase 5 step 1 (user, 2026-10-23).

## Next step

1. ~~Phase 3 case-file batch 2~~ Done (2026-10-11).
2. ~~Phase 4~~ Done (2026-10-11).
3. ~~Phase 2 step 5 (Risk in detail)~~ Done (2026-10-11); it reuses `unlisted.simulate_paths` for the
   whole-fund VaR row and fan chart, and moves unlisted holdings with the listed part in stress tests.
4. ~~Phase 2 step 6 (Reality check)~~ Done (2026-10-11). ~~Step 7~~ Done (2026-10-12): **Phase 2 complete.**
5. ~~Phase 4 follow-ups~~ Done 2026-10-12 (user asked for these after step 6, 2026-10-11). Order: (a) sheet refresh,
   (b) short-duration bond proxy, (c) "can't sell in a hurry" pop-up. Commit after each.

   **(a) Refresh stale unit-trust sheets: DONE (2026-10-12).** `data/unit_trusts.yaml` now uses:
   SIAB4 and SEYB1 = Momentum-hosted July 2026 MDDs (renamed "Sanlam Investment Management SCI ...", manager notes
   the Ninety One acquisition, Feb 2026; both sheets' fee tables are A1 class: SIAB4 keeps EasyEquities B4 fees, SEYB1
   fees labelled "fact sheet, A1 class (Apr 2023 to Mar 2026)", tc 0.0001); MTBTE = Discovery MANH (H class) end July
   2026 with the proposed FX-netted mapping and 10 top holdings (7 matched to universe tickers); SEPB1 = Prescient-hosted
   June 2026 quarterly MDD, benchmark now J303T. **IDICH also refreshed**: Momentum hosts a newer H-class sheet
   (https://wealth.momentum.co.za/investments/factsheets/ninety-one-diversified-income-fund-(h).pdf, as at
   31 Aug 2026, accessed 2026-10-12): cash 64.5, SA bonds 29.8, property 3.4, equity 0.6, global bonds 1.7; maturity
   profile 0-1 y 9.8, 1-3 y 14.6, 3-7 y 42.5, 7-12 y 11.9, 12+ y 21.2 (in allocation_note). `pdftotext -layout`
   misaligns these tables; `pdftotext -raw` reads them cleanly. New: "momentum" host; optional per-sheet `accessed`
   (overrides the file-wide date, shown in the picker).

   **(b) Short-duration SA bond proxy: DONE (2026-10-12).** Yahoo has no short-dated SA bond series (checked
   2026-10-12: the SA nominal bond ETFs it carries all track all-maturity indices: STXGOV from 2020, ETFBND 2019,
   CSGOVI 2022, ETFSAB 2024; no JSE ETF tracks the ALBI 1-3 Year index; NFGOVI and others return nothing).
   **Decision (user, 2026-10-12):** new class `sa_short_bonds` "SA short-term bonds (0-3 years)" =
   cash + 0.25 × STXGOV's return above cash (`synthetic.PROXY_SCALE`), labelled in the app as an app-made assumption
   (0.25 ≈ a 0-3 year bucket's ~1.5-year duration as a fraction of the all-maturities index's; S&P's index page
   couldn't be opened to source the index's current duration, so no number is quoted). SIAB4 and SEYB1 0-3 yr buckets
   now map to it (modelled vol 7.0% → 4.6% and 8.1% → 5.4% a year). IDICH not remapped: its maturity profile isn't
   split by instrument (FRNs may be in it). Look-through sector "Short-term bonds". 3 new tests.

   **(c) "Can't sell in a hurry" pop-up: DONE (2026-10-12).** Minimal rules engine: `content/rules.yaml` (id, title,
   trigger, above, threshold_note, severity info|warning, noticed with {value}/{threshold}, history, article, sources);
   `fundlab/rules.py` (pure: `TRIGGERS` registry name -> fund measure, `load_rules` validates, `evaluate` -> Insights);
   `ui/insights.py`: `popups(fund)` on the Build page (bordered callout: what I noticed / what history says / Read more
   link / threshold note + source; "Got it" dismisses per fund and rule for the session; a rule that stops tripping
   forgets its dismissal) and `panel(fund)` = sidebar "Insights (n)" expander on every page. First rule
   `cant_sell_in_a_hurry`: `unlisted.illiquid_share` > 20% (labelled as the app's own threshold, not a legal limit);
   history uses only the Woodford case file's FCA-sourced figures (8% sellable within 7 days). Rules apply to the
   applied fund, not the preview. `tests/test_rules.py` (4, incl. AppTest: trips + dismiss, quiet fund); browser check's
   MIXED fund now has a R6 000 coffee shop (25%) and checks the pop-up shows and dismisses.
   **Phase 4 follow-ups all done.**

6. Later: remaining case files (44 approved; a 2008 case file would give the 2008 stress test a library link),
   glossary tooltips, and the other spec section 7 rules on the new engine (one per lesson group; add a trigger to
   `rules.TRIGGERS` + an entry in `content/rules.yaml`; "leverage switched on" needs leverage saved in the fund).

**Phase 3 is done (2026-10-22).** Every approved case file is written (see "case-file batch 5" above). Write currency in
prose as `US\$10` (see the LaTeX bug above). Leftover: the SPIVA 2025 figures could replace the 2015 ones if S&P's
pages become fetchable.

**Phase 5 (2026-10-23):** steps 1–3 done. **Next: step 4, the PDF** (see "Phase 5 plan"); the user is deploying to
Streamlit Cloud and will send the URL (check what `st.context.url` gives there before building the PDF's share link).
