"""Download the whole preset universe and write the bundled sample dataset.

Usage:  python scripts/build_sample.py   (Yahoo for the universe; EasyEquities' feed for data/unit_trusts.yaml)
Writes  data/sample/prices_native.parquet  and  data/sample/meta.json
Run weekly by .github/workflows/refresh-data.yml.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fundlab import data, unit_trusts  # noqa: E402


def main() -> int:
    uni = data.load_universe()
    tickers = uni.all_tickers() + list(unit_trusts.load_unit_trusts().funds)
    print(f"Downloading {len(tickers)} tickers (Yahoo, and EasyEquities for unit trusts)...")
    native, failures = data.download_native(tickers)
    if native.empty:
        print("Nothing downloaded; keeping the existing sample.")
        return 1

    # never let a bad refresh shrink the dataset: keep old columns Yahoo failed to return
    if data.SAMPLE_PATH.exists():
        import pandas as pd
        old = pd.read_parquet(data.SAMPLE_PATH)
        lost = [t for t in old.columns if t not in native.columns]
        if lost:
            print(f"Keeping previous data for {len(lost)} tickers that failed this time: {lost}")
            native = native.combine_first(old[lost])

    data.SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    native.astype("float32").to_parquet(data.SAMPLE_PATH, compression="zstd")
    meta = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Yahoo Finance via yfinance, weekly adjusted closes (auto_adjust=True); unit trusts (UT:<ISIN>): "
                  "EasyEquities' public price feed, unit prices without distributions",
        "first_week": str(native.index.min().date()),
        "last_week": str(native.index.max().date()),
        "n_tickers": int(native.shape[1]),
        "first_dates": {t: str(native[t].first_valid_index().date()) for t in native.columns},
        "failures": failures,
    }
    (data.SAMPLE_PATH.parent / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    size_kb = data.SAMPLE_PATH.stat().st_size / 1024
    print(f"Wrote {native.shape[1]} tickers x {native.shape[0]} weeks ({size_kb:.0f} KB).")
    if failures:
        print("Failures:", json.dumps(failures, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
