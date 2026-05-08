---
phase: 03-patterns-catalog
plan: 03
subsystem: patterns
tags: [patterns, detectors, calibration, scan, pattern-hit]
dependency_graph:
  requires:
    - 03-01 (PatternHit, PatternConfig, ShootingStarCfg, StarCfg, KeyReversalCfg, InsideBarCfg, _calibrate, load_pattern_config)
    - 03-02 (is_hammer/is_inverted_hammer/is_engulfing/is_pin_bar tuple-return + scan_patterns stub firma)
  provides:
    - is_shooting_star (matched, raw_score) -> tuple[bool, float]
    - is_morning_star (b1, b2, b3, cfg) -> tuple[bool, float]
    - is_evening_star (b1, b2, b3, cfg) -> tuple[bool, float]
    - is_key_reversal (prev, curr, direction, cfg) -> tuple[bool, float]
    - is_inside_bar (prev, curr, cfg) -> tuple[bool, float]
    - scan_patterns (bars, last_n, cfg) -> list[PatternHit] (full rebuild)
  affects:
    - patterns.py (5 nuovi detector + scan_patterns ricostruito)
    - tests/test_patterns.py (15 nuovi test + 2 skip rimossi)
tech-stack:
  added: []
  patterns:
    - tuple-return (matched, raw_score) coerente con Wave 2
    - guard rng<=0 / body<=0 -> (False, 0.0) (T-3-07 NaN propagation)
    - 3-bar star detectors anchored su b3 (NO look-ahead — Pitfall 3)
    - PatternHit emission con extreme_price = swing low (bullish) / swing high (bearish) lungo span
    - Inside Bar + Pin Bar coexist: 2 hit distinti (Pitfall 4)
    - Doji emesso con confidence=1.0 hardcoded (CONTEXT — non calibrato)
key-files:
  created:
    - .planning/phases/03-patterns-catalog/03-03-SUMMARY.md
  modified:
    - patterns.py
    - tests/test_patterns.py
decisions:
  - "scan_patterns emette PatternHit bar-by-bar in ordine deterministico (più vecchio -> più recente, tutti i pattern per la barra)"
  - "Inside Bar + Pin Bar emessi come 2 hit distinti su stessa barra (Pitfall 4)"
  - "Doji emesso con confidence=1.0 (hardcoded, non calibrato — CONTEXT)"
  - "Star detectors usano (b1,b2,b3) = (bars[i-2], bars[i-1], bars[i]); anchor=b3, nessun look-ahead"
  - "Key reversal usa midpoint(prev) come threshold di penetrazione close (raw = penetrazione/range_prev)"
  - "Inside bar raw = 1.0 - range_curr/range_prev (più compressione = score maggiore); direction='neutral'"
  - "extreme_price: bullish 1-bar=bar.low, bearish 1-bar=bar.high, 2-bar bullish=min(prev.low,curr.low), 2-bar bearish=max(prev.high,curr.high), 3-bar bullish=min(b1,b2,b3 lows), 3-bar bearish=max(b1,b2,b3 highs), neutral=midpoint(bar)"
metrics:
  duration: ~12 min
  completed: 2026-05-08
  tasks: 3
  files_changed: 2
  tests_added: 15
  tests_total_after: 402  # full suite + 1 skipped Mottl
---

# Phase 3 Plan 03: 5 nuovi detector + scan_patterns rebuild a list[PatternHit] Summary

PATT-02/04/05/06/07: completata Wave 3 di Phase 3. Implementati i 5 detector mancanti (`is_shooting_star`, `is_morning_star`, `is_evening_star`, `is_key_reversal`, `is_inside_bar`) tutti con firma `(matched: bool, raw_score: float)`, e ricostruita `scan_patterns` per restituire `list[PatternHit]` calibrati su tutti i 9 pattern + Doji. 15 nuovi test aggiunti (5 positivi + 5 near-miss + 1 bearish key_reversal + 4 scan_patterns coverage), 2 skip Wave 2 rimossi e riattivati con attribute access.

## Cosa è stato costruito

### Task 1 — 5 nuovi detector (commit `8753b12`)

Aggiunte 5 funzioni in `patterns.py` subito prima di `scan_patterns`:

