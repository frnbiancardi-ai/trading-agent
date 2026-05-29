"""Detector Setup C — Compression Breakout: trigger NR4/NR7 o BB squeeze (STRAT-03, Wave 2 plan-06).

Identificazione: il mercato è compresso (NR4 OPPURE NR7 OPPURE Bollinger squeeze veri sull'ultimo
bar) per almeno MIN_COMPRESSION_BARS bar consecutivi. Direction inferita dal trend slope EMA50.
Entry posizionato come ordine stop al boundary della compression range:
  - BUY → entry = compression_high (range top, stop trigger sopra)
  - SELL → entry = compression_low (range bottom, stop trigger sotto)
SL all'opposite side del range; TP = entry ± 2 × range_size (range-expansion D-10).

NOTA RICONCILIAZIONE Boomer (CONTEXT.md): Setup C consuma il segnale Boomer A2 emesso da
indicators/bars.py:narrow_range che usa la formula CONTEXT.md verbatim
`inside[i] AND inside[i-1] AND (nr4[i] OR nr7[i])`. La versione skill forex-trader-pro
price_action.md:43 (più stringente) NON è usata. Riconciliazione final-locked qui per
Phase 11 paper deploy gate.

Trigger READY/FORMING/NONE:
  - READY: compressed_count >= 3 + grade ≥ C + R:R passa profile_filters
  - FORMING: compressed_count == 2 (in attesa del terzo bar di conferma)
  - NONE: nessuna compressione, slope=0, confluence reject, R:R sotto floor

Campi ExtendedIndicators consumati (lettura difensiva via getattr):
  - atr_14[-1] (mandatory): bandwidth volatilità per buffer/cap SL
  - nr_detect.{nr4, nr7}: list[bool] da Phase 2 INDIC-10 (Boomer A2)
  - bollinger_bands.squeeze: list[bool] da Phase 2 INDIC-01
  - ema50_slope[-1] (mandatory): direction inference
  - rsi_14[-1] / volatility_regime[-1] / closing_score[-1]: 5-factor

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
MIN_BARS = 50                  # warmup minimo storico
MIN_COMPRESSION_BARS = 3       # bar consecutivi compressi richiesti per READY
COMPRESSION_LOOKBACK = 7       # finestra di scansione backward per compressed_count


def _last(seq):
    """Ritorna l'ultimo elemento di una sequenza non vuota, altrimenti None."""
    if seq is None:
        return None
    try:
        return seq[-1]
    except (TypeError, IndexError, KeyError):
        return None


def _at(seq, idx):
    """Lettura difensiva seq[idx] con fallback None su out-of-range / type error."""
    if seq is None:
        return None
    try:
        return seq[idx]
    except (TypeError, IndexError, KeyError):
        return None


def _get_low(bar):
    if isinstance(bar, dict):
        return bar.get("low")
    return getattr(bar, "low", None)


def _get_high(bar):
    if isinstance(bar, dict):
        return bar.get("high")
    return getattr(bar, "high", None)


def _compute_levels_c(
    direction: str,
    compression_low: float,
    compression_high: float,
    atr: float,
) -> tuple[float, float, float]:
    """SL/TP universale Setup C (D-10): entry come stop-order al boundary, SL opposite side
    capato a 1.5×ATR, TP = entry ± 2 × range_size.

    BUY:  entry = compression_high (stop sopra il range, breakout long).
          SL = compression_low − 0.3×ATR (anti-fakeout sotto il bottom), capato a 1.5×ATR.
          TP = entry + 2 × (compression_high − compression_low).
    SELL: entry = compression_low (stop sotto il range, breakout short).
          SL = compression_high + 0.3×ATR, capato.
          TP = entry − 2 × range.

    Range-expansion 2× è il target tipico del compression-breakout (Murphy + skill
    forex-trader-pro: "compression resolves into 2-3× range expansion").
    """
    if direction == "BUY":
        entry = compression_high
        structural_level = compression_low
    else:  # SELL
        entry = compression_low
        structural_level = compression_high

    _, sl = compute_levels_with_atr_cap(
        direction, entry, structural_level, atr,
        buffer_atr_mult=0.3, cap_atr_mult=1.5,
    )

    range_size = compression_high - compression_low
    if direction == "BUY":
        tp = entry + 2.0 * range_size
    else:
        tp = entry - 2.0 * range_size
    return entry, sl, tp


