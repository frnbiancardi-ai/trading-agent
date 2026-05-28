"""Test indicators.hurst (INDIC-12) — sintetici + opzionale parity Mottl `hurst`.

Per Hurst non esiste un oracolo pandas-ta; le serie sintetiche sono la verità
(persistente → H>0.55, anti-persistente → H<0.45, random walk → H≈0.5).
La libreria opzionale Mottl `hurst` (`pip install hurst`) viene usata come
belt-and-suspenders con tolerance rilassata 1e-1 — vedi Assumption A1 in
02-RESEARCH.md (sub-window choices differiscono leggermente fra le due impl).
"""
from __future__ import annotations

import importlib.util
import math
import random

import pytest

from indicators.hurst import hurst_rs


_HAVE_MOTTL = importlib.util.find_spec("hurst") is not None
_SKIP_MOTTL = pytest.mark.skipif(not _HAVE_MOTTL, reason="Mottl hurst lib non installata")


def test_hurst_persistent_linear_ramp():
    """Rampa lineare = serie deterministica fortemente persistente → H ≈ 1.0."""
    values = [float(i) for i in range(200)]
    r = hurst_rs(values, 100)
    assert r.window == 100
    assert len(r.hurst) == 200
    # Tutti gli indici dal warmup in poi devono essere persistenti (> 0.55)
    for i in range(99, 200):
        h = r.hurst[i]
        assert h is not None, f"hurst[{i}] None inatteso su rampa lineare"
        assert h > 0.55, f"hurst[{i}]={h} non persistente (atteso > 0.55)"


def test_hurst_white_noise_near_half():
    """Rumore bianco i.i.d. N(0,1) (NON cumulato) → H ≈ 0.5 ± 0.15.

    Nota concettuale: R/S applicato direttamente alla serie. Per H≈0.5 nel
    framework R/S sui livelli, occorre una serie i.i.d. (no auto-correlazione).
    Una cumsum(gauss) — che modella i prezzi di un random walk — produrrebbe
    H≈1.0 (forte persistenza dei livelli), NON 0.5 (vedere Mottl `hurst` con
    kind='random_walk' applicato agli incrementi).

    Banda larga [0.35, 0.65] perché su ~300 campioni la varianza della stima
    R/S è apprezzabile (Pitfall 6: 100-300 rumoroso). Seed fisso 42 per
    determinismo cross-machine.
    """
    rng = random.Random(42)
    series = [rng.gauss(0.0, 1.0) for _ in range(300)]
    r = hurst_rs(series, 100)
    valid = [h for h in r.hurst[99:] if h is not None]
    assert valid, "nessuna stima Hurst valida su white noise"
    mean_h = sum(valid) / len(valid)
    assert 0.35 <= mean_h <= 0.65, f"white noise media H={mean_h} fuori banda [0.35, 0.65]"


def test_hurst_anti_persistent_series():
    """Serie zigzag deterministica fortemente anti-persistente → H < 0.45.

    Costruzione: oscillazione +1/-1 ad ampiezza decrescente attorno a una
    media fissa. Ogni step inverte il segno → forte mean-reversion → H bassa.
    """
    # Zigzag stretto: alterna +1 e -1 attorno allo zero
    series = [(-1.0 if i % 2 == 0 else 1.0) for i in range(200)]
    r = hurst_rs(series, 100)
    valid = [h for h in r.hurst[99:] if h is not None]
    assert valid, "nessuna stima valida sulla serie zigzag"
    mean_h = sum(valid) / len(valid)
    assert mean_h < 0.45, f"zigzag mean H={mean_h} non anti-persistente (atteso < 0.45)"


def test_hurst_warmup_none():
    """Primi window-1 indici devono essere None; entry a window-1 deve esistere."""
    values = [float(i) for i in range(200)]
    r = hurst_rs(values, 100)
    assert all(v is None for v in r.hurst[:99]), "warmup non None"
    assert r.hurst[99] is not None, "primo indice valido (99) None inatteso"


def test_hurst_window_too_small_raises():
    """window<20 deve sollevare ValueError (Pitfall 6: stabilità)."""
    with pytest.raises(ValueError):
        hurst_rs([1.0] * 100, 10)


def test_hurst_constant_series_returns_none():
    """Serie costante: tutti i chunk hanno std=0 → R/S indefinito → entries None.

    Rifletto la convenzione documentata in indicators/hurst.py: scarta i chunk
    con S=0; se nessun chunk valido in alcuna sub-window, ritorna None.
    """
    r = hurst_rs([5.0] * 200, 100)
    # Tutti gli entry post-warmup devono essere None (no chunk con std>0)
    for i in range(99, 200):
        assert r.hurst[i] is None, f"hurst[{i}]={r.hurst[i]} atteso None su serie costante"


@_SKIP_MOTTL
def test_hurst_parity_with_mottl(eurusd_h1_500):
    """Parity opzionale vs libreria Mottl `hurst` su EURUSD H1 closes.

    Tolerance 1e-1 (rilassata vs 1e-6 dei parity pandas-ta) perché:
    - Mottl usa `kind='price'` con simplified=True, sub-window choices diverse.
    - 02-RESEARCH Assumption A1 documenta esplicitamente la flessibilità ≤ 1e-1.
    """
    from hurst import compute_Hc  # noqa: WPS433  (import dentro test gated)

    closes = [b["close"] for b in eurusd_h1_500]
    ours = hurst_rs(closes, 100)
    # Confronta gli ultimi 5 indici validi
    indices = [i for i in range(len(closes) - 1, -1, -1) if ours.hurst[i] is not None][:5]
    assert len(indices) >= 1, "nessuna stima nostra valida per la parity"
    for i in indices:
        wnd = closes[i - 99 : i + 1]
        H_mottl, _, _ = compute_Hc(wnd, kind="price", simplified=True)
        diff = abs(ours.hurst[i] - H_mottl)
        assert diff < 0.1, (
            f"parity Mottl violata @ i={i}: ours={ours.hurst[i]}, mottl={H_mottl}, diff={diff}"
        )
