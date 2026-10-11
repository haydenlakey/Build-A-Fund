"""Due-diligence checklists by holding type, auto-filled from data where possible (no Streamlit).

The wording lives in content/due_diligence.yaml; this module only attaches findings:
    finding  a plain-language description of what the data shows ("" if nothing to show)
    flag     True when the finding is worth a closer look (an app rule of thumb, stated in the text)
Nothing here recommends buying or selling.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .unlisted import EXTREME_RETURN, HIGH_RETURN, Assumptions

CONTENT_PATH = Path(__file__).resolve().parent.parent / "content" / "due_diligence.yaml"
# rules of thumb behind the flags (shown with each finding)
NET_DEBT_EBITDA = 3.0
CASH_CONVERSION = 0.8
PE_STRETCH = 1.5
FEE_FLAG = 0.015
ISS_FLAG = 8
OVERLAP_FLAG = 3
FINANCIALS = {"Financial Services"}


@dataclass
class Item:
    id: str
    question: str
    why: str
    auto: bool = False
    read: str = ""
    links: list = field(default_factory=list)  # [{title, url, accessed}]
    finding: str = ""
    flag: bool = False


@dataclass
class Checklist:
    kind: str  # company | fund | unlisted
    title: str
    intro: str
    items: list[Item]
    note: str = ""  # data source and date

    def item(self, id_: str) -> Item:
        return next(i for i in self.items if i.id == id_)

    @property
    def flags(self) -> int:
        return sum(i.flag for i in self.items)


def load_content(path: Path | str = CONTENT_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _blank(content: dict, kind: str) -> Checklist:
    sec, links = content[kind], content.get("links", {})
    items = [Item(id=d["id"], question=d["question"], why=d["why"], auto=bool(d.get("auto")), read=d.get("read", ""),
                  links=[links[k] for k in d.get("links", []) if k in links]) for d in sec["items"]]
    return Checklist(kind, sec["title"], sec.get("intro", ""), items)


def _money(x: float | None, cur: str) -> str:
    if x is None:
        return "n/a"
    sym = {"ZAR": "R", "USD": "$", "EUR": "€", "GBP": "£"}.get(cur, cur + " ")
    a = abs(x)
    s = f"{a / 1e9:,.1f} bn" if a >= 1e9 else f"{a / 1e6:,.0f} m" if a >= 1e6 else f"{a:,.0f}"
    return ("-" if x < 0 else "") + sym + s


def _sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return " ".join(parts[:n])


# ---- a company -----------------------------------------------------------------------------

def company_checklist(content: dict, ticker: str, entry: dict | None, f: dict | None, peers: dict[str, dict],
                      price_native: pd.Series | None = None, fetched: str | None = None,
                      sector_of: dict[str, str] | None = None) -> Checklist:
    """`f` is this company's fundamentals (fundlab.fundamentals), `peers` the snapshot's companies,
    `price_native` its weekly price in the quote currency (for P/E history of US shares), `sector_of`
    the app's own sector per ticker (peers are grouped by it; Yahoo's sector is the fallback)."""
    sector_of = sector_of or {}
    c = _blank(content, "company")
    entry = entry or {}
    f = f or {}
    cur = f.get("currency") or ("ZAR" if ticker.endswith(".JO") else "USD")
    sector = entry.get("sector") or f.get("sector") or ""
    c.note = (f"Company figures from Yahoo Finance, read {f.get('fetched') or fetched or 'n/a'}; statements in "
              f"{cur}. Yahoo's figures can contain errors, so treat them as a starting point.") if f else \
        "No company figures available from Yahoo for this ticker."

    it = c.item("business")
    bits = [x for x in (sector, entry.get("industry") or f.get("industry")) if x]
    it.finding = (" · ".join(bits) + ". " if bits else "") + _sentences(f.get("summary", ""))

    rows = [r for r in f.get("annual", []) if r.get("revenue") is not None or r.get("net_income") is not None]
    it = c.item("earnings")
    if len(rows) >= 2:
        first, last = rows[0], rows[-1]
        n = len(rows) - 1
        txt = []
        if first.get("revenue") and last.get("revenue") and first["revenue"] > 0:
            g = (last["revenue"] / first["revenue"]) ** (1 / n) - 1
            txt.append(f"Sales {'grew' if g >= 0 else 'shrank'} about {abs(g):.0%} a year over the last {n} "
                       f"financial years ({_money(first['revenue'], cur)} to {_money(last['revenue'], cur)}).")
            it.flag |= g < 0
        ni = [r["net_income"] for r in rows if r.get("net_income") is not None]
        losses = sum(x < 0 for x in ni)
        if ni:
            txt.append(f"Profit in the latest year: {_money(ni[-1], cur)}"
                       + (f"; a loss in {losses} of the {len(ni)} years shown." if losses else "."))
            it.flag |= losses > 0
        pairs = [(r["net_income"], r["op_cash_flow"]) for r in rows
                 if r.get("net_income") is not None and r.get("op_cash_flow") is not None]
        if pairs and sum(p for p, _ in pairs) > 0:
            conv = sum(o for _, o in pairs) / sum(p for p, _ in pairs)
            txt.append(f"Cash from operations was {conv:.1f}× reported profit over these years"
                       + (f" (below {CASH_CONVERSION:.1f}×, worth a closer look)." if conv < CASH_CONVERSION else "."))
            it.flag |= conv < CASH_CONVERSION
        it.finding = " ".join(txt)
    else:
        it.finding = "Not enough annual figures on Yahoo to show a trend."

    it = c.item("debt")
    debt, cash, ebitda = f.get("total_debt"), f.get("total_cash"), f.get("ebitda")
    if sector in FINANCIALS:
        it.finding = ("For banks and insurers, borrowing is the raw material of the business, so debt ratios "
                      "aren't comparable with other companies; their capital ratios (in the annual report) are the "
                      "usual measure.")
    elif debt is not None:
        nd = debt - (cash or 0)
        txt = [f"Debt {_money(debt, cur)}, cash {_money(cash, cur)}, so net debt {_money(nd, cur)}."]
        if ebitda and ebitda > 0:
            r = nd / ebitda
            txt.append(f"That is {r:.1f} years of operating earnings (EBITDA)"
                       + (f", above this app's rule of thumb of {NET_DEBT_EBITDA:.0f}." if r > NET_DEBT_EBITDA else "."))
            it.flag = r > NET_DEBT_EBITDA
        elif ebitda is not None:
            txt.append("Operating earnings (EBITDA) were negative, so the debt isn't covered by current earnings.")
            it.flag = nd > 0
        it.finding = " ".join(txt)
    else:
        it.finding = "No debt figures on Yahoo."

    it = c.item("valuation")
    pe, pb = f.get("trailing_pe"), f.get("price_to_book")
    txt = []
    if pe:
        txt.append(f"Price-to-earnings {pe:.1f}" + (f", price-to-book {pb:.1f}" if pb else "") + " (Yahoo).")
        my_sector = sector or f.get("sector")
        sec_pes = [p.get("trailing_pe") for t, p in peers.items() if t != ticker
                   and sector_of.get(t, p.get("sector")) == my_sector and p.get("trailing_pe") and 0 < p["trailing_pe"] < 200]
        if len(sec_pes) >= 3:
            med = float(np.median(sec_pes))
            txt.append(f"The median among the app's {len(sec_pes)} other {my_sector} companies is {med:.1f}.")
            it.flag |= pe > PE_STRETCH * med
        hist = _pe_history(f, price_native) if not ticker.endswith(".JO") else []
        if len(hist) >= 3:
            hm = float(np.median(hist))
            txt.append(f"Its own price-to-earnings at its last {len(hist)} year-ends had a median of about {hm:.1f} "
                       "(prices adjusted for dividends, so slightly understated).")
            it.flag |= pe > PE_STRETCH * hm
        elif ticker.endswith(".JO"):
            txt.append("A comparison with its own history isn't shown for JSE shares: Yahoo's per-share history mixes "
                       "cents and rand and isn't adjusted for share splits.")
        if it.flag:
            txt.append(f"(Flagged when more than {PE_STRETCH:.1f}× the comparison, an app rule of thumb.)")
    elif f:
        txt.append("No price-to-earnings ratio on Yahoo (often because profits were negative).")
    it.finding = " ".join(txt)

    it = c.item("dividends")
    dv = {int(k): v for k, v in (f.get("dividends_by_year") or {}).items()}
    if dv:
        last_full = max(dv) - (1 if max(dv) >= pd.Timestamp.today().year else 0)
        years = list(range(last_full - 9, last_full + 1))
        paid = [y for y in years if dv.get(y, 0) > 0]
        cuts = [y for y in years[1:] if dv.get(y - 1, 0) > 0 and dv.get(y, 0) < 0.9 * dv[y - 1]]
        it.finding = (f"Paid dividends in {len(paid)} of the 10 calendar years {years[0]}-{years[-1]}"
                      + (f"; the yearly total fell by more than 10% in {', '.join(map(str, cuts))}" if cuts
                         else "; the yearly total never fell by more than 10%")
                      + (f". Yield about {f['dividend_yield_pct']:.1f}%." if f.get("dividend_yield_pct") else ".")
                      + (" Totals are per calendar year in the share's trading currency, so a payment that moved "
                         "between years, or the exchange rate, can look like a cut." if cuts else ""))
        it.flag = len(paid) < 10 or len(cuts) >= 2
    else:
        it.finding = "No dividends recorded on Yahoo."

    it = c.item("governance")
    iss = {k: f.get(f"iss_{k}") for k in ("overall", "audit", "board", "compensation", "shareholder")}
    if iss["overall"]:
        parts = ", ".join(f"{k} {int(v)}" for k, v in iss.items() if v)
        it.finding = (f"ISS governance risk scores (1 = lower risk, 10 = higher, via Yahoo): {parts}. They score "
                      "board structure, pay and shareholder rights; they say nothing about whether the accounts are "
                      "honest. Auditor changes and restatements are in the company's SENS announcements and annual "
                      "reports.")
        it.flag = iss["overall"] >= ISS_FLAG
    else:
        it.finding = ("No governance scores on Yahoo for this company. Auditor changes and restatements are in its "
                      "SENS announcements and annual reports.")

    it = c.item("dependence")
    exp = entry.get("exposure")
    words = {"sa": "Earns mostly in South Africa, so it rides on the SA economy and the rand.",
             "sa_dollar": "SA operations selling a dollar-priced product: its rand profits rise when the rand weakens "
                          "and fall with the product's price.",
             "global": "Earns mostly offshore, so in rand it tends to gain when the rand weakens.",
             "africa": "Earns mostly in Africa outside South Africa: several currencies and economies at once.",
             "mixed": "Earns in South Africa and offshore."}
    txt = [words[exp]] if exp in words else []
    if sector in ("Basic Materials", "Energy"):
        txt.append(f"As a {sector.lower()} company its profits follow commodity prices.")
        it.flag = True
    it.finding = " ".join(txt) or "Not classified in the app's data; the annual report's segment breakdown shows it."
    return c


def _pe_history(f: dict, price: pd.Series | None) -> list[float]:
    if price is None or price.dropna().empty:
        return []
    p = price.dropna()
    out = []
    for r in f.get("annual", []):
        eps = r.get("eps")
        ts = pd.Timestamp(r["year_end"])
        if not eps or eps <= 0 or ts < p.index[0]:
            continue
        out.append(float(p.asof(ts) / eps))
    return out


# ---- a fund ---------------------------------------------------------------------------------

def fund_checklist(content: dict, name: str, *, tracks: str = "", asisa: str = "", benchmark: str = "",
                   ter: float | None = None, tc: float | None = None, performance_fee: str = "", manager: str = "",
                   inception: str = "", size: str = "", sheet: dict | None = None, candidate_companies=None,
                   fund_companies=None, kind_label: str = "ETF") -> Checklist:
    """`candidate_companies` are the fund's known top holdings (DataFrame key, name, frac);
    `fund_companies` the current fund's look-through companies (key, name, total)."""
    c = _blank(content, "fund")
    sheet = sheet or {}
    c.note = (f"Fact sheet data as at {sheet.get('as_of')}." if sheet.get("as_of") else "") + \
        (" Costs and look-through from the app's data files (each names its source)." if ter is not None else "")

    it = c.item("mandate")
    if tracks:
        it.finding = f"An index tracker: it aims to follow {tracks}, less its costs."
    elif asisa or benchmark:
        it.finding = (f"ASISA category: {asisa}. " if asisa else "") + (f"Benchmark: {benchmark}." if benchmark else "")
    else:
        it.finding = "Not in the app's data: the fund's fact sheet (minimum disclosure document) states both."

    it = c.item("fees")
    if ter is not None:
        total = ter + (tc or 0)
        it.finding = (f"Total expense ratio {ter:.2%}" + (f" plus transaction costs {tc:.2%}" if tc else "")
                      + f": about R{total * 10_000:,.0f} a year on every R10 000."
                      + (f" Performance fee: {performance_fee}." if performance_fee else ""))
        it.flag = total > FEE_FLAG
        if it.flag:
            it.finding += f" (Above {FEE_FLAG:.1%} a year, an app rule of thumb for a closer look.)"
    else:
        it.finding = "Not in the app's data."

    it = c.item("performance")
    if sheet.get("url"):
        it.finding = (f"The fact sheet (data as at {sheet.get('as_of')}) shows returns after fees against the "
                      "benchmark over 1, 3, 5, 10 years and since launch: [open it](" + sheet["url"] + ").")
    elif tracks:
        it.finding = ("For an index tracker the question is how closely it follows its index: the gap (tracking "
                      "difference) is mostly its costs. The provider's fact sheet shows both returns.")
    else:
        it.finding = "See the fund's fact sheet."

    it = c.item("overlap")
    if candidate_companies is not None and len(candidate_companies):
        cand = candidate_companies.set_index("key")
        if fund_companies is not None and len(fund_companies):
            fc = fund_companies.set_index("key")
            both = [k for k in cand.index if k in fc.index]
            if both:
                parts = [f"{cand.at[k, 'name']} ({cand.at[k, 'frac']:.1%} of this fund; {fc.at[k, 'total']:.1%} of yours "
                         "already)" for k in both]
                it.finding = (f"{len(both)} of its {len(cand)} published top holdings are already in your fund: "
                              + "; ".join(parts) + ".")
                it.flag = len(both) >= OVERLAP_FLAG
            else:
                it.finding = f"None of its {len(cand)} published top holdings are in your fund yet."
        else:
            it.finding = "Top holdings: " + ", ".join(f"{r['name']} {r['frac']:.1%}" for _, r in cand.head(5).iterrows()) + "."
    else:
        it.finding = "No top holdings with weights in the app's data."

    c.item("manager").finding = (f"{manager}" + (f"; fund running since {inception}." if inception else ".")) if manager \
        else "Not in the app's data: the fact sheet names the managers."
    c.item("size").finding = size or "Not in the app's data: the fact sheet gives the fund size."
    c.item("classification").finding = (f"{asisa}." if asisa else
                                        f"A JSE- or US-listed {kind_label}." if tracks else "Not in the app's data.")
    return c


