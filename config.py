import os
from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes")


def _get_list(name: str, default: list[str]) -> list[str]:
    val = os.getenv(name)
    if val is None:
        return default
    parts = [p.strip() for p in val.split(",")]
    return [p for p in parts if p]


def _get_int(name: str, default: int) -> int:
    """Parse intero da env var. Accetta suffissi comuni (es. '5d', '15m')
    rimuovendo parte non numerica trailing. Su valore non parsabile, usa default.
    """
    val = os.getenv(name)
    if val is None:
        return default
    s = val.strip()
    digits = ""
    for ch in s:
        if ch.isdigit() or (ch == "-" and not digits):
            digits += ch
        else:
            break
    if not digits or digits == "-":
        return default
    try:
        return int(digits)
    except ValueError:
        return default


def _get_int_list(name: str, default: list[int]) -> list[int]:
    val = os.getenv(name)
    if val is None:
        return default
    out: list[int] = []
    for p in val.split(","):
        p = p.strip()
        if not p:
            continue
        try:
            out.append(int(p))
        except ValueError:
            continue
    return out or default


class Config:
    # MT5
    MT5_LOGIN: int = int(os.getenv("MT5_LOGIN", "0"))
    MT5_PASSWORD: str = os.getenv("MT5_PASSWORD", "")
    MT5_SERVER: str = os.getenv("MT5_SERVER", "FPMarkets-Demo")

    # Risk
    RISK_PER_TRADE_PERCENT: float = float(os.getenv("RISK_PER_TRADE_PERCENT", "0.5"))
    MAX_DAILY_DRAWDOWN_PERCENT: float = float(os.getenv("MAX_DAILY_DRAWDOWN_PERCENT", "2.0"))
    MIN_SL_PIPS: int = int(os.getenv("MIN_SL_PIPS", "8"))
    MAX_SL_PIPS: int = int(os.getenv("MAX_SL_PIPS", "80"))
    RISK_MODE: str = os.getenv("RISK_MODE", "CONSERVATIVE")
    RISK_AMOUNT_MODE: str = os.getenv("RISK_AMOUNT_MODE", "PERCENT")
    RISK_PER_TRADE_AMOUNT: float = float(os.getenv("RISK_PER_TRADE_AMOUNT", "100.0"))
    MAX_LOTS_PER_TRADE: float = float(os.getenv("MAX_LOTS_PER_TRADE", "0"))

    # Symbols / Session
    SYMBOLS: list[str] = _get_list("SYMBOLS", ["EURUSD"])
    SESSION_START: str = os.getenv("SESSION_START", "08:00")
    SESSION_END: str = os.getenv("SESSION_END", "20:00")
    SESSION_START_HOUR: int = int(os.getenv("SESSION_START", "08:00").split(":")[0])
    SESSION_END_HOUR: int = int(os.getenv("SESSION_END", "20:00").split(":")[0])
    USE_SESSION_FILTER: bool = _get_bool("USE_SESSION_FILTER", True)

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/agent.log")

    # Claude API
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    CLAUDE_MAX_TOKENS: int = int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))
    CLAUDE_TEMPERATURE: float = float(os.getenv("CLAUDE_TEMPERATURE", "0.5"))

    # Analisi
    TIMEFRAME: str = os.getenv("TIMEFRAME", "M15")

    # Execution
    EXECUTION_MODE: str = os.getenv("EXECUTION_MODE", "shadow")

    # Scheduler / Daily orchestrator (fase 13)
    OPERATING_TIMEZONE: str = os.getenv("OPERATING_TIMEZONE", "Europe/Rome")
    OPERATING_START_HOUR: int = int(os.getenv("OPERATING_START_HOUR", "8"))
    OPERATING_END_HOUR: int = int(os.getenv("OPERATING_END_HOUR", "22"))
    OPERATING_WEEKDAYS: list[int] = _get_int_list("OPERATING_WEEKDAYS", [0, 1, 2, 3, 4])
    MAIN_CYCLE_HOURS: int = max(1, int(os.getenv("MAIN_CYCLE_HOURS", "3")))
    DAILY_TARGET_DECISIONS: int = max(1, int(os.getenv("DAILY_TARGET_DECISIONS", "5")))
    MAX_DELAY_MINUTES: int = min(120, max(1, int(os.getenv("MAX_DELAY_MINUTES", "120"))))
    MAX_SYMBOLS_TO_DEEPEN: int = max(1, int(os.getenv("MAX_SYMBOLS_TO_DEEPEN", "3")))
    FOLLOWUP_ENABLED: bool = _get_bool("FOLLOWUP_ENABLED", True)
    SCHEDULER_POLL_SECONDS: int = max(1, int(os.getenv("SCHEDULER_POLL_SECONDS", "5")))
    INTRADAY_CYCLE_MINUTES: int = max(1, _get_int("INTRADAY_CYCLE_MINUTES", 5))

    # Scheduler H24 (fase 16)
    INTRADAY_SCAN_INTERVAL_MINUTES: int = max(
        1, _get_int("INTRADAY_SCAN_INTERVAL_MINUTES", 15)
    )
    INTRADAY_FIRST_CYCLE_DELAY_MINUTES: int = max(
        0, _get_int("INTRADAY_FIRST_CYCLE_DELAY_MINUTES", 5)
    )
    PAUSE_TRADING: bool = _get_bool("PAUSE_TRADING", False)
    DRY_RUN: bool = _get_bool("DRY_RUN", False)
    MIN_PROTECT_PROFIT_R_MULTIPLIER: float = float(
        os.getenv("MIN_PROTECT_PROFIT_R_MULTIPLIER", "1.0")
    )
    ROLLING_DRAWDOWN_WINDOW_HOURS: int = max(
        1, int(os.getenv("ROLLING_DRAWDOWN_WINDOW_HOURS", "24"))
    )
    ROLLING_DRAWDOWN_MAX_PERCENT: float = float(
        os.getenv("ROLLING_DRAWDOWN_MAX_PERCENT", "3.0")
    )
    LOG_ROTATION: str = os.getenv("LOG_ROTATION", "weekly").strip().lower()
    WEEKLY_LOG_BACKUP_COUNT: int = max(
        1, int(os.getenv("WEEKLY_LOG_BACKUP_COUNT", "8"))
    )
    CLOSE_BEFORE_END_OF_WINDOW: bool = _get_bool(
        "CLOSE_BEFORE_END_OF_WINDOW", True
    )

    # Strategia Intraday (fase 14)
    STRATEGY_MODE: str = os.getenv("STRATEGY_MODE", "intraday")
    INTRADAY_SYMBOLS: list[str] = _get_list("INTRADAY_SYMBOLS", ["EURUSD", "GBPUSD"])
    INTRADAY_TIMEFRAME: str = os.getenv("INTRADAY_TIMEFRAME", "M15")
    INTRADAY_LOOKBACK_BARS: int = max(50, int(os.getenv("INTRADAY_LOOKBACK_BARS", "200")))
    INTRADAY_SCAN_TOP_N: int = max(1, int(os.getenv("INTRADAY_SCAN_TOP_N", "3")))
    INTRADAY_START_HOUR: int = int(os.getenv("INTRADAY_START_HOUR", "8"))
    INTRADAY_END_HOUR: int = int(os.getenv("INTRADAY_END_HOUR", "20"))
    AVOID_MAJOR_NEWS_TIMES: bool = _get_bool("AVOID_MAJOR_NEWS_TIMES", True)

    # Parametri tecnici intraday
    MIN_ATR_PIPS: float = float(os.getenv("MIN_ATR_PIPS", "3"))
    MAX_ATR_PIPS: float = float(os.getenv("MAX_ATR_PIPS", "50"))
    MIN_TREND_STRENGTH: float = float(os.getenv("MIN_TREND_STRENGTH", "0.65"))
    MIN_BREAKOUT_VOLUME_RATIO: float = float(os.getenv("MIN_BREAKOUT_VOLUME_RATIO", "1.3"))
    MIN_RISK_REWARD_RATIO: float = float(os.getenv("MIN_RISK_REWARD_RATIO", "1.5"))
    MAX_RSI_OVERBOUGHT: int = int(os.getenv("MAX_RSI_OVERBOUGHT", "75"))
    MIN_RSI_OVERSOLD: int = int(os.getenv("MIN_RSI_OVERSOLD", "25"))
    MIN_CONFIDENCE_TO_PROPOSE: float = float(os.getenv("MIN_CONFIDENCE_TO_PROPOSE", "0.60"))

    # Pattern recognition
    ENABLE_CANDLESTICK_PATTERNS: bool = _get_bool("ENABLE_CANDLESTICK_PATTERNS", True)
    PATTERN_CONFIRMATION_BARS: int = max(1, int(os.getenv("PATTERN_CONFIRMATION_BARS", "2")))

    # Support / Resistance
    SR_LOOKBACK_BARS: int = max(20, int(os.getenv("SR_LOOKBACK_BARS", "100")))
    SR_TOLERANCE_PIPS: float = float(os.getenv("SR_TOLERANCE_PIPS", "5"))

    # Strategy v2 fase 17.2 — Compressione di volatilità
    ENABLE_VOLATILITY_SQUEEZE_SETUP: bool = _get_bool("ENABLE_VOLATILITY_SQUEEZE_SETUP", True)
    BB_PERIOD: int = max(2, int(os.getenv("BB_PERIOD", "20")))
    BB_K: float = float(os.getenv("BB_K", "2.0"))
    BB_SQUEEZE_LOOKBACK: int = max(20, int(os.getenv("BB_SQUEEZE_LOOKBACK", "100")))
    BB_SQUEEZE_PERCENTILE: float = float(os.getenv("BB_SQUEEZE_PERCENTILE", "0.2"))
    SQUEEZE_ENTRY_BUFFER_ATR: float = float(os.getenv("SQUEEZE_ENTRY_BUFFER_ATR", "0.1"))
    SQUEEZE_SL_BUFFER_ATR: float = float(os.getenv("SQUEEZE_SL_BUFFER_ATR", "0.2"))

    # Strategy v2 fase 17.3 — Pullback engine
    ENABLE_PULLBACK_SETUP: bool = _get_bool("ENABLE_PULLBACK_SETUP", True)
    BREAKOUT_LOOKBACK_BARS: int = max(5, int(os.getenv("BREAKOUT_LOOKBACK_BARS", "20")))
    PULLBACK_TOLERANCE_ATR_MULTIPLE: float = float(os.getenv("PULLBACK_TOLERANCE_ATR_MULTIPLE", "0.5"))
    PULLBACK_MIN_BARS_AFTER_BREAKOUT: int = max(1, int(os.getenv("PULLBACK_MIN_BARS_AFTER_BREAKOUT", "2")))
    PULLBACK_MAX_BARS_AFTER_BREAKOUT: int = max(2, int(os.getenv("PULLBACK_MAX_BARS_AFTER_BREAKOUT", "8")))
    PULLBACK_REQUIRE_VOLUME_CONTRACTION: bool = _get_bool("PULLBACK_REQUIRE_VOLUME_CONTRACTION", True)
    PULLBACK_ENTRY_BUFFER_ATR: float = float(os.getenv("PULLBACK_ENTRY_BUFFER_ATR", "0.1"))
    PULLBACK_SL_BUFFER_ATR: float = float(os.getenv("PULLBACK_SL_BUFFER_ATR", "0.1"))

    # Strategy v2 fase 17.4 — Multi-timeframe + divergenze attive
    ENABLE_MTF_FILTER: bool = _get_bool("ENABLE_MTF_FILTER", True)
    MTF_TIMEFRAME: str = os.getenv("MTF_TIMEFRAME", "H1")
    MTF_BARS: int = max(50, int(os.getenv("MTF_BARS", "100")))
    ENABLE_DIVERGENCE_VETO: bool = _get_bool("ENABLE_DIVERGENCE_VETO", True)
    DIVERGENCE_LOOKBACK: int = max(5, int(os.getenv("DIVERGENCE_LOOKBACK", "20")))

    # Strategy v2 fase 17.5 — Position management attiva
    ENABLE_ACTIVE_POSITION_MGMT: bool = _get_bool("ENABLE_ACTIVE_POSITION_MGMT", True)
    BREAKEVEN_TRIGGER_R: float = float(os.getenv("BREAKEVEN_TRIGGER_R", "1.0"))
    PARTIAL_CLOSE_TRIGGER_R: float = float(os.getenv("PARTIAL_CLOSE_TRIGGER_R", "2.0"))
    PARTIAL_CLOSE_FRACTION: float = float(os.getenv("PARTIAL_CLOSE_FRACTION", "0.5"))
    TRAIL_ATR_MULTIPLIER: float = float(os.getenv("TRAIL_ATR_MULTIPLIER", "3.0"))

    # Strategy v3 fase 18.1 — Intermarket context engine (Murphy)
    ENABLE_INTERMARKET_FILTER: bool = _get_bool("ENABLE_INTERMARKET_FILTER", True)
    INTERMARKET_TIMEFRAME: str = os.getenv("INTERMARKET_TIMEFRAME", "H4")
    INTERMARKET_LOOKBACK_BARS: int = max(50, int(os.getenv("INTERMARKET_LOOKBACK_BARS", "100")))
    INTERMARKET_SYMBOLS: list[str] = _get_list("INTERMARKET_SYMBOLS", ["XAUUSD", "USOIL"])
    DXY_PROXY_SYMBOL: str = os.getenv("DXY_PROXY_SYMBOL", "EURUSD")

    # Strategy v3 fase 18.2 — Regime detection
    ENABLE_REGIME_DETECTION: bool = _get_bool("ENABLE_REGIME_DETECTION", True)
    REGIME_RISK_OFF_VETO: bool = _get_bool("REGIME_RISK_OFF_VETO", True)
    REGIME_CONFIDENCE_PENALTY: float = float(os.getenv("REGIME_CONFIDENCE_PENALTY", "0.15"))

    # Strategy v3 fase 18.3 — Correlation monitor
    ENABLE_CORRELATION_MONITOR: bool = _get_bool("ENABLE_CORRELATION_MONITOR", True)
    CORRELATION_PERIOD: int = max(5, int(os.getenv("CORRELATION_PERIOD", "20")))
    CORRELATION_DIVERGENCE_THRESHOLD: float = float(os.getenv("CORRELATION_DIVERGENCE_THRESHOLD", "0.5"))

    # Strategy v3 fase 18.4 — Cross-asset confirmation
    ENABLE_CROSS_ASSET_FILTER: bool = _get_bool("ENABLE_CROSS_ASSET_FILTER", True)
    CROSS_ASSET_VETO_ON_CONTRADICTION: bool = _get_bool("CROSS_ASSET_VETO_ON_CONTRADICTION", True)
    CROSS_ASSET_BOOST: float = float(os.getenv("CROSS_ASSET_BOOST", "0.10"))
    CROSS_ASSET_PENALTY: float = float(os.getenv("CROSS_ASSET_PENALTY", "0.20"))

    # Strategy v3 fase 18.5 — Session awareness (Probo)
    ENABLE_SESSION_FILTER: bool = _get_bool("ENABLE_SESSION_FILTER", True)
    SESSION_QUALITY_MIN: float = float(os.getenv("SESSION_QUALITY_MIN", "0.3"))
    SESSION_LONDON_START: int = int(os.getenv("SESSION_LONDON_START", "8"))
    SESSION_LONDON_END: int = int(os.getenv("SESSION_LONDON_END", "16"))
    SESSION_NY_START: int = int(os.getenv("SESSION_NY_START", "14"))
    SESSION_NY_END: int = int(os.getenv("SESSION_NY_END", "22"))

    # Strategy v3 fase 18.6 — Fibonacci targets (Probo)
    ENABLE_FIBONACCI_TARGETS: bool = _get_bool("ENABLE_FIBONACCI_TARGETS", True)
    FIBONACCI_PARTIAL_CLOSE_LEVELS: list[str] = _get_list("FIBONACCI_PARTIAL_CLOSE_LEVELS", ["0.382", "0.618"])
    FIBONACCI_TRAIL_AFTER_LEVEL: float = float(os.getenv("FIBONACCI_TRAIL_AFTER_LEVEL", "0.618"))


