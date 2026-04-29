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
