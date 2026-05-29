import os
from pathlib import Path

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
    # Default 20.0: il kill-switch giornaliero deve permettere ~5-10 trade perdenti
    # prima di fermare la giornata. Su account ~€100 con RISK_PER_TRADE_PERCENT=2%
    # (=€2/trade), 20% = €20 = 10 perdite — soglia operativa dichiarata dall'utente.
    # Valore condiviso live + backtest + training ML (un solo regime di drawdown
    # per evitare distribution shift fra train e inference).
    MAX_DAILY_DRAWDOWN_PERCENT: float = float(os.getenv("MAX_DAILY_DRAWDOWN_PERCENT", "20.0"))
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

    # Phase 6 MCP (D-C1, D-D1, D-A4)
    MCP_DEFAULT_BARS: int = int(os.getenv("MCP_DEFAULT_BARS", "200"))
    # D-A4 cap=1: massimo backtest concorrenti gestiti dal JobQueue (Wave 2).
    MCP_MAX_CONCURRENT_RUNS: int = int(os.getenv("MCP_MAX_CONCURRENT_RUNS", "1"))
    # D-B2 trail daemon (Wave 3): timeframe usato dal daemon per ATR del trail
    # + flag che vieta tightening dello SL non-favorable (BUY: candidate<=last_sl).
    TRAIL_TICK_TIMEFRAME: str = os.getenv("TRAIL_TICK_TIMEFRAME", "M15")
    TRAIL_FAVORABLE_ONLY: bool = _get_bool("TRAIL_FAVORABLE_ONLY", True)

    # Phase 8 MCP ML (D-08-A1/B1/D3)
    # ML_MODEL_PATH: bundle joblib Phase 7 Plan 07-05 D-15 path convention.
    # Symlink models/classifier_v1_latest.pkl -> classifier_v1_{date}.pkl per
    # swap rolling senza restart MCP server (caricamento singleton a bootstrap).
    ML_MODEL_PATH: Path = Path(os.getenv("ML_MODEL_PATH", "models/classifier_v1_latest.pkl"))
    # MCP_TRAINING_DATA_PATH: parquet baseline (D-08-B1 hardcoded data source enum-only).
    MCP_TRAINING_DATA_PATH: Path = Path(os.getenv(
        "MCP_TRAINING_DATA_PATH", "data/training/baseline_decisions/part-0.parquet",
    ))
    # MCP_ML_THRESHOLD_MARGIN_PCT: margine entro cui un trade rejected dal ML
    # gate e' considerato "marginale" nella Degraded Slices Analysis (D-08-D4).
    MCP_ML_THRESHOLD_MARGIN_PCT: float = float(os.getenv(
        "MCP_ML_THRESHOLD_MARGIN_PCT", "0.05",
    ))

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
    # CRIT-2 (audit 2026-05-28): spread baseline per il fattore spread_session della
    # confluence. In backtest il BacktestBroker non espone bid/ask, quindi
    # _check_spread_session (confluence.py) usa il fallback ctx.spread_baseline_pips.
    # Prima questo attributo non esisteva → spread_baseline_pips=None → fattore
    # spread_session SEMPRE False in backtest. 1.0 pip è un baseline conservativo
    # multi-pair (costs.yaml: EURUSD 0.5 / GBPUSD 0.7 / USDJPY 0.6).
    SPREAD_BASELINE_PIPS: float = float(os.getenv("SPREAD_BASELINE_PIPS", "1.0"))

    # Enable/disable per-setup (2026-05-29). B_reversal disabilitato di default:
    # expectancy costantemente negativa (-52..-55 USD/trade su EURUSD H1 2020, 3 profili)
    # con la confluence riparata (regime+spread wired). Riattivabile via env.
    ENABLE_SETUP_A: bool = _get_bool("ENABLE_SETUP_A", True)
    ENABLE_SETUP_B: bool = _get_bool("ENABLE_SETUP_B", False)
    ENABLE_SETUP_C: bool = _get_bool("ENABLE_SETUP_C", True)
    ENABLE_SETUP_D: bool = _get_bool("ENABLE_SETUP_D", True)

    # Pattern recognition
    ENABLE_CANDLESTICK_PATTERNS: bool = _get_bool("ENABLE_CANDLESTICK_PATTERNS", True)
    PATTERN_CONFIRMATION_BARS: int = max(1, int(os.getenv("PATTERN_CONFIRMATION_BARS", "2")))

    # Support / Resistance
    SR_LOOKBACK_BARS: int = max(20, int(os.getenv("SR_LOOKBACK_BARS", "100")))
    SR_TOLERANCE_PIPS: float = float(os.getenv("SR_TOLERANCE_PIPS", "5"))

    # Setup mode (fase 16+)
    # true  = READY richiede breakout=="CLEAN" (rottura attiva max swing + volume)
    # false = READY ammesso anche su trend-continuation/pullback senza rottura
    REQUIRE_BREAKOUT_FOR_READY: bool = _get_bool("REQUIRE_BREAKOUT_FOR_READY", True)


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
