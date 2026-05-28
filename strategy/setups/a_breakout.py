"""Detector Setup A — Breakout: rottura pulita di S/R orizzontale (STRAT-01, Wave 2 plan-05).

Identificazione: l'ultimo close supera la resistance (BUY) o il support (SELL) di un livello
S/R orizzontale calcolato dal Phase 2 ExtendedIndicators / Phase 4 StrategyContext.sr.
Trigger READY/FORMING/NONE in funzione di:
  - distanza prezzo vs livello (entro SR_TOLERANCE_PIPS → FORMING; oltre → READY)
  - 5-factor confluence (≥2 fattori veri → grade A+/A/B/C; ≤1 → reject)
  - R:R sopra il floor di profile (CONSERVATIVE 2.5 / MODERATE 1.8 / AGGRESSIVE 1.3)

Campi ExtendedIndicators consumati (lettura difensiva via getattr):
  - atr_14[-1] (mandatory): bandwidth volatilità per buffer/cap SL e TP target
  - rsi_14[-1] / closing_score[-1] / ema50_slope[-1] / volatility_regime[-1]: 5-factor
  - donchian_high/low (info, no gating qui)
  - nr_detect / bollinger_bands / fibonacci: NON usati da Setup A — riservati ad altri setup

Pure module: nessun broker, nessun logging, nessun datetime.now(), nessun I/O.
"""
from __future__ import annotations

from strategy.context import StrategyContext
from strategy.confluence import compute_confidence, grade_for, score_factors
from strategy.proposal import (
    ProposalDraft,
    compute_levels_with_atr_cap,
    rr_meets_profile_floor,
)


# Modulo costanti (CLAUDE.md: zero magic numbers nel detector body)
SR_TOLERANCE_PIPS = 5  # distanza max prezzo↔livello per FORMING (mirror legacy SR_TOLERANCE_PIPS)
MIN_BARS = 50         # minimo storico per warmup ATR/EMA50 stabili


def _last(seq):
    """Ritorna l'ultimo elemento di una sequenza non vuota, altrimenti None."""
    if seq is None:
        return None
    try:
        return seq[-1]
    except (TypeError, IndexError, KeyError):
        return None


def _get_close(bar):
    """Estrae 'close' da bar (dict o oggetto). Ritorna None se mancante."""
    if isinstance(bar, dict):
        return bar.get("close")
    return getattr(bar, "close", None)


def _compute_levels_a(
    direction: str,
    entry: float,
    broken_level: float,
    atr: float,
) -> tuple[float, float, float]:
    """SL/TP universale Setup A (D-10): SL = livello rotto ± 0.4×ATR, capato a 1.5×ATR;
    TP = entry + 2.5×ATR (BUY) / entry − 2.5×ATR (SELL).

    Il buffer 0.4×ATR posiziona lo stop oltre il livello rotto (anti-fakeout immediato).
    Il TP a 2.5×ATR è il target momentum tipico del breakout (R:R ≈ 6.25 con SL=0.4×ATR).
    """
    entry_out, sl = compute_levels_with_atr_cap(
        direction, entry, broken_level, atr, buffer_atr_mult=0.4, cap_atr_mult=1.5
    )
    if direction == "BUY":
        tp = entry_out + 2.5 * atr
    else:  # SELL
        tp = entry_out - 2.5 * atr
    return entry_out, sl, tp


