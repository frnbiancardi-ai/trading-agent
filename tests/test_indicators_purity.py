"""Test universali di purezza: nessun import oracolare a runtime, nessuna future leakage.

Le proprieta verificate qui valgono per OGNI indicatore rolling che il pacchetto
`indicators` esporra. Wave 1+ DEVONO aggiungere test parametrizzati analoghi per
i nuovi indicatori (BB, ADX, MACD, Stoch, Donchian, Keltner, regime, Hurst, ...).
"""
from __future__ import annotations

import sys

import pytest


def test_no_pandas_ta_at_runtime():
    """Pitfall 8: pandas_ta e dev-dep, mai importato dal pacchetto runtime."""
    if "pandas_ta" in sys.modules:
        del sys.modules["pandas_ta"]
    # Force a fresh import of the indicators package
    for mod in list(sys.modules):
        if mod == "indicators" or mod.startswith("indicators."):
            del sys.modules[mod]
    import indicators  # noqa: F401
    assert "pandas_ta" not in sys.modules, "pandas_ta importato a runtime — vietato (D-07)"


def test_backward_compat_callsite_imports():
    """Le 4 callsite esistenti devono continuare a risolvere."""
    # claude_agent.py:12 + mcp_server.py:28
    from indicators import compute_all  # noqa: F401
    # scanner.py:10
    from indicators import sma, ema, rsi, atr  # noqa: F401
    # strategy.py:11
    from indicators import (  # noqa: F401
        sma,
        ema,
        rsi,
        atr,
        avg_volume,
        calculate_trend_strength,
        find_support_resistance,
        check_breakout_quality,
        calculate_risk_reward,
    )


@pytest.mark.parametrize("idx", [50, 100, 200, 350, 499])
def test_no_future_leakage_atr(eurusd_h1_500, idx):
    """ATR(prefix)[i] == ATR(full)[i] per i fissato — assenza di future leakage."""
    from indicators import atr
    bars = eurusd_h1_500
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    full = atr(highs, lows, closes, 14)
    prefix = bars[: idx + 1]
    p_h = [b["high"] for b in prefix]
    p_l = [b["low"] for b in prefix]
    p_c = [b["close"] for b in prefix]
    partial = atr(p_h, p_l, p_c, 14)
    assert partial[idx] == full[idx], f"future leakage at i={idx}"


@pytest.mark.parametrize("idx", [25, 100, 250, 400, 499])
def test_no_future_leakage_sma_ema_rsi(eurusd_h1_500, idx):
    """SMA/EMA/RSI(prefix)[i] == (full)[i] per i fissato."""
    from indicators import sma, ema, rsi
    bars = eurusd_h1_500
    closes = [b["close"] for b in bars]
    prefix_closes = closes[: idx + 1]
    assert sma(closes, 20)[idx] == sma(prefix_closes, 20)[idx]
    assert ema(closes, 50)[idx] == ema(prefix_closes, 50)[idx]
    assert rsi(closes, 14)[idx] == rsi(prefix_closes, 14)[idx]


@pytest.mark.parametrize("idx", [50, 100, 250, 400, 499])
def test_no_future_leakage_bollinger(eurusd_h1_500, idx):
    """Bollinger(prefix)[i] == (full)[i] su upper/lower/bbw/squeeze.

    `squeeze_lookback_bars=60` per garantire che la finestra sia raggiungibile
    anche al primo idx parametrizzato (50 < 60+19, quindi squeeze[i]=None=None: OK).
    """
    from indicators.volatility import bollinger_bands
    closes = [b["close"] for b in eurusd_h1_500]
    full = bollinger_bands(closes, length=20, std=2.0, squeeze_lookback_bars=60)
    partial = bollinger_bands(closes[: idx + 1], length=20, std=2.0, squeeze_lookback_bars=60)
    assert partial.upper[idx] == full.upper[idx]
    assert partial.lower[idx] == full.lower[idx]
    assert partial.bbw[idx] == full.bbw[idx]
    assert partial.squeeze[idx] == full.squeeze[idx]


@pytest.mark.parametrize("idx", [50, 100, 250, 400, 499])
def test_no_future_leakage_keltner(eurusd_h1_500, idx):
    """Keltner(prefix)[i] == (full)[i] su upper/middle/lower."""
    from indicators.volatility import keltner
    bars = eurusd_h1_500
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    full = keltner(highs, lows, closes, length=20, scalar=2.0)
    partial = keltner(
        highs[: idx + 1], lows[: idx + 1], closes[: idx + 1], length=20, scalar=2.0
    )
    assert partial.upper[idx] == full.upper[idx]
    assert partial.middle[idx] == full.middle[idx]
    assert partial.lower[idx] == full.lower[idx]