# ---- unlisted -------------------------------------------------------------------------------

def unlisted_checklist(content: dict, a: Assumptions) -> Checklist:
    c = _blank(content, "unlisted")
    c.note = "Findings below come only from the assumptions you entered."
    it = c.item("realistic")
    it.finding = (f"You entered {a.exp_return:.0%} a year if it goes to plan; after a {a.p_loss:.0%} yearly chance of "
                  f"total loss that is an expected {a.expected_return:.1%}.")
    it.flag = a.exp_return >= HIGH_RETURN
    if a.exp_return >= EXTREME_RETURN:
        it.finding += " That is far beyond what any listed market has paid over long periods."
    elif it.flag:
        it.finding += f" That is above {HIGH_RETURN:.0%}, this app's rule of thumb for an unusually high promise."
    it = c.item("withdrawal")
    if a.lockin_years > 0:
        it.finding = (f"Locked in for {a.lockin_years:g} years; on your numbers, the chance it is lost before then is "
                      f"{a.p_lost_over(a.lockin_years):.0%}.")
        it.flag = a.lockin_years >= 5
    else:
        it.finding = "You entered no lock-in. Check the agreement: many unlisted investments have notice periods."
    it = c.item("scam_signs")
    signs = []
    if a.high - a.low < 0.05:
        signs.append("an almost guaranteed return (a very narrow range)")
    if a.p_loss == 0:
        signs.append("no chance of losing everything")
    if a.exp_return >= EXTREME_RETURN:
        signs.append("an extreme promised return")
    it.finding = ("Your inputs describe " + ", ".join(signs) + "." if signs else
                  "Nothing in your inputs matches these patterns; the others (pressure, recruiting) only you can see.")
    it.flag = bool(signs)
    return c
