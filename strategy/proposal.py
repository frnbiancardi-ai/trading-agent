"""ProposalDraft + adapter per il path live/backtest (D-03).

Wave 0: ProposalDraft frozen dataclass (output canonico dei detector).
Wave 1 (Plan 04-03, STRAT-07):
  - draft_to_trade_proposal: ProposalDraft READY → models.TradeProposal (path live)
  - draft_to_technical_setup: ProposalDraft qualunque → models.TechnicalSetup (path scheduler)
  - rr_meets_profile_floor: gate R:R per profile_filters[profile].min_rr
  - compute_levels_with_atr_cap: SL universale livello strutturale ± buffer×ATR, cap 1.5×ATR

Pure module: nessun broker, nessun logging, nessun datetime.now(), nessun I/O
(eccetto il caricamento di config/strategy.yaml via load_strategy_config in
rr_meets_profile_floor — già lru_cache-ato a monte).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # solo type-checking — niente import runtime per evitare cicli
    from models import TechnicalSetup, TradeProposal


@dataclass(frozen=True)
class ProposalDraft:
    setup_type: Literal["READY", "FORMING", "NONE"]
    setup_name: Literal["A_breakout", "B_reversal", "C_compression", "D_pullback"] | None = None
    direction: Literal["BUY", "SELL"] | None = None
    entry_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    factors: dict | None = None
    grade: Literal["A+", "A", "B", "C", "reject"] | None = None
    confidence: float = 0.0
    reason: str = ""
    rationale_parts: dict | None = None
    setup_specific: dict | None = None

    def __post_init__(self):
        # Frozen dataclass: usa object.__setattr__ per inizializzare dict mutabili.
        if self.factors is None:
            object.__setattr__(self, "factors", {})
        if self.rationale_parts is None:
            object.__setattr__(self, "rationale_parts", {})
        if self.setup_specific is None:
            object.__setattr__(self, "setup_specific", {})


# ==========================================================================
# Wave 1 — Adapter ProposalDraft → models.TradeProposal / models.TechnicalSetup
# ==========================================================================


def draft_to_trade_proposal(
    draft: ProposalDraft,
    symbol: str,
    timeframe: str,
) -> "TradeProposal":
    """Converte un ProposalDraft READY in TradeProposal per il path live (D-03).

    Solleva ValueError se draft.setup_type != 'READY' o se direction/entry/sl/tp
    sono None. Il `comment` è fissato a 'python_strategy' per coerenza con la
    legacy IntradayStrategy.build_trade_proposal.
    """
    from models import TradeProposal  # import locale: evita cicli con strategy_legacy

    if draft.setup_type != "READY":
        raise ValueError(
            f"draft_to_trade_proposal richiede setup_type=READY, "
            f"ricevuto {draft.setup_type!r}"
        )
    if (
        draft.direction is None
        or draft.entry_price is None
        or draft.stop_loss_price is None
        or draft.take_profit_price is None
    ):
        raise ValueError(
            "draft READY deve avere direction + entry_price + stop_loss_price + "
            "take_profit_price non-None"
        )

    return TradeProposal(
        symbol=symbol,
        direction=draft.direction,
        entry_price=draft.entry_price,
        stop_loss_price=draft.stop_loss_price,
        take_profit_price=draft.take_profit_price,
        timeframe=timeframe,
        comment="python_strategy",
        confidence=draft.confidence,
        rationale=draft.reason,
    )


def draft_to_technical_setup(
    draft: ProposalDraft,
    symbol: str,
    timeframe: str,
) -> "TechnicalSetup":
    """Converte qualsiasi ProposalDraft (READY/FORMING/NONE) in TechnicalSetup
    per il path scheduler.

    Mappa i field names del draft sui field di TechnicalSetup:
      - draft.stop_loss_price   → TechnicalSetup.stop_loss
      - draft.take_profit_price → TechnicalSetup.take_profit
    Il dict `indicators` riceve i meta del draft (factors, grade, setup_name,
    rationale_parts) per ispezione downstream / logging.
    """
    from models import TechnicalSetup  # import locale: evita cicli

    return TechnicalSetup(
        symbol=symbol,
        timeframe=timeframe,
        setup_type=draft.setup_type,
        direction=draft.direction,
        entry_price=draft.entry_price,
        stop_loss=draft.stop_loss_price,
        take_profit=draft.take_profit_price,
        confidence=draft.confidence,
        reason=draft.reason,
        indicators={
            "factors": dict(draft.factors or {}),
            "grade": draft.grade,
            "setup_name": draft.setup_name,
            "rationale_parts": dict(draft.rationale_parts or {}),
        },
        support_resistance=None,
    )


# ==========================================================================
# Wave 1 — R:R floor per profile + ATR cap helper (D-10, STRAT-07)
# ==========================================================================


def rr_meets_profile_floor(
    entry: float,
    sl: float,
    tp: float,
    direction: str,
    profile: str,
    cfg=None,
) -> tuple[bool, float]:
    """Verifica R:R >= profile_filters[profile].min_rr (D-10, STRAT-07).

    Ritorna (passes, rr_value) dove rr_value è arrotondato a 4 cifre.
    Se risk o reward sono <= 0 (prezzi incoerenti rispetto a direction)
    ritorna (False, 0.0) senza sollevare.

    Solleva ValueError per direction non BUY/SELL o profile non in profile_filters.
    """
    from strategy.confluence import load_strategy_config

    cfg = cfg or load_strategy_config()
    if profile not in cfg.profile_filters:
        raise ValueError(
            f"profile {profile!r} non in profile_filters: "
            f"{list(cfg.profile_filters)}"
        )
    min_rr = float(cfg.profile_filters[profile]["min_rr"])

    if direction == "BUY":
        risk = entry - sl
        reward = tp - entry
    elif direction == "SELL":
        risk = sl - entry
        reward = entry - tp
    else:
        raise ValueError(
            f"direction deve essere BUY/SELL, ricevuto {direction!r}"
        )

    if risk <= 0 or reward <= 0:
        return False, 0.0

    rr = reward / risk
    # Epsilon FP: 0.001 * 1.3 produce 0.0012999...e/0.001 = 1.2999... per
    # arithmetic-noise float; il confronto >= min_rr fallirebbe falsamente
    # esattamente al boundary. 1e-9 è enormemente piu' grande del rumore FP
    # tipico (~1e-16) e enormemente piu' piccolo della granularita' R:R (0.1).
    return (rr >= min_rr - 1e-9), round(rr, 4)


def grade_meets_profile_floor(grade: str, profile: str, cfg=None) -> bool:
    """True se grade >= profile_filters[profile].min_grade (CRIT-3, 2026-05-29).

    Backward-compat: se min_grade non è definito per il profilo → True (nessun
    filtro). Solleva ValueError per profilo non in profile_filters.
    """
    from strategy.confluence import grade_meets_min, load_strategy_config

    cfg = cfg or load_strategy_config()
    if profile not in cfg.profile_filters:
        raise ValueError(
            f"profile {profile!r} non in profile_filters: {list(cfg.profile_filters)}"
        )
    min_grade = cfg.profile_filters[profile].get("min_grade")
    if min_grade is None:
        return True
    return grade_meets_min(grade, min_grade)


def confidence_meets_profile_floor(confidence: float, profile: str, cfg=None) -> bool:
    """True se confidence >= profile_filters[profile].min_confidence (CRIT-3).

    Backward-compat: se min_confidence non è definito → True. Solleva ValueError
    per profilo non in profile_filters.
    """
    from strategy.confluence import load_strategy_config

    cfg = cfg or load_strategy_config()
    if profile not in cfg.profile_filters:
        raise ValueError(
            f"profile {profile!r} non in profile_filters: {list(cfg.profile_filters)}"
        )
    min_conf = cfg.profile_filters[profile].get("min_confidence")
    if min_conf is None:
        return True
    return confidence >= float(min_conf)


def compute_levels_with_atr_cap(
    direction: str,
    entry: float,
    structural_level: float,
    atr: float,
    buffer_atr_mult: float,
    cap_atr_mult: float = 1.5,
) -> tuple[float, float]:
    """SL universale per tutti i 4 setup (D-10): livello strutturale ± buffer×ATR,
    capato a cap×ATR dall'entry.

    BUY:  sl = max(level - buffer×ATR, entry - cap×ATR)   # cap → SL non troppo lontano
    SELL: sl = min(level + buffer×ATR, entry + cap×ATR)

    Ritorna (entry, sl). TP è specifico per setup → il detector lo calcola.
    Solleva ValueError per atr <= 0 o direction non BUY/SELL.
    """
    if atr is None or atr <= 0:
        raise ValueError(f"atr deve essere > 0, ricevuto {atr!r}")

    buf = buffer_atr_mult * atr
    cap = cap_atr_mult * atr

    if direction == "BUY":
        sl = structural_level - buf
        sl = max(sl, entry - cap)  # cap ATR enforced
    elif direction == "SELL":
        sl = structural_level + buf
        sl = min(sl, entry + cap)
    else:
        raise ValueError(
            f"direction deve essere BUY/SELL, ricevuto {direction!r}"
        )

    return entry, sl
