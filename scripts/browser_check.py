"""Drive the running app in headless Chromium: screenshots at desktop, phone and dark-mode sizes,
plus a check that the risk-return marker really animates, the composition page in each view,
the active-bets page, the fact sheet (and its PDF), and the library (index and a few articles, each must show its chart).

Usage (with the app running on localhost:8501):
    python scripts/browser_check.py [out_dir] [url]
Needs the dev requirements:  pip install -r requirements-dev.txt && python -m playwright install chromium
Prints console errors per viewport and exits non-zero if any are found or the animation doesn't move.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Frame, Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fundlab.model import Fund, Holding  # noqa: E402

EXAMPLE = Fund("Example fund", [Holding("STX40.JO", "Satrix 40", "jse_etf", 10_000),
                                Holding("STX500.JO", "Satrix S&P 500", "jse_etf", 5_000),
                                Holding("NPN.JO", "Naspers", "jse_share", 2_000),
                                Holding("CPI.JO", "Capitec Bank", "jse_share", 1_500),
                                Holding("GLD.JO", "NewGold Gold ETF", "jse_etf", 2_000)])

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "browser_check")
URL = (sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8501").rstrip("/")
# the coffee shop is 25% of the rands, enough to trip the "can't be sold in a hurry" insight (listed in the sidebar)
MIXED = Fund("Mixed fund", [Holding("STX40.JO", "Satrix 40", "jse_etf", 10_000),
                            Holding("UT:ZAE000177358", "Allan Gray Balanced Fund (C)", "unit_trust", 8_000,
                                    method="price_history", params={"allocation": {"sa_equity": 60, "global_equity": 40},
                                                                    "ter": 0.0148}),
                            Holding("UL:coffee-shop", "Coffee shop", "unlisted", 6_000, method="assumptions",
                                    params={"exp_return": 0.25, "lockin_years": 5, "p_loss": 0.05})])
LIBRARY_ARTICLES = ["situational-awareness", "sa-property-2018", "woodford", "gfc-2008", "vbs", "us-century",
                    "tulip-mania"]  # prices, multi-line, 2-point, log and "no chart" articles
NO_CHART = {"tulip-mania"}
VIEWPORTS = [  # tall viewports, because Streamlit scrolls inside its own container
    ("desktop", {"width": 1366, "height": 2600}, "light"),
    ("phone", {"width": 390, "height": 4200}, "light"),
    ("desktop-dark", {"width": 1366, "height": 2600}, "dark"),
]


def app(page: Page) -> Page | Frame:
    """Community Cloud wraps the app in an iframe; local Streamlit does not."""
    return next((frame for frame in page.frames if frame.url.startswith(f"{URL}/~/+/")), page)


def cloud_console_noise(source: str) -> bool:
    """Known failures in Community Cloud's wrapper, outside the Streamlit app."""
    parsed = urlsplit(source)
    return (source in {"https://sdk.us.heap-api.com/js/heap-.js", "https://cdn.heapanalytics.com/js/heap-.js"}
            or (parsed.netloc == urlsplit(URL).netloc and parsed.path in {
                "/api/v1/app/event/open", "/api/v2/user/details"}))


def settle(page: Page) -> None:
    """Wait for 2 s of continuous idle (the header shows a 'Stop' button while a run is in progress)."""
    deadline = time.monotonic() + 120
    while not app(page).locator("h1").count():
        if time.monotonic() >= deadline:
            page.screenshot(path=OUT / "load-timeout.png")
            raise TimeoutError(f"No app heading at {page.url}; frames: {[f.url for f in page.frames]}")
        page.wait_for_timeout(250)
    idle = 0
    for _ in range(600):
        idle = idle + 1 if app(page).get_by_role("button", name="Stop").count() == 0 else 0
        if idle >= 8:
            return
        time.sleep(0.25)


def pick(page: Page, query: str, amount: str | None = None) -> None:
    app(page).locator("[data-testid='stSelectbox']").filter(has_text="Search for a share").locator("input").click()
    page.keyboard.type(query)
    time.sleep(1)
    page.keyboard.press("Enter")
    settle(page)
    if amount:
        app(page).locator("input[aria-label='Rand amount']").fill(amount)
        page.keyboard.press("Enter")
        settle(page)


