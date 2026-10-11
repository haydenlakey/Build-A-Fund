"""Download company fundamentals for every share in the universe and write the dated snapshot.

Usage:  python scripts/build_fundamentals.py
Writes  data/sample/fundamentals.json  (used by the due-diligence checklist)
Run weekly by .github/workflows/refresh-data.yml, after build_sample.py.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fundlab import data, fundamentals  # noqa: E402


def main() -> int:
    uni = data.load_universe()
    shares = [t for t, e in uni.entries.items() if e["kind"] in ("jse_share", "us_share")]
    old = fundamentals.load_snapshot().get("companies", {})
    out, failed = {}, []
    for i, t in enumerate(shares, 1):
        d = fundamentals.fetch(t)
        if d is None:
            failed.append(t)
            if t in old:  # never let a bad refresh lose a company
                out[t] = old[t]
        else:
            out[t] = d
        print(f"{i}/{len(shares)} {t}: {'ok' if d else 'failed'}")
        time.sleep(0.3)
    snap = {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "Yahoo Finance via yfinance (info, annual income statement and cash flow, dividends)",
            "failed": failed, "companies": out}
    fundamentals.SNAPSHOT_PATH.write_text(json.dumps(snap, indent=1), encoding="utf-8")
    print(f"Wrote {len(out)} companies; failed: {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
