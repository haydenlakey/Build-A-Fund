"""About the tool, its data and its limits."""
import json

import streamlit as st

from fundlab import data
from ui import cached
from ui.components import DISCLAIMER

st.title("About and data")
st.markdown(DISCLAIMER)

st.markdown("""
**Build-a-Fund Lab** lets you assemble your own "unit trust" from investments you could buy on a
South African platform, then see how each holding changes the fund's risk, expected return and
character. Everything is measured in rand.

### Where the numbers come from
- **Prices:** Yahoo Finance via the free `yfinance` library: weekly closing prices adjusted for
  dividends and splits, so returns include reinvested dividends. A copy is bundled with the app
  so it works even when Yahoo is unavailable.
- **JSE prices** are quoted by Yahoo in cents and converted to rand. **US prices** are converted
  at that week's USD/ZAR rate, so currency swings are part of every US holding's risk.
- **Sectors and countries** for JSE shares come from a hand-curated list, because Yahoo's
  classifications are patchy for South African companies.

### Known limits
- Yahoo's USD/ZAR history starts in December 2003, so US holdings can't be measured in rand before 2004.
- Yahoo's JSE share history starts in 2000 at the earliest, and some shares listed on the JSE much more recently.
- Holdings with less than a year of history are left out of the statistics (the app tells you
  when this happens). Under three years, the app warns that the numbers are rough.
- Expected returns are the least reliable numbers in the app. Small changes in the period
  measured can change them a lot.
""")

meta_path = data.SAMPLE_PATH.parent / "meta.json"
if meta_path.exists():
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    st.caption(f"Bundled dataset: {meta['n_tickers']} series, weeks {meta['first_week']} to "
               f"{meta['last_week']}, built {meta['built_utc']}.")
u = cached.universe()
st.caption(f"Preset universe as of {u.as_of}: {len(u.entries)} holdings to choose from.")
