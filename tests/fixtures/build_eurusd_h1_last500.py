"""Genera tests/fixtures/eurusd_h1_last500.csv via Phase 1 loader.

Esegui una volta: `python tests/fixtures/build_eurusd_h1_last500.py`.
Lo snapshot viene committato (D-08) per garantire test deterministici e
non rileggere ad ogni run i 148k+ rec del CSV storico EURUSD H1.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# Permette esecuzione standalone (`python tests/fixtures/build_...py`).
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from backtest.loader import load_bars  # noqa: E402
src = REPO / "data" / "historical" / "EURUSD" / "H1.csv"
bars = load_bars(src, "EURUSD", "H1")[-500:]
out = REPO / "tests" / "fixtures" / "eurusd_h1_last500.csv"
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["time", "open", "high", "low", "close", "volume"])
    for b in bars:
        w.writerow([b.time, b.open, b.high, b.low, b.close, b.volume])
print(f"wrote {out} ({len(bars)} rows)")
