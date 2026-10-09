# Build-a-Fund Lab

An educational Streamlit app where someone builds their own "unit trust" from
investments available on EasyEquities (JSE shares, JSE ETFs, US shares, unit
trusts) plus unlisted holdings, and sees how each holding changes the fund's
risk, expected return and character. It includes a sourced library of finance
history and theory, plus rule-based insight pop-ups. Audience: a statistics
Honours student and smart friends who are new to investing.

**Before doing any work, read [PLAN.md](PLAN.md) (current status, decisions,
next step) and [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) (the full spec).**

## Run and test (Windows, Git Bash paths)

```bash
python -m venv .venv                      # Python 3.10
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest -q         # maths tests
.venv/Scripts/streamlit run app.py        # the app (app.py not written yet; see PLAN.md)
```

pip has hung on this machine before during a single large install. If it
stalls, install in smaller groups and log the output to a file.

## Hard constraints

- **Zero cost.** No paid APIs, no keys that need a credit card. Data comes from
  yfinance plus a bundled sample dataset. Deployment is Streamlit Community Cloud.
- **Education, not advice.** Never tell the user to buy or sell. Explain what a
  characteristic means and what history says about it.
- **Every historical claim and figure is sourced** with a link and an access
  date. If something can't be verified, leave it out and tell the user.
- Library content, glossary and pop-up rules live in Markdown/YAML under
  `content/` so they can be edited without touching code.

## Code conventions

- `fundlab/` is pure Python (numpy, pandas, scipy) and **never imports
  Streamlit**. All UI lives in `app.py`, `pages/` and `ui/`.
- Statistics are computed from **weekly simple returns** and annualised with
  `fundlab.PERIODS_PER_YEAR = 52`. Everything is in rand: US prices are converted
  with USD/ZAR, and JSE prices come from Yahoo in cents (divide by 100).
- Weights are always **derived from rand amounts** (`Fund.weights()`) and never stored.
- Weights, mu and cov are pandas objects indexed by ticker; functions align by
  index, not position.
- Losses (VaR, ES) are reported as positive fractions; drawdowns as negative fractions.
- `Fund` edits (`with_amount`, `without`) return a new `Fund`, so before/after comparisons are easy.
- Random numbers use `np.random.default_rng(seed)` with a user-visible seed (default 42).
- Docstrings state the formula being implemented. Comments are sparse.
- Tests go in `tests/` and run with pytest.

## Working rules

- Keep `PLAN.md` current whenever a phase finishes, a decision is made or the plan changes.
- Commit after each working step with a clear message.
- Finish each step by running the app and the tests and fixing what's broken.
- When a session gets long, stop at a natural point, update `PLAN.md`, commit,
  and tell the user so they can start a fresh session.
