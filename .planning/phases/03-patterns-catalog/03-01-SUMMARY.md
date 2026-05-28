---
phase: 03-patterns-catalog
plan: 01
subsystem: patterns
tags: [patterns, config, calibration, dataclass, foundation]
dependency_graph:
  requires: []
  provides:
    - PatternHit
    - PatternConfig
    - CalibrationAnchors
    - HammerCfg
    - InvertedHammerCfg
    - ShootingStarCfg
    - EngulfingCfg
    - StarCfg
    - KeyReversalCfg
    - InsideBarCfg
    - PinBarCfg
    - DojiCfg
    - _calibrate
    - load_pattern_config
    - DEFAULT_CONFIG_PATH
  affects:
    - patterns.py (extension only — existing detectors untouched)
tech-stack:
  added:
    - PyYAML (already installed via Phase 1; reused)
  patterns:
    - frozen dataclass schema (mirror backtest/costs.py)
    - YAML safe_load + path precedence (param > env > default)
    - piecewise-linear calibration with 0.7 knee at typical
key-files:
  created:
    - config/patterns.yaml
    - tests/test_pattern_config.py
  modified:
    - patterns.py
    - .env.example
decisions:
  - "PatternHit fields fixed at 6: name, bar_index, span_bars, extreme_price, confidence, direction"
  - "Calibration knee 0.7 at typical anchor — lascia headroom 0.3 per hit sopra-tipici"
  - "yaml.safe_load (T-3-01 mitigation) e validazione min<typical<max (T-3-02 mitigation)"
  - "Path precedence: parametro esplicito > env PATTERNS_CONFIG_PATH > DEFAULT_CONFIG_PATH"
  - "Detector booleani esistenti (is_hammer/is_inverted_hammer/is_engulfing/is_doji/is_pin_bar/scan_patterns) intoccati — refactor demandato a 03-02/03-03"
metrics:
  duration: ~10 min
  completed: 2026-05-08
  tasks: 3
  files_changed: 4
  tests_added: 11
  tests_total_after: 385
---

# Phase 3 Plan 01: PatternHit + frozen config + calibration anchors + YAML loader Summary

PATT-07 foundation: schema `PatternHit` immutabile, gerarchia `PatternConfig` nidificata e frozen, helper `_calibrate` con knee a 0.7, loader `load_pattern_config` che legge `config/patterns.yaml` via `yaml.safe_load` con precedenza param > env > default — il tutto AGGIUNTO a `patterns.py` senza toccare i 5 detector booleani esistenti.

## Cosa è stato costruito

### Task 1 — `config/patterns.yaml` (commit `3c465c1`)
File YAML con 10 chiavi top-level: 9 pattern calibrati (`hammer`, `inverted_hammer`, `shooting_star`, `engulfing`, `morning_star`, `evening_star`, `key_reversal`, `inside_bar`, `pin_bar`) ognuno con `geometry:` + `calibration:` (`min`, `typical`, `max`), più `doji` con sola `geometry.body_tolerance=0.1`. Valori da `03-RESEARCH.md` (lines 572-667), Phase 5 li ri-tarerà empiricamente sui dati storici.

### Task 2 — Estensione `patterns.py` (commit `4b1a2fa`)
- 11 dataclass `@dataclass(frozen=True)`: `CalibrationAnchors`, `HammerCfg`, `InvertedHammerCfg`, `ShootingStarCfg`, `EngulfingCfg`, `StarCfg`, `KeyReversalCfg`, `InsideBarCfg`, `PinBarCfg`, `DojiCfg`, `PatternConfig`, `PatternHit` (12 totali — `grep -c "@dataclass(frozen=True)" patterns.py` = 12).
- `_calibrate(raw, anchors) -> float`: piecewise-linear in 4 rami (raw≤min→0.0; min<raw<typ→0.7·(raw-lo)/(typ-lo); typ≤raw<max→0.7+0.3·(raw-typ)/(hi-typ); raw≥max→1.0).
- `_anchors_from`: factory `CalibrationAnchors` con validazione `min < typical < max` (ValueError fail-closed).
- `_build_pattern_config`: marshalling dict→`PatternConfig` con check chiavi mancanti (KeyError).
- `load_pattern_config(path=None)`: precedenza `param` > `os.environ['PATTERNS_CONFIG_PATH']` > `DEFAULT_CONFIG_PATH = Path("config/patterns.yaml")`. Mirror struttura di `backtest.costs.load_cost_model`.
- Sicurezza: `yaml.safe_load` (T-3-01); validazione ancore (T-3-02).
- Geometry helpers (`_body`, `_range`, `_upper_shadow`, `_lower_shadow`, `_is_bullish`, `_is_bearish`) e detector booleani esistenti (`is_hammer`, `is_inverted_hammer`, `is_engulfing`, `is_doji`, `is_pin_bar`, `scan_patterns`) **completamente intoccati**.

