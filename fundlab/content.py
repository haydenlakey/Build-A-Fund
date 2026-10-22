"""Library articles: Markdown files with a YAML header, under content/library/.

Each file looks like

    ---
    title: Dot-com bubble (1995-2002)
    section: case            # basics | bubbles | case | counter | sector | theory
    group: Bubbles and manias   # case files only: the lesson group
    order: 8                 # position within its section or group
    summary: One or two sentences shown on the card.
    lesson: The one-line lesson for someone building a fund.
    years: "1995-2002"       # optional
    chart:                   # optional
      kind: prices           # prices (from the app's price data) | points (sourced values in this file) |
                             # none (no sourced series exists; `reason` says why, shown instead of a chart)
      tickers: [^J200.JO]
      start: 2007-06-01
      end: 2009-12-31
      title: ...
      unit: ...              # points charts: y-axis label
      points: [[1929-09-03, 381.17], ...]   # one series (named by `series`), or
      lines: {Name A: [[date, value], ...], Name B: [...]}   # several named series
      source: ...            # points charts: where the values come from
    sources:
      - {title: ..., url: https://..., accessed: 2026-10-09}
    ---
    Markdown body...

Nothing here imports Streamlit, so the files can be validated in tests.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

LIBRARY_PATH = Path(__file__).resolve().parent.parent / "content" / "library"

SECTIONS = {
    "basics": "Why we invest",
    "bubbles": "How bubbles work",
    "case": "Case files",
    "counter": "When patience paid",
    "sector": "Sector histories",
    "theory": "Theory, explained",
}
GROUPS = [
    "Bubbles and manias", "Leverage and forced selling", "Inflation and rates", "Currency and country",
    "Fraud and governance", "Banks and credit", "Sector collapses", "Shocks", "Liquidity and locked money",
]


@dataclass
class Article:
    slug: str
    title: str
    section: str
    body: str
    summary: str = ""
    lesson: str = ""
    group: str = ""
    order: float = 0
    years: str = ""
    chart: dict | None = None
    sources: list[dict] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    path: Path | None = None


def parse(text: str, slug: str, path: Path | None = None) -> Article:
    if not text.startswith("---"):
        raise ValueError(f"{slug}: missing YAML header")
    _, header, body = re.split(r"^---\s*?$", text, maxsplit=2, flags=re.M)
    meta = yaml.safe_load(header) or {}
    for k in ("title", "section"):
        if not meta.get(k):
            raise ValueError(f"{slug}: header needs '{k}'")
    if meta["section"] not in SECTIONS:
        raise ValueError(f"{slug}: unknown section {meta['section']!r}")
    return Article(
        slug=slug, title=str(meta["title"]), section=meta["section"], body=body.strip(),
        summary=str(meta.get("summary", "")).strip(), lesson=str(meta.get("lesson", "")).strip(),
        group=str(meta.get("group", "")), order=float(meta.get("order", 0)), years=str(meta.get("years", "")),
        chart=meta.get("chart"), sources=list(meta.get("sources") or []), related=list(meta.get("related") or []),
        path=path,
    )


def load_library(path: Path | str = LIBRARY_PATH) -> dict[str, Article]:
    """All articles keyed by slug (the file name without .md), files starting with '_' skipped."""
    out = {}
    for f in sorted(Path(path).glob("*.md")):
        if f.name.startswith("_"):
            continue
        out[f.stem] = parse(f.read_text(encoding="utf-8"), f.stem, f)
    return out


def by_section(articles: dict[str, Article], section: str) -> list[Article]:
    items = [a for a in articles.values() if a.section == section]
    if section == "case":
        return sorted(items, key=lambda a: (GROUPS.index(a.group) if a.group in GROUPS else 99, a.order, a.title))
    return sorted(items, key=lambda a: (a.order, a.title))
