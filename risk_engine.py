import logging
from datetime import datetime
from math import floor
from zoneinfo import ZoneInfo

from config import Config
from models import AccountState, RiskDecision, TradeProposal
from mt5_client import Mt5Client

logger = logging.getLogger(__name__)

_TZ_ROME = ZoneInfo("Europe/Rome")
_RETRY_N = 3

PROFILES = {
    "CONSERVATIVE": {"max_lots": 0.3, "max_drawdown_pct": 1.5},
    "MODERATE":     {"max_lots": 0.5, "max_drawdown_pct": 2.5},
    "AGGRESSIVE":   {"max_lots": 1.0, "max_drawdown_pct": 4.0},
}


def _call_retry(fn, *args, **kwargs):
    last_exc = None
    for _ in range(_RETRY_N):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
    raise last_exc


def evaluate_trade(
    proposal: TradeProposal,
    account: AccountState,
    mt5_client: Mt5Client,
    cfg: Config | None = None,
) -> RiskDecision:
    if cfg is None:
        cfg = Config()

    profile = PROFILES.get(cfg.RISK_MODE.upper(), PROFILES["CONSERVATIVE"])
    effective_max_lots = cfg.MAX_LOTS_PER_TRADE if cfg.MAX_LOTS_PER_TRADE > 0 else profile["max_lots"]

    def reject(reason: str) -> RiskDecision:
        logger.info("Trade rifiutato: %s", reason)
        return RiskDecision(
            approved=False,
            size_lots=0.0,
            reason=reason,
            adjusted_stop_loss=proposal.stop_loss_price,
            adjusted_take_profit=proposal.take_profit_price,
        )

    # 1. Kill switch giornaliero
    drawdown_limit = account.starting_balance_of_day * (1 - cfg.MAX_DAILY_DRAWDOWN_PERCENT / 100)
    if account.balance <= drawdown_limit:
        actual_pct = (
            (account.starting_balance_of_day - account.balance) / account.starting_balance_of_day * 100
            if account.starting_balance_of_day > 0 else 0.0
        )
        return reject(
            f"Kill switch giornaliero attivo: drawdown {actual_pct:.1f}% > {cfg.MAX_DAILY_DRAWDOWN_PERCENT:.1f}%"
        )

    # 2. Filtro sessione
    if cfg.USE_SESSION_FILTER:
        now = datetime.now(tz=_TZ_ROME)
        if not (cfg.SESSION_START_HOUR <= now.hour < cfg.SESSION_END_HOUR):
            return reject(
                f"Fuori sessione: ora {now.hour:02d}:{now.minute:02d} "
                f"non è tra {cfg.SESSION_START_HOUR:02d}:00 e {cfg.SESSION_END_HOUR:02d}:00"
            )

    # 3. Limiti SL in pips
    symbol = proposal.symbol
    try:
        sym_info = _call_retry(mt5_client.get_symbol_info, symbol)
    except Exception as exc:
        return reject(f"Impossibile leggere symbol_info per {symbol}: {exc}")

    if sym_info is None:
        return reject(f"Symbol {symbol} non disponibile")

    point = sym_info.point
    digits = sym_info.digits
    pip_size = point * 10 if digits in (3, 5) else point

    distance_raw = abs(proposal.entry_price - proposal.stop_loss_price)
    distance_pips = distance_raw / pip_size if pip_size > 0 else 0.0

    if distance_pips < cfg.MIN_SL_PIPS:
        return reject(f"SL troppo stretto: {distance_pips:.1f} pip < minimo {cfg.MIN_SL_PIPS}")
    if distance_pips > cfg.MAX_SL_PIPS:
        return reject(f"SL troppo largo: {distance_pips:.1f} pip > massimo {cfg.MAX_SL_PIPS}")

    # 4. Risk amount
    if cfg.RISK_AMOUNT_MODE == "FIXED_AMOUNT":
        risk_amount = cfg.RISK_PER_TRADE_AMOUNT
    else:
        risk_amount = account.balance * cfg.RISK_PER_TRADE_PERCENT / 100

    # 6. Calcolo size
    tick_value = sym_info.trade_tick_value
    tick_size = sym_info.trade_tick_size
    if tick_size <= 0 or tick_value <= 0:
        return reject("Dati tick_value/tick_size non validi per il calcolo della size")

    pip_value = tick_value * pip_size / tick_size
    if pip_value <= 0 or distance_pips <= 0:
        return reject("pip_value o distance_pips non calcolabili")

    size = risk_amount / (pip_value * distance_pips)
    size = min(size, effective_max_lots)

    volume_step = sym_info.volume_step if sym_info.volume_step > 0 else 0.01
    size = floor(size / volume_step) * volume_step
    size = round(size, 8)

    if size < 0.01:
        return reject(f"Size calcolata {size:.4f} lotti < minimo 0.01 dopo normalizzazione")

    # 7. Margin check
    try:
        margin = _call_retry(
            mt5_client.calc_order_margin,
            symbol, proposal.direction, size, proposal.entry_price,
        )
    except Exception as exc:
        return reject(f"Impossibile calcolare il margine: {exc}")

    while margin > account.free_margin * 0.9 and size >= 0.01:
        size *= 0.8
        size = floor(size / volume_step) * volume_step
        size = round(size, 8)
        if size < 0.01:
            break
        try:
            margin = _call_retry(
                mt5_client.calc_order_margin,
                symbol, proposal.direction, size, proposal.entry_price,
            )
        except Exception:
            break

    if size < 0.01:
        return reject("Margine insufficiente: size ridotta sotto 0.01 lotti")

    # 8. Approved
    return RiskDecision(
        approved=True,
        size_lots=size,
        reason="OK",
        adjusted_stop_loss=proposal.stop_loss_price,
        adjusted_take_profit=proposal.take_profit_price,
    )