### Task 3 — Test loader/calibrazione + env (commit `0768112`)
- `tests/test_pattern_config.py` con 11 test:
  1. `test_load_pattern_config_default` — carica `config/patterns.yaml`
  2. `test_load_pattern_config_param_path` — path esplicito su tmp_path
  3. `test_load_config_param_overrides_env` — parametro vince su env
  4. `test_load_config_env_override` — env letto quando path=None
  5. `test_load_config_invalid_anchors_raises` — min==typical → ValueError("hammer")
  6. `test_load_config_missing_pattern_raises` — chiave hammer assente → KeyError
  7. `test_load_config_empty_yaml_raises` — YAML vuoto → KeyError
  8. `test_pattern_config_frozen` — FrozenInstanceError su mutazione (top + nested)
  9. `test_pattern_hit_frozen_schema` — 6 campi + `hash(h)` ok + frozen
  10. `test_calibrate_boundaries` — sotto min, esatto min/typ/max, sopra max, mid_lower=0.35
  11. `test_calibrate_monotonic` — 101 punti uniformi non-decrescenti
- `.env.example` documenta `PATTERNS_CONFIG_PATH` (commentato, opzionale)

## Verifica

| Check | Risultato |
|-------|-----------|
| `python -c "import yaml; yaml.safe_load(open('config/patterns.yaml',encoding='utf-8'))"` | OK (10 chiavi) |
| `python -c "from patterns import PatternHit, PatternConfig, _calibrate, load_pattern_config; ..."` | OK (boundary 0/0.7/1) |
| `pytest tests/test_pattern_config.py -q` | 11 passed |
| `pytest tests/test_patterns.py -q` (regression detector esistenti) | 14 passed |
| `pytest -q` (full suite) | 385 passed, 1 skipped |
| `grep -c "@dataclass(frozen=True)" patterns.py` | 12 (>=11 atteso) |
| `grep -q "yaml.safe_load" patterns.py` | OK |
| `grep -q "PATTERNS_CONFIG_PATH" patterns.py` | OK |
| `grep -q "def is_hammer(bar: dict) -> bool:" patterns.py` | OK (intoccato) |
| `grep -q "def scan_patterns" patterns.py` | OK (intoccato) |

## Truth-set verifica (must_haves dal plan)

- [x] PatternHit dataclass exists, frozen, hashable, with all 6 fields
- [x] PatternConfig + nested per-pattern sub-cfgs + CalibrationAnchors are frozen dataclasses
- [x] load_pattern_config() reads config/patterns.yaml via yaml.safe_load and returns frozen PatternConfig
- [x] _calibrate(raw, anchors) maps raw geometry score to [0,1] with 0.7 knee at typical anchor
- [x] Config loader validates min < typical < max per pattern, raising ValueError on violation
- [x] Parameter > PATTERNS_CONFIG_PATH env var > default precedence works

## Deviations from Plan

None — plan executed exactly as written. `_tmp_write_05.py` (untracked artifact da MCP planning di Phase 6) lasciato intatto: out of scope.

## Threat surface scan

Nessun threat flag introdotto: `T-3-01` (yaml.safe_load) e `T-3-02` (validazione ancore) mitigati come da plan; `T-3-03` accettato (uso solo dev/CI con file in repo); `T-3-04` accettato (file <5KB).

## Note di handoff per 03-02 / 03-03 / 03-04

- `patterns.py` ora espone API stratificata: detector booleani legacy + dataclass schema + loader. I piani successivi (03-02/03-03) refactorizzeranno i detector da `bool` a `(matched, raw_score)` tupla e useranno `_calibrate` per mappare raw→confidence.
- `DEFAULT_CONFIG_PATH = Path("config/patterns.yaml")` è relativo al CWD del processo. I callsite (`strategy.py`) dovranno chiamare `load_pattern_config()` una volta sola in inizializzazione (D-19) e passare `PatternConfig` ai detector.
- `PatternHit.bar_index` usa convenzione offset negativo (-1 = ultima bar) in linea con `scan_patterns` esistente.
- `span_bars` ∈ {1, 2, 3}: 1 single-bar (hammer/pin_bar/doji/inside_bar/shooting_star/inverted_hammer), 2 (engulfing/key_reversal), 3 (morning_star/evening_star).

## Self-Check: PASSED

Verificato con git e filesystem:
- `config/patterns.yaml` FOUND
- `tests/test_pattern_config.py` FOUND
- `patterns.py` FOUND (esteso, detector legacy preservati)
- `.env.example` FOUND (PATTERNS_CONFIG_PATH presente)
- Commit `3c465c1` (Task 1) FOUND
- Commit `4b1a2fa` (Task 2) FOUND
- Commit `0768112` (Task 3) FOUND
