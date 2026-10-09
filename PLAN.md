# PLAN: Build-a-Fund Lab

Living status document. Update whenever a phase finishes, a decision is made or
the plan changes. Full spec: [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md).

_Last updated: 2026-10-09_

## Phase status

| # | Phase (from the spec) | Status |
|---|---|---|
| 1 | Fund builder and core risk maths | **In progress.** Maths, data layer, universe, bundled sample and 52 tests are done. Still to do: analysis/verdict layer and the whole UI. |
| 2 | Composition, risk and reality-check views | Not started |
| 3 | Library and insight pop-ups | Not started |
| 4 | Due diligence, unit trusts and unlisted holdings | Not started |
| 5 | Fact sheet and polish | Not started |

### Phase 1 checklist

- [x] `fundlab/estimators.py`: mean (+ shrinkage, standard error), sample / Ledoit-Wolf / EWMA covariance
- [x] `fundlab/risk.py`: vol, Euler risk contributions, Sharpe, diversification ratio, effective holdings, drawdown, average correlation, rolling vol
- [x] `fundlab/var.py`: parametric (normal, t), historical and Monte Carlo VaR/ES
- [x] `fundlab/frontier.py`: long-only efficient frontier, efficiency gap
- [x] `fundlab/active.py`: active weights, TE, TE budget, pairwise bet, average-vol/average-corr rule of thumb (built early because the spec's quality bar tests it)
- [x] `fundlab/model.py`: Fund / Holding / FundSettings, derived weights, JSON and share-link encoding
- [x] `tests/test_maths.py` (30 tests) and `tests/test_data.py` (22 tests, offline): weights sum to 1, RCs sum to vol, MC→parametric (normal and t), pairwise bet 4.43%/87.1%/12.9%, LW partial shrinkage, cents/FX/anchor handling, 100× repair, bundled-sample sanity
- [x] `data/universe.yaml`: 41 Top 40 lines, 31 JSE ETFs, 37 US shares, 16 US ETFs, 8 factors. JSE ETF TERs, holdings and sector splits are **deferred to phase 2** (look-through)
- [x] `fundlab/data.py`: Universe (load/search/kind_of), quote units, 100× repair, daily→Friday weekly resample, rand conversion, retrying download, PriceStore (sample → cache → live, failures recorded, `history_from` cut-offs)
- [x] `scripts/build_sample.py` + `data/sample/prices_native.parquet` (129 tickers × 1 658 weeks, 1995-01-06 to 2026-10-09, about 740 KB) + `meta.json`
- [ ] `fundlab/analysis.py`: history window rule, `FundStats`, before/after comparison on a common window
- [ ] `fundlab/verdict.py`: plain-language verdict
- [ ] `app.py` + Build page: name the fund, search a ticker, enter rands, preview → before/after panel, animated frontier marker, verdict, save/load/duplicate, share link, disclaimer
- [x] `.github/workflows/refresh-data.yml`: Saturdays 06:00 UTC plus manual run; commits only when the data changed. **Untested until the repo is on GitHub.**
- [ ] Run the app, check it at desktop and phone widths, fix what's broken

## Architecture (as it exists)

```
Build A Fund/
├── CLAUDE.md, PLAN.md, requirements.txt (pinned), .gitignore
├── docs/ORIGINAL_PROMPT.md
└── fundlab/               # pure Python, no Streamlit
    ├── __init__.py        # PERIODS_PER_YEAR = 52
    ├── estimators.py      # prices_to_returns, mean_returns, mean_standard_error, sample_cov, ewma_cov,
    │                      # ledoit_wolf_cov (→ cov, delta), covariance(method), cov_to_corr
    ├── risk.py            # portfolio_return/vol, risk_contributions, risk_shares, sharpe,
    │                      # diversification_ratio, effective_holdings, portfolio_returns,
    │                      # drawdown_series, max_drawdown, average_correlation, rolling_vol
    ├── var.py             # parametric_var_es, horizon_returns, historical_var_es, simulate_paths, mc_var_es
    ├── frontier.py        # Frontier dataclass (vol_at), efficient_frontier, efficiency_gap
    ├── active.py          # active_weights, tracking_error, te_budget, pairwise_bet, te_rule_of_thumb
    └── model.py           # Holding, FundSettings, Fund, HOLDING_KINDS, share codes
```

Also present: `fundlab/data.py`, `data/universe.yaml`, `data/sample/` (parquet + meta.json),
`scripts/build_sample.py`, `tests/` (test_maths.py, test_data.py), `pytest.ini`,
`.github/workflows/refresh-data.yml`. `data/cache/` (live downloads) is git-ignored.

Planned (not yet created): `fundlab/analysis.py`, `fundlab/verdict.py`, `app.py`, `pages/`, `ui/`,
`content/` (library Markdown, glossary.yaml, rules.yaml).

## Data model (as it exists in `fundlab/model.py`)

- **Holding**: `ticker, name, kind, amount_zar, currency="ZAR", method="price_history"`.
  `kind` ∈ jse_share, jse_etf, us_share, us_etf, unit_trust, unlisted. `method` ∈
  price_history, uploaded, allocation_model, assumptions. Negative amounts are rejected.
- **FundSettings**: `lookback_years=5, cov_method="ledoit_wolf", mean_shrinkage=0.5,
  risk_free=0.07, var_alpha=0.95, var_horizon_weeks=4, seed=42, benchmark="STX40.JO"`.
- **Fund**: `name, holdings, objective, settings, id` (8-hex uuid). `weights()` and
  `amounts()` merge duplicate tickers and drop zero amounts. Edits (`with_amount`,
  `without`, `copy`) return new Funds. Serialised as JSON with `schema_version = 1`.
  Share code = zlib + URL-safe base64 of compact JSON (about 400 characters for 3 holdings).
- Still to add (phase 4): unlisted parameters (`exp_return, low, high, lockin_years,
  p_total_loss, assumed_corr`).

## Decisions made

Agreed with the user (2026-10-08):
- Stack: Streamlit + Plotly, pure-Python `fundlab` core, Streamlit Community Cloud. Zero cost.
- The case-file list (44 files in 10 groups) is approved. It's listed below.
- Situational Awareness: report the conflicting figures as a sourced range (about $20bn
  vs about $45bn AUM; about $16bn public book sold to Citadel at roughly a 10% discount),
  not a single "$45bn→$10bn" figure.
- Add a GitHub Action that refreshes the bundled data weekly. The repo will be public.
- A new "Liquidity and locked money" lesson group, so the "can't sell in a hurry" rule has a case file to link to.

Proposed in the plan and accepted along with it:
- **Weekly returns**, not daily: the JSE and US markets close at different times, which biases daily cross-market correlations down.
- **Short-history rule**: stats use the window all holdings share. Below 156 weeks, warn.
  Below 52 weeks, leave the holding out of the stats (with a label and an override option).
  Before/after comparisons use the window of the union of both funds, so the change reflects the holding, not the window.
- **Benchmark proxies**: Top 40 = STX40.JO; S&P 500 in rand = ^GSPC × USDZAR; the balanced
  benchmark is a transparent ETF mix (60% SA equity / 20% SA bonds / 20% global), labelled as a proxy.
- **Unlisted correlation** with listed equity is user-set, default 0.5 (not 0).
- Bundled data is the primary source on Streamlit Cloud, because Yahoo often blocks cloud IPs. Live fetching is a bonus.
- Fact-sheet PDF: fpdf2 + matplotlib (avoids kaleido/Chrome on Cloud).
- Glossary tooltips must open on tap (there's no hover on phones).

Inferred from the code (not discussed explicitly):
- *(inferred)* Ledoit-Wolf shrinks toward the **constant-correlation** target (LW 2004
  "Honey, I shrunk…"), not the scaled identity. A scaled-identity target pulls equity
  correlations toward 0 and understates risk.
- *(inferred)* Mean shrinkage pulls each asset toward the cross-sectional average with
  intensity `a` (default 0.5). That preserves the average.
- *(inferred)* EWMA λ = 0.97 on weekly data (half-life of about 23 weeks), with weighted-sample bias correction.
- *(inferred)* Monte Carlo rebalances weekly and simulates at fund level. Student-t uses a shared
  chi-square mixing variable, so crashes hit all assets at once, and it's scaled to keep the
  same covariance. MC→parametric equality only holds exactly at a 1-week horizon (compounding).
- *(inferred)* Efficiency gap = fund vol minus frontier vol at the same expected return, measured against **the fund's own holdings' frontier**.
- Prices are total-return (yfinance `auto_adjust=True`, so dividends are reinvested via adjusted closes).
- **Data pipeline (decided 2026-10-09):** download *daily* closes and resample to Friday week-ends
  ourselves, because Yahoo's weekly bars use different anchors per ticker (Monday for JSE, Sunday for US,
  Thursday-to-Wednesday weeks for some JSE ETFs). Store native units after cleaning (JSE ÷100 to rand);
  convert USD→ZAR on load. Indices (`^J200.JO`) are in points, not cents.
- Universe `sector` uses Yahoo/Morningstar sector names for both JSE and US, so there's one scheme. JSE
  rows are curated: e.g. Naspers/Prosus are "Technology", not Yahoo's "Consumer Cyclical / Internet Retail".
  `exposure` (sa / sa_dollar / africa / mixed / global) is a curated approximation and drives rand-hedge labelling.
- Commodity factor = DBC ETF in rand (Yahoo has no ^BCOM). Gold = GC=F futures in rand.
- Only JSE (.JO) and US-listed tickers are accepted as ad-hoc search entries (`data.is_supported`).
- *(inferred)* Risk-free default 7% is a placeholder user assumption, not a sourced figure.

## Research done so far

- **Top 40 constituents** (41 lines, because Investec has Ltd and PLC listings) as at 8 Oct 2026, from Satrix's product page
  (https://satrix.co.za/products/product-details?id=44, accessed 2026-10-08):
  ABG, AGL, ANG, ANH, APN, BHG, BID, BTI, BVT, CFR, CLS, CPI, DSY, FSR, GFI, GLN, GRT, HAR,
  IMP, INL, INP, MRP, MTN, NED, NPH, NPN, NRP, OMU, OUT, PAN, PPH, PRX, REM, RNI, SBK, SHP,
  SLM, SOL, SSW, VAL, VOD. The same page gives an STX40 TER of 0.10%.
- **Situational Awareness** and the **July 2026 AI sell-off** were confirmed on 2026-10-08. Sources: Quartz,
  Yahoo Finance, CNBC (5 Aug and 21 Aug 2026), Crypto Briefing, SpotGamma, NBC News, CNBC
  (29 Jul), Bloomberg (28 Jul), XTB. URLs are in the session transcript; copy them into the case files when writing them.

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

- **pip hung** on the first combined install of all packages (killed after about 15 min, cause unknown).
  Installing in two smaller groups worked. Everything is now installed and pinned in `requirements.txt`
  (streamlit 1.65.0, plotly 7.1.0, yfinance 1.7.0, pandas 2.3.3, numpy 2.2.6, scipy 1.15.3, pyarrow 25.0.1).
- `Fund.with_amount` defaults `kind="jse_share"` when adding a new ticker. Callers must pass
  the correct kind, or US shares would be mislabelled. Fix when the universe lookup exists.
- **Data limits found 2026-10-09:**
  - Yahoo's USD/ZAR (ZAR=X) starts Dec 2003, so nothing priced in dollars has a rand series before 2004.
    The 1997/1998/2001 episodes can't be replayed for US holdings.
  - JSE share history on Yahoo starts Jan 2000 at the earliest. ^J200.JO (Top 40 price index) goes back to 1995.
  - STX40.JO on Yahoo starts only in 2009 (the fund itself is older). SA bonds (STXGOV.JO) start only in May 2020,
    which limits the balanced benchmark's history. Need a longer SA bond proxy (open question).
  - Short JSE histories: CFR.JO from 2023, BHG.JO 2022, NPH.JO 2021, SSW.JO 2020, PRX.JO 2019, CRWV 2025.
  - OUT.JO's history before 2011-03-18 is a predecessor company (−82% artefact week). Cut via `history_from`.
  - Six ETF tickers return nothing: STXSWX, SYGSW4, DIVTRX, NFEMOM, NFTRCI, PTXTEN.
  - CoreShares ETFs are now branded 10X. ETFSWX is now "1nvest Capped All Share". Names were fixed from Yahoo longName.
  - The scan of extreme weekly moves found no other glitches (remaining extremes like Sasol in Mar 2020 and BAC in Mar 2009 are real).
- yfinance works locally (probe on 2026-10-09). STX40.JO returned 10 280, i.e. cents (R102.80,
  consistent with Satrix's NAV of R101.21 on 8 Oct), which confirms the ÷100 rule. Not yet tested from Streamlit Cloud.
- Smoke test note: with data simulated from an exactly constant-correlation model, LW delta = 1.0.
  That's correct (the target is the truth), but the real test should use a non-constant correlation structure.

## Open questions

- The risk-free rate default (7%) needs a sourced current SA 91-day T-bill rate, or a clear "your assumption" label.
- Which JSE ETFs make the universe, and their TERs/holdings from current fact sheets (each with an as-of date).
- A longer free SA government bond series for the balanced benchmark (STXGOV.JO starts 2020).
- `tracks: null` ETFs in universe.yaml: confirm each index from the provider's fact sheet in phase 2.
- Browser checking: Playwright + headless Chromium (free) for desktop/phone screenshots. Not installed yet.

## Next step

Write `fundlab/analysis.py` (history-window rule, `FundStats`, before/after on a common window, with tests)
and `fundlab/verdict.py` (plain-language verdict, with tests). Then build `app.py` + the Build page.