def marker_moves(page: Page) -> bool:
    js = "() => { const g = document.querySelector('.js-plotly-plot'); return g._fullData.find(t => t.name === 'After').x[0]; }"
    end = app(page).evaluate(js)
    app(page).get_by_text("Replay the move").click()
    xs = []
    for _ in range(20):
        xs.append(app(page).evaluate(js))
        time.sleep(0.04)
    return len(set(round(x, 5) for x in xs)) > 3 and abs(xs[-1] - end) < 1e-6


def check_pdf(page: Page) -> list[str]:
    """Download a one-page PDF and check its links use the tested public address."""
    with page.expect_download(timeout=120_000) as dl:
        app(page).get_by_role("button", name="Download the fact sheet (PDF)").first.click()
    path = OUT / "factsheet.pdf"
    dl.value.save_as(path)
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF"):
        return ["fact sheet download is not a PDF"]
    try:
        import io

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        n = len(reader.pages)
        if n != 1:
            return [f"fact sheet PDF has {n} pages"]
        links = [a.get_object()["/A"]["/URI"] for a in reader.pages[0].get("/Annots", [])
                 if "/A" in a.get_object() and "/URI" in a.get_object()["/A"]]
        expected = f"{URL}/?fund={EXAMPLE.to_share_code()}"
        if expected not in links:
            return [f"fact sheet PDF does not link to the example fund at {URL}"]
        if any(not link.startswith(f"{URL}/") for link in links):
            return [f"fact sheet PDF contains links outside {URL}: {links}"]
        print(f"PDF: one page; {len(links)} links use {URL}")
    except ImportError:
        pass
    if shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-png", "-r", "110", str(path), str(OUT / "factsheet-pdf")], check=False)
    return []


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    problems = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for label, vp, scheme in VIEWPORTS:
            print(f"Checking {label} at {URL}", flush=True)
            ctx = browser.new_context(viewport=vp, color_scheme=scheme,
                                      device_scale_factor=2 if label == "phone" else 1)
            page = ctx.new_page()
            errors: list[str] = []
            cloud_errors: list[str] = []
            # deep links make Streamlit probe <page>/_stcore/* first (404, then it falls back): not our errors
            def console_error(message):
                source = (message.location or {}).get("url", "")
                if message.type == "error" and "/_stcore/" not in source:
                    target = cloud_errors if cloud_console_noise(source) else errors
                    target.append(f"{message.text} ({source})")

            page.on("console", console_error)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(URL)
            settle(page)
            page.screenshot(path=OUT / f"{label}-1-empty.png")
            app(page).get_by_role("button", name="Open the example fund").click()
            settle(page)
            page.screenshot(path=OUT / f"{label}-2-example.png")
            pick(page, "NewGold Platinum", "8000")
            page.screenshot(path=OUT / f"{label}-3-preview.png")
            app(page).get_by_text("Before you add it", exact=False).first.click()
            settle(page)
            page.screenshot(path=OUT / f"{label}-3b-checklist.png")
            if label == "desktop" and not marker_moves(page):
                problems.append("risk-return marker did not animate on Replay")
            page.set_viewport_size({"width": vp["width"], "height": vp["height"] + 3400})
            page.goto(f"{URL}/composition?fund={EXAMPLE.to_share_code()}")
            settle(page)
            page.screenshot(path=OUT / f"{label}-4-composition.png")
            for i, view in enumerate(["Country and currency", "Where earnings come from"]):
                app(page).get_by_text(view, exact=True).click()
                settle(page)
                page.screenshot(path=OUT / f"{label}-5-composition-{i}.png")
            page.goto(f"{URL}/active_bets?fund={EXAMPLE.to_share_code()}")
            settle(page)
            page.screenshot(path=OUT / f"{label}-6-active.png")
            page.set_viewport_size({"width": vp["width"], "height": vp["height"] + 7000})
            page.goto(f"{URL}/risk?fund={EXAMPLE.to_share_code()}")
            settle(page)
            app(page).get_by_text("2×", exact=True).click()
            settle(page)
            if app(page).get_by_role("button", name="Got it").count() == 0:
                problems.append(f"{label}: no leverage pop-up at 2×")
            if app(page).locator(".js-plotly-plot").count() < 7:
                problems.append(f"{label}: risk page shows fewer than 7 charts")
            page.screenshot(path=OUT / f"{label}-10-risk.png")
            page.goto(f"{URL}/reality?fund={EXAMPLE.to_share_code()}")
            settle(page)
            if app(page).locator(".js-plotly-plot").count() < 3:
                problems.append(f"{label}: reality check page shows fewer than 3 charts")
            page.screenshot(path=OUT / f"{label}-11-reality.png")
            page.goto(f"{URL}/explore?fund={EXAMPLE.to_share_code()}")
            settle(page)
            if app(page).locator(".js-plotly-plot").count() < 2:
                problems.append(f"{label}: explore page shows fewer than 2 charts")
            page.screenshot(path=OUT / f"{label}-12-explore.png")
            app(page).get_by_role("button", name="Make a copy with it").click()
            settle(page)
            app(page).get_by_text("Compare them side by side").click()  # a link keeps the session (and the copy)
            settle(page)
            if app(page).locator(".js-plotly-plot").count() < 2:
                problems.append(f"{label}: compare page shows fewer than 2 charts")
            page.screenshot(path=OUT / f"{label}-13-compare.png")
            page.set_viewport_size({"width": vp["width"], "height": vp["height"] + 3400})
            page.goto(f"{URL}/?fund={MIXED.to_share_code()}")
            settle(page)
            if app(page).get_by_text("Illiquid sleeve and the whole fund").count() == 0:
                problems.append(f"{label}: mixed fund has no illiquid sleeve panel")
            page.screenshot(path=OUT / f"{label}-9-mixed-build.png")
            # a fund opened from a link lists its insights in the sidebar; only a change pops up (AppTests cover that)
            if label != "phone" and app(page).get_by_text("Insights (0)").count():
                problems.append(f"{label}: mixed fund lists no insights")
            page.goto(f"{URL}/composition?fund={MIXED.to_share_code()}")
            settle(page)
            page.screenshot(path=OUT / f"{label}-9-mixed-composition.png")
            page.goto(f"{URL}/factsheet?fund={EXAMPLE.to_share_code()}")
            settle(page)
            if app(page).locator(".js-plotly-plot").count() < 3:
                problems.append(f"{label}: fact sheet shows fewer than 3 charts")
            page.screenshot(path=OUT / f"{label}-14-factsheet.png")
            if label == "desktop":
                problems += check_pdf(page)
            page.goto(f"{URL}/factsheet?fund={MIXED.to_share_code()}")
            settle(page)
            if app(page).get_by_text("Whole fund volatility (with unlisted)").count() == 0:
                problems.append(f"{label}: mixed fund's fact sheet has no whole-fund volatility")
            page.screenshot(path=OUT / f"{label}-14-factsheet-mixed.png")
            page.goto(f"{URL}/library")
            settle(page)
            app(page).get_by_text("Case files", exact=True).click()
            settle(page)
            page.screenshot(path=OUT / f"{label}-7-library.png")
            for slug in LIBRARY_ARTICLES:
                page.goto(f"{URL}/library?article={slug}")
                settle(page)
                if slug in NO_CHART:
                    if app(page).get_by_text("No chart:").count() == 0:
                        problems.append(f"{label}: library article {slug} does not say why it has no chart")
                elif app(page).locator(".js-plotly-plot").count() == 0:
                    problems.append(f"{label}: library article {slug} has no chart")
                if app(page).locator("span.gl[data-def]").count() == 0:
                    problems.append(f"{label}: library article {slug} has no glossary terms marked")
                page.screenshot(path=OUT / f"{label}-8-library-{slug}.png")
            print(f"{label}: console errors {errors[:5]}")
            if cloud_errors:
                print(f"{label}: Community Cloud wrapper errors ({len(cloud_errors)}): {sorted(set(cloud_errors))}")
            problems += [f"{label}: {e}" for e in errors]
            ctx.close()
        browser.close()
    print("screenshots in", OUT.resolve())
    if problems:
        print("PROBLEMS:", *problems, sep="\n  ")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
