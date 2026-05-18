"""Subset edge-hunt per il dataset Plan 05-10.

Dopo aver stabilito (diag_decay_05_10.py BLOCK 6) che la strategia base ha
expectancy negativa (win_rate 24-27%, 73-83% SL, balance morto per tutti
i 27 run), questo script cerca isole sane:

  esiste un subset (regime, profile, symbol, timeframe, setup) dove
  win_rate >= 40% E mean_pnl_usd > 0 (anche con n_trades modesto)?

Se SI -> Phase 7 ML può diventare un classifier-di-gating su quel subset.
Se NO -> la strategia core va fixata prima di qualsiasi ML training.

Lancio:  python scripts/diag_decay_subset.py
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

DEFAULT_PARQUET = "data/training/baseline_decisions/part-0.parquet"
parquet_path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PARQUET)

if not parquet_path.exists():
    sys.exit(f"FILE NON TROVATO: {parquet_path}")

print(f"Loading {parquet_path} ...")
df = pq.read_table(parquet_path).to_pandas()
print(f"  -> {len(df):,} rows × {len(df.columns)} cols\n")

df["pnl_sign"] = (df["pnl_usd"] > 0).astype(int)


def show(group_cols: list[str], min_n: int = 50, top: int = 20) -> None:
    print("=" * 80)
    print(f"GROUP BY {group_cols}  (filter n>={min_n}, top {top} by mean_pnl)")
    print("=" * 80)
    g = df.groupby(group_cols).agg(
        n=("pnl_usd", "size"),
        win_rate=("pnl_sign", "mean"),
        mean_pnl=("pnl_usd", "mean"),
        sum_pnl=("pnl_usd", "sum"),
        median_pnl=("pnl_usd", "median"),
        mean_lot=("lot_size", "mean"),
    )
    g = g[g["n"] >= min_n].copy()
    g["win_rate"] = g["win_rate"].round(3)
    g["mean_pnl"] = g["mean_pnl"].round(3)
    g["sum_pnl"] = g["sum_pnl"].round(0)
    g["median_pnl"] = g["median_pnl"].round(3)
    g["mean_lot"] = g["mean_lot"].round(4)
    g_pos = g[g["mean_pnl"] > 0].sort_values("mean_pnl", ascending=False).head(top)
    g_neg = g.sort_values("mean_pnl").head(5)

    print(f"\n  -- POSITIVE expectancy (n={len(g_pos)} of {len(g)} groups) --")
    if len(g_pos) == 0:
        print("    (nessuno)")
    else:
        print(g_pos.to_string())
    print(f"\n  -- WORST 5 groups --")
    print(g_neg.to_string())
    print()


# ── 1-way breakdowns ----------------------------------------------------------
for cols in [["regime_state"], ["profile"], ["symbol"], ["timeframe"]]:
    show(cols, min_n=20)

# ── 2-way breakdowns ----------------------------------------------------------
for pair in combinations(["regime_state", "profile", "symbol", "timeframe"], 2):
    show(list(pair), min_n=50, top=10)

# ── 3-way: focus su (symbol, timeframe, regime_state) -----------------------
show(["symbol", "timeframe", "regime_state"], min_n=100, top=15)

# ── 4-way: full breakdown -----------------------------------------------------
show(["symbol", "timeframe", "profile", "regime_state"], min_n=50, top=20)


# ── Direction (BUY vs SELL) check -- struttura long/short ---------------------
if "direction" in df.columns:
    print("=" * 80)
    print("DIRECTION breakdown (BUY/SELL bias check)")
    print("=" * 80)
    print(
        df.groupby("direction")
        .agg(
            n=("pnl_usd", "size"),
            win_rate=("pnl_sign", "mean"),
            mean_pnl=("pnl_usd", "mean"),
            sum_pnl=("pnl_usd", "sum"),
        )
        .round(3)
        .to_string()
    )
    print()
    # combinato direction × symbol
    print("DIRECTION × symbol:")
    print(
        df.groupby(["direction", "symbol"])
        .agg(
            n=("pnl_usd", "size"),
            win_rate=("pnl_sign", "mean"),
            mean_pnl=("pnl_usd", "mean"),
        )
        .round(3)
        .to_string()
    )
    print()


# ── First-year subset only: forse early 2002-2003 c'era edge prima di overfit ─
print("=" * 80)
print("Early years 2002-2003 only (sanity: edge presente all'inizio?)")
print("=" * 80)
df["year"] = pd.to_datetime(df["decision_ts_utc"], utc=True).dt.year
early = df[df["year"].isin([2002, 2003])]
print(f"Rows early: {len(early):,}")
print(
    early.groupby(["symbol", "timeframe"])
    .agg(
        n=("pnl_usd", "size"),
        win_rate=("pnl_sign", "mean"),
        mean_pnl=("pnl_usd", "mean"),
        sum_pnl=("pnl_usd", "sum"),
    )
    .round(3)
    .to_string()
)
print()


print("=" * 80)
print("DONE — copia tutto.")
print("=" * 80)