def detect_a_breakout(
    bars: list,
    indicators,
    ctx: StrategyContext,
) -> ProposalDraft:
    """Detector pure-fn Setup A — Breakout (STRAT-01).

    Ritorna ProposalDraft con setup_type ∈ {READY, FORMING, NONE}. Mai None.

    Flow:
      1. Guard insufficient_bars / atr_not_ready / last_close_missing.
      2. FORMING se prezzo entro SR_TOLERANCE_PIPS dal livello (BUY sotto resistance,
         SELL sopra support).
      3. READY se prezzo oltre il livello in entrambe le direzioni.
      4. score_factors → grade; reject → NONE confluence_below_2_factors.
      5. _compute_levels_a → R:R floor; sotto soglia → NONE rr_below_profile_min_<rr>.
      6. compute_confidence → ProposalDraft READY completo.
    """
    # --- Guard 1: storia minima ---
    if not bars or len(bars) < MIN_BARS:
        return ProposalDraft(setup_type="NONE", reason="insufficient_bars")

    # --- Guard 2: ATR mandatory per SL/TP universali ---
    atr_val = _last(getattr(indicators, "atr_14", None))
    if atr_val is None or atr_val <= 0:
        return ProposalDraft(setup_type="NONE", reason="atr_not_ready")

    # --- Guard 3: ultimo close ---
    last_close = _get_close(bars[-1])
    if last_close is None:
        return ProposalDraft(setup_type="NONE", reason="last_close_missing")

    # --- S/R + tolleranza in pip ---
    sr = ctx.sr or {}
    resistance = sr.get("resistance")
    support = sr.get("support")
    pip_size = ctx.pip_size or 0.0001
    tol = pip_size * SR_TOLERANCE_PIPS

    # --- FORMING: prezzo dentro tolleranza, non ancora oltre il livello ---
    if resistance is not None and 0 < (resistance - last_close) <= tol:
        return ProposalDraft(
            setup_type="FORMING",
            setup_name="A_breakout",
            direction="BUY",
            confidence=0.0,
            reason="prezzo_vicino_a_resistance_attendo_breakout",
            setup_specific={
                "resistance": resistance,
                "distance_pips": (resistance - last_close) / pip_size,
            },
        )
    if support is not None and 0 < (last_close - support) <= tol:
        return ProposalDraft(
            setup_type="FORMING",
            setup_name="A_breakout",
            direction="SELL",
            confidence=0.0,
            reason="prezzo_vicino_a_support_attendo_breakdown",
            setup_specific={
                "support": support,
                "distance_pips": (last_close - support) / pip_size,
            },
        )

    # --- Identificazione direzione READY: prezzo oltre il livello ---
    if resistance is not None and last_close > resistance:
        direction = "BUY"
        broken_level = resistance
    elif support is not None and last_close < support:
        direction = "SELL"
        broken_level = support
    else:
        return ProposalDraft(setup_type="NONE", reason="no_breakout_detected")

    # --- 5-factor confluence ---
    factors = score_factors("A_breakout", indicators, ctx, direction)
    grade = grade_for(factors)
    if grade == "reject":
        return ProposalDraft(
            setup_type="NONE",
            setup_name="A_breakout",
            direction=direction,
            factors=factors,
            grade=grade,
            reason="confluence_below_2_factors",
            setup_specific={"breakout_level": broken_level},
        )

    # --- SL/TP via helper universale ---
    entry, sl, tp = _compute_levels_a(direction, last_close, broken_level, atr_val)

    # --- Gate R:R per profile ---
    passes_rr, rr_value = rr_meets_profile_floor(entry, sl, tp, direction, ctx.profile)
    if not passes_rr:
        return ProposalDraft(
            setup_type="NONE",
            setup_name="A_breakout",
            direction=direction,
            entry_price=entry,
            stop_loss_price=sl,
            take_profit_price=tp,
            factors=factors,
            grade=grade,
            reason=f"rr_below_profile_min_{rr_value:.2f}",
            setup_specific={"breakout_level": broken_level, "rr": rr_value},
        )

    # --- Confidence calibrata ---
    confidence = compute_confidence(
        grade, ctx, "A_breakout", factors=factors, indicators=indicators
    )

    return ProposalDraft(
        setup_type="READY",
        setup_name="A_breakout",
        direction=direction,
        entry_price=entry,
        stop_loss_price=sl,
        take_profit_price=tp,
        factors=factors,
        grade=grade,
        confidence=confidence,
        reason=f"breakout_{direction.lower()}_level={broken_level:.5f}",
        rationale_parts={
            "broken_level": f"{broken_level:.5f}",
            "atr_at_break": f"{atr_val:.5f}",
            "rr": f"{rr_value:.2f}",
            "grade": grade,
        },
        setup_specific={
            "breakout_level": broken_level,
            "atr_at_break": atr_val,
            "rr": rr_value,
        },
    )
