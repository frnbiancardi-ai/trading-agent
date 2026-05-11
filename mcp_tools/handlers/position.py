"""Position handlers per Phase 6 Wave 3 (Plan 06-04).

Tool inclusi:
- modify_position (MCP-16, D-B1 atomic combo + D-B3 stops_level validation)
- get_position_state (MCP-17): read-only stato + P&L + distances + holding
- close_position: spostato qui da mcp_tools/server.py inline branch (invariato)

EXECUTION_MODE=shadow: cfg.DRY_RUN gate mirror del pattern close_position
(mcp_server.py:411-421). MAI bypassare. CLAUDE.md mandate.
"""
from __future__ import annotations

import dataclasses

from mcp.types import Tool

from mcp_tools.errors import ErrorCodes, envelope
from mcp_tools.schemas import (
    GET_POSITION_STATE_SCHEMA,
    MODIFY_POSITION_SCHEMA,
)
from mcp_tools.trail_daemon import register_trail


# ── Tool registrations (D-F1) ─────────────────────────────────────────────────

MODIFY_POSITION_TOOL = Tool(
    name="modify_position",
    description=(
        "Combo tool atomico per gestione posizione attiva (D-B1):\n"
        "- new_sl / new_tp: modifica diretta SL/TP via TRADE_ACTION_SLTP\n"
        "- move_sl_to_breakeven: SL = entry_price\n"
        "- partial_close_lots: chiude parzialmente, mantiene stesso ticket\n"
        "- trail_stop_atr_mult: registra trail ATR-based (daemon scheduler-driven)\n"
        "Almeno 1 arg deve essere settato. Conflitti rifiutati:\n"
        "  trail+sl, be+sl, partial>=volume\n"
        "Stops-level pre-validato (no auto-clamp); violazione → suggested_sl."
    ),
    inputSchema=MODIFY_POSITION_SCHEMA,
)


