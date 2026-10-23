"""The fact sheet as a one-page A4 PDF (fpdf2 for the page, matplotlib for the charts).

Both are pure-Python wheels, so this works on Streamlit Community Cloud with no system packages.
Charts use the light palette from ui/theme.py (a PDF is a printed page). The font is DejaVu Sans,
which ships with matplotlib and covers R, €, − and ≈. matplotlib and fpdf2 are imported on first
use, so they don't slow down the app's start-up.
"""
from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from fundlab import factsheet
from fundlab.factsheet import FactSheet
from ui.theme import LIGHT

PAGE_W, PAGE_H, MARGIN = 210.0, 297.0, 10.0
LEFT_W, GAP = 116.0, 6.0
RIGHT_X = MARGIN + LEFT_W + GAP
RIGHT_W = PAGE_W - MARGIN - RIGHT_X
QR_MM = 27.0
QR_MAX_CHARS = 2000  # longer share links make a QR code too dense to scan from a screen
FONT = "DejaVu"


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ---- charts -----------------------------------------------------------------------------------

def _axes(w_mm: float, h_mm: float):
    from matplotlib.figure import Figure
    p = LIGHT
    fig = Figure(figsize=(w_mm / 25.4, h_mm / 25.4), dpi=200)
    fig.patch.set_facecolor("white")
    ax = fig.add_subplot()
    ax.set_facecolor("white")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(p["axis"])
    ax.tick_params(colors=p["muted"], labelsize=6, length=2)
    return fig, ax


def _png(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, facecolor="white")
    buf.seek(0)
    return buf


def growth_chart(growth: pd.DataFrame, bench_name: str, w_mm: float, h_mm: float) -> io.BytesIO:
    p = LIGHT
    fig, ax = _axes(w_mm, h_mm)
    ax.plot(growth.index, growth["fund"], color=p["series"][0], lw=1.3, label="Your fund")
    if "benchmark" in growth:
        b = growth["benchmark"].dropna()
        ax.plot(b.index, b.values, color=p["series"][1], lw=0.9, label=bench_name)
    ax.axhline(1000, color=p["muted"], lw=0.6, ls=":")
    ax.set_xlim(growth.index[0], growth.index[-1])
    from matplotlib import dates
    ax.xaxis.set_major_locator(dates.YearLocator())
    ax.xaxis.set_major_formatter(dates.DateFormatter("%Y"))
    ax.grid(axis="y", color=p["grid"], lw=0.5)
    ax.yaxis.set_major_formatter(lambda v, _: f"R{v:,.0f}".replace(",", " "))
    ax.legend(loc="upper left", fontsize=6, frameon=False, labelcolor=p["ink2"])
    fig.tight_layout(pad=0.3)
    return _png(fig)


def bar_chart(s: pd.Series, w_mm: float, h_mm: float) -> io.BytesIO:
    p = LIGHT
    fig, ax = _axes(w_mm, h_mm)
    s = s.sort_values()
    ax.barh(list(s.index), s.values, color=p["series"][0], height=0.6)
    for y, v in enumerate(s.values):
        ax.text(v, y, f" {v:.0%}", va="center", fontsize=5.5, color=p["ink2"])
    ax.set_xlim(0, max(s.max() * 1.25, 0.01))
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", labelsize=5.5, colors=p["ink2"], length=0)
    fig.tight_layout(pad=0.3)
    return _png(fig)


# ---- page -------------------------------------------------------------------------------------

