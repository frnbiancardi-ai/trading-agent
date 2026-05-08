"""Esponente di Hurst — analisi R/S su finestra rolling (INDIC-12).

Convenzione: window=100, sub-windows [10, 20, 40, 80], OLS log-log per stimare H.

Interpretazione del valore di H:
- H > 0.5 → serie persistente / trending (auto-correlazione positiva).
- H < 0.5 → serie anti-persistente / mean-reverting (auto-correlazione negativa).
- H ≈ 0.5 → random walk (incrementi indipendenti).

Metodologia (RESEARCH §"Don't Hand-Roll Hurst" + Pitfall 6):
per ogni finestra rolling di lunghezza `window`, si suddivide in chunk di
varie sub-window-size n; per ogni n si calcola la media R/S sui chunk; infine
si fitta `log(R/S_mean) = H · log(n) + costante` via OLS — la pendenza è H.
NON il naive `log(R/S)/log(N)` che è biased per finestre piccole.

A1 (RESEARCH): nessun oracolo pandas-ta per Hurst; serie sintetiche sono la verita.
La libreria opzionale Mottl `hurst` può essere usata come belt-and-suspenders
con tolerance rilassata 1e-3 (NON 1e-6) — vedi tests/test_indicators_hurst.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class HurstResult:
    """Output di `hurst_rs`. `hurst` ha la stessa lunghezza dell'input.

    I primi `window-1` indici sono `None` (warmup); successivi possono essere
    `None` se la finestra è degenere (es. tutti gli RS=0 per serie costante).
    """

    hurst: list[float | None]
    window: int


def _rs_for_subwindow(series: list[float], n: int) -> float | None:
    """R/S medio sui chunk di lunghezza n in `series`.

    Ritorna None se la serie è troppo corta o tutti i chunk hanno std nulla
    (range R indefinito relativamente alla deviazione standard S=0).

    R = max(cumsum(deviazioni)) - min(cumsum(deviazioni))
    S = sqrt(varianza popolazionale del chunk)
    """
    N = len(series)
    if N < n or n < 2:
        return None
    chunks = N // n
    rs_values: list[float] = []
    for k in range(chunks):
        chunk = series[k * n : (k + 1) * n]
        mean = sum(chunk) / n
        dev = [v - mean for v in chunk]
        # cumulative sum delle deviazioni dalla media del chunk
        cum: list[float] = []
        running = 0.0
        for d in dev:
            running += d
            cum.append(running)
        R = max(cum) - min(cum)
        # varianza popolazionale (Hurst R/S classico — Mandelbrot/Wallis)
        var = sum(d * d for d in dev) / n
        S = math.sqrt(var)
        if S == 0:
            # chunk costante: R/S indefinito → scartato
            continue
        rs_values.append(R / S)
    if not rs_values:
        return None
    return sum(rs_values) / len(rs_values)


def _hurst_single_window(window_values: list[float], sub_sizes: list[int]) -> float | None:
    """Stima H come slope OLS di log(R/S) vs log(n) sui sub-window sizes.

    Servono almeno 2 sub-window con R/S valido > 0 per avere una retta.
    Ritorna None se i dati non bastano o la varianza in x è nulla.
    """
    log_n: list[float] = []
    log_rs: list[float] = []
    for n in sub_sizes:
        rs = _rs_for_subwindow(window_values, n)
        if rs is None or rs <= 0:
            continue
        log_n.append(math.log(n))
        log_rs.append(math.log(rs))
    if len(log_n) < 2:
        return None
    # OLS slope: cov(x,y) / var(x) — formula chiusa con due passi
    m = len(log_n)
    mean_x = sum(log_n) / m
    mean_y = sum(log_rs) / m
    num = sum((log_n[i] - mean_x) * (log_rs[i] - mean_y) for i in range(m))
    den = sum((log_n[i] - mean_x) ** 2 for i in range(m))
    if den == 0:
        return None
    return num / den


def hurst_rs(values: list[float], window: int = 100) -> HurstResult:
    """INDIC-12: Hurst R/S su finestra rolling.

    Args:
        values: serie di prezzi (tipicamente close).
        window: lunghezza della finestra rolling (default 100).
            Pitfall 6: window<100 produce stime instabili. Si richiede `window>=20`.

    Returns:
        HurstResult con `hurst` di lunghezza `len(values)`. I primi `window-1`
        indici sono None (warmup). Dall'indice `window-1` in poi, l'entry può
        essere None se la finestra è degenere (es. tutti chunk costanti) o
        contenere lo slope OLS log-log come stima di H.

    Raises:
        ValueError: se `window < 20` (sotto la soglia di stabilità documentata).
    """
    if window < 20:
        raise ValueError(f"window deve essere >= 20 per stabilità R/S, ricevuto {window}")
    n = len(values)
    out: list[float | None] = [None] * n
    # Sub-window sizes: potenze di 2 strettamente minori del window (escludiamo
    # n==window perché un solo chunk non aggiunge informazione al fit).
    sub_sizes = [s for s in [10, 20, 40, 80] if s < window]
    if not sub_sizes:
        return HurstResult(hurst=out, window=window)
    for i in range(window - 1, n):
        wv = values[i - window + 1 : i + 1]
        out[i] = _hurst_single_window(wv, sub_sizes)
    return HurstResult(hurst=out, window=window)
