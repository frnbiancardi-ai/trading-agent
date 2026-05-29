"""Runner edge-discovery batteria 1 (research, 2026-05-29).

Per ogni pair (EURUSD, GBPUSD) H1: carica full history, calcola feature causali,
verifica anti-leakage, valuta ogni segnale su 'all' + 5 anni regime-misto.
Scrive .planning/research/edge_discovery_b1_results.json + stampa tabella maestra.

Uso: python scripts/edge_discovery/run_b1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.loader import load_bars  # noqa: E402
from scripts.edge_discovery._harness import (  # noqa: E402
    assert_causal_features, compute_features, evaluate_signal, year_index_range,
)
from scripts.edge_discovery.signals import build_signals  # noqa: E402

PAIRS = {"EURUSD": 1.0, "GBPUSD": 1.5}  # cost_pips round-trip (grezzo)
PIP = 0.0001
YEARS = [2008, 2014, 2017, 2020, 2023]
OUT = ROOT / ".planning/research/edge_discovery_b1_results.json"


def main() -> int:
    results: dict = {}
    for pair, cost in PAIRS.items():
        csv = ROOT / f"data/historical/{pair}/H1.csv"
        bars = load_bars(csv, pair, "H1")
        print(f"\n=== {pair} H1: {len(bars)} bars {bars[0].time}..{bars[-1].time} ===", flush=True)
        feats = compute_features(bars)
        assert_causal_features(bars, feats)  # anti-leakage guard (raise se future leak)
        print("  anti-leakage guard PASS", flush=True)

        periods = {"all": (250, len(bars))}
        for y in YEARS:
            lo, hi = year_index_range(feats, y)
            if hi - lo > 250:
                periods[str(y)] = (max(lo, 250), hi)

        signals = build_signals()  # rebuild per-pair (random seed fisso ⇒ indipendente per pair)
        for sname, (sfn, horizon) in signals.items():
            for pname, (lo, hi) in periods.items():
                m = evaluate_signal(feats, sfn, horizon, cost, PIP, lo=lo, hi=hi)
                m["horizon"] = horizon
                results.setdefault(sname, {}).setdefault(pair, {})[pname] = m

    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nwritten {OUT}", flush=True)

    # tabella maestra ordinata per |t-stat| (solo periodo 'all', sintesi)
    print("\n=== MASTER (period=all), sorted by |t-stat| ===", flush=True)
    rows = []
    for sname, perpair in results.items():
        for pair in PAIRS:
            m = perpair.get(pair, {}).get("all")
            if m and m.get("t_stat") is not None:
                rows.append((abs(m["t_stat"]), sname, pair, m))
    rows.sort(reverse=True)
    print(f"{'signal':24} {'pair':7} {'n':>6} {'hit%':>6} {'mean':>8} {'t':>7} {'sharpe':>8}")
    for _, sname, pair, m in rows:
        print(f"{sname:24} {pair:7} {m['n_signals']:>6} {str(m['hit_rate']):>6} "
              f"{str(m['mean_pips']):>8} {str(m['t_stat']):>7} {str(m['sharpe']):>8}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