- **`is_shooting_star(bar, cfg: ShootingStarCfg) -> tuple[bool, float]`** — mirror geometrico di inverted_hammer ma con soglie più stringenti (body_ratio_max=0.3 vs 0.4). raw_score = `upper_shadow / body`.
- **`is_morning_star(b1, b2, b3, cfg: StarCfg) -> tuple[bool, float]`** — pattern bullish 3-bar (Murphy ch.10): b1 bearish con body grande (>= trend_body_min_ratio*range1), b2 small body (<= star_body_max_ratio*range2), b3 bullish con close oltre midpoint(b1) (>= min_b3_penetration). raw_score = `(b3.close - mid_body_b1) / body_b1`. Anchor=b3, nessun look-ahead.
- **`is_evening_star(b1, b2, b3, cfg: StarCfg) -> tuple[bool, float]`** — speculare bearish.
- **`is_key_reversal(prev, curr, direction, cfg: KeyReversalCfg) -> tuple[bool, float]`** — outside reversal 2-bar. bullish: `curr.low < prev.low - min_extreme_break_pips` AND `curr.close > midpoint(prev)`; bearish simmetrico. raw_score = penetrazione del close oltre midpoint normalizzata su range_prev.
- **`is_inside_bar(prev, curr, cfg: InsideBarCfg) -> tuple[bool, float]`** — `curr.high <= prev.high AND curr.low >= prev.low` AND `range_curr / range_prev <= max_compression_ratio`. raw_score = `1.0 - range_curr/range_prev` (più compressione = score maggiore). Direction='neutral'.

Tutti guard `rng <= 0 or body <= 0 -> (False, 0.0)` (T-3-07). Star detectors guard su `b1`, `b2`, `b3` indipendentemente.

### Task 2 — scan_patterns rebuild (commit `9fbe21c`)

Sostituita integralmente la stub Wave 2 con full implementation:

- `scan_patterns(bars, last_n=5, cfg=None) -> list[PatternHit]`
- `cfg=None -> load_pattern_config()` lazy default (Wave 1 loader)
- Itera ultime `last_n` barre (`for i in range(start, n)` con `start = max(0, n - last_n)`)
- Per ogni `i`:
  - **1-bar** (sempre): `hammer`, `inverted_hammer`, `shooting_star`, `doji`, `pin_bar` (bull/bear)
  - **2-bar** (`i >= 1`): `engulfing` (bull/bear), `key_reversal` (bull/bear), `inside_bar`
  - **3-bar** (`i >= 2`): `morning_star`, `evening_star`
- `bar_index` = `i - n` (offset negativo, -1 = ultima barra)
- `extreme_price` deterministico per direction/span:
  - bullish 1-bar: `bar["low"]`
  - bearish 1-bar: `bar["high"]`
  - neutral 1-bar (doji): midpoint(bar)
  - 2-bar bullish: `min(prev.low, curr.low)`
  - 2-bar bearish: `max(prev.high, curr.high)`
  - 2-bar neutral (inside_bar): midpoint(curr)
  - 3-bar bullish (morning_star): `min(b1.low, b2.low, b3.low)`
  - 3-bar bearish (evening_star): `max(b1.high, b2.high, b3.high)`
- `span_bars` = 1 / 2 / 3 a seconda del pattern
- `confidence` via `_calibrate(raw, cfg.X.calibration)` per tutti tranne Doji (hardcoded `1.0`, CONTEXT)
- Inside Bar + Pin Bar coexist: 2 hit distinti su stessa barra (Pitfall 4)
- Ordine deterministico: bar-by-bar dall'indice più vecchio al più recente, tutti i pattern per quella barra prima di passare alla successiva

### Task 3 — 15 nuovi test + 2 skip rimossi (commit `dc7676a`)

`tests/test_patterns.py` esteso. **2 test riattivati** (rimossi `@pytest.mark.skip`): `test_scan_patterns_multiple`, `test_scan_patterns_respects_last_n` — già con attribute access (`.name`, `.bar_index`).

**15 nuovi test aggiunti:**

Positivi (5):
- `test_is_shooting_star_classic` — body=2 su range=30, upper=24, lower=4
- `test_is_morning_star_classic` — penetration=0.6 >= 0.5
- `test_is_evening_star_classic` — penetration=0.6 >= 0.5
- `test_is_key_reversal_bullish` — outside break + close 0.7 oltre midpoint
- `test_is_inside_bar_classic` — curr range=40 contenuto in prev range=100

