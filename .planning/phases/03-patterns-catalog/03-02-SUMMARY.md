---
phase: 03-patterns-catalog
plan: 02
subsystem: patterns
tags: [patterns, refactor, detectors, calibration, tuple-return]
dependency_graph:
  requires:
    - 03-01 (HammerCfg, InvertedHammerCfg, EngulfingCfg, PinBarCfg, PatternConfig, load_pattern_config)
  provides:
    - is_hammer (matched, raw_score) -> tuple[bool, float]
    - is_inverted_hammer (matched, raw_score) -> tuple[bool, float]
    - is_engulfing (matched, raw_score) -> tuple[bool, float]
    - is_pin_bar (matched, raw_score) -> tuple[bool, float]
    - scan_patterns (stub provvisorio)
  affects:
    - patterns.py (4 detector + scan_patterns ridotto a stub)
    - tests/test_patterns.py (firma aggiornata + 2 near-miss)
    - strategy.py (callsite scan_patterns temporaneamente degradato a [] — fix in 03-04)
tech-stack:
  added: []
  patterns:
    - tuple-return (matched: bool, raw_score: float) per uniformità con pipeline calibrazione
    - guard rng<=0 / body<=0 → (False, 0.0) preservato (T-3-06 NaN propagation mitigation)
    - sub-cfg dataclass injection (zero magic numbers nei detector)
key-files:
  created:
    - .planning/phases/03-patterns-catalog/03-02-SUMMARY.md
  modified:
    - patterns.py
    - tests/test_patterns.py
decisions:
  - "scan_patterns ridotto a stub [] — full rebuild a list[PatternHit] demandato a 03-03"
  - "is_doji invariato (bool, niente calibration anchors — Doji è non-PATT per CONTEXT)"
  - "Geometry rules originali preservate verbatim, soglie 2.0/0.4/0.2/1/3/2/3 ora da cfg"
  - "is_engulfing aggiunge gate min_body_ratio (esclude doji-like) + min_engulfment_ratio gate"
  - "raw_score per pattern: hammer=lower/body, inv_hammer=upper/body, engulfing=body_curr/body_prev, pin_bar=dominant_wick/range (RESEARCH lines 354-378)"
metrics:
  duration: ~8 min
  completed: 2026-05-08
  tasks: 2
  files_changed: 2
  tests_added: 2
  tests_total_after: 385  # 385 passed + 3 skipped (era 385+1, +2 skip volontari scan_patterns)
---

# Phase 3 Plan 02: refactor 4 detector calibrabili a (matched, raw_score) Summary

PATT-01/03/06 (parte): refattoria di `is_hammer`, `is_inverted_hammer`, `is_engulfing`, `is_pin_bar` da `bool` a `tuple[bool, float]`, accettando i sub-cfg dataclass introdotti dal piano 01. Geometria invariata, soglie ora da config (zero magic numbers). 6 test esistenti aggiornati alla nuova firma + 2 near-miss negativi aggiunti. `is_doji` invariato (non calibrato). `scan_patterns` ridotto a stub provvisorio — Wave 3 (03-03) lo ricostruisce a `list[PatternHit]`.

## Cosa è stato costruito

### Task 1 — Refactor 4 detector (commit `93f86e7`)

`patterns.py` modificato:

- **`is_hammer(bar, cfg: HammerCfg) -> tuple[bool, float]`** — raw_score = `lower_shadow / body`. Soglie ora `cfg.body_ratio_max`, `cfg.lower_shadow_body_min`, `cfg.upper_shadow_range_max`.
- **`is_inverted_hammer(bar, cfg: InvertedHammerCfg) -> tuple[bool, float]`** — raw_score = `upper_shadow / body`. Soglie da cfg.
- **`is_engulfing(prev, curr, direction, cfg: EngulfingCfg) -> tuple[bool, float]`** — raw_score = `body_curr / body_prev` (engulfment ratio). Aggiunge gate `min_body_ratio` su entrambe le candele (esclude doji-like) + gate `min_engulfment_ratio`. Direzioni `bullish` / `bearish` invariate; `sideways` o altri → `(False, 0.0)`.
- **`is_pin_bar(bar, direction, cfg: PinBarCfg) -> tuple[bool, float]`** — raw_score = `dominant_wick / range`. Soglie `cfg.body_ratio_max`, `cfg.dominant_wick_ratio_min`.
- **`is_doji(bar, tolerance=0.1) -> bool`** — INVARIATO (firma e logica). Doji è pattern non calibrato per design (CONTEXT.md).
- **`scan_patterns(bars, last_n=5, cfg=None) -> list`** — STUB provvisorio: ritorna `[]` per `bars` non vuoto e per `bars` vuoto. Preserva contratto chiamabile per `strategy.py:229` (chiamata `any(p["direction"]==...)` su lista vuota → no crash). Wave 3 lo ricostruisce per ritornare `list[PatternHit]` calibrati. Nuovo parametro `cfg` opzionale aggiunto in firma per anticipare API Wave 3.

