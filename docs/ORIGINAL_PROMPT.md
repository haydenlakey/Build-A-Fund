# Project: Build-your-own-fund lab

Build an interactive web tool where someone constructs their own "unit trust" from investments they could actually buy on EasyEquities (JSE shares, JSE-listed ETFs, US shares, unit trusts) plus unlisted investments, and sees exactly how each holding changes the fund's risk, expected return and character. The tool also teaches: it has a library of finance history and theory, and it pops up relevant lessons when the fund shows a characteristic worth knowing about.

## Who it's for
Me (a statistics Honours student) and my friends in other fields who keep asking me about investing. They are new to investing but smart, and they enjoy technical detail and good graphs. So:
- Plain language comes first, and the detail is always one click away, never hidden. Every chart has a "what am I looking at" note and a "show me the maths" toggle.
- A glossary: any technical term is hoverable for a one-line definition.
- A short guided first run that builds a sample fund step by step.

## How to work
- Show me a plan (architecture, data model, phases) before coding. Build in phases, each one runnable: (1) fund builder and core risk maths, (2) composition, risk and reality-check views, (3) library and insight pop-ups, (4) due diligence, unit trusts and unlisted holdings, (5) fact sheet and polish.
- Stack: Python with Streamlit and Plotly, deployed free on Streamlit Community Cloud. Core maths in a separate, tested module with no Streamlit code in it.
- Hard constraint: zero cost. No paid APIs or keys needing a credit card.
- Data: yfinance (.JO tickers for the JSE). Handle its quirks: JSE prices are quoted in cents, tickers go missing, the API fails at times. Cache downloads and bundle a sample dataset so the app always works.
- Sector, industry and country data is patchy for JSE shares, so build a curated mapping file for a preset universe (Top 40 constituents, the main JSE ETFs, popular US shares). For the ETFs include top holdings, sector split and expense ratio, so funds can be analysed on a look-through basis.
- No accounts. Each visitor's fund lives in their session; they save and load funds as a downloaded file, and can share a fund with a friend by sending that file or a link that encodes it.

## Ground rules for written content
- Everything is educational. Never tell the user to buy or sell; explain what a characteristic means and what history says about it. Show a clear "education, not financial advice" notice.
- Every historical claim and figure must be researched and sourced, with a link and a date. If you can't verify something, leave it out and tell me.
- Store all library content and pop-up rules as Markdown and config files, so I can edit and add entries without touching code.

## 1. Build the fund
- The user names their fund and adds holdings by searching a ticker and entering a **rand amount** (not a weight). Weights are derived. Support fractional amounts.
- Convert US holdings to rand using USD/ZAR history, so all returns and risk are in rand and currency risk is included.
- Funds can be saved, loaded, duplicated and compared side by side.

## 2. "What does this holding do?" (the centrepiece)
- When adding, removing or resizing a holding, show a **before and after** panel: expected return, volatility, Sharpe ratio, max drawdown, VaR and diversification, each with the change highlighted.
- Animate the fund's marker moving on the risk-return chart, with the efficient frontier of the current holdings behind it, showing whether the change moved toward or away from efficient.
- A plain-language verdict, for example: "Adds return, but it's 0.85 correlated with what you already hold, so risk rises almost one for one."
- **Explore diversifiers:** from the preset universe, show which holdings would historically have lowered the fund's risk most per rand added, framed as exploration and not a recommendation.

## 3. What kind of fund is it?
- Breakdown charts (sunburst or treemap) by sector, asset type, country and currency, on a look-through basis. Label the tilt in words: tech-heavy, resources-heavy, rand-hedge, bank-heavy.
- Concentration: top five share, effective number of holdings, a warning when one position dominates.
- **Risk contribution versus money contribution:** a paired bar chart of each holding's share of the rands against its share of the risk.
- Sensitivities: beta to the JSE Top 40, the S&P 500, USD/ZAR, gold and a broad commodity index, by regression with confidence intervals.
- Clustered correlation heatmap, so groups that move together are obvious.
- **Active bets view:** the user picks a benchmark (Top 40, a balanced fund benchmark, or a global index). Show active weights against it, the fund's tracking error, and each bet's share of the tracking error budget. Show the rule-of-thumb versions (pairwise bet sizing, and the average-volatility, average-correlation approximation) beside the exact covariance calculation.

