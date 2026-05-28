"""Detector Setup D — Trend Pullback (STRAT-04, Wave 2 plan-05).

Identificazione: trend stabilito (slope EMA50 sopra soglia) + prezzo dal lato giusto della
EMA50 + pullback dentro EMA20 OR Fib 0.382-0.618 zone, con continuation pattern (closing_score
neutrale 30-70).

Trend-following per definizione: NO counter-trend gate. Direction = sign(ema50_slope):
slope>0 → BUY, slope<0 → SELL. Mai emette trade contro la pendenza EMA50.

Campi ExtendedIndicators consumati (lettura difensiva via getattr):
  - atr_14[-1] (mandatory): bandwidth volatilità per buffer/cap SL e TP fallback
  - ema20[-1] / ema50[-1] / ema50_slope[-1] (mandatory): trend e zona pullback
  - fibonacci.levels (optional): zona retracement 38.2/61.8 + leg_high/leg_low per TP
  - closing_score / rsi_14 / volatility_regime / nr_detect / bollinger_bands: 5-factor

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
MIN_BARS = 50
SLOPE_THRESHOLD = 0.00005     # |slope| minimo per riconoscere trend (≈ 5 pip / bar EUR/USD M15)
PULLBACK_ATR_MULT = 0.5       # raggio EMA20 zone in unità ATR
PULLBACK_LOOKBACK = 5         # bars per estrarre pullback_extreme (low/high recente)
FIB_RETRACE_LO = 0.382        # zona Fib retracement inferiore
FIB_RETRACE_HI = 0.618        # zona Fib retracement superiore
FIB_EXTENSION = 1.618         # extension TP fallback
TP_ATR_FALLBACK_MULT = 1.618  # se leg_size mancante: ext = 1.618 * ATR


def _last(seq):
    """Ritorna l'ultimo elemento di una sequenza non vuota, altrimenti None."""
    if seq is None:
        return None
    try:
        return seq[-1]
    except (TypeError, IndexError, KeyError):
        return None


def _get_close(bar):
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


def _fib_level(fib, key_str: str, key_float: float):
    """Lettura difensiva su fibonacci.levels: prova sia chiave string sia float."""
    if fib is None:
        return None
    levels = getattr(fib, "levels", None)
    if not isinstance(levels, dict):
        return None
    return levels.get(key_str, levels.get(key_float))


def _compute_levels_d(
    direction: str,
    entry: float,
    pullback_extreme: float,
    atr: float,
    prior_swing: float | None,
    leg_size: float | None,
) -> tuple[float, float, float]:
    """SL/TP universale Setup D (D-10): SL = pullback_extreme ± 0.3×ATR, capato a 1.5×ATR.
    TP = prior_swing se sul lato corretto, altrimenti entry + 1.618 × leg_size (BUY) /
    entry − 1.618 × leg_size (SELL); fallback leg_size = 1.618 × ATR se assente.

    Buffer 0.3×ATR (più stretto di Setup A) perché il pullback_extreme è già un'estrema
    locale → buffer minimo per anti-noise sufficiente.
    """
    entry_out, sl = compute_levels_with_atr_cap(
        direction, entry, pullback_extreme, atr, buffer_atr_mult=0.3, cap_atr_mult=1.5
    )

    # TP: prior_swing prevale se valido sul lato corretto rispetto a direction
    if prior_swing is not None:
        if direction == "BUY" and prior_swing > entry_out:
            return entry_out, sl, prior_swing
        if direction == "SELL" and prior_swing < entry_out:
            return entry_out, sl, prior_swing

    # Fallback: estensione Fib su leg_size
    leg = leg_size if (leg_size is not None and leg_size > 0) else (TP_ATR_FALLBACK_MULT * atr)
    ext = leg * FIB_EXTENSION
    if direction == "BUY":
        tp = entry_out + ext
    else:
        tp = entry_out - ext
    return entry_out, sl, tp


