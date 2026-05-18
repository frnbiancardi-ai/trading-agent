"""Diagnostica decay strategia Plan 05-10.

Investiga il pattern visto nel parquet baseline_decisions (209k rows):
  - 51k trades/anno 2003-2004
  - decay progressivo 2005-2012
  - quasi-zero 2013-2020
  - cutoff 2021-10-19 nonostante CSV fino al 2026-05-04

Ipotesi da verificare:
  H1 balance-exhaustion: dopo molte trade perdenti, balance simulato si esaurisce,
     lot_size collassa al minimo o risk_engine rifiuta tutto.
  H2 setup-detector calibration: soglie absolute (ATR/spread/volatility) calibrate
     su regime moderno, non scattano su regimi pre/post 2013.
  H3 regime classifier: cambio drastico di regime_state riconosciuto post-2013
     che blocca i setup.

Lancio:  python scripts/diag_decay_05_10.py
Output:  stdout testuale (copia-incollabile)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

# ── path: usa parquet locale, override con argv[1] -----------------------------
DEFAULT_PARQUET = "data/training/baseline_decisions/part-0.parquet"
parquet_path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PARQUET)

if not parquet_path.exists():
    sys.exit(f"FILE NON TROVATO: {parquet_path}")

print(f"Loading {parquet_path} ...")
df = pq.read_table(parquet_path).to_pandas()
print(f"  -> {len(df):,} rows × {len(df.columns)} cols\n")

# ── normalizzazione timestamp + bucket annuali --------------------------------
for col in ("decision_ts_utc", "entry_ts_utc", "exit_ts_utc"):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
df["year"] = df["decision_ts_utc"].dt.year

# bucket 3 ere per confronti aggregate
def era_bucket(y: int) -> str:
    if y <= 2010:
        return "1_early_2002-2010"
    if y <= 2015:
        return "2_mid_2011-2015"
    return "3_modern_2016-2026"

df["era"] = df["year"].map(era_bucket)
df["pnl_sign"] = (df["pnl_usd"] > 0).astype(int)  # winning trade flag


# ── BLOCK 1 — per-year overview ----------------------------------------------
print("=" * 80)
print("BLOCK 1 — Per-year overview (sanity check)")
print("=" * 80)
agg = df.groupby("year").agg(
    n=("pnl_usd", "size"),
    win_rate=("pnl_sign", "mean"),
    mean_pnl_usd=("pnl_usd", "mean"),
    sum_pnl_usd=("pnl_usd", "sum"),
    mean_lot=("lot_size", "mean"),
    mean_risk_usd=("risk_usd", "mean"),
    mean_conf=("confidence", "mean"),
    mean_atr14=("atr_14", "mean"),
)
agg["mean_pnl_usd"] = agg["mean_pnl_usd"].round(3)
agg["sum_pnl_usd"] = agg["sum_pnl_usd"].round(0)
agg["win_rate"] = agg["win_rate"].round(3)
agg["mean_lot"] = agg["mean_lot"].round(4)
agg["mean_risk_usd"] = agg["mean_risk_usd"].round(2)
agg["mean_conf"] = agg["mean_conf"].round(3)
agg["mean_atr14"] = agg["mean_atr14"].round(5)
print(agg.to_string())
print()


# ── BLOCK 2 — era aggregates -------------------------------------------------
print("=" * 80)
print("BLOCK 2 — Era aggregates (early vs mid vs modern)")
print("=" * 80)
era_agg = df.groupby("era").agg(
    n=("pnl_usd", "size"),
    win_rate=("pnl_sign", "mean"),
    mean_pnl_usd=("pnl_usd", "mean"),
    sum_pnl_usd=("pnl_usd", "sum"),
    mean_lot=("lot_size", "mean"),
    mean_risk_usd=("risk_usd", "mean"),
    median_lot=("lot_size", "median"),
    min_lot=("lot_size", "min"),
    max_lot=("lot_size", "max"),
)
print(era_agg.round(4).to_string())
print()


# ── BLOCK 3 — exit_reason distribution per era -------------------------------
if "exit_reason" in df.columns:
    print("=" * 80)
    print("BLOCK 3 — exit_reason distribution per era")
    print("=" * 80)
    cross = pd.crosstab(df["exit_reason"], df["era"], normalize="columns")
    print((cross * 100).round(2).to_string())
    print()


# ── BLOCK 4 — setup_type distribution per era --------------------------------
if "setup_type" in df.columns:
    print("=" * 80)
    print("BLOCK 4 — setup_type distribution per era (top 15)")
    print("=" * 80)
    cross = pd.crosstab(df["setup_type"], df["era"], normalize="columns")
    top = cross.sum(axis=1).sort_values(ascending=False).head(15).index
    print((cross.loc[top] * 100).round(2).to_string())
    print()


# ── BLOCK 5 — regime_state distribution per era ------------------------------
if "regime_state" in df.columns:
    print("=" * 80)
    print("BLOCK 5 — regime_state distribution per era")
    print("=" * 80)
    cross = pd.crosstab(df["regime_state"], df["era"], normalize="columns")
    print((cross * 100).round(2).to_string())
    print()


# ── BLOCK 6 — cumulative PnL per run_id: quando muore il balance? -----------
print("=" * 80)
print("BLOCK 6 — Cumulative PnL per run_id (quando il balance simulato collassa?)")
print("=" * 80)
# H1: se balance-exhaustion, cumulative pnl per run_id raggiunge minimo
# precoce poi piatto. Tracciamo per ogni run_id il timestamp di:
#   - peak cumulative pnl
#   - trough (min cumulative)
#   - ultimo trade
df_sorted = df.sort_values(["run_id", "exit_ts_utc"]).copy()
df_sorted["cum_pnl"] = df_sorted.groupby("run_id")["pnl_usd"].cumsum()

rows = []
for run_id, g in df_sorted.groupby("run_id"):
    peak_idx = g["cum_pnl"].idxmax()
    trough_idx = g["cum_pnl"].idxmin()
    last = g.iloc[-1]
    rows.append({
        "run_id": run_id,
        "n_trades": len(g),
        "first_trade": g["exit_ts_utc"].iloc[0],
        "last_trade": last["exit_ts_utc"],
        "peak_pnl": round(g.loc[peak_idx, "cum_pnl"], 0),
        "peak_when": g.loc[peak_idx, "exit_ts_utc"],
        "trough_pnl": round(g.loc[trough_idx, "cum_pnl"], 0),
        "trough_when": g.loc[trough_idx, "exit_ts_utc"],
        "final_pnl": round(last["cum_pnl"], 0),
    })

summary = pd.DataFrame(rows).set_index("run_id")
print(summary.to_string())
print()


# ── BLOCK 7 — last-trade clustering ------------------------------------------
print("=" * 80)
print("BLOCK 7 — Last-trade timestamp per run_id (cliff diagnosis)")
print("=" * 80)
# Se tutti i run smettono ENTRO una piccola finestra → suggerisce evento sistemico
# (balance morto, regime switch). Se varia molto → suggerisce esaurimento naturale
# per simbolo/profilo.
last_per_run = (
    df.groupby("run_id")["decision_ts_utc"]
    .max()
    .sort_values()
)
print(last_per_run.to_string())
print()
print(f"Range last-trade: {last_per_run.min()}  →  {last_per_run.max()}")
print(f"Spread: {(last_per_run.max() - last_per_run.min()).days} giorni")
print()


# ── BLOCK 8 — lot_size collapse check ----------------------------------------
print("=" * 80)
print("BLOCK 8 — lot_size per quartile temporale (H1 balance-exhaustion)")
print("=" * 80)
df_sorted2 = df.sort_values("decision_ts_utc")
df_sorted2["temporal_quartile"] = pd.qcut(
    df_sorted2["decision_ts_utc"].rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"]
)
print(
    df_sorted2.groupby("temporal_quartile", observed=True)
    .agg(
        n=("pnl_usd", "size"),
        mean_lot=("lot_size", "mean"),
        median_lot=("lot_size", "median"),
        min_lot=("lot_size", "min"),
        mean_risk=("risk_usd", "mean"),
        mean_atr=("atr_14", "mean"),
    )
    .round(5)
    .to_string()
)
print()


print("=" * 80)
print("DIAG COMPLETED — copia tutto l'output e mandamelo per analisi finale.")
print("=" * 80)