## 4. Risk and return detail
- Expected return (historical mean with optional shrinkage; say clearly this is the least reliable number on the page) and covariance (sample, Ledoit-Wolf, exponentially weighted).
- VaR and expected shortfall three ways side by side: historical, parametric, and Monte Carlo with normal or Student-t innovations. Show the simulated distribution of rand outcomes over a chosen horizon.
- A fan chart projecting the fund's rand value with percentile bands.
- Stress tests: replay the fund through 2008, the December 2015 rand crash, March 2020, 2022 and the July 2026 AI sell-off, where history allows.
- Drawdown chart and rolling volatility.
- **Leverage toggle:** let the user model borrowing against the fund (for example two or four times) and see how drawdowns, the chance of being wiped out, and forced selling change.

## 5. Reality checks
- Costs: fund expense ratios and an editable brokerage fee, shown as the drag on return and as rands lost over 10 and 20 years.
- Backtest against the Top 40, the S&P 500 in rand, a balanced benchmark and an equal-weight version of the fund, with periodic rebalancing.
- "The optimiser would hold these same assets in these weights instead", with the difference shown and a note on why optimisers are unreliable.

## 6. The library
A section anyone can read without building a fund:
- **Why we invest at all:** what a share is, the origin of the joint-stock company (the Dutch East India Company, 1602, limited liability), shares as a claim on company earnings and why that makes equities a traditional inflation hedge, and what bonds, property, cash and offshore assets each do in a fund.
- **How bubbles work:** the five phases (displacement, euphoria, mania, distress, revulsion), illustrated with real episodes.
- **Case files.** The list below is a minimum, not the full set. Research and add every major episode a fund builder should know, aiming for at least 30, grouped by the lesson they teach. Propose the full list to me before writing. Each file covers what happened, why, who was hurt, a chart, and the lesson for someone building a fund.
  - Bubbles and manias: tulip mania, the South Sea bubble, 1929, Japan's 1989 peak, the dot-com bubble, crypto in 2022.
  - Leverage and forced selling: LTCM, 2008, Archegos, and Situational Awareness (2026: a leveraged long AI infrastructure, short software fund that went from about $45 billion to about $10 billion in weeks and sold its public book to Citadel after margin calls; the lessons are single-theme concentration, leverage, a hedge that failed at the same time as the main bet, and being right on the thesis but ruined on the timing).
  - Inflation and rates: 1970s stagflation, the Volcker shock, 2022.
  - Currency and country risk: the 1997 Asian crisis, the 1998 rand crisis, the December 2015 rand crash, Zimbabwe's hyperinflation.
  - Fraud and governance: Enron, Madoff, Wirecard, Steinhoff, Tongaat Hulett, and South African scams such as Mirror Trading International.
  - Banks and credit: Lehman, African Bank, VBS, Silicon Valley Bank.
  - Sector collapses: the 2018 South African listed property crash, the 2014 to 2016 commodity slump, platinum's long decline.
  - Shocks: the 1987 crash, March 2020.
