"""Trail daemon (D-B2) per Phase 6 MCP Tools.

Architettura:
- Tabella SQLite `position_trails` persistente (logs/trades.db) — sopravvive al restart.
- `trail_tick(mt5_client, db_path, cfg)` chiamato dallo scheduler ogni ciclo
  (Phase 16 IntradayLoopScheduler.run_one_cycle).
- Idempotente: position chiusa → row.active=0; broker reject → log + skip,
  prossimo tick rivaluta.
- ATR-based: candidate_sl = pos.price_current ± atr * atr_mult.
- Pre-validate stops_level (Pitfall 2): clamp candidate alla boundary broker
  per evitare reject loop infinito; re-check favorability post-clamp.

Deviation Rule 3 (Plan 06-04): la signature reale di indicators è
`atr(highs, lows, closes, period=14) -> list[float|None]` (vedi
`indicators/volatility.py`), NON `compute_atr(bars, period=14)` come scritto
nel plan. `compute_atr` qui è uno shim che adatta `list[dict]` → 3 list per
poter monkeypatchare l'ATR nei test senza dover replicare la generazione
di bar realistiche.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from indicators import atr as _atr_series
from logger import init_logger
from config import Config

_log_cfg = Config()
log = init_logger(_log_cfg)


_POSITION_TRAILS_DDL = """
CREATE TABLE IF NOT EXISTS position_trails (
    position_id    INTEGER PRIMARY KEY,
    symbol         TEXT NOT NULL,
    direction      TEXT NOT NULL,           -- BUY | SELL
    timeframe      TEXT NOT NULL,
    atr_mult       REAL NOT NULL,
    last_sl        REAL NOT NULL,
    activated_at   TEXT NOT NULL,           -- ISO8601 UTC
    last_update_at TEXT,                    -- NULL on register
    active         INTEGER NOT NULL DEFAULT 1
)
"""


def _utcnow_iso() -> str:
    """ISO8601 UTC con suffisso 'Z' (audit trail uniforme con Wave 0/2)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compute_atr(bars: list[dict], period: int = 14) -> float:
    """Shim trail_daemon: estrae ATR(period) dall'ultimo bar di `bars`.

    Wrapper su `indicators.atr(highs, lows, closes, period)`. Ritorna il valore
    ATR dell'ultimo bar (price units). `bars` deve avere almeno `period+1` elementi
    altrimenti ritorna 0.0 (skip-friendly: tick stops sopra a `len(bars) < 14`).

    Esposto come simbolo monkeypatchable per i test (vedi `test_mcp_trail_daemon`).
    """
    if not bars or len(bars) < period + 1:
        return 0.0
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    closes = [float(b["close"]) for b in bars]
    series = _atr_series(highs, lows, closes, period=period)
    # Ultimo valore non-None
    for v in reversed(series):
        if v is not None:
            return float(v)
    return 0.0


def ensure_table(db_path: str | Path) -> None:
    """Idempotente: crea position_trails se manca + WAL mode.

    Re-eseguibile senza side-effect. Chiamato da `_bootstrap_state()` al boot
    del server MCP (Phase 6 D-F4 ordering).
    """
    with sqlite3.connect(str(db_path)) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute(_POSITION_TRAILS_DDL)


def register_trail(
    db_path: str | Path,
    position_id: int,
    symbol: str,
    direction: str,
    timeframe: str,
    atr_mult: float,
    initial_sl: float,
) -> None:
    """Registra intent trail. INSERT OR REPLACE per idempotency su re-register.

    Chiamato da `handle_modify_position` quando l'arg `trail_stop_atr_mult` è settato.
    `initial_sl` parte dal current pos.stop_loss (o entry_price se SL non set).
    """
    with sqlite3.connect(str(db_path)) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute(
            """
            INSERT OR REPLACE INTO position_trails (
                position_id, symbol, direction, timeframe, atr_mult,
                last_sl, activated_at, last_update_at, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 1)
            """,
            (
                int(position_id), symbol, direction, timeframe,
                float(atr_mult), float(initial_sl), _utcnow_iso(),
            ),
        )
    log.info(
        "trail registrato: pos=%d symbol=%s dir=%s atr_mult=%.2f initial_sl=%.5f",
        position_id, symbol, direction, atr_mult, initial_sl,
    )


def _deactivate(db_path: str | Path, position_id: int) -> None:
    """Marca riga inattiva (posizione chiusa lato broker)."""
    with sqlite3.connect(str(db_path)) as c:
        c.execute(
            "UPDATE position_trails SET active=0 WHERE position_id=?",
            (int(position_id),),
        )


