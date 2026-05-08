"""Test indicators.volatility — parity vs pandas-ta + sanity hand-calc.

pandas-ta è dev-dep (oracolo): se non installato i test parity sono SKIPPED.
I test sanity (zero-variance) girano sempre.
"""
from __future__ import annotations

import importlib.util

import pytest

from indicators.volatility import bollinger_bands, keltner

_HAVE_PTA = importlib.util.find_spec("pandas_ta") is not None
_SKIP = pytest.mark.skipif(not _HAVE_PTA, reason="pandas-ta dev-dep non installato")


# ── Sanity hand-calc (sempre eseguiti) ────────────────────────────────────────


def test_bollinger_zero_variance() -> None:
    """Serie costante → BB collassano sulla media, BBW = 0."""
    r = bollinger_bands([1.0] * 30, length=20, std=2.0)
    assert r.middle[19] == 1.0
    assert r.upper[19] == 1.0
    assert r.lower[19] == 1.0
    assert r.bbw[19] == 0.0


def test_keltner_constant_series() -> None:
    """ATR == 0 su serie H==L==C costante; upper == lower == middle.

    Nota: ATR(period=20) richiede 21 bar prima del primo valore valido (seed
    su tr[1..period]); con length=20 la prima posizione Keltner valida è i=20.
    Usiamo 40 bar per essere comodi e verifichiamo all'indice 25.
    """
    h = [1.0] * 40
    l = [1.0] * 40
    c = [1.0] * 40
    r = keltner(h, l, c, length=20, scalar=2.0)
    assert r.middle[25] == 1.0
    assert r.upper[25] == 1.0
    assert r.lower[25] == 1.0


def test_bollinger_warmup_none() -> None:
    """Indici < length-1 sono None (warmup)."""
    r = bollinger_bands([float(i) for i in range(30)], length=20, std=2.0)
    assert all(v is None for v in r.middle[:19])
    assert r.middle[19] is not None


def test_keltner_input_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        keltner([1.0, 2.0], [1.0], [1.0, 2.0], length=2)


# ── Parity vs pandas-ta (SKIPPED se non installato) ───────────────────────────


@_SKIP
def test_bbands_parity_with_pandas_ta(eurusd_h1_500: list[dict]) -> None:
    """BB upper/middle/lower bit-for-bit (1e-6) vs pandas-ta `bbands(20, 2.0)`."""
    import pandas as pd
    import pandas_ta as pta

    df = pd.DataFrame(eurusd_h1_500)
    ours = bollinger_bands(df["close"].tolist(), length=20, std=2.0)
    expected = pta.bbands(df["close"], length=20, std=2.0)
    cols = list(expected.columns)
    col_up = next(c for c in cols if c.startswith("BBU"))
    col_mid = next(c for c in cols if c.startswith("BBM"))
    col_lo = next(c for c in cols if c.startswith("BBL"))
    # Skip i primi 2*length per evitare transienti di seed pandas-ta.
    start = 40
    for i in range(start, len(df)):
        if ours.upper[i] is None:
            continue
        assert abs(ours.upper[i] - expected[col_up].iloc[i]) < 1e-6, f"upper mismatch i={i}"
        assert abs(ours.middle[i] - expected[col_mid].iloc[i]) < 1e-6, f"middle mismatch i={i}"
        assert abs(ours.lower[i] - expected[col_lo].iloc[i]) < 1e-6, f"lower mismatch i={i}"


@_SKIP
def test_keltner_parity_with_pandas_ta(eurusd_h1_500: list[dict]) -> None:
    """Keltner upper/middle/lower bit-for-bit (1e-6) vs pandas-ta `kc(20, 2, ema)`."""
    import pandas as pd
    import pandas_ta as pta

    df = pd.DataFrame(eurusd_h1_500)
    ours = keltner(
        df["high"].tolist(),
        df["low"].tolist(),
        df["close"].tolist(),
        length=20,
        scalar=2.0,
    )
    expected = pta.kc(
        df["high"], df["low"], df["close"], length=20, scalar=2, mamode="ema"
    )
    cols = list(expected.columns)
    col_lo = next(c for c in cols if c.startswith("KCL"))
    col_mid = next(c for c in cols if c.startswith("KCB"))
    col_up = next(c for c in cols if c.startswith("KCU"))
    start = 40
    for i in range(start, len(df)):
        if ours.upper[i] is None:
            continue
        assert abs(ours.upper[i] - expected[col_up].iloc[i]) < 1e-6, f"upper mismatch i={i}"
        assert abs(ours.middle[i] - expected[col_mid].iloc[i]) < 1e-6, f"middle mismatch i={i}"
        assert abs(ours.lower[i] - expected[col_lo].iloc[i]) < 1e-6, f"lower mismatch i={i}"
