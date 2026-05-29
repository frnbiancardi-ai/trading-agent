"""Detector Setup B — S/R Reversal: reversal a livello con PatternHit confermante (STRAT-02, Wave 2 plan-06).

Identificazione: il prezzo si trova A LIVELLO (resistance per SELL, support per BUY) entro
SR_TOLERANCE_PIPS, ed esiste un PatternHit recente (-3..-1) con direction concorde
(bearish per SELL, bullish per BUY). 5-factor confluence + R:R floor.
NOTA (2026-05-19): il counter-trend gate D-07 è stato RIMOSSO — Setup B è un reversal,
quindi counter-trend per design; il gate bloccava il 100% dei candidati. Qualità ora
protetta solo da reject (≤1 fattore) + R:R floor downstream.

Trigger READY/FORMING/NONE:
  - READY: prezzo at-level + PatternHit recente + grade ≥ B
  - FORMING: prezzo at-level ma nessun PatternHit recente
  - NONE: lontano da S/R, oppure reject (≤1 fattore), oppure R:R sotto floor.

Campi ExtendedIndicators consumati (lettura difensiva via getattr):
  - atr_14[-1] (mandatory): bandwidth volatilità per buffer/cap SL
  - ema50_slope[-1] (mandatory per gate D-07): direzione trend di medio termine
  - rsi_14[-1] / volatility_regime[-1] / closing_score[-1]: 5-factor

Campi StrategyContext consumati:
  - ctx.sr.{resistance, support}: livelli orizzontali Phase 2
  - ctx.patterns: list[PatternHit] da Phase 3 — accesso ATTRIBUTE-only
    (p.name, p.direction, p.bar_index, p.extreme_price). MAI dict-key access (RESEARCH Pitfall #3).
  - ctx.pip_size: granularità prezzo per tolleranza S/R

Pure module: nessun broker, nessun logging, nessun datetime.now(), nessun I/O.
"""
from __future__ import annotations

from strategy.context import StrategyContext
from strategy.confluence import compute_confidence, grade_for, score_factors
from strategy.proposal import (
    ProposalDraft,
    compute_levels_with_atr_cap,
    confidence_meets_profile_floor,
    grade_meets_profile_floor,
    rr_meets_profile_floor,
)


# Modulo costanti (CLAUDE.md: zero magic numbers nel detector body)
MIN_BARS = 50              # warmup minimo storico
SR_TOLERANCE_PIPS = 8      # tolleranza at-level (più larga di Setup A: B vuole prezzo AL livello)
RECENT_PATTERN_BARS = 3    # PatternHit deve essere negli ultimi 3 bars (-3..-1)


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


def _get_low(bar):
    if isinstance(bar, dict):
        return bar.get("low")
    return getattr(bar, "low", None)


def _get_high(bar):
    if isinstance(bar, dict):
        return bar.get("high")
    return getattr(bar, "high", None)


def _compute_levels_b(
    direction: str,
    entry: float,
    reversal_extreme: float,
    atr: float,
    opposite_range_end: float | None,
) -> tuple[float, float, float]:
    """SL/TP universale Setup B (D-10): SL = reversal_extreme ± 0.3×ATR, capato a 1.5×ATR.
    TP = opposite_range_end se sul lato corretto rispetto a entry; altrimenti
    entry ± 1.5×ATR fallback (BUY → +, SELL → −).

    Buffer 0.3×ATR (più stretto di Setup A 0.4×) perché reversal_extreme è già un'estrema
    locale del bar di reversal (low del hammer, high dello shooting star); buffer minimo
    per anti-noise sufficiente. Cap 1.5×ATR identico ai 4 setup (D-10).
    """
    entry_out, sl = compute_levels_with_atr_cap(
        direction, entry, reversal_extreme, atr,
        buffer_atr_mult=0.3, cap_atr_mult=1.5,
    )
    # TP: opposite_range_end (livello strutturale opposto) prevale se sul lato corretto
    if opposite_range_end is not None:
        if direction == "BUY" and opposite_range_end > entry_out:
            return entry_out, sl, opposite_range_end
        if direction == "SELL" and opposite_range_end < entry_out:
            return entry_out, sl, opposite_range_end

    # Fallback: 1.5×ATR projection
    if direction == "BUY":
        tp = entry_out + 1.5 * atr
    else:  # SELL
        tp = entry_out - 1.5 * atr
    return entry_out, sl, tp


