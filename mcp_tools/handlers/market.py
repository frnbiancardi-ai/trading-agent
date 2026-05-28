"""Market handlers per Phase 6 (D-C1, D-D1, D-E1).

Tool inclusi (Wave 1):
- get_symbol_universe (legacy, invariato)
- get_symbol_indicators (legacy, invariato)
- get_market_snapshot (R1 — additive: bars override + indicators_extended + as_of_ts D-D1)
- scan_symbol_candidates (R2 — additive: regime + correlation_warnings)

Wave 4 (06-05-PLAN) aggiungera': get_correlation_matrix, get_session_state,
get_multi_tf_snapshot, get_pattern_catalog.

Riferimento: 06-CONTEXT.md D-C1 (additive backward-compat), 06-RESEARCH.md R1.
"""
from __future__ import annotations

import dataclasses
from typing import Any

from claude_agent import cheap_scan_symbol
from indicators import compute_all

from mcp_tools.bar_source import BarSource
from mcp_tools.errors import ErrorCodes, envelope


def _serialize_extended(indicators_ext) -> dict | None:
    """Converte ExtendedIndicators (dict o dataclass) in dict JSON-safe.

    Phase 2 compute_all_extended ritorna dict; questa funzione e' tollerante
    a dataclass per evoluzioni future del contratto.
    """
    if indicators_ext is None:
        return None
    if dataclasses.is_dataclass(indicators_ext):
        return dataclasses.asdict(indicators_ext)
    if isinstance(indicators_ext, dict):
        return indicators_ext
    return None


def _extract_regime(indicators_ext: dict | None) -> str:
    """Estrae regime_state da ExtendedIndicators; fallback 'normal'.

    Phase 2 INDIC-14 ritorna 'compressed'/'normal'/'expanded' via regime_state.
    Quando compute_all_extended e' invocato senza regime_cfg, regime_state e' None
    -> fallback 'normal' (default conservativo come da contratto R2).
    """
    if not indicators_ext:
        return "normal"
    state = indicators_ext.get("regime_state") if isinstance(indicators_ext, dict) else None
    if state in ("compressed", "normal", "expanded"):
        return state
    return "normal"


def handle_get_market_snapshot(args: dict, mt5_client, cfg) -> dict:
    """R1 additive (D-C1): default 200 bars + indicators_extended + as_of_ts (D-D1).

    Args:
        args: dict con keys 'symbol' (req), 'bars' (opt 50-500), 'timeframe' (opt),
              'as_of_ts' (opt ISO8601 UTC; D-D1 historical replay).
        mt5_client: Mt5Client istanza (live mode).
        cfg: Config con MCP_DEFAULT_BARS + TIMEFRAME.

    Returns:
        dict con symbol, timeframe, bars_used, ohlc, tick, indicators (legacy),
        indicators_extended (Phase 2). Su errore: envelope D-F2.
    """
    symbol = args["symbol"]
    bars_n = int(args.get("bars", getattr(cfg, "MCP_DEFAULT_BARS", 200)))
    tf = args.get("timeframe", cfg.TIMEFRAME)
    as_of = args.get("as_of_ts")

    try:
        ohlc = BarSource.get(symbol, tf, bars_n,
                              as_of_ts=as_of, mt5_client=mt5_client)
    except FileNotFoundError as exc:
        return envelope(
            ErrorCodes.HISTORICAL_DATA_UNAVAILABLE,
            f"CSV mancante per {symbol}/{tf}",
            path=str(exc),
        )
    except ValueError as exc:
        msg = str(exc)
        if "warmup_insufficient" in msg:
            return envelope(ErrorCodes.AS_OF_TS_WARMUP_INSUFFICIENT, msg)
        return envelope(ErrorCodes.AS_OF_TS_OUT_OF_RANGE, msg)

    # Tick info: solo in live mode (replay storico non ha bid/ask reali)
    tick = {}
    if as_of is None and hasattr(mt5_client, "get_symbol_info"):
        sym_info = mt5_client.get_symbol_info(symbol)
        if sym_info is not None:
            tick = {
                "bid": getattr(sym_info, "bid", None),
                "ask": getattr(sym_info, "ask", None),
                "point": getattr(sym_info, "point", None),
                "digits": getattr(sym_info, "digits", None),
            }

    # Indicators legacy (4 chiavi sma_20/ema_50/rsi_14/atr_14) - backward compat
    indicators_legacy = compute_all(ohlc) if ohlc else {}

    # Indicators extended (Phase 2) - additive D-C1; degrade graceful se mancante
    indicators_ext_payload: dict | None = None
    try:
        from indicators import compute_all_extended  # Phase 2
        ext = compute_all_extended(ohlc) if ohlc else None
        indicators_ext_payload = _serialize_extended(ext)
    except ImportError:
        # Phase 2 non ancora deployata; campo presente ma None.
        pass

    return {
        "symbol": symbol,
        "timeframe": tf,
        "bars_used": len(ohlc),
        "ohlc": ohlc,
        "tick": tick,
        "indicators": indicators_legacy,              # legacy compat
        "indicators_extended": indicators_ext_payload,  # additive D-C1 R1
    }


