"""Anti-regression per il fix confluence (audit 2026-05-28, CRIT-1 + CRIT-2).

Prevengono il ritorno dei due bug:
  - CRIT-1: build_ctx_live iniettava volatility_regime=[None]*N → fattore 4
    sempre False → grade ceiling B, A+ irraggiungibile.
  - CRIT-2: spread_baseline_pips=None (manca SPREAD_BASELINE_PIPS in config) →
    fattore spread_session sempre False in backtest.

I test usano il VERO build_ctx_live con un BacktestBroker alimentato da bar
sintetici (nessuno stub che popola artificialmente regime/spread — l'audit ha
mostrato che proprio quegli stub mascheravano i bug).
"""
from __future__ import annotations

import math

from backtest.broker import BacktestBroker
from backtest.costs import CostModel
from backtest.loader import Bar
from config import Config
from strategy.adapters.live import build_ctx_live
from strategy.confluence import score_factors


def _synthetic_broker(n: int = 320) -> BacktestBroker:
    """BacktestBroker EURUSD H1 con n bar sintetici (trend + oscillazione + range vario).

    Volatilità non costante (ampiezza variabile) così il classificatore regime
    può produrre compressed/normal/expanded — non solo un singolo stato.
    """
    cost = CostModel(
        spread_pips=0.5, slippage_pips=0.3, commission_pips_round_trip=0.5,
        pip_size=0.0001, pip_value_usd=10.0,
    )
    brk = BacktestBroker("EURUSD", "H1", 10_000.0, cost, max_window=500)
    px = 1.10
    t0 = 1_600_000_000
    for i in range(n):
        # ampiezza del bar che cresce/decresce a onde → ATR variabile → regime vario
        amp = 0.0003 + 0.0006 * (0.5 + 0.5 * math.sin(i / 23.0))
        drift = 0.00015 * math.sin(i / 17.0)
        px += drift
        o = px
        h = px + amp
        l = px - amp
        c = px + 0.4 * amp * math.sin(i / 5.0)
        brk.advance(Bar(
            time=t0 + i * 3600, open=o, high=h, low=l, close=c,
            volume=100, symbol="EURUSD", timeframe="H1",
        ))
        px = c
    return brk


def _cfg() -> Config:
    cfg = Config()
    cfg.INTRADAY_TIMEFRAME = "H1"
    return cfg


def test_build_ctx_live_populates_volatility_regime():
    """CRIT-1: la serie volatility_regime deve avere valori non-None (non tutta None)."""
    brk = _synthetic_broker()
    ctx = build_ctx_live("EURUSD", brk, "MODERATE", cfg=_cfg())

    series = getattr(ctx._indicators, "volatility_regime", None)
    assert series is not None, "volatility_regime mancante dagli indicatori"
    non_none = [v for v in series if v is not None]
    assert non_none, "volatility_regime è ancora tutta None (CRIT-1 regressione)"
    # l'ultimo bar (quello che il detector consuma via [-1]) deve essere valido
    assert series[-1] in ("compressed", "normal", "expanded"), (
        f"volatility_regime[-1]={series[-1]!r} non è uno stato valido"
    )


def test_build_ctx_live_sets_spread_baseline_pips():
    """CRIT-2: ctx.spread_baseline_pips deve essere non-None (da config SPREAD_BASELINE_PIPS)."""
    cfg = _cfg()
    brk = _synthetic_broker()
    ctx = build_ctx_live("EURUSD", brk, "MODERATE", cfg=cfg)
    assert ctx.spread_baseline_pips is not None, "spread_baseline_pips ancora None (CRIT-2)"
    assert ctx.spread_baseline_pips == float(cfg.SPREAD_BASELINE_PIPS)


def test_score_factors_can_set_regime_and_spread_true_via_real_adapter():
    """Con il context reale, sia volatility_regime sia spread_session possono essere True.

    Pre-fix erano entrambi SEMPRE False in backtest (grade ceiling B). Verifichiamo
    che almeno uno dei 4 setup, su almeno una direzione, riesca a marcarli True.
    """
    brk = _synthetic_broker()
    ctx = build_ctx_live("EURUSD", brk, "MODERATE", cfg=_cfg())
    ind = ctx._indicators

    saw_regime_true = False
    saw_spread_true = False
    for setup in ("A_breakout", "B_reversal", "C_compression", "D_pullback"):
        for direction in ("BUY", "SELL"):
            f = score_factors(setup, ind, ctx, direction)
            saw_regime_true |= bool(f["volatility_regime"])
            saw_spread_true |= bool(f["spread_session"])

    assert saw_spread_true, "spread_session mai True col context reale (CRIT-2 regressione)"
    assert saw_regime_true, "volatility_regime mai True col context reale (CRIT-1 regressione)"