Near-miss (5):
- `test_is_shooting_star_rejects_large_body`
- `test_is_morning_star_rejects_shallow_b3` — close < mid_b1
- `test_is_evening_star_rejects_shallow_b3` — close > mid_b1
- `test_is_key_reversal_rejects_no_penetration` — close < midpoint
- `test_is_inside_bar_rejects_overflow` — curr.high > prev.high

Bearish key_reversal (1):
- `test_is_key_reversal_bearish` — outside break al rialzo + close sotto midpoint

scan_patterns coverage (4):
- `test_scan_patterns_returns_pattern_hit` — tipo dataclass + accesso 6 campi
- `test_confidence_in_unit_interval` — `0.0 <= h.confidence <= 1.0` su fixture multi-pattern
- `test_inside_and_pin_coexist` — Pitfall 4: 2 hit distinti
- `test_morning_star_extreme_is_swing_low` — extreme_price = min(low) dei 3 bar

## Verifica

| Check | Risultato |
|-------|-----------|
| Smoke detector import (`is_shooting_star`, `is_morning_star`, `is_evening_star`, `is_key_reversal`, `is_inside_bar`) | OK |
| Smoke `scan_patterns` ritorna `list[PatternHit]` con confidence in [0,1] | OK (0 hit su flat bar) |
| `pytest tests/test_patterns.py -q` | 31 passed (era 14 + 2 skip) |
| `pytest tests/test_pattern_config.py -q` | 11 passed (regression Wave 1) |
| `pytest -q` (full suite) | 402 passed, 1 skipped (era 385 + 3 skipped) — delta atteso: +15 nuovi test, +2 skip riattivati |
| `grep -q "def is_shooting_star(bar: dict, cfg: ShootingStarCfg) -> tuple\[bool, float\]:" patterns.py` | OK |
| `grep -q "def is_morning_star(b1: dict, b2: dict, b3: dict, cfg: StarCfg) -> tuple\[bool, float\]:" patterns.py` | OK |
| `grep -q "def is_evening_star(b1: dict, b2: dict, b3: dict, cfg: StarCfg) -> tuple\[bool, float\]:" patterns.py` | OK |
| `grep -q "def is_key_reversal(" patterns.py` | OK |
| `grep -q "def is_inside_bar(" patterns.py` | OK |
| `grep -q "list\[PatternHit\]" patterns.py` | OK |
| `grep -c "PatternHit(" patterns.py` | 13 (>= 11 atteso: 1 dataclass + 12 emissioni nello scan, hammer/inverted_hammer/shooting_star/doji/pin_bar bull/pin_bar bear/engulfing bull/engulfing bear/key_reversal bull/key_reversal bear/inside_bar/morning_star/evening_star) |
| `! grep -q "STUB" patterns.py` | OK (stub Wave 2 rimosso) |
| `! grep -E "bars\[i\s*\+\s*[0-9]" patterns.py` | OK (no future leakage) |
| `! grep -q "@pytest.mark.skip" tests/test_patterns.py` | OK (0 skip residui) |
| `grep -c "def test_" tests/test_patterns.py` | 31 (>= 27 atteso) |

## Truth-set verifica (must_haves dal plan)

- [x] Five new detectors implemented: is_shooting_star, is_morning_star, is_evening_star, is_key_reversal, is_inside_bar — tutti `(matched, raw_score)` tuple return
- [x] scan_patterns(bars, last_n, cfg) returns list[PatternHit] covering all 9 patterns + Doji
- [x] Each PatternHit has correct extreme_price (swing low for bullish, swing high for bearish over span)
- [x] span_bars: 1 (single-bar) | 2 (engulfing, key_reversal, inside_bar) | 3 (stars)
- [x] Doji emits PatternHit with confidence=1.0 and direction='neutral' when matched
- [x] Inside Bar + Pin Bar coexist: a bar matching both emits 2 distinct PatternHit entries (`test_inside_and_pin_coexist` PASSED)
- [x] Each new detector has hand-crafted positive + near-miss negative test
- [x] All confidence values in [0.0, 1.0] (`test_confidence_in_unit_interval` PASSED)