@pytest.mark.parametrize("idx", [50, 100, 250, 400, 499])
def test_no_future_leakage_adx(eurusd_h1_500, idx):
    """ADX(prefix)[i] == (full)[i] su adx/plus_di/minus_di."""
    from indicators.momentum import adx
    bars = eurusd_h1_500
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    full = adx(highs, lows, closes, period=14)
    partial = adx(
        highs[: idx + 1], lows[: idx + 1], closes[: idx + 1], period=14
    )
    assert partial.adx[idx] == full.adx[idx]
    assert partial.plus_di[idx] == full.plus_di[idx]
    assert partial.minus_di[idx] == full.minus_di[idx]


@pytest.mark.parametrize("idx", [50, 100, 250, 400, 499])
def test_no_future_leakage_macd(eurusd_h1_500, idx):
    """MACD(prefix)[i] == (full)[i] su line/signal/histogram."""
    from indicators.momentum import macd
    closes = [b["close"] for b in eurusd_h1_500]
    full = macd(closes, fast=12, slow=26, signal=9)
    partial = macd(closes[: idx + 1], fast=12, slow=26, signal=9)
    assert partial.macd[idx] == full.macd[idx]
    assert partial.signal[idx] == full.signal[idx]
    assert partial.histogram[idx] == full.histogram[idx]


@pytest.mark.parametrize("idx", [50, 100, 250, 400, 499])
def test_no_future_leakage_stochastic(eurusd_h1_500, idx):
    """Stochastic(prefix)[i] == (full)[i] su k/d."""
    from indicators.momentum import stochastic
    bars = eurusd_h1_500
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    full = stochastic(highs, lows, closes, k_period=14, d_period=3, smooth_k=3)
    partial = stochastic(
        highs[: idx + 1], lows[: idx + 1], closes[: idx + 1],
        k_period=14, d_period=3, smooth_k=3,
    )
    assert partial.k[idx] == full.k[idx]
    assert partial.d[idx] == full.d[idx]


@pytest.mark.parametrize("idx", [120, 200, 300, 400, 499])
def test_no_future_leakage_hurst(eurusd_h1_500, idx):
    """Hurst R/S(prefix)[i] == (full)[i]. INDIC-12.

    Indici scelti tutti >= window-1=99 (window=100) per avere stime valide
    da confrontare. Idx=120 è il primo "post-warmup" verificato.
    """
    from indicators.hurst import hurst_rs
    closes = [b["close"] for b in eurusd_h1_500]
    full = hurst_rs(closes, 100)
    partial = hurst_rs(closes[: idx + 1], 100)
    assert partial.hurst[idx] == full.hurst[idx], f"future leakage hurst @ i={idx}"


@pytest.mark.parametrize("idx", [50, 100, 250, 400, 499])
def test_no_future_leakage_donchian(eurusd_h1_500, idx):
    """Donchian(prefix)[i] == (full)[i] su upper/lower/middle. INDIC-05."""
    from indicators.structure import donchian
    bars = eurusd_h1_500
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    full = donchian(highs, lows, 20)
    partial = donchian(highs[: idx + 1], lows[: idx + 1], 20)
    assert partial.upper[idx] == full.upper[idx]
    assert partial.lower[idx] == full.lower[idx]
    assert partial.middle[idx] == full.middle[idx]


@pytest.mark.parametrize("idx", [100, 200, 300, 400, 499])
def test_no_future_leakage_pivots(eurusd_h1_500, idx):
    """Pivots(prefix)[i] == (full)[i] su P + Camarilla h1. INDIC-09.

    Anchor 'daily': bar usa H/L/C della sessione precedentemente chiusa, quindi
    pivots su prefix[:idx+1] e su full devono concordare a indice idx purché
    almeno un boundary di sessione sia già stato attraversato. Tutti i 5 idx
    parametrizzati sono >= 100 per garantirlo (la fixture H1 attraversa la
    prima sessione entro le prime ~24 bar)."""
    from indicators.structure import pivots
    bars = eurusd_h1_500
    full = pivots(bars, anchor="daily")
    partial = pivots(bars[: idx + 1], anchor="daily")
    assert partial.p[idx] == full.p[idx], f"future leakage pivots.p @ i={idx}"
    assert partial.r1[idx] == full.r1[idx]
    assert partial.s3[idx] == full.s3[idx]
    assert partial.camarilla["h1"][idx] == full.camarilla["h1"][idx]
    assert partial.camarilla["l4"][idx] == full.camarilla["l4"][idx]


@pytest.mark.parametrize("idx", [50, 100, 250, 400, 499])
def test_no_future_leakage_vwap_intraday(eurusd_h1_500, idx):
    """VWAP intraday(prefix)[i] == (full)[i] su vwap/cumulative_pv/cumulative_v. INDIC-07.

    Reset session NY-17 è funzione locale dei timestamp delle bar, quindi il
    cumulativo di una sessione dipende solo dalle bar precedenti nella stessa
    sessione — leakage-free per costruzione."""
    from indicators.volume import vwap_intraday
    bars = eurusd_h1_500
    full = vwap_intraday(bars)
    partial = vwap_intraday(bars[: idx + 1])
    assert partial.vwap[idx] == full.vwap[idx], f"future leakage vwap @ i={idx}"
    assert partial.cumulative_pv[idx] == full.cumulative_pv[idx]
    assert partial.cumulative_v[idx] == full.cumulative_v[idx]