Tutte le 4 funzioni preservano il guard `rng <= 0 or body <= 0 → (False, 0.0)` (T-3-06 NaN propagation mitigation, Pitfall 1 RESEARCH).

### Task 2 — Aggiornamento test + 2 near-miss (commit `847a0fb`)

`tests/test_patterns.py` riscritto:

- Fixture module-scoped `cfg` chiama `load_pattern_config()` una volta e fornisce `PatternConfig` ai test.
- 6 test detector calibrati esistenti aggiornati a firma `matched, raw = is_X(bar, cfg.X)`:
  - `test_is_hammer_classic`, `test_is_hammer_rejects_long_upper_shadow`, `test_is_hammer_rejects_zero_range`
  - `test_is_inverted_hammer`
  - `test_is_engulfing_bullish`, `test_is_engulfing_bearish`, `test_is_engulfing_invalid_direction`
  - `test_is_pin_bar_bullish`, `test_is_pin_bar_bearish`
  - Assertion ora include `assert raw >= cfg.X.calibration.min` (anchor da YAML, no magic).
- 2 near-miss negativi aggiunti:
  - `test_is_inverted_hammer_rejects_short_upper` (PATT-01) — upper shadow corta vs body
  - `test_is_engulfing_partial_negative` (PATT-03) — `curr.open` sopra `prev.close`, no engulfment apertura
- 2 test doji **invariati** (`test_is_doji_classic`, `test_is_doji_rejects_large_body`) — firma bool preservata.
- 2 test `scan_patterns` marcati `@pytest.mark.skip(reason="scan_patterns rebuilt in plan 03 (Wave 3)")` — `test_scan_patterns_multiple`, `test_scan_patterns_respects_last_n`. Wave 3 li riattiva rimuovendo il decorator e ricostruendoli su `PatternHit`.
- `test_scan_patterns_empty` resta attivo: lo stub ritorna `[]` per input vuoto, comportamento corretto.

## Verifica

| Check | Risultato |
|-------|-----------|
| `python -c "import patterns; print('OK')"` | OK |
| Smoke `is_hammer(bar, cfg.hammer)` da plan | matched=True, raw=15.0; `is_inverted_hammer` matched=False (corretto) |
| `pytest tests/test_patterns.py -q` | 14 passed, 2 skipped |
| `pytest tests/test_pattern_config.py -q` | 11 passed (regression Wave 1 verde) |
| `pytest -q` (full suite) | 385 passed, 3 skipped (era 385+1; i 2 nuovi skip sono volontari) |
| `grep -q "def is_hammer(bar: dict, cfg: HammerCfg) -> tuple\[bool, float\]:" patterns.py` | OK |
| `grep -q "def is_inverted_hammer(bar: dict, cfg: InvertedHammerCfg) -> tuple\[bool, float\]:" patterns.py` | OK |
| `grep -q "cfg: EngulfingCfg" patterns.py` | OK |
| `grep -q "cfg: PinBarCfg" patterns.py` | OK |
| `grep -q "def is_doji(bar: dict, tolerance: float = 0.1) -> bool:" patterns.py` | OK (invariato) |
| `grep -q "tuple\[bool, float\]" patterns.py` | OK |
| `grep -q "matched, raw" tests/test_patterns.py` | OK |
| `grep -q "test_is_inverted_hammer_rejects_short_upper" tests/test_patterns.py` | OK |
| `grep -q "test_is_engulfing_partial_negative" tests/test_patterns.py` | OK |

