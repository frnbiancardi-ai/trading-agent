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
