"""Test indicators.mtf (INDIC-13) — stream sintetici.

Verifica `align(streams)` su 4 livelli di score {0.0, 0.33, 0.67, 1.0}, warmup,
dead-zone (Pitfall 7) e validazione chiavi richieste H4/H1/M15 (D-13/D-14).

NOTA stream sizing: con `ema_period=50` + `slope_lookback=3`, ciascun stream deve
avere almeno 53 bar valide al timestamp dell'ultima bar M15 affinche `h*_dir` sia
calcolabile. M15 dt=60s, H1 dt=240s (4x), H4 dt=960s (16x): per warmare H4 fino a
indice 52, M15 deve coprire >= 52*960=49920s → M15 length >= 833 bar. Usiamo 1200
M15, 300 H1, 100 H4 (margine ampio) per tutti i test di steady state.
"""
from __future__ import annotations

import pytest

from indicators.mtf import align


def _stream(p0: float, slope: float, n: int, dt_seconds: int) -> list[dict]:
    """Stream sintetico: closes seguono p0 + slope*i; OHLC tutti uguali al close."""
    return [
        {
            "time": i * dt_seconds,
            "open": p0 + slope * i,
            "high": p0 + slope * i,
            "low": p0 + slope * i,
            "close": p0 + slope * i,
            "volume": 1,
            "tick_volume": 1,
        }
        for i in range(n)
    ]


def test_align_missing_key_raises():
    """ValueError fail-fast quando manca una chiave richiesta (D-13)."""
    with pytest.raises(ValueError, match="H4"):
        align({"H1": [], "M15": []})
    with pytest.raises(ValueError, match="H1"):
        align({"H4": [], "M15": []})
    with pytest.raises(ValueError, match="M15"):
        align({"H4": [], "H1": []})


def test_align_full_coherence_uptrend():
    """Tre stream monotone-up → score=1.0 a steady state (M15 ancora, tutti d=+1)."""
    m15 = _stream(100.0, 0.5, 1200, 60)
    h1 = _stream(100.0, 2.0, 300, 240)
    h4 = _stream(100.0, 8.0, 100, 960)
    r = align({"H4": h4, "H1": h1, "M15": m15})
    assert len(r.score) == 1200
    # Steady state: ultime 100 indici tutti score 1.0
    tail_scores = r.score[-100:]
    assert all(s == 1.0 for s in tail_scores), f"non tutti 1.0: {set(tail_scores)}"


def test_align_full_coherence_downtrend():
    """Tre stream monotone-down → score=1.0 a steady state (tutti d=-1)."""
    m15 = _stream(1000.0, -0.5, 1200, 60)
    h1 = _stream(1000.0, -2.0, 300, 240)
    h4 = _stream(1000.0, -8.0, 100, 960)
    r = align({"H4": h4, "H1": h1, "M15": m15})
    tail_scores = r.score[-100:]
    assert all(s == 1.0 for s in tail_scores)
    # Verifica che le direzioni siano effettivamente -1
    assert r.m15_dir[-1] == -1
    assert r.h1_dir[-1] == -1
    assert r.h4_dir[-1] == -1


def test_align_partial_coherence():
    """M15 up, H1 up, H4 down → 2 accordi su 3 → score = round(2/3, 2) = 0.67."""
    m15 = _stream(100.0, 0.5, 1200, 60)
    h1 = _stream(100.0, 2.0, 300, 240)
    h4 = _stream(1000.0, -8.0, 100, 960)  # discordante
    r = align({"H4": h4, "H1": h1, "M15": m15})
    final = r.score[-1]
    assert final == round(2 / 3, 2) == 0.67, f"atteso 0.67, ottenuto {final}"
    assert r.m15_dir[-1] == 1
    assert r.h1_dir[-1] == 1
    assert r.h4_dir[-1] == -1


def test_align_zero_score_disagreement():
    """M15 up, H1 down, H4 down → 1 accordo (solo M15 con se stesso) → score = 1/3 = 0.33."""
    m15 = _stream(100.0, 0.5, 1200, 60)
    h1 = _stream(1000.0, -2.0, 300, 240)
    h4 = _stream(1000.0, -8.0, 100, 960)
    r = align({"H4": h4, "H1": h1, "M15": m15})
    final = r.score[-1]
    assert final == round(1 / 3, 2) == 0.33, f"atteso 0.33, ottenuto {final}"


def test_align_warmup_returns_none():
    """Primi indici M15 (i < ema_period+slope_lookback-1 = 52) hanno score None.

    Specifico: a i=0..49 M15-EMA50 stessa non e calcolabile (period=50, primo
    valore valido a i=49). A i=49,50,51 EMA[i-3] e None → m15_dir=None → score=None.
    Solo a i >= 52 si puo avere m15_dir != None.
    """
    m15 = _stream(100.0, 0.5, 1200, 60)
    h1 = _stream(100.0, 2.0, 300, 240)
    h4 = _stream(100.0, 8.0, 100, 960)
    r = align({"H4": h4, "H1": h1, "M15": m15})
    # I primi 52 indici devono essere None (m15 stessa in warmup)
    for i in range(52):
        assert r.score[i] is None, f"score[{i}] non e None: {r.score[i]}"
    assert r.m15_dir[0] is None
    assert r.m15_dir[51] is None


def test_align_dead_zone_yields_zero_dir():
    """Slope sotto dead-zone 1e-5 → m15_dir=0 (non +/-1).

    Costruzione: slope cosi piccola che |EMA[i]-EMA[i-3]|/|EMA[i]| < 1e-5.
    Con EMA su rampa lineare, slope EMA ≈ slope close in steady state. Per slope
    close = s e prezzo p, |delta_ema|/|ema| ≈ 3*s/p. Per dead-zone < 1e-5: 3s/p <
    1e-5 → s < p * 3.33e-6. Con p=10000 e s=0.001 → 3*0.001/10000 = 3e-7 < 1e-5. OK.
    """
    m15 = _stream(10000.0, 0.001, 1200, 60)
    h1 = _stream(10000.0, 0.001, 300, 240)
    h4 = _stream(10000.0, 0.001, 100, 960)
    r = align({"H4": h4, "H1": h1, "M15": m15})
    # A steady state m15_dir deve essere 0 (slope troppo piccola)
    assert r.m15_dir[-1] == 0, f"atteso 0, ottenuto {r.m15_dir[-1]}"
    # Tutti d=0 → tutti accordo con M15 → score=1.0 (m15_dir==0, h1_dir==0, h4_dir==0)
    assert r.score[-1] == 1.0