GET_POSITION_STATE_TOOL = Tool(
    name="get_position_state",
    description=(
        "Stato corrente di una posizione (MCP-17): P&L pips/money, "
        "distance to SL/TP in pips, holding time minuti, max favorable excursion. "
        "Read-only."
    ),
    inputSchema=GET_POSITION_STATE_SCHEMA,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pip_size(symbol: str) -> float:
    """0.0001 per coppie non-JPY, 0.01 per JPY (FX convention)."""
    return 0.01 if "JPY" in symbol.upper() else 0.0001


def _stops_level_pips(symbol_info, pip_size: float) -> float:
    """Conversione `trade_stops_level` (points) → pips usando `point`."""
    return symbol_info.trade_stops_level * symbol_info.point / pip_size


def _validate_sl_distance(
    pos,
    new_sl: float,
    stops_level_pips: float,
    pip_size: float,
    current_price: float,
) -> tuple[bool, float]:
    """D-B3: ritorna (ok, suggested_sl). Direction da `pos.direction`."""
    min_distance = stops_level_pips * pip_size
    if pos.direction == "BUY":
        if current_price - new_sl < min_distance:
            return False, current_price - min_distance
    else:
        if new_sl - current_price < min_distance:
            return False, current_price + min_distance
    return True, new_sl


# ── Handlers ──────────────────────────────────────────────────────────────────

def handle_modify_position(args: dict, mt5_client, cfg, log) -> dict:
    """MCP-16 D-B1: atomic combo. EXECUTION_MODE=shadow gate mirror close_position."""
    pid = int(args["position_id"])

    # Validazione: almeno 1 arg di mutazione
    has_any = (
        any(args.get(k) is not None for k in (
            "new_sl", "new_tp", "partial_close_lots", "trail_stop_atr_mult",
        ))
        or args.get("move_sl_to_breakeven") is True
    )
    if not has_any:
        return envelope(
            "missing_mutation_arg",
            "Almeno uno tra new_sl/new_tp/partial_close_lots/"
            "move_sl_to_breakeven/trail_stop_atr_mult deve essere settato",
            position_id=pid,
        )

    # Conflict detection (D-B1)
    if (
        args.get("trail_stop_atr_mult") is not None
        and args.get("new_sl") is not None
    ):
        return envelope(
            ErrorCodes.CONFLICT_TRAIL_AND_MANUAL_SL,
            "trail_stop_atr_mult e new_sl non possono coesistere",
            position_id=pid,
        )
    if args.get("move_sl_to_breakeven") and args.get("new_sl") is not None:
        return envelope(
            ErrorCodes.CONFLICT_BE_AND_MANUAL_SL,
            "move_sl_to_breakeven e new_sl non possono coesistere",
            position_id=pid,
        )

    # Recupera posizione corrente
    pos = mt5_client.get_position(pid)
    if pos is None:
        return envelope(
            ErrorCodes.POSITION_NOT_FOUND,
            f"Posizione {pid} non trovata",
            position_id=pid,
        )

    # partial_close >= volume → suggerisci close_position
    if (
        args.get("partial_close_lots") is not None
        and args["partial_close_lots"] >= pos.lots
    ):
        return envelope(
            ErrorCodes.PARTIAL_EXCEEDS_VOLUME,
            f"partial_close_lots ({args['partial_close_lots']}) "
            f">= pos.volume ({pos.lots}); usa close_position",
            position_id=pid, current_volume=pos.lots,
        )

    # Determina new_sl effettivo (breakeven sostituisce a entry_price)
    new_sl = args.get("new_sl")
    if args.get("move_sl_to_breakeven"):
        new_sl = float(pos.entry_price)
    new_tp = args.get("new_tp")

    # ── DRY_RUN gate (CLAUDE.md EXECUTION_MODE=shadow) ────────────────────────
    if getattr(cfg, "DRY_RUN", False):
        intent: list[dict] = []
        if new_sl is not None or new_tp is not None:
            intent.append({"action": "modify_sltp", "sl": new_sl, "tp": new_tp})
        if args.get("partial_close_lots") is not None:
            intent.append({
                "action": "partial_close",
                "lots": args["partial_close_lots"],
            })
        if args.get("trail_stop_atr_mult") is not None:
            intent.append({
                "action": "trail_registered",
                "atr_mult": args["trail_stop_atr_mult"],
            })
        log.info(
            "MCP modify_position DRY_RUN ticket=%d intent=%s", pid, intent,
        )
        return {
            "ok": True,
            "execution_mode": cfg.EXECUTION_MODE,
            "dry_run": True,
            "position_id": pid,
            "applied": intent,
            "note": "DRY_RUN: nessun ordine inviato a MT5",
        }

    applied: list[dict] = []

    # ── SL/TP via TRADE_ACTION_SLTP ──────────────────────────────────────────
    if new_sl is not None or new_tp is not None:
        sym_info = mt5_client.get_symbol_info(pos.symbol)
        if sym_info is None:
            return envelope(
                ErrorCodes.MT5_NOT_READY,
                f"symbol_info indisponibile per {pos.symbol}",
                position_id=pid,
            )
        pip = _pip_size(pos.symbol)
        sl_pips = _stops_level_pips(sym_info, pip)
        # BUY chiude a bid, SELL a ask (convenzione FX)
        current_price = (
            sym_info.bid if pos.direction == "BUY" else sym_info.ask
        )

        if new_sl is not None:
            ok, suggested = _validate_sl_distance(
                pos, new_sl, sl_pips, pip, current_price,
            )
            if not ok:
                return envelope(
                    ErrorCodes.STOPS_LEVEL_VIOLATION,
                    f"SL viola stops_level broker (min {sl_pips:.1f} pips)",
                    position_id=pid,
                    current_price=current_price,
                    min_distance_pips=sl_pips,
                    requested_sl=new_sl,
                    suggested_sl=suggested,
                )

        result = mt5_client.modify_position(pid, sl=new_sl, tp=new_tp)
        if not result.success:
            return envelope(
                ErrorCodes.BROKER_REJECTED,
                f"modify SL/TP rifiutato: {result.error_message}",
                position_id=pid, applied_so_far=applied,
                broker_error=result.error_message,
            )
        applied.append({"action": "modify_sltp", "sl": new_sl, "tp": new_tp})

    # ── Partial close ────────────────────────────────────────────────────────
    if args.get("partial_close_lots") is not None:
        result = mt5_client.partial_close(pid, args["partial_close_lots"])
        if not result.success:
            return envelope(
                ErrorCodes.BROKER_REJECTED,
                f"partial close rifiutato: {result.error_message}",
                position_id=pid, applied_so_far=applied,
                broker_error=result.error_message,
            )
        applied.append({
            "action": "partial_close",
            "lots": args["partial_close_lots"],
        })

    # ── Trail register ───────────────────────────────────────────────────────
    if args.get("trail_stop_atr_mult") is not None:
        from logger import _trades_db_path
        db_path = str(_trades_db_path(cfg))
        register_trail(
            db_path, pid, pos.symbol, pos.direction,
            cfg.TRAIL_TICK_TIMEFRAME,
            args["trail_stop_atr_mult"],
            float(pos.stop_loss) if pos.stop_loss else float(pos.entry_price),
        )
        applied.append({
            "action": "trail_registered",
            "atr_mult": args["trail_stop_atr_mult"],
        })

    return {
        "ok": True,
        "execution_mode": cfg.EXECUTION_MODE,
        "dry_run": False,
        "position_id": pid,
        "applied": applied,
    }


def handle_get_position_state(args: dict, mt5_client, cfg) -> dict:
    """MCP-17: read-only stato + P&L pips/money + distances + holding."""
    pid = int(args["position_id"])
    pos = mt5_client.get_position(pid)
    if pos is None:
        return envelope(
            ErrorCodes.POSITION_NOT_FOUND,
            f"Posizione {pid} non trovata",
            position_id=pid,
        )

    sym_info = mt5_client.get_symbol_info(pos.symbol)
    if sym_info is None:
        return envelope(
            ErrorCodes.MT5_NOT_READY,
            f"symbol_info indisponibile per {pos.symbol}",
            position_id=pid,
        )

    pip = _pip_size(pos.symbol)
    current_price = (
        sym_info.bid if pos.direction == "BUY" else sym_info.ask
    )

    pnl_pips = (
        (current_price - pos.entry_price) / pip
        if pos.direction == "BUY"
        else (pos.entry_price - current_price) / pip
    )

    distance_to_sl_pips = (
        abs(current_price - pos.stop_loss) / pip if pos.stop_loss else None
    )
    distance_to_tp_pips = (
        abs(pos.take_profit - current_price) / pip if pos.take_profit else None
    )

    # Holding minutes: PositionInfo Wave 1 non ha `time` field; aggiungerlo
    # è out-of-scope qui — segna None (Wave 9 future: storico in trades_log).
    holding_minutes = None

    # MFE: max favorable excursion. Senza tracking storico, proxy = pnl positivo
    # corrente (Wave 9 future: colonna mfe_pips in trades_log per persistente).
    mfe_pips = max(0.0, pnl_pips)

    return {
        "position_id": pid,
        "symbol": pos.symbol,
        "direction": pos.direction,
        "lots": pos.lots,
        "entry_price": pos.entry_price,
        "current_price": current_price,
        "stop_loss": pos.stop_loss,
        "take_profit": pos.take_profit,
        "pnl_pips": pnl_pips,
        "pnl_money": pos.profit,
        "distance_to_sl_pips": distance_to_sl_pips,
        "distance_to_tp_pips": distance_to_tp_pips,
        "holding_minutes": holding_minutes,
        "mfe_pips": mfe_pips,
    }


def handle_close_position(args: dict, mt5_client, cfg, log) -> dict:
    """Spostato da mcp_tools/server.py:325-342 invariato — DRY_RUN gate canonico."""
    pid = int(args["position_id"])
    if cfg.DRY_RUN:
        log.info(
            "MCP close_position DRY_RUN ticket=%d (nessun ordine reale)", pid,
        )
        return {
            "ok": True,
            "success": True,
            "order_id": None,
            "error_message": None,
            "execution_mode": cfg.EXECUTION_MODE,
            "dry_run": True,
            "note": "DRY_RUN: nessun ordine inviato a MT5",
        }
    result = mt5_client.close_position(pid)
    return {
        **dataclasses.asdict(result),
        "execution_mode": cfg.EXECUTION_MODE,
        "dry_run": False,
    }