def detect_d_pullback(
    bars: list,
    indicators,
    ctx: StrategyContext,
) -> ProposalDraft:
    """Detector pure-fn Setup D — Trend Pullback (STRAT-04).

    Sempre trend-following: direction segue sign(ema50_slope). Mai counter-trend.

    Flow:
      1. Guard insufficient_bars / atr_not_ready / ema_not_ready / last_close_missing.
      2. Slope sotto soglia → NONE no_trend_slope_below_threshold.
      3. Direction da slope; verifica prezzo sopra EMA50 (BUY) / sotto (SELL).
      4. Pullback in zone: |close - ema20| <= 0.5×ATR OR close in Fib 0.382-0.618.
      5. score_factors → grade; reject → NONE confluence_below_2_factors.
      6. _compute_levels_d → R:R floor → ProposalDraft READY.
    """
    # --- Guard 1: storia minima ---
    if not bars or len(bars) < MIN_BARS:
        return ProposalDraft(setup_type="NONE", reason="insufficient_bars")

    # --- Guard 2: ATR mandatory ---
    atr_val = _last(getattr(indicators, "atr_14", None))
    if atr_val is None or atr_val <= 0:
        return ProposalDraft(setup_type="NONE", reason="atr_not_ready")

    # --- Guard 3: EMA20/EMA50/slope mandatory ---
    ema20 = _last(getattr(indicators, "ema20", None))
    ema50 = _last(getattr(indicators, "ema50", None))
    slope = _last(getattr(indicators, "ema50_slope", None))
    if ema20 is None or ema50 is None or slope is None:
        return ProposalDraft(setup_type="NONE", reason="ema_not_ready")

    # --- Trend strength gate ---
    if abs(slope) < SLOPE_THRESHOLD:
        return ProposalDraft(
            setup_type="NONE",
            reason="no_trend_slope_below_threshold",
            setup_specific={"slope": slope, "threshold": SLOPE_THRESHOLD},
        )

    # Direction trend-following per costruzione
    direction = "BUY" if slope > 0 else "SELL"

    # --- Guard 4: ultimo close ---
    last_close = _get_close(bars[-1])
    if last_close is None:
        return ProposalDraft(setup_type="NONE", reason="last_close_missing")

    # --- Lato corretto vs EMA50 ---
    if direction == "BUY" and last_close < ema50:
        return ProposalDraft(
            setup_type="NONE",
            direction="BUY",
            reason="price_below_ema50_in_uptrend",
            setup_specific={"ema50": ema50, "last_close": last_close},
        )
    if direction == "SELL" and last_close > ema50:
        return ProposalDraft(
            setup_type="NONE",
            direction="SELL",
            reason="price_above_ema50_in_downtrend",
            setup_specific={"ema50": ema50, "last_close": last_close},
        )

    # --- Pullback zone detection ---
    pullback_dist = abs(last_close - ema20)
    pullback_threshold = PULLBACK_ATR_MULT * atr_val
    in_ema20_zone = pullback_dist <= pullback_threshold

    fib = getattr(indicators, "fibonacci", None)
    fib_38 = _fib_level(fib, "0.382", 0.382)
    fib_61 = _fib_level(fib, "0.618", 0.618)
    in_fib_zone = False
    if fib_38 is not None and fib_61 is not None:
        lo, hi = sorted((fib_38, fib_61))
        in_fib_zone = lo <= last_close <= hi

    if not (in_ema20_zone or in_fib_zone):
        return ProposalDraft(
            setup_type="FORMING",
            setup_name="D_pullback",
            direction=direction,
            confidence=0.0,
            reason="trend_ok_pullback_not_in_zone",
            setup_specific={"ema20": ema20, "ema50": ema50, "slope": slope},
        )

    # --- 5-factor confluence ---
    factors = score_factors("D_pullback", indicators, ctx, direction)
    grade = grade_for(factors)
    if grade == "reject":
        return ProposalDraft(
            setup_type="NONE",
            setup_name="D_pullback",
            direction=direction,
            factors=factors,
            grade=grade,
            reason="confluence_below_2_factors",
            setup_specific={"ema20": ema20, "ema50": ema50, "slope": slope},
        )

    # --- Pullback extreme (low/high recente per ancorare SL) ---
    look = bars[-PULLBACK_LOOKBACK:] if len(bars) >= PULLBACK_LOOKBACK else bars
    if direction == "BUY":
        lows = [_get_low(b) for b in look]
        lows = [v for v in lows if v is not None]
        pullback_extreme = min(lows) if lows else last_close
    else:
        highs = [_get_high(b) for b in look]
        highs = [v for v in highs if v is not None]
        pullback_extreme = max(highs) if highs else last_close

    # --- Prior swing / leg_size da fibonacci (se disponibili) ---
    leg_high = getattr(fib, "leg_high", None) if fib is not None else None
    leg_low = getattr(fib, "leg_low", None) if fib is not None else None
    if leg_high is not None and leg_low is not None:
        leg_size = abs(leg_high - leg_low)
        prior_swing = leg_high if direction == "BUY" else leg_low
    else:
        leg_size = None
        prior_swing = None

    # --- SL/TP via helper universale ---
    entry, sl, tp = _compute_levels_d(
        direction, last_close, pullback_extreme, atr_val, prior_swing, leg_size
    )

    # --- Gate R:R per profile ---
    passes_rr, rr_value = rr_meets_profile_floor(entry, sl, tp, direction, ctx.profile)
    if not passes_rr:
        return ProposalDraft(
            setup_type="NONE",
            setup_name="D_pullback",
            direction=direction,
            entry_price=entry,
            stop_loss_price=sl,
            take_profit_price=tp,
            factors=factors,
            grade=grade,
            reason=f"rr_below_profile_min_{rr_value:.2f}",
            setup_specific={
                "ema20": ema20,
                "ema50": ema50,
                "slope": slope,
                "rr": rr_value,
            },
        )

    # --- Confidence calibrata ---
    confidence = compute_confidence(
        grade, ctx, "D_pullback", factors=factors, indicators=indicators
    )

    return ProposalDraft(
        setup_type="READY",
        setup_name="D_pullback",
        direction=direction,
        entry_price=entry,
        stop_loss_price=sl,
        take_profit_price=tp,
        factors=factors,
        grade=grade,
        confidence=confidence,
        reason=f"pullback_{direction.lower()}_ema20={ema20:.5f}_slope={slope:.6f}",
        rationale_parts={
            "ema20": f"{ema20:.5f}",
            "ema50": f"{ema50:.5f}",
            "slope": f"{slope:.6f}",
            "atr": f"{atr_val:.5f}",
            "rr": f"{rr_value:.2f}",
            "in_fib_zone": str(in_fib_zone),
            "in_ema20_zone": str(in_ema20_zone),
            "grade": grade,
        },
        setup_specific={
            "pullback_extreme": pullback_extreme,
            "ema20": ema20,
            "ema50": ema50,
            "slope": slope,
            "leg_size": leg_size,
            "prior_swing": prior_swing,
            "rr": rr_value,
        },
    )
