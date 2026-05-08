"""Test indicators.momentum (INDIC-02/03/04) — parity vs pandas-ta a 1e-6.

pandas-ta è dev-dep (oracolo): se non installato i parity test sono SKIPPED.
I test sanity (constant series, signal-lag, extreme-high) girano sempre.
"""
from __future__ import annotations

import importlib.util

import pytest

from indicators.momentum import (
    ADXResult,
    MACDResult,
    StochasticResult,
    adx,
    macd,
    stochastic,
)

_HAVE_PTA = importlib.util.find_spec("pandas_ta") is not None
_SKIP = pytest.mark.skipif(not _HAVE_PTA, reason="pandas-ta dev-dep non installato")


# ── Sanity hand-calc (sempre eseguiti) ────────────────────────────────────────


def test_adx_constant_no_raise() -> None:
    """Serie H==L==C costante non deve sollevare; warmup mascherato a None."""
    r = adx([1.0] * 60, [1.0] * 60, [1.0] * 60, period=14)
    assert isinstance(r, ADXResult)
    assert len(r.adx) == 60
    # Primi 2*period=28 valori di ADX sono None (warmup mascherato).
    assert all(v is None for v in r.adx[:28])
    # Nessuna eccezione su denominatori nulli (sm_tr=0 -> +DI/-DI restano None).


def test_macd_signal_lag() -> None:
    """Su serie ad accelerazione positiva (parabolica), la linea MACD è
    positiva e supera la signal in lag.

    Nota: una serie strettamente lineare `range(100)` farebbe convergere
    line e signal allo stesso valore (7.0) per costruzione (no momentum
    change → signal raggiunge la line). Una parabola y=i² mantiene
    accelerazione costante → signal resta sempre in lag rispetto alla line.
    """
    closes = [float(i * i) for i in range(100)]
    m = macd(closes, fast=12, slow=26, signal=9)
    assert isinstance(m, MACDResult)
    # Indice 60 ben oltre il warmup di slow+signal.
    assert m.macd[60] is not None
    assert m.signal[60] is not None
    assert m.macd[60] > m.signal[60] > 0


def test_stoch_extreme_high() -> None:
    """Serie monotona crescente: il close è vicino al top del range, k > 80."""
    closes = [float(i) for i in range(60)]
    highs = closes
    lows = [c - 1.0 for c in closes]
    r = stochastic(highs, lows, closes, k_period=14, d_period=3, smooth_k=3)
    assert isinstance(r, StochasticResult)
    assert r.k[59] is not None
    assert r.k[59] > 80


def test_adx_input_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        adx([1.0, 2.0], [1.0], [1.0, 2.0], period=14)


def test_stochastic_input_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        stochastic([1.0, 2.0], [1.0], [1.0, 2.0], k_period=14)


# ── Parity vs pandas-ta (SKIPPED se non installato) ───────────────────────────


@_SKIP
def test_adx_parity_with_pandas_ta(eurusd_h1_500: list[dict]) -> None:
    """ADX/+DI/-DI bit-for-bit (1e-6) vs `pta.adx(length=14, mamode='rma')`."""
    import pandas as pd
    import pandas_ta as pta

    df = pd.DataFrame(eurusd_h1_500)
    ours = adx(
        df["high"].tolist(),
        df["low"].tolist(),
        df["close"].tolist(),
        period=14,
    )
    expected = pta.adx(df["high"], df["low"], df["close"], length=14, mamode="rma")
    cols = list(expected.columns)
    col_adx = next(c for c in cols if c.startswith("ADX"))
    col_dmp = next(c for c in cols if c.startswith("DMP"))
    col_dmn = next(c for c in cols if c.startswith("DMN"))

    # ADX: skip i primi 2*period=28 indici (transient doppio Wilder).
    start = 28
    n = len(df)
    cmp_adx = cmp_dmp = cmp_dmn = 0
    for i in range(start, n):
        exp_adx = expected[col_adx].iloc[i]
        exp_dmp = expected[col_dmp].iloc[i]
        exp_dmn = expected[col_dmn].iloc[i]
        if ours.adx[i] is not None and not pd.isna(exp_adx):
            assert abs(ours.adx[i] - float(exp_adx)) < 1e-6, f"ADX mismatch i={i}"
            cmp_adx += 1
        if ours.plus_di[i] is not None and not pd.isna(exp_dmp):
            assert abs(ours.plus_di[i] - float(exp_dmp)) < 1e-6, f"+DI mismatch i={i}"
            cmp_dmp += 1
        if ours.minus_di[i] is not None and not pd.isna(exp_dmn):
            assert abs(ours.minus_di[i] - float(exp_dmn)) < 1e-6, f"-DI mismatch i={i}"
            cmp_dmn += 1
    # Sanity: almeno 100 confronti per ciascuna serie su 500 bar.
    assert cmp_adx > 100 and cmp_dmp > 100 and cmp_dmn > 100


