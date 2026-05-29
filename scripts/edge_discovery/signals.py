"""Segnali atomici per edge discovery batteria 1 (research, 2026-05-29).

Ogni signal_fn(features, i) -> +1/-1/0 usando SOLO features all'indice ≤ i.
Parametri: pochi valori fissi ragionevoli (NO ottimizzazione — overfitting nemico #1).
Ogni segnale dichiara l'horizon consigliato (bar) in SIGNALS.
"""
from __future__ import annotations

import numpy as np

# ── Famiglia 1 — Mean-reversion (indizio Setup B) ────────────────────────────

def mr_consecutive(K=4):
    """Dopo K barre consecutive stessa direzione → segnala inversione."""
    def fn(f, i):
        c = f.consec[i]
        if c >= K:
            return -1   # troppi up → short (reversione)
        if c <= -K:
            return +1   # troppi down → long
        return 0
    return fn


def mr_atr_extension(N=2.0):
    """close esteso > N×ATR dalla EMA20 → ritorno verso la media."""
    def fn(f, i):
        atr = f.atr14[i]
        if np.isnan(atr) or atr <= 0:
            return 0
        dev = f.close[i] - f.ema20[i]
        if dev > N * atr:
            return -1   # troppo sopra → short
        if dev < -N * atr:
            return +1   # troppo sotto → long
        return 0
    return fn


def mr_bollinger():
    """close oltre banda Bollinger 2σ → rientro."""
    def fn(f, i):
        if np.isnan(f.bb_upper[i]):
            return 0
        if f.close[i] > f.bb_upper[i]:
            return -1
        if f.close[i] < f.bb_lower[i]:
            return +1
        return 0
    return fn


# ── Famiglia 2 — Sessione / ora del giorno ───────────────────────────────────

def session_london_open():
    """Bar nelle ore 08:00-09:00 UTC: edge direzionale? (long-bias probe).

    Segnale = +1 nei bar della finestra (misura il forward return medio della
    finestra; il segno dell'edge emerge dalla metrica, non da una view a priori).
    """
    def fn(f, i):
        return 1 if 8 <= f.hour[i] <= 9 else 0
    return fn


def session_ny_overlap():
    """Bar 13:00-15:00 UTC (overlap Londra-NY): forward return della finestra."""
    def fn(f, i):
        return 1 if 13 <= f.hour[i] <= 15 else 0
    return fn


def session_asia_breakout():
    """Direzione del bar di apertura Londra (08:00 UTC) vs il range Asia (00-07 UTC):
    se close[i] rompe sopra il max del range Asia → long; sotto il min → short.
    """
    def fn(f, i):
        if f.hour[i] != 8:
            return 0
        # range Asia: i bar di OGGI con hour in 0..7 → cerco indietro fino a stamattina
        hi = lo = None
        j = i - 1
        steps = 0
        while j >= 0 and steps < 24:
            h = f.hour[j]
            if 0 <= h <= 7:
                hi = f.high[j] if hi is None else max(hi, f.high[j])
                lo = f.low[j] if lo is None else min(lo, f.low[j])
            elif h >= 8 and steps > 0:
                break  # uscito dalla notte precedente
            j -= 1
            steps += 1
        if hi is None:
            return 0
        if f.close[i] > hi:
            return +1
        if f.close[i] < lo:
            return -1
        return 0
    return fn


# ── Famiglia 3 — Volatility regime (dove Setup B funzionava) ─────────────────

def vol_compression_break():
    """ATR sotto 30° pct (200) E close rompe sopra/sotto il range 20-bar → continuazione."""
    def fn(f, i):
        p = f.atr_pctile[i]
        if np.isnan(p) or p >= 0.30:
            return 0
        if np.isnan(f.bb_upper[i]):
            return 0
        # uso le bande Bollinger come proxy del range recente
        if f.close[i] > f.bb_upper[i]:
            return +1   # breakout long (continuazione)
        if f.close[i] < f.bb_lower[i]:
            return -1
        return 0
    return fn


def vol_expansion_fade(N=2.0):
    """ATR sopra 70° pct (alta vol) E close esteso > N×ATR da EMA20 → fade (mean-rev).

    È l'ipotesi diretta dell'edge di Setup B in 2020/2023 (reversal in alta volatilità).
    """
    def fn(f, i):
        p = f.atr_pctile[i]
        atr = f.atr14[i]
        if np.isnan(p) or p <= 0.70 or np.isnan(atr) or atr <= 0:
            return 0
        dev = f.close[i] - f.ema20[i]
        if dev > N * atr:
            return -1
        if dev < -N * atr:
            return +1
        return 0
    return fn


# ── Famiglia 4 — Baseline di controllo (sanity) ──────────────────────────────

def random_signal(seed=42):
    """Segnale casuale deterministico (seed fisso) — DEVE dare hit~50% / t~0."""
    rng = np.random.default_rng(seed)
    def fn(f, i):
        r = rng.integers(0, 3)  # 0,1,2 → -1/0/+1 bilanciato
        return {0: -1, 1: 0, 2: 1}[int(r)]
    return fn


def always_long():
    """Sempre long — misura il drift di fondo del pair."""
    def fn(f, i):
        return 1
    return fn


# Registry: nome → (factory(), horizon consigliato)
def build_signals() -> dict:
    return {
        # Famiglia 1
        "mr_consecutive_K4": (mr_consecutive(4), 3),
        "mr_atr_extension_N2": (mr_atr_extension(2.0), 5),
        "mr_bollinger_2sd": (mr_bollinger(), 5),
        # Famiglia 2
        "session_london_open": (session_london_open(), 4),
        "session_ny_overlap": (session_ny_overlap(), 4),
        "session_asia_breakout": (session_asia_breakout(), 6),
        # Famiglia 3
        "vol_compression_break": (vol_compression_break(), 5),
        "vol_expansion_fade_N2": (vol_expansion_fade(2.0), 5),
        # Famiglia 4 (controllo)
        "random_signal": (random_signal(42), 5),
        "always_long": (always_long(), 5),
    }
