"""Riconoscimento pattern candlestick base in Python puro.

Bar dict atteso: {'open': float, 'high': float, 'low': float, 'close': float, ...}
Tutte le funzioni gestiscono input degenere (open == close, range nullo) senza crash.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import yaml


@dataclass(frozen=True)
class CalibrationAnchors:
    """Ancore di calibrazione per mappare raw_score in [0,1]."""
    min: float
    typical: float
    max: float


@dataclass(frozen=True)
class HammerCfg:
    body_ratio_max: float
    lower_shadow_body_min: float
    upper_shadow_range_max: float
    calibration: CalibrationAnchors


@dataclass(frozen=True)
class InvertedHammerCfg:
    body_ratio_max: float
    upper_shadow_body_min: float
    lower_shadow_range_max: float
    calibration: CalibrationAnchors


@dataclass(frozen=True)
class ShootingStarCfg:
    body_ratio_max: float
    upper_shadow_body_min: float
    lower_shadow_range_max: float
    calibration: CalibrationAnchors


@dataclass(frozen=True)
class EngulfingCfg:
    min_engulfment_ratio: float
    min_body_ratio: float
    calibration: CalibrationAnchors


@dataclass(frozen=True)
class StarCfg:
    trend_body_min_ratio: float
    star_body_max_ratio: float
    min_b3_penetration: float
    calibration: CalibrationAnchors


@dataclass(frozen=True)
class KeyReversalCfg:
    min_extreme_break_pips: float
    min_close_penetration_ratio: float
    calibration: CalibrationAnchors


@dataclass(frozen=True)
class InsideBarCfg:
    max_compression_ratio: float
    calibration: CalibrationAnchors


@dataclass(frozen=True)
class PinBarCfg:
    body_ratio_max: float
    dominant_wick_ratio_min: float
    calibration: CalibrationAnchors


@dataclass(frozen=True)
class DojiCfg:
    body_tolerance: float


@dataclass(frozen=True)
class PatternConfig:
    hammer: HammerCfg
    inverted_hammer: InvertedHammerCfg
    shooting_star: ShootingStarCfg
    engulfing: EngulfingCfg
    morning_star: StarCfg
    evening_star: StarCfg
    key_reversal: KeyReversalCfg
    inside_bar: InsideBarCfg
    pin_bar: PinBarCfg
    doji: DojiCfg


@dataclass(frozen=True)
class PatternHit:
    """Risultato di un detector calibrato.

    name: identificatore pattern (es. 'hammer', 'morning_star')
    bar_index: offset negativo dalla fine della lista bars (-1 = ultima)
    span_bars: 1 single-bar, 2 engulfing/key_reversal, 3 stars
    extreme_price: swing low (bullish) / swing high (bearish) lungo lo span
    confidence: 0.0..1.0 calibrata
    direction: 'bullish' | 'bearish' | 'neutral'
    """
    name: str
    bar_index: int
    span_bars: int
    extreme_price: float
    confidence: float
    direction: str


DEFAULT_CONFIG_PATH = Path("config/patterns.yaml")


def _body(bar: dict) -> float:
    return abs(bar["close"] - bar["open"])


def _range(bar: dict) -> float:
    return bar["high"] - bar["low"]


def _upper_shadow(bar: dict) -> float:
    return bar["high"] - max(bar["open"], bar["close"])


def _lower_shadow(bar: dict) -> float:
    return min(bar["open"], bar["close"]) - bar["low"]


def _is_bullish(bar: dict) -> bool:
    return bar["close"] > bar["open"]


def _is_bearish(bar: dict) -> bool:
    return bar["close"] < bar["open"]


def is_hammer(bar: dict, cfg: HammerCfg) -> tuple[bool, float]:
    """Hammer: long lower shadow, upper shadow piccola, body piccolo.

    Restituisce (matched, raw_score). raw_score = lower_shadow / body.
    Geometria parametrizzata da cfg (zero magic numbers).
    """
    rng = _range(bar)
    body = _body(bar)
    if rng <= 0 or body <= 0:
        return False, 0.0
    lower = _lower_shadow(bar)
    upper = _upper_shadow(bar)
    matched = (
        body <= cfg.body_ratio_max * rng
        and lower >= cfg.lower_shadow_body_min * body
        and upper <= cfg.upper_shadow_range_max * rng
    )
    if not matched:
        return False, 0.0
    return True, lower / body


def is_inverted_hammer(bar: dict, cfg: InvertedHammerCfg) -> tuple[bool, float]:
    """Inverted hammer: long upper shadow, lower shadow piccola, body piccolo.

    Restituisce (matched, raw_score). raw_score = upper_shadow / body.
    """
    rng = _range(bar)
    body = _body(bar)
    if rng <= 0 or body <= 0:
        return False, 0.0
    lower = _lower_shadow(bar)
    upper = _upper_shadow(bar)
    matched = (
        body <= cfg.body_ratio_max * rng
        and upper >= cfg.upper_shadow_body_min * body
        and lower <= cfg.lower_shadow_range_max * rng
    )
    if not matched:
        return False, 0.0
    return True, upper / body


def is_engulfing(
    prev_bar: dict,
    current_bar: dict,
    direction: str,
    cfg: EngulfingCfg,
) -> tuple[bool, float]:
    """Engulfing: corpo corrente ingloba corpo precedente.

    direction = 'bullish': prev bearish, curr bullish, curr.open <= prev.close,
                           curr.close >= prev.open
    direction = 'bearish': prev bullish, curr bearish, curr.open >= prev.close,
                           curr.close <= prev.open
    Restituisce (matched, raw_score). raw_score = body_curr / body_prev.
    Gate addizionale: ogni body >= cfg.min_body_ratio del proprio range
    (esclude doji-like che non costituiscono engulfing significativi).
    """
    direction = direction.lower()
    body_prev = _body(prev_bar)
    body_curr = _body(current_bar)
    rng_prev = _range(prev_bar)
    rng_curr = _range(current_bar)
    if body_prev <= 0 or body_curr <= 0 or rng_prev <= 0 or rng_curr <= 0:
        return False, 0.0
    if (body_prev / rng_prev) < cfg.min_body_ratio:
        return False, 0.0
    if (body_curr / rng_curr) < cfg.min_body_ratio:
        return False, 0.0

    if direction == "bullish":
        if not (_is_bearish(prev_bar) and _is_bullish(current_bar)):
            return False, 0.0
        if not (current_bar["open"] <= prev_bar["close"]
                and current_bar["close"] >= prev_bar["open"]):
            return False, 0.0
    elif direction == "bearish":
        if not (_is_bullish(prev_bar) and _is_bearish(current_bar)):
            return False, 0.0
        if not (current_bar["open"] >= prev_bar["close"]
                and current_bar["close"] <= prev_bar["open"]):
            return False, 0.0
    else:
        return False, 0.0

    ratio = body_curr / body_prev
    if ratio < cfg.min_engulfment_ratio:
        return False, 0.0
    return True, ratio


def is_doji(bar: dict, tolerance: float = 0.1) -> bool:
    """Doji: |close - open| <= tolerance * range."""
    rng = _range(bar)
    if rng <= 0:
        return False
    return _body(bar) <= tolerance * rng


def is_pin_bar(
    bar: dict,
    direction: str,
    cfg: PinBarCfg,
) -> tuple[bool, float]:
    """Pin bar: long wick opposto alla direzione, body piccolo.

    direction = 'bullish': lower wick >= cfg.dominant_wick_ratio_min * range, close > open
    direction = 'bearish': upper wick >= cfg.dominant_wick_ratio_min * range, close < open
    Restituisce (matched, raw_score). raw_score = dominant_wick / range.
    """
    direction = direction.lower()
    rng = _range(bar)
    body = _body(bar)
    if rng <= 0:
        return False, 0.0
    if body > cfg.body_ratio_max * rng:
        return False, 0.0

    if direction == "bullish":
        wick = _lower_shadow(bar)
        if not _is_bullish(bar):
            return False, 0.0
    elif direction == "bearish":
        wick = _upper_shadow(bar)
        if not _is_bearish(bar):
            return False, 0.0
    else:
        return False, 0.0

    ratio = wick / rng
    if ratio < cfg.dominant_wick_ratio_min:
        return False, 0.0
    return True, ratio


def scan_patterns(
    bars: list[dict],
    last_n: int = 5,
    cfg: "PatternConfig | None" = None,
) -> list:
    """STUB Wave 2 — scan_patterns completo è ricostruito in Wave 3 (piano 03).

    Questa versione provvisoria preserva il contratto chiamabile (firma compatibile
    con strategy.py:229) ma restituisce solo doji hits per evitare di chiamare
    detector dalla firma cambiata. La Wave 3 ricostruisce la lista completa
    PatternHit dal cfg.
    """
    if not bars:
        return []
    return []


def _calibrate(raw: float, anchors: CalibrationAnchors) -> float:
    """Mappa raw score in [0,1] via interpolazione lineare a tratti.

    raw <= min       -> 0.0
    min < raw < typ  -> linear interp 0.0 -> 0.7
    typ <= raw < max -> linear interp 0.7 -> 1.0
    raw >= max       -> 1.0
    Knee 0.7 a `typical` lascia headroom per hit sopra-tipici.
    """
    lo, typ, hi = anchors.min, anchors.typical, anchors.max
    if raw <= lo:
        return 0.0
    if raw >= hi:
        return 1.0
    if raw < typ:
        return 0.7 * (raw - lo) / (typ - lo)
    return 0.7 + 0.3 * (raw - typ) / (hi - typ)


def _anchors_from(raw: dict, pattern_name: str) -> CalibrationAnchors:
    """Costruisce CalibrationAnchors validando min < typical < max."""
    cal = raw.get("calibration")
    if cal is None:
        raise KeyError(f"missing 'calibration' for pattern {pattern_name!r}")
    a = CalibrationAnchors(
        min=float(cal["min"]),
        typical=float(cal["typical"]),
        max=float(cal["max"]),
    )
    if not (a.min < a.typical < a.max):
        raise ValueError(
            f"invalid anchors for {pattern_name!r}: require min<typical<max, "
            f"got min={a.min} typical={a.typical} max={a.max}"
        )
    return a


def _build_pattern_config(raw: dict) -> PatternConfig:
    """Marshalling raw YAML -> PatternConfig nidificato.

    Solleva KeyError per chiavi mancanti, ValueError per ancore invalide.
    """
    required = [
        "hammer", "inverted_hammer", "shooting_star", "engulfing",
        "morning_star", "evening_star", "key_reversal", "inside_bar",
        "pin_bar", "doji",
    ]
    for key in required:
        if key not in raw:
            raise KeyError(f"missing pattern config: {key!r}")

    h = raw["hammer"]; hg = h["geometry"]
    hammer = HammerCfg(
        body_ratio_max=float(hg["body_ratio_max"]),
        lower_shadow_body_min=float(hg["lower_shadow_body_min"]),
        upper_shadow_range_max=float(hg["upper_shadow_range_max"]),
        calibration=_anchors_from(h, "hammer"),
    )

    ih = raw["inverted_hammer"]; ihg = ih["geometry"]
    inverted_hammer = InvertedHammerCfg(
        body_ratio_max=float(ihg["body_ratio_max"]),
        upper_shadow_body_min=float(ihg["upper_shadow_body_min"]),
        lower_shadow_range_max=float(ihg["lower_shadow_range_max"]),
        calibration=_anchors_from(ih, "inverted_hammer"),
    )

    ss = raw["shooting_star"]; ssg = ss["geometry"]
    shooting_star = ShootingStarCfg(
        body_ratio_max=float(ssg["body_ratio_max"]),
        upper_shadow_body_min=float(ssg["upper_shadow_body_min"]),
        lower_shadow_range_max=float(ssg["lower_shadow_range_max"]),
        calibration=_anchors_from(ss, "shooting_star"),
    )

    e = raw["engulfing"]; eg = e["geometry"]
    engulfing = EngulfingCfg(
        min_engulfment_ratio=float(eg["min_engulfment_ratio"]),
        min_body_ratio=float(eg["min_body_ratio"]),
        calibration=_anchors_from(e, "engulfing"),
    )

    ms = raw["morning_star"]; msg = ms["geometry"]
    morning_star = StarCfg(
        trend_body_min_ratio=float(msg["trend_body_min_ratio"]),
        star_body_max_ratio=float(msg["star_body_max_ratio"]),
        min_b3_penetration=float(msg["min_b3_penetration"]),
        calibration=_anchors_from(ms, "morning_star"),
    )

    es = raw["evening_star"]; esg = es["geometry"]
    evening_star = StarCfg(
        trend_body_min_ratio=float(esg["trend_body_min_ratio"]),
        star_body_max_ratio=float(esg["star_body_max_ratio"]),
        min_b3_penetration=float(esg["min_b3_penetration"]),
        calibration=_anchors_from(es, "evening_star"),
    )

    kr = raw["key_reversal"]; krg = kr["geometry"]
    key_reversal = KeyReversalCfg(
        min_extreme_break_pips=float(krg["min_extreme_break_pips"]),
        min_close_penetration_ratio=float(krg["min_close_penetration_ratio"]),
        calibration=_anchors_from(kr, "key_reversal"),
    )

    ib = raw["inside_bar"]; ibg = ib["geometry"]
    inside_bar = InsideBarCfg(
        max_compression_ratio=float(ibg["max_compression_ratio"]),
        calibration=_anchors_from(ib, "inside_bar"),
    )

    pb = raw["pin_bar"]; pbg = pb["geometry"]
    pin_bar = PinBarCfg(
        body_ratio_max=float(pbg["body_ratio_max"]),
        dominant_wick_ratio_min=float(pbg["dominant_wick_ratio_min"]),
        calibration=_anchors_from(pb, "pin_bar"),
    )

    dj = raw["doji"]; djg = dj["geometry"]
    doji = DojiCfg(body_tolerance=float(djg["body_tolerance"]))

    return PatternConfig(
        hammer=hammer, inverted_hammer=inverted_hammer, shooting_star=shooting_star,
        engulfing=engulfing, morning_star=morning_star, evening_star=evening_star,
        key_reversal=key_reversal, inside_bar=inside_bar, pin_bar=pin_bar, doji=doji,
    )


def load_pattern_config(path: str | Path | None = None) -> PatternConfig:
    """Carica PatternConfig da YAML.

    Precedenza: parametro `path` > env `PATTERNS_CONFIG_PATH` > DEFAULT_CONFIG_PATH.
    Solleva KeyError per pattern mancanti, ValueError per ancore invalide
    (min >= typical o typical >= max). Mirror di backtest.costs.load_cost_model.
    """
    if path is None:
        path = os.environ.get("PATTERNS_CONFIG_PATH") or DEFAULT_CONFIG_PATH
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return _build_pattern_config(raw)
