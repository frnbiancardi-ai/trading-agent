"""Runner edge-discovery batteria 2 v2 — panic-fade INTRADAY (research, 2026-05-29).

Pair EURUSD+GBPUSD+USDJPY (JPY = out-of-sample), H1. Per ogni segnale panic-fade ×
pair × crisi: misura DUE versioni — INTRADAY (chiusura forzata pre-rollover 22:00 UTC /
venerdì 20:00 UTC) e OVERNIGHT-allowed (horizon pieno + swap modellato). La versione
intraday è quella che conta per il verdetto (vincolo NO-overnight non negoziabile).

Scrive .planning/research/edge_discovery_b2_results.json + tabelle.
Uso: python scripts/edge_discovery/run_b2.py
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
    assert_causal_features, compute_features, date_index_range,
    evaluate_signal, evaluate_signal_intraday,
)
from scripts.edge_discovery.signals import (  # noqa: E402
    random_signal, vol_extreme_fade_dynamic, vol_extreme_fade_pctile,
)

PAIRS = {  # pair -> (pip_size, cost_pips round-trip)
    "EURUSD": (0.0001, 1.0),
    "GBPUSD": (0.0001, 1.5),
    "USDJPY": (0.01, 1.5),
}
CRISES = {
    "GFC_2008":     ("2008-09-01", "2009-04-01"),
    "EUROZONE_10":  ("2010-05-01", "2011-09-01"),
    "CHF_2015":     ("2015-01-01", "2015-03-01"),
    "BREXIT_2016":  ("2016-06-01", "2016-08-01"),
    "COVID_2020":   ("2020-02-01", "2020-05-01"),
    "RATEGILT_22":  ("2022-09-01", "2022-11-01"),
}
# segnale -> (factory, max_horizon)
SIGNALS = {
    "fade_pctile_N1.5":   (vol_extreme_fade_pctile(1.5, 0.90), 8),
    "fade_pctile_N2.0":   (vol_extreme_fade_pctile(2.0, 0.90), 8),
    "fade_dyn_K2.0_N2.0": (vol_extreme_fade_dynamic(2.0, 2.0), 8),
    "fade_dyn_K2.5_N2.0": (vol_extreme_fade_dynamic(2.5, 2.0), 8),
}
OUT = ROOT / ".planning/research/edge_discovery_b2_results.json"


def main() -> int:
    results: dict = {}
    feats_by_pair = {}
    for pair, (pip, cost) in PAIRS.items():
        bars = load_bars(ROOT / f"data/historical/{pair}/H1.csv", pair, "H1")
        f = compute_features(bars)
        assert_causal_features(bars, f)
        feats_by_pair[pair] = (f, pip, cost, len(bars))
        # sanity: random gross deve restare ~50%/t~0 (harness edits non rompono causalità)
        rg = evaluate_signal(f, random_signal(42), 5, 0.0, pip, lo=250)
        print(f"[{pair}] bars={len(bars)} | sanity random GROSS hit={rg['hit_rate']} t={rg['t_stat']}", flush=True)

    for sname, (sfn, h) in SIGNALS.items():
        for pair, (f, pip, cost, nb) in feats_by_pair.items():
            cell = {}
            # frequency su tutto lo storico (intraday) — quanti trade in 24y
            allm = evaluate_signal_intraday(f, sfn, h, cost, pip, lo=250, hi=nb)
            cell["all_intraday"] = allm
            for cname, (s_iso, e_iso) in CRISES.items():
                lo, hi = date_index_range(f, s_iso, e_iso)
                if hi - lo < 5:
                    continue
                lo = max(lo, 250)
                intr = evaluate_signal_intraday(f, sfn, h, cost, pip, lo=lo, hi=hi, overnight=False)
                ovn = evaluate_signal_intraday(f, sfn, h, cost, pip, lo=lo, hi=hi, overnight=True)
                cell[cname] = {"intraday": intr, "overnight": ovn}
            results.setdefault(sname, {})[pair] = cell

    # horizon sweep INTRADAY sul detector dinamico K2.5 (3/6/8 bar)
    sweep = {}
    base = vol_extreme_fade_dynamic(2.5, 2.0)
    for h in (3, 6, 8):
        for pair, (f, pip, cost, nb) in feats_by_pair.items():
            agg = []
            for cname, (s_iso, e_iso) in CRISES.items():
                lo, hi = date_index_range(f, s_iso, e_iso)
                if hi - lo < 5:
                    continue
                m = evaluate_signal_intraday(f, base, h, cost, pip, lo=max(lo, 250), hi=hi)
                agg.append((cname, m))
            sweep.setdefault(f"h{h}", {})[pair] = {c: m for c, m in agg}
    results["_horizon_sweep_dyn_K2.5"] = sweep

    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nwritten {OUT}", flush=True)

    # ── tabella INTRADAY per crisi (detector dinamico K2.5, il più "senza mani") ──
    print("\n=== INTRADAY — fade_dyn_K2.5_N2.0 (gate vol-spike dinamico) ===", flush=True)
    print(f"{'crisi':14}{'pair':8}{'n':>5}{'hit%':>6}{'mean':>8}{'t':>7}{'held_med':>9}", flush=True)
    for cname in CRISES:
        for pair in PAIRS:
            c = results["fade_dyn_K2.5_N2.0"][pair].get(cname)
            if not c:
                continue
            m = c["intraday"]
            print(f"{cname:14}{pair:8}{m['n_signals']:>5}{str(m['hit_rate']):>6}"
                  f"{str(m['mean_pips']):>8}{str(m['t_stat']):>7}{str(m['bars_held_median']):>9}", flush=True)

    # ── DECISIVA: intraday vs overnight (mean) per pair, COVID_2020 + GFC_2008 ──
    print("\n=== DECISIVA intraday vs overnight (fade_dyn_K2.5) ===", flush=True)
    print(f"{'crisi':14}{'pair':8}{'mean_INTRA':>11}{'mean_OVN':>10}{'held_med':>9}{'nights_med_ovn':>15}", flush=True)
    for cname in CRISES:
        for pair in PAIRS:
            c = results["fade_dyn_K2.5_N2.0"][pair].get(cname)
            if not c:
                continue
            mi, mo = c["intraday"], c["overnight"]
            print(f"{cname:14}{pair:8}{str(mi['mean_pips']):>11}{str(mo['mean_pips']):>10}"
                  f"{str(mi['bars_held_median']):>9}{str(mo['nights_median']):>15}", flush=True)

    # frequency 24y
    print("\n=== frequenza 24y (all_intraday) per detector ===", flush=True)
    for sname in SIGNALS:
        for pair in PAIRS:
            m = results[sname][pair]["all_intraday"]
            print(f"  {sname:20}{pair:8} n_24y={m['n_signals']} mean={m['mean_pips']} t={m['t_stat']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