_VALID_INTRADAY_TIMEFRAMES = {"M1", "M5", "M10", "M15", "M30"}
if Config.INTRADAY_TIMEFRAME not in _VALID_INTRADAY_TIMEFRAMES:
    raise ValueError(
        f"INTRADAY_TIMEFRAME={Config.INTRADAY_TIMEFRAME} non valido. "
        f"Ammessi: {sorted(_VALID_INTRADAY_TIMEFRAMES)}"
    )

_VALID_LOG_ROTATIONS = {"daily", "weekly", "size"}
if Config.LOG_ROTATION not in _VALID_LOG_ROTATIONS:
    raise ValueError(
        f"LOG_ROTATION={Config.LOG_ROTATION} non valido. "
        f"Ammessi: {sorted(_VALID_LOG_ROTATIONS)}"
    )


def _attach_news_sentiment(cls):
    cls.ENABLE_NEWS_SENTIMENT = _get_bool("ENABLE_NEWS_SENTIMENT", False)
    cls.NEWS_FETCH_INTERVAL_MINUTES = max(1, int(os.getenv("NEWS_FETCH_INTERVAL_MINUTES", "15")))
    cls.NEWS_LOOKBACK_HOURS = max(1, int(os.getenv("NEWS_LOOKBACK_HOURS", "2")))
    cls.NEWS_CACHE_MAX_HOURS = max(1, int(os.getenv("NEWS_CACHE_MAX_HOURS", "24")))
    cls.SENTIMENT_MIN_STRENGTH_FILTER = float(os.getenv("SENTIMENT_MIN_STRENGTH_FILTER", "0.6"))
    cls.SENTIMENT_BOOST_FACTOR = float(os.getenv("SENTIMENT_BOOST_FACTOR", "0.15"))
    action = os.getenv("SENTIMENT_CONFLICT_ACTION", "delay").strip().lower()
    if action not in ("skip", "delay", "reduce_confidence"):
        raise ValueError(
            f"SENTIMENT_CONFLICT_ACTION={action} non valido. "
            f"Ammessi: skip, delay, reduce_confidence"
        )
    cls.SENTIMENT_CONFLICT_ACTION = action
    cls.SENTIMENT_CONFLICT_DELAY_MINUTES = max(
        1, int(os.getenv("SENTIMENT_CONFLICT_DELAY_MINUTES", "60"))
    )
    cls.RSS_FEEDS = _get_list("RSS_FEEDS", [])
    return cls


_attach_news_sentiment(Config)


def _attach_backtest_realism(cls):
    """Parametri costi reali per backtest. Default valori conservativi forex retail."""
    cls.BACKTEST_SPREAD_PIPS = float(os.getenv("BACKTEST_SPREAD_PIPS", "1.0"))
    cls.BACKTEST_COMMISSION_PER_LOT = float(os.getenv("BACKTEST_COMMISSION_PER_LOT", "5.0"))
    cls.BACKTEST_SLIPPAGE_PIPS = float(os.getenv("BACKTEST_SLIPPAGE_PIPS", "0.5"))
    cls.BACKTEST_SWAP_PER_LOT_PER_NIGHT = float(
        os.getenv("BACKTEST_SWAP_PER_LOT_PER_NIGHT", "0.0")
    )
    return cls


_attach_backtest_realism(Config)
