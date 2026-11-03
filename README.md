# Build-a-Fund Lab

[Open the live app](https://build-a-fund-hlakes.streamlit.app/)

Build your own "unit trust" from investments you could buy on EasyEquities (JSE shares, JSE-listed ETFs,
US shares, unit trusts) plus unlisted holdings, and see how each holding changes the fund's risk, expected
return and character. A library of sourced finance history and theory explains what the numbers mean.

> **Education, not financial advice.** The app explains what a fund's characteristics mean and what history
> says about them. It never tells you to buy or sell anything. Past returns are a poor guide to future returns.

## What it does

- **Build your fund** with rand amounts. Every change shows a before-and-after panel (expected return,
  volatility, Sharpe ratio, worst fall, VaR, diversification), a plain-language verdict, and the fund's marker
  moving on the risk-return chart against the efficient frontier. A due-diligence checklist comes with each holding.
- **What kind of fund is it?** Look-through breakdowns by sector, country, currency and earnings; concentration;
  share of the risk against share of the money; sensitivities to the JSE, the S&P 500, the rand, gold and
  commodities; holdings that move together.
- **Against a benchmark:** active weights, tracking error and which bets use it up.
- **Risk in detail:** VaR and expected shortfall three ways, a fan chart, stress tests (2008, the December 2015 rand
  crash, March 2020, 2022, July 2026), drawdowns, rolling volatility and what borrowing to invest does.
- **Reality check:** costs over 10 and 20 years, a rebalanced backtest, and what an optimiser would do instead.
- **Explore diversifiers** and **compare funds** side by side.
- **Fact sheet:** your fund on one page, in the style of a South African unit trust fact sheet, as a PDF with a
  QR code so a friend can open the same fund.
- **Library:** 61 sourced articles (case files from tulip mania to Steinhoff and VBS, plus counterexamples and
  theory), a glossary on every page, and insight pop-ups when a fund shows something worth knowing about.

No accounts: a fund lives in your browser session. Save it as a file, or share it as a link.

## Run it locally

Python 3.10.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt    # on macOS/Linux: .venv/bin/python
.venv/Scripts/streamlit run app.py                          # http://localhost:8501
```

For development (tests and the browser check):

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m playwright install chromium
.venv/Scripts/python -m pytest -q
.venv/Scripts/python scripts/browser_check.py <out_dir> [url]   # with the app running
```

## Data

- Prices come from Yahoo Finance through [yfinance](https://github.com/ranaroussi/yfinance). A weekly sample of
  every series the app uses is bundled in `data/sample/`, so the app works when Yahoo doesn't. A GitHub Action
  refreshes it every Saturday.
- Unit trust prices come from EasyEquities' public price feed. Sector, country, fee and holding data for ETFs and
  unit trusts come from the providers' fact sheets; each block in `data/` gives its source and date.
- Every historical figure in the library links to its source with the date it was read. Library articles, the
  glossary, insight rules, stress tests and due-diligence checklists live in `content/` as Markdown and YAML.

Everything is free to run: no paid APIs and no keys.

## Layout

- `fundlab/`: the maths and data handling, pure Python (no Streamlit), with formulas in the docstrings.
- `views/`: the pages. `ui/`: state, caching, charts, theme and other Streamlit helpers. `app.py` ties them together.
- `content/`, `data/`: editable content and curated data. `tests/`: pytest, including headless app tests.
- [PLAN.md](PLAN.md): status, decisions and known issues. [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md): the
  original brief.