def detect_b_reversal(
    bars: list,
    indicators,
    ctx: StrategyContext,
) -> ProposalDraft:
    """Detector pure-fn Setup B — S/R Reversal (STRAT-02).

    Ritorna ProposalDraft con setup_type ∈ {READY, FORMING, NONE}. Mai None.

    Flow:
      1. Guard insufficient_bars / atr_not_ready / last_close_missing.
      2. Identifica direzione candidata da prossimità S/R:
         - Vicino a resistance (entro SR_TOLERANCE_PIPS) → SELL candidate.
         - Vicino a support → BUY candidate.
         - Altrimenti → NONE/not_at_sr_zone.
      3. Cerca PatternHit con direction matching negli ultimi 3 bars (attribute access).
         Se assente → FORMING/at_sr_zone_waiting_pattern.
      4. score_factors → grade.
      5. grade=reject → NONE/confluence_below_2_factors.
      6. _compute_levels_b → R:R floor → ProposalDraft READY.
      (Counter-trend gate D-07 RIMOSSO 2026-05-19 — vedi docstring modulo.)
    """
    # --- Guard 1: storia minima ---
    if not bars or len(bars) < MIN_BARS:
        return ProposalDraft(setup_type="NONE", reason="insufficient_bars")

    # --- Guard 2: ATR mandatory ---
    atr_val = _last(getattr(indicators, "atr_14", None))
    if atr_val is None or atr_val <= 0:
        return ProposalDraft(setup_type="NONE", reason="atr_not_ready")

    # --- Guard 3: ultimo close ---
    last_close = _get_close(bars[-1])
    if last_close is None:
        return ProposalDraft(setup_type="NONE", reason="last_close_missing")

    # --- S/R + tolleranza in pip (più larga di Setup A) ---
    sr = ctx.sr or {}
    resistance = sr.get("resistance")
    support = sr.get("support")
    pip_size = ctx.pip_size or 0.0001
    tol = pip_size * SR_TOLERANCE_PIPS

    # --- Identifica direzione candidata da prossimità S/R ---
    candidate_direction: str | None = None
    level: float | None = None
    opposite: float | None = None
    if resistance is not None and abs(resistance - last_close) <= tol:
        candidate_direction = "SELL"
        level = resistance
        opposite = support
    elif support is not None and abs(last_close - support) <= tol:
        candidate_direction = "BUY"
        level = support
        opposite = resistance

    if candidate_direction is None:
        return ProposalDraft(setup_type="NONE", reason="not_at_sr_zone")

    # --- PatternHit search via ATTRIBUTE access (RESEARCH Pitfall #3) ---
    want_dir = "bullish" if candidate_direction == "BUY" else "bearish"
    pattern = next(
        (
            p for p in (ctx.patterns or [])
            if getattr(p, "direction", None) == want_dir
            and abs(getattr(p, "bar_index", -99)) <= RECENT_PATTERN_BARS
        ),
        None,
    )

    if pattern is None:
        return ProposalDraft(
            setup_type="FORMING",
            setup_name="B_reversal",
            direction=candidate_direction,
            confidence=0.0,
            reason="at_sr_zone_waiting_pattern",
            setup_specific={
                "level": level,
                "candidate_direction": candidate_direction,
            },
        )

    direction = candidate_direction  # pattern conferma direzione
    pattern_name = getattr(pattern, "name", "unknown")

    # --- 5-factor confluence ---
    factors = score_factors("B_reversal", indicators, ctx, direction)
    grade = grade_for(factors)

    # --- Trend context (D-07 gate RIMOSSO — Setup B è reversal per design) ---
    # NOTA: il counter-trend gate è stato rimosso il 2026-05-19. Diagnosi:
    # bloccava il 100% dei candidati reversal perché grade strutturalmente ≤ C
    # (trend_alignment sempre False per un reversal). Il counter-trend è feature
    # del setup, non un rischio da gateare qui. Protezione qualità delegata a:
    # reject (≤1 fattore True) + R:R floor downstream.
    slope = _last(getattr(indicators, "ema50_slope", None)) or 0.0
    trend_dir: str | None = None
    if slope > 0:
        trend_dir = "BUY"
    elif slope < 0:
        trend_dir = "SELL"
    is_counter_trend = trend_dir is not None and direction != trend_dir
    # is_counter_trend resta tracciato in setup_specific per analisi ex-post.

    # --- Reject (≤1 fattore True) ---
    if grade == "reject":
        return ProposalDraft(
            setup_type="NONE",
            setup_name="B_reversal",
            direction=direction,
            factors=factors,
            grade=grade,
            reason="confluence_below_2_factors",
            setup_specific={"level": level, "pattern_name": pattern_name},
        )

    # --- Reversal extreme (low del hammer / high dello shooting star) ---
    reversal_extreme = getattr(pattern, "extreme_price", None)
    if reversal_extreme is None:
        # Fallback: low del bar corrente per BUY, high per SELL
        if direction == "BUY":
            reversal_extreme = _get_low(bars[-1])
        else:
            reversal_extreme = _get_high(bars[-1])
        if reversal_extreme is None:
            reversal_extreme = last_close  # extreme fallback

    # --- SL/TP via helper Setup B specifico ---
    entry, sl, tp = _compute_levels_b(
        direction, last_close, reversal_extreme, atr_val, opposite
    )

    # --- Gate R:R per profile ---
    passes_rr, rr_value = rr_meets_profile_floor(entry, sl, tp, direction, ctx.profile)
    if not passes_rr:
        return ProposalDraft(
            setup_type="NONE",
            setup_name="B_reversal",
            direction=direction,
            entry_price=entry,
            stop_loss_price=sl,
            take_profit_price=tp,
            factors=factors,
            grade=grade,
            reason=f"rr_below_profile_min_{rr_value:.2f}",
            setup_specific={
                "level": level,
                "pattern_name": pattern_name,
                "rr": rr_value,
            },
        )

    # --- Gate min_grade per profile (CRIT-3) ---
    if not grade_meets_profile_floor(grade, ctx.profile):
        return ProposalDraft(
            setup_type="NONE",
            setup_name="B_reversal",
            direction=direction,
            entry_price=entry,
            stop_loss_price=sl,
            take_profit_price=tp,
            factors=factors,
            grade=grade,
            reason=f"grade_below_profile_min_{grade}",
            setup_specific={"level": level, "pattern_name": pattern_name, "rr": rr_value},
        )

    # --- Confidence calibrata ---
    confidence = compute_confidence(
        grade, ctx, "B_reversal", factors=factors, indicators=indicators
    )

    # --- Gate min_confidence per profile (CRIT-3) ---
    if not confidence_meets_profile_floor(confidence, ctx.profile):
        return ProposalDraft(
            setup_type="NONE",
            setup_name="B_reversal",
            direction=direction,
            entry_price=entry,
            stop_loss_price=sl,
            take_profit_price=tp,
            factors=factors,
            grade=grade,
            confidence=confidence,
            reason=f"confidence_below_profile_min_{confidence:.2f}",
            setup_specific={"level": level, "pattern_name": pattern_name, "rr": rr_value},
        )

    return ProposalDraft(
        setup_type="READY",
        setup_name="B_reversal",
        direction=direction,
        entry_price=entry,
        stop_loss_price=sl,
        take_profit_price=tp,
        factors=factors,
        grade=grade,
        confidence=confidence,
        reason=f"reversal_{direction.lower()}_at_{level:.5f}_pattern={pattern_name}",
        rationale_parts={
            "pattern_name": pattern_name,
            "level": f"{level:.5f}",
            "atr": f"{atr_val:.5f}",
            "slope_at_entry": f"{slope:.6f}",
            "rr": f"{rr_value:.2f}",
            "grade": grade,
        },
        setup_specific={
            "reversal_bar_extreme": reversal_extreme,
            "level": level,
            "pattern_name": pattern_name,
            "rr": rr_value,
            "is_counter_trend": is_counter_trend,
        },
    )
