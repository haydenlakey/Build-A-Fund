"""Company fundamentals for the due-diligence checklist: a dated snapshot plus live fetching.

The snapshot (data/sample/fundamentals.json) is built by scripts/build_fundamentals.py for the
universe's shares; tickers outside it are fetched live from Yahoo (yfinance) when possible.
Figures are as Yahoo reports them; statements are in the company's reporting currency.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import pandas as pd

from .data import ROOT

SNAPSHOT_PATH = ROOT / "data" / "sample" / "fundamentals.json"
INFO_KEYS = {  # our name -> Yahoo info key
    "summary": "longBusinessSummary", "sector": "sector", "industry": "industry",
    "currency": "financialCurrency", "trailing_pe": "trailingPE", "price_to_book": "priceToBook",
    "debt_to_equity": "debtToEquity", "total_debt": "totalDebt", "total_cash": "totalCash", "ebitda": "ebitda",
    "profit_margin": "profitMargins", "roe": "returnOnEquity", "dividend_yield_pct": "dividendYield",
    "payout_ratio": "payoutRatio", "iss_audit": "auditRisk", "iss_board": "boardRisk",
    "iss_compensation": "compensationRisk", "iss_shareholder": "shareHolderRightsRisk", "iss_overall": "overallRisk",
}
ROWS = {"revenue": "Total Revenue", "net_income": "Net Income", "shares": "Diluted Average Shares", "eps": "Diluted EPS"}


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def fetch(ticker: str) -> dict | None:
    """One company's fundamentals from Yahoo, or None if Yahoo has nothing usable."""
    import yfinance as yf

    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        inc, cf, divs = tk.income_stmt, tk.cashflow, tk.dividends
    except Exception:  # noqa: BLE001 - network or Yahoo errors
        return None
    if not info.get("longBusinessSummary") and (inc is None or inc.empty):
        return None
    out = {"ticker": ticker, "fetched": date.today().isoformat()}
    for k, src in INFO_KEYS.items():
        v = info.get(src)
        out[k] = v if isinstance(v, str) else _num(v)
    annual = []
    if inc is not None and not inc.empty:
        for col in inc.columns:
            row = {"year_end": pd.Timestamp(col).date().isoformat()}
            for k, src in ROWS.items():
                row[k] = _num(inc.at[src, col]) if src in inc.index else None
            row["op_cash_flow"] = (_num(cf.at["Operating Cash Flow", col])
                                   if cf is not None and "Operating Cash Flow" in cf.index and col in cf.columns else None)
            if any(row[k] is not None for k in ("revenue", "net_income")):
                annual.append(row)
    out["annual"] = sorted(annual, key=lambda r: r["year_end"])
    by_year = {}
    if divs is not None and len(divs):
        for ts, v in divs.items():
            y = str(pd.Timestamp(ts).year)
            by_year[y] = by_year.get(y, 0.0) + float(v)
    out["dividends_by_year"] = by_year
    return out


def load_snapshot(path: Path | str = SNAPSHOT_PATH) -> dict:
    p = Path(path)
    if not p.exists():
        return {"built": None, "companies": {}}
    return json.loads(p.read_text(encoding="utf-8"))