def _update_last_sl(db_path: str | Path, position_id: int, new_sl: float) -> None:
    """Update last_sl + last_update_at dopo modify_position success."""
    with sqlite3.connect(str(db_path)) as c:
        c.execute(
            """
            UPDATE position_trails
               SET last_sl=?, last_update_at=?
             WHERE position_id=?
            """,
            (float(new_sl), _utcnow_iso(), int(position_id)),
        )


def _pip_size(symbol: str) -> float:
    """0.0001 per coppie non-JPY, 0.01 per JPY (FX convention)."""
    return 0.01 if "JPY" in symbol.upper() else 0.0001


def _clamp_to_stops_level(
    direction: str,
    candidate_sl: float,
    price_current: float,
    stops_level_price_units: float,
) -> float:
    """Pitfall 2: se candidate viola stops_level broker, ritorna boundary valida.

    BUY: SL deve essere <= price_current - stops_level
    SELL: SL deve essere >= price_current + stops_level
    Altrimenti il broker rigetta l'order e il daemon entra in reject loop.
    """
    if direction == "BUY":
        max_sl = price_current - stops_level_price_units
        if candidate_sl > max_sl:
            return max_sl
    else:
        min_sl = price_current + stops_level_price_units
        if candidate_sl < min_sl:
            return min_sl
    return candidate_sl


def trail_tick(mt5_client, db_path: str | Path, cfg) -> None:
    """Run dallo scheduler ogni ciclo. Idempotente.

    Args:
        mt5_client: Mt5Client (Wave 1 ha aggiunto get_position/modify_position).
        db_path: logs/trades.db (str o Path).
        cfg: Config con `TRAIL_FAVORABLE_ONLY` bool.

    Semantica per ogni riga attiva:
        1. get_position → None → _deactivate + continue.
        2. get_ohlc(symbol, timeframe, 15) → ATR(14); se warmup insufficiente skip.
        3. candidate = current_price ∓ atr * atr_mult (BUY=-, SELL=+).
        4. TRAIL_FAVORABLE_ONLY + candidate non favorable → skip.
        5. Clamp a stops_level boundary (Pitfall 2).
        6. Re-check favorability post-clamp; non favorable → skip.
        7. modify_position(sl=candidate); success → _update_last_sl.
    """
    db_str = str(db_path)
    with sqlite3.connect(db_str) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM position_trails WHERE active=1"
        ).fetchall()

    for row in rows:
        pid = int(row["position_id"])
        pos = mt5_client.get_position(pid)
        if pos is None:
            _deactivate(db_str, pid)
            log.info("trail tick: pos=%d chiusa, deactivate", pid)
            continue

        # ATR warmup
        try:
            bars = mt5_client.get_ohlc(row["symbol"], row["timeframe"], 15)
            if not bars or len(bars) < 14:
                continue
            atr_val = compute_atr(bars, period=14)
            if atr_val <= 0.0:
                continue
        except Exception as exc:
            log.warning("trail tick atr failure: pos=%d err=%s", pid, exc)
            continue

        sym_info = mt5_client.get_symbol_info(row["symbol"])
        if sym_info is None:
            continue

        # Current price: BUY chiude a bid, SELL a ask (convenzione FX)
        current_price = (
            sym_info.bid if row["direction"] == "BUY" else sym_info.ask
        )

        candidate = (
            current_price - atr_val * row["atr_mult"]
            if row["direction"] == "BUY"
            else current_price + atr_val * row["atr_mult"]
        )

        favorable = (
            (row["direction"] == "BUY" and candidate > row["last_sl"])
            or (row["direction"] == "SELL" and candidate < row["last_sl"])
        )
        if cfg.TRAIL_FAVORABLE_ONLY and not favorable:
            continue

        # Pitfall 2: clamp a stops_level boundary
        stops_level_pu = sym_info.trade_stops_level * sym_info.point
        candidate = _clamp_to_stops_level(
            row["direction"], candidate, current_price, stops_level_pu,
        )

        # Re-check favorable post-clamp (clamp può rendere unfavorable)
        favorable_post = (
            (row["direction"] == "BUY" and candidate > row["last_sl"])
            or (row["direction"] == "SELL" and candidate < row["last_sl"])
        )
        if cfg.TRAIL_FAVORABLE_ONLY and not favorable_post:
            continue

        result = mt5_client.modify_position(pid, sl=candidate)
        if result.success:
            _update_last_sl(db_str, pid, candidate)
            log.info(
                "trail tick: pos=%d new_sl=%.5f atr=%.5f mult=%.2f",
                pid, candidate, atr_val, row["atr_mult"],
            )
        else:
            log.warning(
                "trail tick fallito: pos=%d err=%s",
                pid, result.error_message,
            )
