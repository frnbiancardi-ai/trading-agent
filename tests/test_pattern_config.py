"""Test loader PatternConfig + helper _calibrate (Phase 3, PATT-07)."""
from __future__ import annotations
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from patterns import (
    CalibrationAnchors,
    PatternConfig,
    PatternHit,
    _calibrate,
    load_pattern_config,
)


VALID_YAML = """
hammer:
  geometry:
    body_ratio_max: 0.4
    lower_shadow_body_min: 2.0
    upper_shadow_range_max: 0.2
  calibration: {min: 2.0, typical: 3.5, max: 6.0}
inverted_hammer:
  geometry:
    body_ratio_max: 0.4
    upper_shadow_body_min: 2.0
    lower_shadow_range_max: 0.2
  calibration: {min: 2.0, typical: 3.5, max: 6.0}
shooting_star:
  geometry:
    body_ratio_max: 0.3
    upper_shadow_body_min: 2.0
    lower_shadow_range_max: 0.15
  calibration: {min: 2.0, typical: 3.5, max: 6.0}
engulfing:
  geometry:
    min_engulfment_ratio: 1.0
    min_body_ratio: 0.3
  calibration: {min: 1.0, typical: 1.5, max: 2.5}
morning_star:
  geometry:
    trend_body_min_ratio: 0.6
    star_body_max_ratio: 0.3
    min_b3_penetration: 0.5
  calibration: {min: 0.5, typical: 0.8, max: 1.2}
evening_star:
  geometry:
    trend_body_min_ratio: 0.6
    star_body_max_ratio: 0.3
    min_b3_penetration: 0.5
  calibration: {min: 0.5, typical: 0.8, max: 1.2}
key_reversal:
  geometry:
    min_extreme_break_pips: 0.0
    min_close_penetration_ratio: 0.5
  calibration: {min: 0.5, typical: 0.75, max: 1.0}
inside_bar:
  geometry:
    max_compression_ratio: 0.9
  calibration: {min: 0.1, typical: 0.4, max: 0.7}
pin_bar:
  geometry:
    body_ratio_max: 0.333
    dominant_wick_ratio_min: 0.667
  calibration: {min: 0.667, typical: 0.75, max: 0.9}
doji:
  geometry:
    body_tolerance: 0.1
"""


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "patterns.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_pattern_config_default():
    """Default path config/patterns.yaml deve caricarsi senza errori."""
    cfg = load_pattern_config()
    assert isinstance(cfg, PatternConfig)
    assert cfg.hammer.calibration.typical == 3.5
    assert cfg.engulfing.min_engulfment_ratio == 1.0
    assert cfg.doji.body_tolerance == 0.1


def test_load_pattern_config_param_path(tmp_path):
    p = _write_yaml(tmp_path, VALID_YAML)
    cfg = load_pattern_config(p)
    assert cfg.hammer.body_ratio_max == 0.4
    assert cfg.morning_star.calibration.max == 1.2


def test_load_config_param_overrides_env(tmp_path, monkeypatch):
    """Parametro path > env PATTERNS_CONFIG_PATH."""
    good = _write_yaml(tmp_path, VALID_YAML)
    monkeypatch.setenv("PATTERNS_CONFIG_PATH", "/nonexistent/should_be_ignored.yaml")
    cfg = load_pattern_config(good)  # parametro vince
    assert isinstance(cfg, PatternConfig)


def test_load_config_env_override(tmp_path, monkeypatch):
    """Quando path=None, env PATTERNS_CONFIG_PATH viene letto."""
    p = _write_yaml(tmp_path, VALID_YAML)
    monkeypatch.setenv("PATTERNS_CONFIG_PATH", str(p))
    cfg = load_pattern_config(path=None)
    assert cfg.pin_bar.dominant_wick_ratio_min == 0.667


def test_load_config_invalid_anchors_raises(tmp_path):
    """min == typical viola min<typical<max -> ValueError."""
    bad = VALID_YAML.replace(
        "calibration: {min: 2.0, typical: 3.5, max: 6.0}",
        "calibration: {min: 3.5, typical: 3.5, max: 6.0}",
        1,
    )
    p = _write_yaml(tmp_path, bad)
    with pytest.raises(ValueError, match="hammer"):
        load_pattern_config(p)


def test_load_config_missing_pattern_raises(tmp_path):
    """YAML senza chiave 'hammer' -> KeyError."""
    # ricostruzione minima senza hammer (rimuove tutto fino a inverted_hammer)
    bad_yaml = VALID_YAML.split("inverted_hammer", 1)[1]
    bad_yaml = "inverted_hammer" + bad_yaml
    p = _write_yaml(tmp_path, bad_yaml)
    with pytest.raises(KeyError, match="hammer"):
        load_pattern_config(p)


def test_load_config_empty_yaml_raises(tmp_path):
    """File vuoto -> KeyError (nessun pattern presente)."""
    p = _write_yaml(tmp_path, "")
    with pytest.raises(KeyError):
        load_pattern_config(p)


def test_pattern_config_frozen(tmp_path):
    p = _write_yaml(tmp_path, VALID_YAML)
    cfg = load_pattern_config(p)
    with pytest.raises(FrozenInstanceError):
        cfg.hammer = None  # type: ignore[misc]
    # nested dataclass anche frozen
    with pytest.raises(FrozenInstanceError):
        cfg.hammer.calibration.min = 99.0  # type: ignore[misc]


def test_pattern_hit_frozen_schema():
    h = PatternHit(
        name="hammer", bar_index=-1, span_bars=1,
        extreme_price=1.0980, confidence=0.7, direction="bullish",
    )
    assert h.name == "hammer"
    assert h.span_bars == 1
    assert hash(h) is not None  # frozen -> hashable
    with pytest.raises(FrozenInstanceError):
        h.confidence = 0.9  # type: ignore[misc]


def test_calibrate_boundaries():
    a = CalibrationAnchors(min=2.0, typical=3.5, max=6.0)
    assert _calibrate(1.0, a) == 0.0          # sotto min
    assert _calibrate(2.0, a) == 0.0          # esatto min
    assert abs(_calibrate(3.5, a) - 0.7) < 1e-9  # typical
    assert _calibrate(6.0, a) == 1.0          # esatto max
    assert _calibrate(10.0, a) == 1.0         # sopra max
    # punto intermedio sotto typical: lineare 0 -> 0.7
    mid_lower = _calibrate(2.75, a)  # (2.75-2)/(3.5-2) * 0.7 = 0.35
    assert abs(mid_lower - 0.35) < 1e-9


def test_calibrate_monotonic():
    a = CalibrationAnchors(min=2.0, typical=3.5, max=6.0)
    xs = [2.0 + i * (6.0 - 2.0) / 100 for i in range(101)]
    ys = [_calibrate(x, a) for x in xs]
    for prev, curr in zip(ys, ys[1:]):
        assert curr >= prev - 1e-12, f"non-monotonic: {prev} -> {curr}"
    assert ys[0] == 0.0
    assert ys[-1] == 1.0