def handle_scan_symbol_candidates(args: dict, mt5_client, cfg) -> dict:
    """R2 additive (D-C1): aggiunge regime + correlation_warnings per candidato.

    Args:
        args: dict con 'symbols' (list req) e 'timeframe' (opt).
        mt5_client: Mt5Client istanza.
        cfg: Config con TIMEFRAME.

    Returns:
        dict con timeframe, count, candidates (list di SymbolScanCandidate-as-dict
        arricchiti con 'regime' e 'correlation_warnings').

    Pattern Wave 1: regime derivato per-candidate da compute_all_extended Phase 2;
    correlation_warnings vuoto (popolato da Wave 4 con get_correlation_matrix).
    """
    symbols = args.get("symbols") or []
    tf = args.get("timeframe") or cfg.TIMEFRAME

    candidates = []
    for sym in symbols:
        # Cheap scan legacy (ritorna SymbolScanCandidate dataclass)
        cand_dc = cheap_scan_symbol(mt5_client, tf, sym)
        cand = dataclasses.asdict(cand_dc) if dataclasses.is_dataclass(cand_dc) else dict(cand_dc)

        # Additive R2: regime (Phase 2 INDIC-14)
        try:
            from indicators import compute_all_extended
            ohlc = mt5_client.get_ohlc(sym, tf, 200)
            ext = compute_all_extended(ohlc) if ohlc else None
            cand["regime"] = _extract_regime(ext) if ext else "normal"
        except ImportError:
            cand["regime"] = "normal"
        except Exception:
            # Difensivo: errori OHLC/calcolo non bloccano lo scan
            cand["regime"] = "normal"

        # Additive R2: correlation_warnings (Wave 4 lo popola via MCP-09)
        cand["correlation_warnings"] = []

        candidates.append(cand)

    return {
        "timeframe": tf,
        "count": len(candidates),
        "candidates": candidates,
    }


# ── Legacy handlers spostati verbatim ────────────────────────────────────────

def handle_get_symbol_universe(cfg, filter_asset_class: str | None = None) -> dict:
    """Lista simboli operativi configurati (spostato da mcp_server.py)."""
    symbols = list(getattr(cfg, "SYMBOLS", []) or [])
    return {
        "symbols": symbols,
        "count": len(symbols),
        "source": "config.SYMBOLS",
        "filter_asset_class": filter_asset_class,
    }


def handle_get_symbol_indicators(symbol: str, mt5_client, cfg,
                                  timeframe: str | None = None) -> dict:
    """Indicatori legacy SMA/EMA/RSI/ATR (spostato da mcp_server.py:142-155)."""
    tf = timeframe or cfg.TIMEFRAME
    ohlc = mt5_client.get_ohlc(symbol, tf, 100)
    if not ohlc:
        return envelope("no_ohlc_data",
                         f"OHLC vuoto per {symbol}/{tf}",
                         symbol=symbol, timeframe=tf)
    indicators = compute_all(ohlc)
    return {
        "symbol": symbol,
        "timeframe": tf,
        "bars_used": len(ohlc),
        "last_close": ohlc[-1]["close"],
        "indicators": indicators,
    }