class _Page:
    def __init__(self):
        import matplotlib
        from fpdf import FPDF
        fonts = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(False)
        pdf.set_margins(MARGIN, MARGIN, MARGIN)
        pdf.add_font(FONT, "", str(fonts / "DejaVuSans.ttf"))
        pdf.add_font(FONT, "B", str(fonts / "DejaVuSans-Bold.ttf"))
        pdf.set_title("Model fund fact sheet")
        pdf.set_creator("Build-a-Fund Lab")
        pdf.add_page()
        self.pdf = pdf

    def font(self, size: float, bold: bool = False, colour: str = "ink") -> None:
        self.pdf.set_font(FONT, "B" if bold else "", size)
        self.pdf.set_text_color(*_rgb(LIGHT[colour]))

    def lines(self, text: str, w: float) -> list[str]:
        from fpdf.enums import MethodReturnValue
        return self.pdf.multi_cell(w, 1, text, dry_run=True, output=MethodReturnValue.LINES) or [""]

    def text(self, x: float, y: float, w: float, text: str, lh: float, align: str = "L",
             max_lines: int | None = None, link: str = "") -> float:
        """Wrapped text at (x, y); returns the y below it. Text beyond max_lines ends in an ellipsis."""
        rows = self.lines(text, w)
        if max_lines is not None and len(rows) > max_lines:
            rows = rows[:max_lines]
            rows[-1] = rows[-1].rstrip()[:-1].rstrip() + "…"
        for i, row in enumerate(rows):
            self.pdf.set_xy(x, y + i * lh)
            self.pdf.cell(w, lh, row, align=align, link=link)
        return y + len(rows) * lh

    def heading(self, x: float, y: float, w: float, title: str) -> float:
        self.font(9, bold=True)
        self.pdf.set_xy(x, y)
        self.pdf.cell(w, 5, title)
        return y + 5.5

    def table(self, x: float, y: float, widths: list[float], rows: list[tuple], header: tuple | None = None,
              text_cols: int = 1, size: float = 6.6, lh: float = 3.1) -> float:
        """Rows of wrapped cells with a thin rule under each; returns the y below the table."""
        pdf = self.pdf
        pdf.set_draw_color(*_rgb(LIGHT["grid"]))
        pdf.set_line_width(0.2)
        for r, row in enumerate(([header] if header else []) + list(rows)):
            is_head = header is not None and r == 0
            self.font(size, colour="muted" if is_head else "ink")
            heights = []
            for i, cell in enumerate(row):
                heights.append(len(self.lines(str(cell), widths[i] - 1.2)))
            h = max(heights) * lh + 1.0
            cx = x
            for i, cell in enumerate(row):
                self.text(cx + 0.6, y + 0.5, widths[i] - 1.2, str(cell), lh, align="L" if i < text_cols else "R")
                cx += widths[i]
            y += h
            pdf.line(x, y, x + sum(widths), y)
        return y + 1.5


# when a sheet doesn't fit, each level makes it more compact: growth chart height, bar height per row,
# lines of each insight's text
LAYOUTS = [(50.0, 4.2, 2), (42.0, 3.5, 1), (36.0, 3.0, 0)]


def render(sheet: FactSheet, share_url: str = "", article_url: Callable[[str], str] | None = None) -> bytes:
    """The sheet as PDF bytes: one A4 page, made more compact if the content would run into the footer."""
    for level in range(len(LAYOUTS)):
        try:
            return _render(sheet, share_url, article_url, *LAYOUTS[level])
        except OverflowError:
            if level == len(LAYOUTS) - 1:
                raise
    raise AssertionError("unreachable")