@_SKIP
def test_macd_parity_with_pandas_ta(eurusd_h1_500: list[dict]) -> None:
    """MACD line/signal/histogram bit-for-bit (1e-6) vs `pta.macd(12, 26, 9)`."""
    import pandas as pd
    import pandas_ta as pta

    df = pd.DataFrame(eurusd_h1_500)
    ours = macd(df["close"].tolist(), fast=12, slow=26, signal=9)
    expected = pta.macd(df["close"], fast=12, slow=26, signal=9)
    cols = list(expected.columns)
    # MACD_12_26_9 (linea), MACDh_12_26_9 (histogram), MACDs_12_26_9 (signal)
    col_line = next(c for c in cols if c.startswith("MACD_"))
    col_hist = next(c for c in cols if c.startswith("MACDh"))
    col_sig = next(c for c in cols if c.startswith("MACDs"))

    start = 40
    n = len(df)
    cmp_line = cmp_sig = cmp_hist = 0
    for i in range(start, n):
        exp_line = expected[col_line].iloc[i]
        exp_sig = expected[col_sig].iloc[i]
        exp_hist = expected[col_hist].iloc[i]
        if ours.macd[i] is not None and not pd.isna(exp_line):
            assert abs(ours.macd[i] - float(exp_line)) < 1e-6, f"line mismatch i={i}"
            cmp_line += 1
        if ours.signal[i] is not None and not pd.isna(exp_sig):
            assert abs(ours.signal[i] - float(exp_sig)) < 1e-6, f"signal mismatch i={i}"
            cmp_sig += 1
        if ours.histogram[i] is not None and not pd.isna(exp_hist):
            assert abs(ours.histogram[i] - float(exp_hist)) < 1e-6, f"hist mismatch i={i}"
            cmp_hist += 1
    assert cmp_line > 100 and cmp_sig > 100 and cmp_hist > 100


@_SKIP
def test_stoch_parity_with_pandas_ta(eurusd_h1_500: list[dict]) -> None:
    """Stochastic %K/%D bit-for-bit (1e-6) vs `pta.stoch(k=14, d=3, smooth_k=3)`."""
    import pandas as pd
    import pandas_ta as pta

    df = pd.DataFrame(eurusd_h1_500)
    ours = stochastic(
        df["high"].tolist(),
        df["low"].tolist(),
        df["close"].tolist(),
        k_period=14,
        d_period=3,
        smooth_k=3,
    )
    expected = pta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
    cols = list(expected.columns)
    col_k = next(c for c in cols if c.startswith("STOCHk"))
    col_d = next(c for c in cols if c.startswith("STOCHd"))

    start = 20
    n = len(df)
    cmp_k = cmp_d = 0
    for i in range(start, n):
        exp_k = expected[col_k].iloc[i]
        exp_d = expected[col_d].iloc[i]
        if ours.k[i] is not None and not pd.isna(exp_k):
            assert abs(ours.k[i] - float(exp_k)) < 1e-6, f"%K mismatch i={i}"
            cmp_k += 1
        if ours.d[i] is not None and not pd.isna(exp_d):
            assert abs(ours.d[i] - float(exp_d)) < 1e-6, f"%D mismatch i={i}"
            cmp_d += 1
    assert cmp_k > 100 and cmp_d > 100