@pytest.mark.parametrize("idx", [50, 100, 250, 400, 499])
def test_no_future_leakage_narrow_range(eurusd_h1_500, idx):
    """narrow_range(prefix)[i] == (full)[i] su nr4/nr7/inside/boomer. INDIC-10.

    Per costruzione ogni flag a i dipende solo da bar j<=i (range, inside, NR
    window) → leakage-free. Verificato a 5 spot indices."""
    from indicators.bars import narrow_range
    bars = eurusd_h1_500
    full = narrow_range(bars)
    partial = narrow_range(bars[: idx + 1])
    assert partial.nr4[idx] == full.nr4[idx], f"future leakage nr4 @ i={idx}"
    assert partial.nr7[idx] == full.nr7[idx], f"future leakage nr7 @ i={idx}"
    assert partial.inside[idx] == full.inside[idx], f"future leakage inside @ i={idx}"
    assert partial.boomer[idx] == full.boomer[idx], f"future leakage boomer @ i={idx}"


@pytest.mark.parametrize("idx", [10, 100, 250, 400, 499])
def test_no_future_leakage_closing_score(eurusd_h1_500, idx):
    """closing_score(prefix)[i] == (full)[i]. INDIC-11.

    Closing score per bar i dipende SOLO da high/low/close della bar i stessa
    → leakage-free per costruzione (purezza assoluta)."""
    from indicators.bars import closing_score
    bars = eurusd_h1_500
    full = closing_score(bars)
    partial = closing_score(bars[: idx + 1])
    assert partial.score[idx] == full.score[idx], f"future leakage closing_score @ i={idx}"


@pytest.mark.parametrize("idx", [200, 250, 350, 450, 499])
def test_no_future_leakage_volatility_regime(eurusd_h1_500, idx):
    """volatility_regime(prefix)[i] == (full)[i]. INDIC-14 (Pitfall 4).

    Idx scelti tutti >= window-1=199 (window=200) per avere stime valide. Un
    rank-globale (`series.rank(pct=True)`) avrebbe leakage perche il percentile
    di ATR[i] dipenderebbe dai valori 200..499; un rolling rank corretto su
    finestra trailing produce lo stesso risultato su prefix e full.
    """
    from indicators.volatility import volatility_regime
    cfg = {"window": 200, "compressed_below": 30, "expanded_above": 70}
    bars = eurusd_h1_500
    full = volatility_regime(bars, cfg)
    partial = volatility_regime(bars[: idx + 1], cfg)
    assert partial.state[idx] == full.state[idx], f"leakage state @ i={idx}"
    assert partial.atr_percentile[idx] == full.atr_percentile[idx], (
        f"leakage atr_percentile @ i={idx}"
    )


def test_no_future_leakage_align_synthetic():
    """align(streams)[i] == align(prefix)[i]. INDIC-13.

    Verifica che lo slicing di tutti e 3 gli stream a bar con time <= m15[idx].time
    produca lo stesso score a indice idx del calcolo full. Per costruzione `align`
    e leakage-free (cumulativi locali alla sessione), ma il test e una guard
    universale equivalente ai 12 leakage-test esistenti."""
    from indicators.mtf import align

    def _stream(p0: float, slope: float, n: int, dt: int) -> list[dict]:
        return [
            {
                "time": i * dt,
                "high": p0 + slope * i,
                "low": p0 + slope * i,
                "close": p0 + slope * i,
                "open": p0 + slope * i,
                "volume": 1,
                "tick_volume": 1,
            }
            for i in range(n)
        ]

    # Stream sizing: M15 dt=60, H1 dt=240 (4x), H4 dt=960 (16x). Per warmare H4
    # all'indice 52 → M15 deve coprire 52*960=49920s → length >= 833. Usiamo 1200.
    m15 = _stream(100.0, 0.5, 1200, 60)
    h1 = _stream(100.0, 2.0, 300, 240)
    h4 = _stream(100.0, 8.0, 100, 960)
    full = align({"H4": h4, "H1": h1, "M15": m15})
    for idx in (900, 1000, 1100, 1199):
        t = int(m15[idx]["time"])
        m15_p = m15[: idx + 1]
        h1_p = [b for b in h1 if int(b["time"]) <= t]
        h4_p = [b for b in h4 if int(b["time"]) <= t]
        partial = align({"H4": h4_p, "H1": h1_p, "M15": m15_p})
        assert partial.score[idx] == full.score[idx], f"leakage at i={idx}"
