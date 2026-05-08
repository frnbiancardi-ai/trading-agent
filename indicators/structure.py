"""Indicatori di struttura: support/resistance, qualità breakout, Donchian, Fibonacci, Pivots.

Wave 0 (preservato invariato):
- `find_support_resistance` — pivot swing high/low.
- `check_breakout_quality` — classificazione CLEAN/WEAK/NONE su volumi.

Wave 2 (INDIC-05/08/09):
- `donchian` (length=20 di default) — max highs / min lows rolling, middle = (upper+lower)/2.
- `fibonacci_retracements` — livelli 0/0.382/0.5/0.618/1.0 sull'ultimo swing leg
  rilevato (riusa `find_support_resistance`).
- `pivots` (anchor "daily"/"weekly", boundary NY-17 DST-aware tramite `_session_id_ny17`)
  — ritorna `PivotResult` con classico P/R1..R3/S1..S3 + Camarilla h1..h4/l1..l4.

Camarilla multipliers (RESEARCH §Don't Hand-Roll, verificati LiteFinance/Babypips/Defcofx):
  R/S 1..4 = prev_close ± rng * 1.1 / {12, 6, 4, 2}

Niente `pandas_ta` a runtime (D-07 + Pitfall 8) — l'oracolo dev-only resta confinato
ai test.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from indicators._helpers import _session_id_ny17
from indicators.volume import avg_volume


# ── Dataclasses (D-04..D-06) ───────────────────────────────────────────────────


@dataclass
class DonchianResult:
    """Output di `donchian`: tre serie length-N (warmup = None)."""
    upper: list[float | None]
    lower: list[float | None]
    middle: list[float | None]


@dataclass
class FibonacciResult:
    """Output di `fibonacci_retracements`: snapshot, NON serie.

    `direction` ∈ {"up", "down", "none"}. Su "none" `levels` è dict vuoto e gli
    estremi sono None.
    """
    levels: dict[str, float | None]
    leg_high: float | None
    leg_low: float | None
    direction: str


@dataclass
class PivotResult:
    """Output di `pivots`: serie length-N classico + Camarilla.

    `camarilla` è un dict con chiavi "h1".."h4", "l1".."l4", ognuna serie length-N.
    Bar nella prima sessione (no prior) → tutti None. Convenzione bar-close: ogni
    barra usa la H/L/C della sessione precedentemente CHIUSA, mai della corrente.
    """
    p: list[float | None]
    r1: list[float | None]
    r2: list[float | None]
    r3: list[float | None]
    s1: list[float | None]
    s2: list[float | None]
    s3: list[float | None]
    camarilla: dict[str, list[float | None]]


# ── Wave 0: support/resistance + breakout (preservati invariati) ───────────────


def find_support_resistance(bars: list[dict], lookback: int = 100, window: int = 2) -> dict:
    """Support e resistance dinamici via pivot swing high/low.

    Ritorna {'support': float|None, 'resistance': float|None}.
    Pivot: barra il cui high (low) è max (min) nella finestra ±window.
    """
    if not bars:
        return {"support": None, "resistance": None}

    sub = bars[-lookback:] if len(bars) > lookback else bars
    n = len(sub)
    if n < 2 * window + 1:
        return {
            "support": min(b["low"] for b in sub),
            "resistance": max(b["high"] for b in sub),
        }

    swing_highs: list[float] = []
    swing_lows: list[float] = []
    for i in range(window, n - window):
        hi = sub[i]["high"]
        lo = sub[i]["low"]
        is_high = all(sub[i]["high"] >= sub[j]["high"] for j in range(i - window, i + window + 1) if j != i)
        is_low = all(sub[i]["low"] <= sub[j]["low"] for j in range(i - window, i + window + 1) if j != i)
        if is_high:
            swing_highs.append(hi)
        if is_low:
            swing_lows.append(lo)

    resistance = max(swing_highs) if swing_highs else max(b["high"] for b in sub)
    support = min(swing_lows) if swing_lows else min(b["low"] for b in sub)
    return {"support": support, "resistance": resistance}


def check_breakout_quality(
    bars: list[dict],
    sr: dict,
    volume_threshold: float = 1.3,
    avg_period: int = 20,
) -> str:
    """Ritorna 'CLEAN', 'WEAK', 'NONE' valutando ultima barra rispetto a SR."""
    if not bars or not sr:
        return "NONE"
    last = bars[-1]
    support = sr.get("support")
    resistance = sr.get("resistance")
    if support is None and resistance is None:
        return "NONE"

    broke_up = resistance is not None and last["close"] > resistance
    broke_down = support is not None and last["close"] < support
    if not (broke_up or broke_down):
        return "NONE"

    avg_vol = avg_volume(bars[:-1], avg_period)
    if avg_vol <= 0:
        return "WEAK"
    last_vol = last.get("tick_volume", last.get("volume", 0)) or 0
    ratio = last_vol / avg_vol
    return "CLEAN" if ratio >= volume_threshold else "WEAK"


# ── Wave 2: Donchian (INDIC-05) ────────────────────────────────────────────────


def donchian(
    highs: list[float],
    lows: list[float],
    length: int = 20,
) -> DonchianResult:
    """Donchian Channel rolling: upper = max(highs[i-length+1:i+1]),
    lower = min(lows[...]), middle = (upper+lower)/2.

    Le prime `length-1` posizioni sono None (warmup). Implementazione naive
    O(n*length): accettabile per length tipico (20) e n <= 23.5y * 24h ≈ 200k.
    """
    if len(highs) != len(lows):
        raise ValueError("highs e lows devono avere la stessa lunghezza")
    if length <= 0:
        raise ValueError(f"length deve essere > 0, ricevuto {length}")
    n = len(highs)
    upper: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    middle: list[float | None] = [None] * n
    if n < length:
        return DonchianResult(upper=upper, lower=lower, middle=middle)
    for i in range(length - 1, n):
        u = max(highs[i - length + 1:i + 1])
        lo = min(lows[i - length + 1:i + 1])
        upper[i] = u
        lower[i] = lo
        middle[i] = (u + lo) / 2.0
    return DonchianResult(upper=upper, lower=lower, middle=middle)


# ── Wave 2: Fibonacci retracements (INDIC-08) ──────────────────────────────────


def fibonacci_retracements(
    bars: list[dict],
    lookback: int = 100,
    window: int = 2,
) -> FibonacciResult:
    """Retracements 0/0.382/0.5/0.618/1.0 sull'ultimo swing leg completato.

    Open-Q5 RESEARCH: la rilevazione del leg riusa `find_support_resistance`
    (stessa logica di pivot ±window). Direzione determinata da QUALE estremo
    è più recente:
    - swing_high più recente di swing_low → trend recente UP, retracement DOWN.
    - swing_low più recente di swing_high → trend recente DOWN, retracement UP.

    Su input vuoto / nessun pivot rilevabile / estremi mancanti ritorna
    `FibonacciResult(direction="none", ...)`.
    """
    if not bars:
        return FibonacciResult(levels={}, leg_high=None, leg_low=None, direction="none")

    sr = find_support_resistance(bars, lookback=lookback, window=window)
    leg_high = sr.get("resistance")
    leg_low = sr.get("support")
    if leg_high is None or leg_low is None or leg_high == leg_low:
        return FibonacciResult(levels={}, leg_high=None, leg_low=None, direction="none")

    # Determina quale estremo è più recente scansionando bars[-lookback:] dal fondo.
    sub = bars[-lookback:] if len(bars) > lookback else bars
    last_high_idx = -1
    last_low_idx = -1
    # Tolleranza float: usa equality stretta perché leg_high/leg_low provengono già dai bar.
    for i in range(len(sub) - 1, -1, -1):
        if last_high_idx < 0 and sub[i]["high"] == leg_high:
            last_high_idx = i
        if last_low_idx < 0 and sub[i]["low"] == leg_low:
            last_low_idx = i
        if last_high_idx >= 0 and last_low_idx >= 0:
            break

    if last_high_idx < 0 or last_low_idx < 0:
        # Edge: l'estremo restituito da fallback (min/max di sub) potrebbe non
        # combaciare con un bar specifico se sub è stato slicato in modo strano.
        return FibonacciResult(levels={}, leg_high=None, leg_low=None, direction="none")

    rng = leg_high - leg_low
    if last_high_idx > last_low_idx:
        # Swing high più recente → leg UP (low → high), retracement scende.
        direction = "up"
        levels = {
            "0": leg_high,
            "0.382": leg_high - 0.382 * rng,
            "0.5": leg_high - 0.5 * rng,
            "0.618": leg_high - 0.618 * rng,
            "1.0": leg_low,
        }
    else:
        # Swing low più recente (o pari) → leg DOWN (high → low), retracement sale.
        direction = "down"
        levels = {
            "0": leg_low,
            "0.382": leg_low + 0.382 * rng,
            "0.5": leg_low + 0.5 * rng,
            "0.618": leg_low + 0.618 * rng,
            "1.0": leg_high,
        }

    return FibonacciResult(
        levels=levels,
        leg_high=leg_high,
        leg_low=leg_low,
        direction=direction,
    )


# ── Wave 2: Pivots classico + Camarilla (INDIC-09) ─────────────────────────────

# Camarilla multipliers verbatim (RESEARCH §Don't Hand-Roll, verificati 3 fonti
# LiteFinance/Babypips/Defcofx). I literal `1.1/12, 1.1/6, 1.1/4, 1.1/2` sono
# scritti esplicitamente per render rivedibile la formula nel diff.
_CAMARILLA_MULT = (1.1 / 12, 1.1 / 6, 1.1 / 4, 1.1 / 2)


def _iso_week_key(ny_session_date: date) -> tuple[int, int]:
    """Chiave di settimana ISO per anchor weekly (anno_iso, week_iso).

    `ny_session_date` è la data di chiusura sessione NY (output di
    `_session_id_ny17`). Usa il calendario ISO 8601 standard.
    """
    iso = ny_session_date.isocalendar()
    return (iso.year, iso.week)


def _empty_pivot_series(n: int) -> PivotResult:
    """Tutti None (per input vuoto o singola sessione)."""
    none_series = [None] * n
    cam = {f"h{k}": [None] * n for k in (1, 2, 3, 4)}
    cam.update({f"l{k}": [None] * n for k in (1, 2, 3, 4)})
    return PivotResult(
        p=list(none_series),
        r1=list(none_series),
        r2=list(none_series),
        r3=list(none_series),
        s1=list(none_series),
        s2=list(none_series),
        s3=list(none_series),
        camarilla=cam,
    )


def pivots(bars: list[dict], anchor: str = "daily") -> PivotResult:
    """Pivot points classico + Camarilla, ancora NY-17 DST-aware (D-10/D-11).

    `anchor`:
    - "daily": chiave di sessione = output di `_session_id_ny17` (data NY-17).
    - "weekly": chiave = (anno_iso, week_iso) della stessa data NY-17.

    Per ogni barra `i`: i livelli sono calcolati sulla H/L/C della sessione
    PRECEDENTEMENTE chiusa (no future leakage). Le bar nella prima sessione
    osservata non hanno prior → tutti None.

    Formule:
      P  = (H + L + C) / 3
      R1 = 2P - L      ; S1 = 2P - H
      R2 = P + (H - L) ; S2 = P - (H - L)
      R3 = H + 2(P-L)  ; S3 = L - 2(H-P)
      Camarilla h_k = C + (H-L)*1.1/{12,6,4,2}; l_k specchiato.
    """
    if anchor not in ("daily", "weekly"):
        raise ValueError(f"anchor deve essere 'daily' o 'weekly', ricevuto {anchor!r}")
    n = len(bars)
    if n == 0:
        return _empty_pivot_series(0)

    p_s: list[float | None] = [None] * n
    r1_s: list[float | None] = [None] * n
    r2_s: list[float | None] = [None] * n
    r3_s: list[float | None] = [None] * n
    s1_s: list[float | None] = [None] * n
    s2_s: list[float | None] = [None] * n
    s3_s: list[float | None] = [None] * n
    cam: dict[str, list[float | None]] = {f"h{k}": [None] * n for k in (1, 2, 3, 4)}
    cam.update({f"l{k}": [None] * n for k in (1, 2, 3, 4)})

    # Prior session H/L/C disponibile per la sessione corrente (None nella prima).
    prev_h: float | None = None
    prev_l: float | None = None
    prev_c: float | None = None

    # Stato della sessione corrente (in costruzione).
    cur_key: object = None
    cur_h: float | None = None
    cur_l: float | None = None
    cur_c: float | None = None  # close dell'ultima bar vista nella sessione corrente

    for i, bar in enumerate(bars):
        ts = datetime.fromtimestamp(bar["time"], tz=timezone.utc)
        ny_date = _session_id_ny17(ts)
        key = ny_date if anchor == "daily" else _iso_week_key(ny_date)

        if cur_key is None:
            cur_key = key
            cur_h = bar["high"]
            cur_l = bar["low"]
            cur_c = bar["close"]
        elif key != cur_key:
            # Cambio sessione: la sessione appena chiusa diventa il prior della nuova.
            prev_h = cur_h
            prev_l = cur_l
            prev_c = cur_c
            cur_key = key
            cur_h = bar["high"]
            cur_l = bar["low"]
            cur_c = bar["close"]
        else:
            # Stessa sessione: aggiorna H/L/C correnti.
            cur_h = max(cur_h, bar["high"])  # type: ignore[type-var]
            cur_l = min(cur_l, bar["low"])  # type: ignore[type-var]
            cur_c = bar["close"]

        # Scrivi i livelli della barra `i` usando il PRIOR (no future leakage).
        if prev_h is not None and prev_l is not None and prev_c is not None:
            H, L, C = prev_h, prev_l, prev_c
            rng = H - L
            P = (H + L + C) / 3.0
            p_s[i] = P
            r1_s[i] = 2.0 * P - L
            s1_s[i] = 2.0 * P - H
            r2_s[i] = P + rng
            s2_s[i] = P - rng
            r3_s[i] = H + 2.0 * (P - L)
            s3_s[i] = L - 2.0 * (H - P)
            for k_idx, mult in enumerate(_CAMARILLA_MULT, start=1):
                offset = rng * mult
                cam[f"h{k_idx}"][i] = C + offset
                cam[f"l{k_idx}"][i] = C - offset

    return PivotResult(
        p=p_s, r1=r1_s, r2=r2_s, r3=r3_s, s1=s1_s, s2=s2_s, s3=s3_s,
        camarilla=cam,
    )