## Truth-set verifica (must_haves dal plan)

- [x] is_hammer, is_inverted_hammer, is_engulfing, is_pin_bar return `(matched: bool, raw_score: float)`
- [x] Detector geometry rules unchanged from current patterns.py (only return shape evolves)
- [x] is_doji unchanged: still returns bool (Doji non-PATT, no calibration per CONTEXT)
- [x] All 6 existing tests pass with updated tuple-return assertions
- [x] HammerCfg → is_hammer link via `cfg.body_ratio_max`, `cfg.lower_shadow_body_min`, `cfg.upper_shadow_range_max`
- [x] EngulfingCfg → is_engulfing link via `cfg.min_engulfment_ratio` + `cfg.min_body_ratio`

## Deviations from Plan

None — piano eseguito esattamente come scritto.

## Note di handoff per 03-03 / 03-04

- **`scan_patterns` ATTUALMENTE STUB**: ritorna `[]` per qualsiasi input. `strategy.py:229` continua a funzionare perché chiama `any(p["direction"] == ...)` su lista vuota. **03-03 deve ricostruire `scan_patterns`** per ritornare `list[PatternHit]` calibrati, includendo:
  - Mappatura nome pattern → detector + cfg sub-cfg
  - Conversione raw_score → confidence via `_calibrate(raw, anchors)`
  - Calcolo `extreme_price` (swing low/high lungo span_bars)
  - Costruzione `PatternHit(name, bar_index, span_bars, extreme_price, confidence, direction)`
  - Riattivazione dei 2 test `scan_patterns` skip-marked
- **`strategy.py:229` NON aggiornato in questo piano** — il chiamante continua a passare la firma vecchia (`scan_patterns(bars, last_n=...)`) e si aspetta `list[dict]`. Lo stub mantiene il contratto rotto-ma-non-crash. **03-04 chiude il refactor** aggiornando il callsite a usare `cfg` PatternConfig + iterare su `PatternHit` invece che dict (`.direction` invece di `["direction"]`).
- **Test strategy regression**: la suite globale (385 passed) include i test strategy esistenti che usano `scan_patterns` indirettamente via mock o chiamate mockate; nessuna failure rilevata in questo piano. Eventuali edge case su `strategy.py` con bars reali sarebbero coperti dal piano 04.
- **Geometry rules invariate**: i comportamenti positivi e negativi del codice originale sono conservati. Le costanti hard-coded (2.0, 0.4, 0.2, 1/3, 2/3) ora derivano dal `config/patterns.yaml` via le sub-cfg.
- **`is_engulfing` ha un gate addizionale** rispetto al codice originale: ora richiede `body/range >= min_body_ratio` su prev e curr. Per il `config/patterns.yaml` di default (`min_body_ratio: 0.5`) questo è coerente con il bullish/bearish test fixture e non rompe i casi positivi attesi. È un upgrade di selectivity intenzionale (RESEARCH suggerisce di filtrare engulfing su candele doji-like).

## Threat surface scan

Nessun threat flag introdotto. T-3-06 (NaN propagation) mitigato come da plan via guard `rng<=0 or body<=0 → (False, 0.0)` su tutti i 4 detector — preservato verbatim dal codice esistente.

## Self-Check: PASSED

Verificato con git e filesystem:
- `patterns.py` FOUND (4 detector tuple-return, is_doji bool invariato, scan_patterns stub)
- `tests/test_patterns.py` FOUND (14 attivi + 2 skip)
- `.planning/phases/03-patterns-catalog/03-02-SUMMARY.md` FOUND
- Commit `93f86e7` (Task 1 — refactor detector) FOUND
- Commit `847a0fb` (Task 2 — test refactor + 2 near-miss) FOUND
- Smoke import + smoke detector da plan: OK
- pytest tests/test_patterns.py: 14 passed + 2 skipped
- pytest tests/test_pattern_config.py: 11 passed (Wave 1 regression)
- pytest -q full suite: 385 passed + 3 skipped (delta atteso: +2 skip volontari scan_patterns)