def detect_c_compression(
    bars: list,
    indicators,
    ctx: StrategyContext,
) -> ProposalDraft:
    """Detector pure-fn Setup C — Compression Breakout (STRAT-03).

    Ritorna ProposalDraft con setup_type ∈ {READY, FORMING, NONE}. Mai None.

    Flow:
      1. Guard insufficient_bars / atr_not_ready.
      2. Lettura trigger: nr4[-1] OR nr7[-1] OR squeeze[-1] (qualsiasi True → is_compressed).
      3. NOT compressed → NONE/no_compression_detected.
      4. Walk backward COMPRESSION_LOOKBACK bars: count consecutivi con almeno uno dei tre
         trigger True. Stop al primo bar non-compresso.
      5. compressed_count < 2 → NONE/insufficient_compression_window.
         compressed_count == 2 → FORMING/second_compression_bar_waiting_third.
      6. compression_low = min(low) / compression_high = max(high) sugli ultimi
         compressed_count bars.
      7. Direction da slope: > 0 BUY, < 0 SELL, == 0 → NONE/no_directional_bias.
      8. score_factors → grade; reject → NONE/confluence_below_2_factors.
      9. _compute_levels_c → R:R floor → ProposalDraft READY.
    """
    # --- Guard 1: storia minima ---
    if not bars or len(bars) < MIN_BARS:
        return ProposalDraft(setup_type="NONE", reason="insufficient_bars")

    # --- Guard 2: ATR mandatory ---
    atr_val = _last(getattr(indicators, "atr_14", None))
    if atr_val is None or atr_val <= 0:
        return ProposalDraft(setup_type="NONE", reason="atr_not_ready")

    # --- Lettura difensiva trigger ultimo bar ---
    nr = getattr(indicators, "nr_detect", None)
    nr4_seq = getattr(nr, "nr4", None) if nr is not None else None
    nr7_seq = getattr(nr, "nr7", None) if nr is not None else None
    bb = getattr(indicators, "bollinger_bands", None)
    squeeze_seq = getattr(bb, "squeeze", None) if bb is not None else None

    nr4_now = bool(_last(nr4_seq))
    nr7_now = bool(_last(nr7_seq))
    squeeze_now = bool(_last(squeeze_seq))
    is_compressed = nr4_now or nr7_now or squeeze_now

    if not is_compressed:
        return ProposalDraft(
            setup_type="NONE",
            reason="no_compression_detected",
            setup_specific={
                "nr4_now": nr4_now,
                "nr7_now": nr7_now,
                "squeeze_now": squeeze_now,
            },
        )

    # --- Walk backward COMPRESSION_LOOKBACK per contare bar consecutivi compressi ---
    compressed_count = 0
    for offset in range(1, COMPRESSION_LOOKBACK + 1):
        idx = -offset
        nr4_i = _at(nr4_seq, idx)
        nr7_i = _at(nr7_seq, idx)
        sq_i = _at(squeeze_seq, idx)
        bar_compressed = bool(nr4_i or nr7_i or sq_i)
        if bar_compressed:
            compressed_count += 1
        else:
            break  # interrompo la stringa di consecutivi al primo non-compresso

    # --- Trigger type per debug/rationale (priorità: nr7 > nr4 > squeeze) ---
    trigger_type = "nr7" if nr7_now else ("nr4" if nr4_now else "squeeze")

    if compressed_count < MIN_COMPRESSION_BARS:
        if compressed_count == 2:
            return ProposalDraft(
                setup_type="FORMING",
                setup_name="C_compression",
                confidence=0.0,
                reason="second_compression_bar_waiting_third",
                setup_specific={
                    "compressed_bar_count": compressed_count,
                    "trigger_type": trigger_type,
                },
            )
        return ProposalDraft(
            setup_type="NONE",
            reason="insufficient_compression_window",
            setup_specific={
                "compressed_bar_count": compressed_count,
                "trigger_type": trigger_type,
            },
        )

    # --- Compression range: ultimi compressed_count bar ---
    look = bars[-compressed_count:] if len(bars) >= compressed_count else bars
    lows = [_get_low(b) for b in look]
    highs = [_get_high(b) for b in look]
    lows = [v for v in lows if v is not None]
    highs = [v for v in highs if v is not None]
    if not lows or not highs:
        return ProposalDraft(
            setup_type="NONE",
            reason="compression_range_unreadable",
            setup_specific={"compressed_bar_count": compressed_count},
        )
    compression_low = min(lows)
    compression_high = max(highs)
    if compression_high <= compression_low:
        return ProposalDraft(
            setup_type="NONE",
            reason="compression_range_zero",
            setup_specific={
                "compression_low": compression_low,
                "compression_high": compression_high,
            },
        )

    # --- Direction inference da slope EMA50 ---
    slope = _last(getattr(indicators, "ema50_slope", None)) or 0.0
    if slope > 0:
        direction = "BUY"
    elif slope < 0:
        direction = "SELL"
    else:
        return ProposalDraft(
            setup_type="NONE",
            reason="no_directional_bias",
            setup_specific={
                "compression_range": (compression_low, compression_high),
                "compressed_bar_count": compressed_count,
            },
        )

    # --- 5-factor confluence ---
    factors = score_factors("C_compression", indicators, ctx, direction)
    grade = grade_for(factors)
    if grade == "reject":
        return ProposalDraft(
            setup_type="NONE",
            setup_name="C_compression",
            direction=direction,
            factors=factors,
            grade=grade,
            reason="confluence_below_2_factors",
            setup_specific={
                "compression_range": (compression_low, compression_high),
                "compressed_bar_count": compressed_count,
                "trigger_type": trigger_type,
            },
        )

    # --- SL/TP via helper Setup C specifico ---
    entry, sl, tp = _compute_levels_c(
        direction, compression_low, compression_high, atr_val
    )

    # --- Gate R:R per profile ---
    passes_rr, rr_value = rr_meets_profile_floor(entry, sl, tp, direction, ctx.profile)
    if not passes_rr:
        return ProposalDraft(
            setup_type="NONE",
            setup_name="C_compression",
            direction=direction,
            entry_price=entry,
            stop_loss_price=sl,
            take_profit_price=tp,
            factors=factors,
            grade=grade,
            reason=f"rr_below_profile_min_{rr_value:.2f}",
            setup_specific={
                "compression_range": (compression_low, compression_high),
                "compressed_bar_count": compressed_count,
                "trigger_type": trigger_type,
                "rr": rr_value,
            },
        )

    # --- Gate min_grade per profile (CRIT-3) ---
    if not grade_meets_profile_floor(grade, ctx.profile):
        return ProposalDraft(
            setup_type="NONE",
            setup_name="C_compression",
            direction=direction,
            entry_price=entry,
            stop_loss_price=sl,
            take_profit_price=tp,
            factors=factors,
            grade=grade,
            reason=f"grade_below_profile_min_{grade}",
            setup_specific={
                "compression_range": (compression_low, compression_high),
                "compressed_bar_count": compressed_count,
                "trigger_type": trigger_type,
                "rr": rr_value,
            },
        )

    # --- Confidence calibrata ---
    confidence = compute_confidence(
        grade, ctx, "C_compression", factors=factors, indicators=indicators
    )

    # --- Gate min_confidence per profile (CRIT-3) ---
    if not confidence_meets_profile_floor(confidence, ctx.profile):
        return ProposalDraft(
            setup_type="NONE",
            setup_name="C_compression",
            direction=direction,
            entry_price=entry,
            stop_loss_price=sl,
            take_profit_price=tp,
            factors=factors,
            grade=grade,
            confidence=confidence,
            reason=f"confidence_below_profile_min_{confidence:.2f}",
            setup_specific={
                "compression_range": (compression_low, compression_high),
                "compressed_bar_count": compressed_count,
                "trigger_type": trigger_type,
                "rr": rr_value,
            },
        )

    range_size = compression_high - compression_low
    pip_size = ctx.pip_size or 0.0001
    range_pips = range_size / pip_size

    return ProposalDraft(
        setup_type="READY",
        setup_name="C_compression",
        direction=direction,
        entry_price=entry,
        stop_loss_price=sl,
        take_profit_price=tp,
        factors=factors,
        grade=grade,
        confidence=confidence,
        reason=(
            f"compression_{direction.lower()}_breakout_{trigger_type}"
            f"_range={range_pips:.1f}pips"
        ),
        rationale_parts={
            "compression_low": f"{compression_low:.5f}",
            "compression_high": f"{compression_high:.5f}",
            "range_pips": f"{range_pips:.1f}",
            "atr": f"{atr_val:.5f}",
            "rr": f"{rr_value:.2f}",
            "slope": f"{slope:.6f}",
            "trigger": trigger_type,
            "grade": grade,
        },
        setup_specific={
            "compression_range": (compression_low, compression_high),
            "compressed_bar_count": compressed_count,
            "trigger_type": trigger_type,
            "rr": rr_value,
        },
    )