- **Counterexamples:** long periods where patient, diversified, low-cost investing worked, so the library teaches what to do and not only what to fear.
- **Sector histories:** how resources, banks, tech, property, retail and telecoms have behaved over decades, with the South African angle (the JSE's mining roots, Naspers and index concentration).
- **Theory, explained:** diversification, the efficient frontier, risk contribution, benchmarks, tracking error, active weights, the information ratio and the Fundamental Law of Active Management, leverage and margin calls, fees and compounding, estimation error.

## 7. Contextual insights (pop-ups)
- A rules engine: each rule has a trigger computed from the fund, a short message, a severity, and a link into the library.
- Pop-ups appear when a change first trips a rule, are dismissible, never block the user, and are collected in an "insights" panel.
- Pattern for each: what I noticed in your fund, what history or theory says about it, where to read more.
- There must be at least one rule for every lesson group in the case files. Starter rules, at minimum:
  - Heavy tech weighting: the dot-com case file.
  - A fund built around a single theme (for example AI): Situational Awareness.
  - Leverage switched on: LTCM, Archegos and Situational Awareness.
  - Resources-heavy: commodity cycles and the JSE's history.
  - Bank-heavy: 2008 and African Bank.
  - One holding above a threshold share of the fund or its risk: Steinhoff and single-stock risk.
  - Everything South African: home bias and the 2015 rand crash.
  - Listed property concentration: the 2018 collapse.
  - Holdings that rose very sharply in the past year: the five bubble phases.
  - High average correlation: "you own many things but one bet".
  - Relying on bonds to offset shares: the 1970s and 2022.
  - High total fees: what they cost over 20 years.
  - A holding whose share of risk is far above its share of the money.
  - One active bet consuming most of the tracking error budget.
  - A large share of the fund that couldn't be sold in a hurry.
  - An unlisted holding promising unusually high returns: the scam case files.

## 8. Before you add it: due diligence
A checklist shown when adding any holding, tailored to its type, each item explained and auto-filled from data where possible:
- **A company:** what it does and how it earns money, earnings and cash flow trend, debt, valuation ratios against its own history and its sector, dividend record, governance red flags (auditor changes, restated accounts, complex structures, a dominant chief executive), and dependence on one commodity, customer or currency.
- **A unit trust or ETF:** mandate and benchmark, total fees (TER, transaction costs, performance fees), performance after fees against the benchmark over long periods, top holdings and overlap with what the user already holds, manager tenure, fund size, and regulatory classification.
- **Unlisted and alternative investments** (property developments, private businesses, syndications): the promoter and their track record, whether the provider is licensed, where the returns actually come from, how realistic the projections are, how and when money can be withdrawn, how much debt the project carries, the legal structure and what is actually owned, and classic scam warning signs (guaranteed high returns, pressure to commit quickly, returns paid from new investors' money).

## 9. Holding types beyond listed shares
- **Unit trusts:** try to fetch price history; where none is available, let the user upload a price file, or fall back to modelling the fund from its published asset allocation. Label clearly which method is in use. Apply look-through and overlap analysis.
- **Unlisted investments:** no price history exists, so do not fake one. The user enters an expected return, a range of outcomes, a lock-in period and a chance of total loss. Show these in a separate illiquid sleeve, include them in scenario and Monte Carlo analysis using those stated assumptions, and report the share of the fund that is illiquid.

## 10. The fact sheet
- Generate a one-page fund fact sheet styled like a real South African unit trust fact sheet: fund name, objective, holdings table, sector and country charts, performance against benchmark, risk statistics, fees, and the top three insights. Exportable as a PDF, so friends can send each other their funds.

## Quality bar
- Unit tests for the maths: weights sum to one, risk contributions sum to total risk, Monte Carlo VaR converges to the parametric answer in the normal case.
- Active bets check: with a 1% tracking error target, volatilities of 21% and 8% and a correlation of -0.01, the pairwise bet is about 4.4%, with roughly 87% and 13% of tracking error variance from the two sides.
- Every pop-up rule has a test fund that should trigger it and one that should not.
- Fixed random seeds with a visible seed input.
- Clear warnings when a holding has too little history, and a sensible rule for how the fund's statistics handle it.
- Works on a phone, since friends will open the link there.
- A methods page with all formulas in LaTeX.
- Finish each phase by running the app, checking it in the browser, and fixing what's broken before moving on.