def _render(sheet: FactSheet, share_url: str, article_url: Callable[[str], str] | None,
            growth_h: float, bar_row: float, insight_lines: int) -> bytes:
    page = _Page()
    pdf, p = page.pdf, LIGHT

    # header band
    pdf.set_fill_color(*_rgb(p["series"][0]))
    pdf.rect(0, 0, PAGE_W, 3, style="F")
    qr = _qr(share_url) if share_url else None
    title_w = PAGE_W - 2 * MARGIN - (QR_MM + 4 if qr is not None else 0)
    page.font(17, bold=True)
    y = page.text(MARGIN, 7, title_w, sheet.name, 7.5, max_lines=1)
    page.font(7.5, colour="ink2")
    when = f" · Prices to {sheet.as_of:%d %B %Y}" if sheet.as_of is not None else ""
    y = page.text(MARGIN, y + 0.5, title_w, f"Model fund fact sheet{when} · Benchmark: {sheet.benchmark or '–'}", 3.6)
    if sheet.objective:
        page.font(7.5)
        y = page.text(MARGIN, y + 1.5, title_w, f"Objective: {sheet.objective}", 3.5, max_lines=3)
    if qr is not None:
        pdf.image(qr, x=PAGE_W - MARGIN - QR_MM, y=5.5, w=QR_MM, h=QR_MM, link=share_url)
        page.font(5.5, colour="muted")
        page.text(PAGE_W - MARGIN - QR_MM, 5.5 + QR_MM + 0.5, QR_MM, "Scan or tap to open this fund in the app",
                  2.6, align="C")
    y = max(y, 5.5 + QR_MM + 6 if qr is not None else y) + 2
    top = y

    # left column: performance, holdings, sectors and countries
    x = MARGIN
    y = page.heading(x, y, LEFT_W, "Performance (simulated)")
    perf = sheet.performance
    if perf is not None:
        pdf.image(growth_chart(perf.growth, sheet.benchmark, LEFT_W, growth_h), x=x, y=y, w=LEFT_W, h=growth_h)
        y += growth_h + 1
        half = (LEFT_W - 4) / 2
        head = ("", "Fund", "Benchmark")
        cols = [half * 0.38, half * 0.29, half * 0.33]
        y1 = page.table(x, y, cols,
                        [(k, factsheet.pct(r["fund"]), factsheet.pct(r["benchmark"])) for k, r in perf.periods.iterrows()],
                        head)
        y2 = page.table(x + half + 4, y, cols,
                        [(k, factsheet.pct(r["fund"]), factsheet.pct(r["benchmark"])) for k, r in perf.calendar.iterrows()],
                        ("Calendar year", "Fund", "Benchmark"))
        y = max(y1, y2)
        page.font(5.8, colour="muted")
        y = page.text(x, y - 0.5, LEFT_W, "Yearly returns. Today's holdings applied to past prices and rebalanced "
                                          "quarterly: a simulation that benefits from hindsight, not a track record.",
                      2.7) + 1.5
    else:
        page.font(7, colour="muted")
        y = page.text(x, y, LEFT_W, "No performance: none of the holdings has enough price history.", 3.4) + 2
    y = page.heading(x, y, LEFT_W, "Top holdings")
    y = page.table(x, y, [LEFT_W * 0.58, LEFT_W * 0.26, LEFT_W * 0.16],
                   [(r["name"], r["type"], factsheet.pct(r["weight"])) for _, r in sheet.holdings.iterrows()],
                   ("Holding", "Type", "Share"), text_cols=2)
    half = (LEFT_W - 4) / 2
    y_heads = y
    for i, (title, s) in enumerate([("Sectors (looked through)", sheet.by_sector),
                                    ("Countries (looked through)", sheet.by_country)]):
        cx = x + i * (half + 4)
        yy = page.heading(cx, y_heads, half, title)
        if len(s):
            h = 6 + bar_row * len(s)
            pdf.image(bar_chart(s, half, h), x=cx, y=yy, w=half, h=h)
            y = max(y, yy + h)
    left_bottom = y

    # right column: details, risk, fees, asset classes
    x, y = RIGHT_X, top
    widths = [RIGHT_W * 0.55, RIGHT_W * 0.45]
    for title, rows in [("Fund details", sheet.details), ("Risk", sheet.risk), ("Fees", sheet.fees),
                        ("Asset classes", [(k, factsheet.pct(v)) for k, v in sheet.by_asset.items()])]:
        if rows:
            y = page.heading(x, y, RIGHT_W, title)
            y = page.table(x, y, widths, rows)
    page.font(5.8, colour="muted")
    y = page.text(x, y - 0.5, RIGHT_W, "Risk level: the app's own bands on volatility (under 4, 7, 9 and 12% a year) "
                                       "on the five-step scale SA fact sheets use. TER and TC are inside ETF and unit "
                                       "trust prices; platform, account and buying costs are EasyEquities' published "
                                       "defaults.", 2.7)
    right_bottom = y

    # insights across the page
    x, y = MARGIN, max(left_bottom, right_bottom) + 2
    width = PAGE_W - 2 * MARGIN
    if sheet.insights:
        y = page.heading(x, y, width, "Top insights")
        for ins in sheet.insights:
            marker = "Warning: " if ins.severity == "warning" else ""
            page.font(7, bold=True)
            y = page.text(x, y, width, f"{marker}{ins.title}", 3.3, max_lines=1)
            if insight_lines:
                page.font(6.6, colour="ink2")
                y = page.text(x, y, width, ins.noticed, 3.0, max_lines=insight_lines)
            page.font(6.2)
            pdf.set_text_color(*_rgb(p["series"][0]))
            link = article_url(ins.article) if article_url else ""
            y = page.text(x, y, width, f"Read more in the library: {ins.article_title}", 3.0, max_lines=1,
                          link=link) + 1.2

    # footer
    page.font(5.8, colour="muted")
    notes = " ".join(sheet.notes)
    foot = f"{notes} {factsheet.DISCLAIMER}".strip()
    rows = page.lines(foot, width)
    fy = PAGE_H - MARGIN - len(rows) * 2.7
    if share_url:
        fy -= 2.9
        pdf.set_text_color(*_rgb(p["series"][0]))
        page.text(x, fy + len(rows) * 2.7 + 0.2, width, "Open this fund in Build-a-Fund Lab", 2.7, link=share_url)
        page.font(5.8, colour="muted")
    pdf.set_draw_color(*_rgb(p["grid"]))
    pdf.line(x, fy - 1.2, x + width, fy - 1.2)
    page.text(x, fy, width, foot, 2.7)
    if y > fy - 1.5:
        raise OverflowError(f"fact sheet content ends at {y:.0f} mm, past the footer at {fy:.0f} mm")
    return bytes(pdf.output())


def _qr(url: str):
    if len(url) > QR_MAX_CHARS:
        return None
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L
    q = qrcode.QRCode(error_correction=ERROR_CORRECT_L, border=1, box_size=8)
    q.add_data(url)
    q.make(fit=True)
    return q.make_image(fill_color=LIGHT["ink"], back_color="white").get_image()
