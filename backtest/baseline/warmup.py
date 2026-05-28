"""Warm-up helper adattivo per baseline backtest (D-07).

REVISIONE 2026-05-08 (BLOCKER 3 user-locked decision): implementa adaptive helper.
`slice_worker` calcola: warm_up = max(baseline_cfg.warm_up_min_bars,
longest_lookback_required(strategy_cfg)); bars = bars[warm_up:].

Strategia tolerante:
  1. Se `indicators.indicators_full.longest_lookback()` è esposto da Phase 2 → usa quello.
  2. Altrimenti parsa `config/strategy.yaml` indicator block (ema_periods, atr_period,
     bb_period, donchian_period, etc.) e ritorna max valore.
  3. Default fallback: 200 (bias safe per coerenza con `warm_up_min_bars` D-15).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_DEFAULT_FALLBACK = 200

# Chiavi YAML che rappresentano lookback period (Phase 2 indicator config naming).
# Aggiungere chiavi qui se Phase 2 introduce nuovi indicator con lookback.
_LOOKBACK_KEYS = {
    "ema_period", "ema_periods", "atr_period", "rsi_period", "adx_period",
    "bb_period", "donchian_period", "keltner_period", "macd_slow",
    "stoch_period", "vwap_period", "fib_lookback", "hurst_window",
    "longest_lookback", "lookback",
}


def _flatten_numeric(obj: Any) -> list[int]:
    """DFS estrae tutti gli int da chiavi-lookback in un dict/list nested."""
    out: list[int] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _LOOKBACK_KEYS:
                if isinstance(v, (int, float)):
                    out.append(int(v))
                elif isinstance(v, list):
                    out.extend(int(x) for x in v if isinstance(x, (int, float)))
            else:
                out.extend(_flatten_numeric(v))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_flatten_numeric(item))
    return out


def longest_lookback_required(strategy_cfg: Any) -> int:
    """D-07 adaptive warm-up: max bars di lookback su tutti gli indicator configurati.

    strategy_cfg può essere:
      - dict (yaml.safe_load output)
      - Path/str (legge il file YAML)
      - None (usa default)

    Tentativi (in ordine):
      1. Phase 2 hook: indicators.indicators_full.longest_lookback() se esiste.
      2. Parsing dict: max sui valori delle chiavi in _LOOKBACK_KEYS (DFS nested).
      3. Default fallback: 200.
    """
    # Tentativo 1: Phase 2 hook (lazy import, optional)
    try:
        from indicators import indicators_full as _ind  # type: ignore
        fn = getattr(_ind, "longest_lookback", None)
        if callable(fn):
            val = int(fn())
            if val > 0:
                return val
    except Exception:  # noqa: BLE001 — modulo non ancora landed (Phase 2 pending)
        pass

    # Tentativo 2: parsing dict
    cfg_dict: dict | None = None
    if isinstance(strategy_cfg, dict):
        cfg_dict = strategy_cfg
    elif isinstance(strategy_cfg, (str, Path)):
        try:
            import yaml
            with open(strategy_cfg, encoding="utf-8") as f:
                cfg_dict = yaml.safe_load(f) or {}
        except Exception as exc:  # noqa: BLE001
            _log.warning("longest_lookback: impossibile leggere %s (%s)", strategy_cfg, exc)
            cfg_dict = None

    if cfg_dict:
        values = _flatten_numeric(cfg_dict)
        if values:
            return max(values)

    # Tentativo 3: fallback
    _log.info("longest_lookback: nessuna config parseable, uso fallback %d", _DEFAULT_FALLBACK)
    return _DEFAULT_FALLBACK
