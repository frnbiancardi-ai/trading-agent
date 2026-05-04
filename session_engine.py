"""Session Awareness Engine (fase 18.5 — Probo).

Determina sessione corrente (Asian/London/NY/Overlap) e quality_score per simbolo.
Logica Probo:
- Asian (00:00-08:00 CET): best per JPY crosses, low vol EUR/GBP
- London (08:00-16:00 CET): best per GBP, EUR (picco 08-10)
- New York (14:00-22:00 CET): best per USD pairs
- Overlap London-NY (14:00-16:00 CET): max volatilità, best per tutti
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from config import Config
from models import SessionInfo


# Mapping simboli → sessioni preferite
SYMBOL_SESSION_PREFERENCE: dict[str, dict[str, float]] = {
    # GBP best London
    "GBPUSD": {"LONDON": 1.0, "OVERLAP": 1.0, "NEW_YORK": 0.7, "ASIAN": 0.3, "OFF_HOURS": 0.1},
    "EURGBP": {"LONDON": 1.0, "OVERLAP": 1.0, "NEW_YORK": 0.6, "ASIAN": 0.3, "OFF_HOURS": 0.1},
    # EUR best London + NY
    "EURUSD": {"LONDON": 0.9, "OVERLAP": 1.0, "NEW_YORK": 0.85, "ASIAN": 0.4, "OFF_HOURS": 0.1},
    # USD pairs best NY + Overlap
    "USDCAD": {"OVERLAP": 1.0, "NEW_YORK": 0.95, "LONDON": 0.7, "ASIAN": 0.3, "OFF_HOURS": 0.1},
    "USDCHF": {"OVERLAP": 1.0, "NEW_YORK": 0.85, "LONDON": 0.85, "ASIAN": 0.4, "OFF_HOURS": 0.1},
    # JPY best Asian + NY
    "USDJPY": {"OVERLAP": 1.0, "NEW_YORK": 0.85, "ASIAN": 0.85, "LONDON": 0.6, "OFF_HOURS": 0.2},
    "EURJPY": {"OVERLAP": 1.0, "ASIAN": 0.85, "LONDON": 0.7, "NEW_YORK": 0.7, "OFF_HOURS": 0.2},
    "GBPJPY": {"OVERLAP": 1.0, "LONDON": 0.85, "ASIAN": 0.7, "NEW_YORK": 0.6, "OFF_HOURS": 0.2},
    # Commodity ccy
    "AUDUSD": {"OVERLAP": 1.0, "ASIAN": 0.85, "NEW_YORK": 0.7, "LONDON": 0.5, "OFF_HOURS": 0.2},
    "NZDUSD": {"OVERLAP": 1.0, "ASIAN": 0.85, "NEW_YORK": 0.7, "LONDON": 0.5, "OFF_HOURS": 0.2},
    # Gold/Oil
    "XAUUSD": {"OVERLAP": 1.0, "NEW_YORK": 0.85, "LONDON": 0.85, "ASIAN": 0.5, "OFF_HOURS": 0.3},
    "USOIL": {"OVERLAP": 1.0, "NEW_YORK": 0.95, "LONDON": 0.6, "ASIAN": 0.3, "OFF_HOURS": 0.1},
}

DEFAULT_SESSION_QUALITY = {
    "OVERLAP": 0.85,
    "LONDON": 0.7,
    "NEW_YORK": 0.7,
    "ASIAN": 0.5,
    "OFF_HOURS": 0.3,
}


class SessionEngine:
    """Engine per session awareness (Probo cap timing)."""

    def __init__(self, cfg: Config, logger: logging.Logger | None = None):
        self.cfg = cfg
        self.log = logger or logging.getLogger(__name__)

    def get_current_session(self, now: datetime | None = None) -> str:
        """Restituisce nome sessione corrente: ASIAN/LONDON/NEW_YORK/OVERLAP/OFF_HOURS."""
        if now is None:
            now = datetime.now(ZoneInfo("Europe/Rome"))
        elif now.tzinfo is None:
            # Assume Europe/Rome se naive
            now = now.replace(tzinfo=ZoneInfo("Europe/Rome"))
        else:
            now = now.astimezone(ZoneInfo("Europe/Rome"))

        h = now.hour
        london_start = self.cfg.SESSION_LONDON_START
        london_end = self.cfg.SESSION_LONDON_END
        ny_start = self.cfg.SESSION_NY_START
        ny_end = self.cfg.SESSION_NY_END

        in_london = london_start <= h < london_end
        in_ny = ny_start <= h < ny_end

        if in_london and in_ny:
            return "OVERLAP"
        if in_london:
            return "LONDON"
        if in_ny:
            return "NEW_YORK"
        if 0 <= h < london_start:
            return "ASIAN"
        return "OFF_HOURS"

    def get_session_info(
        self,
        symbol: str,
        now: datetime | None = None,
    ) -> SessionInfo:
        """SessionInfo per simbolo + sessione corrente."""
        session = self.get_current_session(now)
        quality = self._quality_for_symbol(symbol, session)
        vol = self._expected_volatility(session)
        return SessionInfo(
            name=session,  # type: ignore[arg-type]
            quality_for_symbol=quality,
            expected_volatility=vol,  # type: ignore[arg-type]
        )

    def is_optimal_session(
        self,
        symbol: str,
        now: datetime | None = None,
    ) -> tuple[bool, float]:
        """(is_optimal, quality_score). is_optimal True se quality >= SESSION_QUALITY_MIN."""
        info = self.get_session_info(symbol, now)
        return info.quality_for_symbol >= self.cfg.SESSION_QUALITY_MIN, info.quality_for_symbol

    def confidence_boost(self, symbol: str, now: datetime | None = None) -> float:
        """Boost confidence in [0, 0.10] proporzionale a quality."""
        if not self.cfg.ENABLE_SESSION_FILTER:
            return 0.0
        _, q = self.is_optimal_session(symbol, now)
        # Map quality 0.5..1.0 → boost 0..0.10
        if q < 0.5:
            return 0.0
        return (q - 0.5) * 0.2  # max 0.10 a q=1.0

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _quality_for_symbol(self, symbol: str, session: str) -> float:
        sym_up = symbol.upper().replace("/", "")
        prefs = SYMBOL_SESSION_PREFERENCE.get(sym_up)
        if prefs is None:
            return DEFAULT_SESSION_QUALITY.get(session, 0.5)
        return prefs.get(session, 0.5)

    def _expected_volatility(self, session: str) -> str:
        if session == "OVERLAP":
            return "HIGH"
        if session in ("LONDON", "NEW_YORK"):
            return "NORMAL"
        if session == "ASIAN":
            return "LOW"
        return "LOW"