## Deviations from Plan

None — piano eseguito esattamente come scritto. Note operative:
- Task 1 e Task 2 implementati in due commit distinti (atomic per task) come da protocollo, anche se concettualmente legati (Task 2 dipende dai detector di Task 1). La sequenza commit è: `8753b12` (5 detector + scan_patterns ancora stub) → `9fbe21c` (scan_patterns full rebuild) → `dc7676a` (test).
- `_tmp_write_05.py` (untracked artifact da MCP planning di Phase 6) lasciato intatto: out of scope.

## Threat surface scan

Nessun threat flag introdotto. T-3-07 (NaN propagation in 5 nuovi detector) mitigato come da plan: guard `rng <= 0 or body <= 0 -> (False, 0.0)` esteso a tutti i 5; per star detectors guard su b1, b2, b3 indipendentemente. T-3-08 (Information Disclosure) e T-3-09 (DoS) accettati: scan_patterns è pure function, last_n controllato dal chiamante interno (strategy.py).

## Note di handoff per 03-04

- **`patterns.py` ora completo per Phase 3**: 9 detector calibrati con tuple-return + Doji bool-only + scan_patterns che restituisce `list[PatternHit]`. PATT-01..07 implementati end-to-end nella patterns layer.
- **`strategy.py:229` callsite ANCORA ROTTO**: lo stub di scan_patterns Wave 2 ha mascherato la rottura (lista vuota → no crash); ora lo scan ritorna PatternHit con attribute access (`.direction`), ma strategy.py:229 chiama `any(p["direction"] == ...)` (subscript access). 03-04 chiude il refactor:
  - Aggiornare `strategy.py:229` (e callsite analoghi) a `p.direction` invece di `p["direction"]`
  - Iniettare `cfg: PatternConfig` una volta sola in inizializzazione (D-19 — `load_pattern_config()` non chiamato dentro hot path)
  - Eventuali altri callsite che assumono dict (cercare `scan_patterns(`)
- **Test strategy regression**: la suite globale (402 passed) include i test strategy che usano `scan_patterns` indirettamente; nessuna failure rilevata in questo piano. Il fix per `strategy.py` è demandato a 03-04 e prevedibile (refactor dict→attribute deterministico).
- **Geometria conservata**: i 5 nuovi detector seguono RESEARCH.md verbatim; le formule raw_score sono quelle della tabella "Per-pattern raw-score formula" (RESEARCH lines 478-490). Anchor `b3` per stars, `curr` per key_reversal/inside_bar, `bar` per single-bar.
- **Calibration anchors `inside_bar`**: range YAML attuale `min=0.1, typical=0.4, max=0.7` mappa raw=0.6 (compressione 60%) → confidence 0.7 + 0.3*(0.6-0.4)/0.3 ≈ 0.9. Coerente con expected del test `test_is_inside_bar_classic` (raw = 1 - 40/100 = 0.6).
- **`test_morning_star_extreme_is_swing_low`** verifica `h.extreme_price == 1.0985`: questo è `b2.low` (=`min(b1.low=1.0990, b2.low=1.0985, b3.low=1.0998)`), conferma che lo scan calcola il vero min dei 3 lows (non solo l'anchor).

## Self-Check: PASSED

Verificato con git e filesystem:
- `patterns.py` FOUND (5 nuovi detector + scan_patterns rebuild + tutti gli helper Wave 1/2 preservati)
- `tests/test_patterns.py` FOUND (31 test attivi, 0 skip)
- `.planning/phases/03-patterns-catalog/03-03-SUMMARY.md` FOUND
- Commit `8753b12` (Task 1 — 5 nuovi detector) FOUND
- Commit `9fbe21c` (Task 2 — scan_patterns rebuild) FOUND
- Commit `dc7676a` (Task 3 — 15 nuovi test + skip removal) FOUND
- `pytest tests/test_patterns.py -q`: 31 passed
- `pytest tests/test_pattern_config.py -q`: 11 passed (regression Wave 1)
- `pytest -q` full suite: 402 passed, 1 skipped (Mottl optional)
- Smoke import 5 detector: OK
- Smoke scan_patterns ritorna list[PatternHit] con confidence in [0,1]: OK
