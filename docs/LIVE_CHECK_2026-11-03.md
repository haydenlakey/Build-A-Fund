# Live verification: 3 November 2026

App: [Build-a-Fund Lab](https://build-a-fund-hlakes.streamlit.app/).

## Browser coverage

Headless Chromium exercised desktop light (1366 px), phone light (390 px, 2x scale),
and desktop dark (1366 px), producing 24 screenshots per viewport. Checks covered:

- Empty builder, example fund, holding preview, due-diligence checklist and marker animation.
- Composition by sector, country/currency and earnings; active bets; risk and leverage insights.
- Reality check, diversifier explorer and side-by-side comparison.
- Mixed listed, unit-trust and unlisted fund through the builder, composition and fact sheet.
- Fact sheet charts and PDF download.
- Library index and seven articles, including logarithmic charts and the explicit no-chart explanation.

All functional assertions passed. Community Cloud wraps the app in an iframe;
`scripts/browser_check.py` now scopes app interactions to that frame while retaining
the public address for navigation. Local Streamlit remains supported.

Community Cloud's wrapper emitted 403/404 errors for `/api/v1/app/event/open`,
`/api/v2/user/details`, and Heap's `heap-.js` analytics script at
`sdk.us.heap-api.com` / `cdn.heapanalytics.com`. The check reports these exact
known endpoints separately. Other console errors and JavaScript exceptions still fail it.

## Live PDF verification

Downloaded both the example and mixed-fund PDFs directly from the hosted app.
Read them with pypdf and decoded the embedded QR images with ZXing (`zxing-cpp`,
installed in a temporary tools directory for this check).

| Check | Example fund | Mixed fund |
|---|---|---|
| PDF page count | 1 | 1 |
| QR decodes to the exact public fund link | Pass | Pass |
| QR and footer link use the public origin | Pass | Pass |
| All three library links use the public origin | Pass | Pass |

Both QR codes contain `https://build-a-fund-hlakes.streamlit.app/?fund=...`, with
the exact share code of the requested fund. All five PDF link annotations per
document use the same public origin. No PDF URL uses localhost or Cloud's internal
`/~/+/` iframe path. This verifies the address derived from live `st.context.url`.
The example PDF was also rendered and visually inspected.

## Local verification and artifacts

`python -m pytest -q`: **591 passed**.

Browser screenshots, downloaded PDFs and `pdf-verification.json` are retained in
`%TEMP%/build-a-fund-live-20261103/` on the verification machine.

To repeat the browser check (with development dependencies and Chromium installed):

```powershell
.venv/Scripts/python -u scripts/browser_check.py "$env:TEMP/build-a-fund-live-check" https://build-a-fund-hlakes.streamlit.app
```
