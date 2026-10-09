"""Drive the running app in headless Chromium: screenshots at desktop, phone and dark-mode sizes,
plus a check that the risk-return marker really animates.

Usage (with the app running on localhost:8501):
    python scripts/browser_check.py [out_dir] [url]
Needs the dev requirements:  pip install -r requirements-dev.txt && python -m playwright install chromium
Prints console errors per viewport and exits non-zero if any are found or the animation doesn't move.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "browser_check")
URL = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8501"
VIEWPORTS = [  # tall viewports, because Streamlit scrolls inside its own container
    ("desktop", {"width": 1366, "height": 2600}, "light"),
    ("phone", {"width": 390, "height": 4200}, "light"),
    ("desktop-dark", {"width": 1366, "height": 2600}, "dark"),
]


def settle(page: Page) -> None:
    """Wait for 2 s of continuous idle (the header shows a 'Stop' button while a run is in progress)."""
    page.wait_for_selector("h1", timeout=120_000)
    idle = 0
    for _ in range(600):
        idle = idle + 1 if page.get_by_role("button", name="Stop").count() == 0 else 0
        if idle >= 8:
            return
        time.sleep(0.25)


def pick(page: Page, query: str, amount: str | None = None) -> None:
    page.locator("[data-testid='stSelectbox']").filter(has_text="Search for a share").locator("input").click()
    page.keyboard.type(query)
    time.sleep(1)
    page.keyboard.press("Enter")
    settle(page)
    if amount:
        page.locator("input[aria-label='Rand amount']").fill(amount)
        page.keyboard.press("Enter")
        settle(page)


def marker_moves(page: Page) -> bool:
    js = "() => { const g = document.querySelector('.js-plotly-plot'); return g._fullData[g._fullData.length - 1].x[0]; }"
    end = page.evaluate(js)
    page.get_by_text("Replay the move").click()
    xs = []
    for _ in range(20):
        xs.append(page.evaluate(js))
        time.sleep(0.04)
    return len(set(round(x, 5) for x in xs)) > 3 and abs(xs[-1] - end) < 1e-6


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    problems = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for label, vp, scheme in VIEWPORTS:
            ctx = browser.new_context(viewport=vp, color_scheme=scheme,
                                      device_scale_factor=2 if label == "phone" else 1)
            page = ctx.new_page()
            errors: list[str] = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(URL)
            settle(page)
            page.screenshot(path=OUT / f"{label}-1-empty.png")
            page.get_by_role("button", name="Open the example fund").click()
            settle(page)
            page.screenshot(path=OUT / f"{label}-2-example.png")
            pick(page, "NewGold Platinum", "8000")
            page.screenshot(path=OUT / f"{label}-3-preview.png")
            if label == "desktop" and not marker_moves(page):
                problems.append("risk-return marker did not animate on Replay")
            print(f"{label}: console errors {errors[:5]}")
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
