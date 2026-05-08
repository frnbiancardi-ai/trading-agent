---
phase: 03-patterns-catalog
verified: 2026-05-08T00:00:00Z
status: passed
score: 3/3 must-haves verificati (ROADMAP SC) + 7/7 PATT-01..07 SATISFIED
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 3: Patterns Catalog — Verification Report

**Phase Goal:** Sostituire il `patterns.py` minimale con un catalog candlestick completo (Hammer, Shooting Star, Engulfing, Morning/Evening Star, Key Reversal, Inside Bar, Pin Bar) che ritorni anchor structurali consumabili da Setup B e ML features.

**Verified:** 2026-05-08
**Status:** PASSED
**Re-verification:** No — initial verification
**Final commit:** `f008a35` (docs 03-04 phase complete)

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Ogni pattern detector ha unit test con caso positivo hand-crafted AND caso near-miss negativo | ✓ VERIFIED | `tests/test_patterns.py` 31 test, 9 detector con coppia positivo+near-miss (vedi tabella sotto). 42 passed totali (31 patterns + 11 config) in 0.31s. |
| 2 | Pattern catalog ritorna list[PatternHit] con `name`, `bar_index`, `extreme_price`, `confidence` (0–1), `direction` | ✓ VERIFIED | `patterns.py:99-115` definisce `@dataclass(frozen=True) PatternHit` con 6 campi (`name`, `bar_index`, `span_bars`, `extreme_price`, `confidence`, `direction`). Smoke runtime: `scan_patterns(bars, last_n=5, cfg=cfg)` ritorna list[PatternHit] e `confidence ∈ [0,1]` (test `test_confidence_in_unit_interval`). Bonus: aggiunto `span_bars` (1/2/3) per ML feature engineering futura. |
| 3 | Caller esistenti `scan_patterns()` in `strategy.py` continuano a funzionare (signature retro-compatibile o adapter shim con deprecation note) | ✓ VERIFIED | `strategy.py:32` import nuovo `from patterns import scan_patterns, load_pattern_config`; `strategy.py:163` `self._pattern_cfg = load_pattern_config()` (cached at __init__); `strategy.py:230` chiamata `scan_patterns(bars, last_n=cfg.PATTERN_CONFIRMATION_BARS, cfg=self._pattern_cfg)`; `strategy.py:316/319/621` consumo via attribute access `p.direction`. Nessun shim — refactor end-to-end (scelta esplicita di rottura interna, nessun consumer esterno coinvolto). Suite globale 402 passed. |

**Score ROADMAP:** 3/3 truths verificati ✓

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `patterns.py` | 9 detector calibrati (matched, raw_score) + is_doji bool + scan_patterns + dataclass | ✓ VERIFIED | 742 righe, 9 detector tuple-return + `is_doji`, 12 `@dataclass(frozen=True)` (PatternHit, PatternConfig, 9 sub-cfg, CalibrationAnchors), `scan_patterns(bars, last_n, cfg) -> list[PatternHit]` orchestrator, `_calibrate` interpolazione lineare a tratti, `load_pattern_config(path?)` con env override `PATTERNS_CONFIG_PATH`. Zero TODO/FIXME/PLACEHOLDER. |
| `config/patterns.yaml` | Soglie geometria + calibrazione min/typical/max per 9 pattern + doji | ✓ VERIFIED | 94 righe, 10 sezioni (hammer, inverted_hammer, shooting_star, engulfing, morning_star, evening_star, key_reversal, inside_bar, pin_bar, doji), tutte con `geometry:` + `calibration: {min, typical, max}` (eccetto doji solo `body_tolerance`). |
| `strategy.py` | Integrazione PatternConfig cached, scan_patterns usato, attribute access | ✓ VERIFIED | Import + init + callsite + 3 consumi via `p.direction` (linee 316, 319, 621). 15 occorrenze totali `p.direction` nel modulo (anche su Position/Setup, valore atteso ≥3). |
| `tests/test_patterns.py` | Coppia positivo+near-miss per ogni detector + scan_patterns + PatternHit | ✓ VERIFIED | 353 righe, 31 test passed, copertura completa 9 detector (vedi tabella requirements). |
| `tests/test_pattern_config.py` | Loader + _calibrate + override env + dataclass frozen | ✓ VERIFIED | 11 test passed: default load, param path, env override, invalid anchors raise, missing pattern raise, empty yaml raise, frozen schema (PatternConfig + PatternHit), calibrate boundaries, calibrate monotonic. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `strategy.py` | `patterns.scan_patterns` | `import` + chiamata riga 230 | ✓ WIRED | Import esplicito + chiamata con `cfg=self._pattern_cfg` |
| `strategy.py` | `patterns.load_pattern_config` | `import` + chiamata in `IntradayStrategy.__init__` riga 163 | ✓ WIRED | Cached a startup (D-19, no reload YAML in hot path 5min scheduler) |
| `scan_patterns` | `config/patterns.yaml` | `load_pattern_config()` -> `_build_pattern_config(yaml.safe_load(...))` | ✓ WIRED | Default `DEFAULT_CONFIG_PATH = Path("config/patterns.yaml")`; precedenza arg > env `PATTERNS_CONFIG_PATH` > default |
| `scan_patterns` | `is_hammer/is_engulfing/is_morning_star/...` | Chiamate dirette per ogni detector con `cfg.<sub>` | ✓ WIRED | Verificato runtime: hits emessi su bars sintetici (count=5) |
| `_score_confidence` (strategy.py:610+) | `PatternHit.direction` | Attribute access `p.direction` | ✓ WIRED | Riga 621: `has_aligned = any(p.direction == wanted for p in patterns)` |

### Data-Flow Trace (Level 4)

| Artifact | Variabile dato | Sorgente | Produces Real Data | Status |
|----------|----------------|----------|---------------------|--------|
| `strategy.py` `indicators_snapshot["patterns"]` | list[PatternHit] | `scan_patterns(bars, ..., cfg=self._pattern_cfg)` | Sì — verifica runtime: 5 hits su bars sintetici hammer-like; ogni hit con confidence ∈ [0,1] (test `test_confidence_in_unit_interval`). | ✓ FLOWING |
| `_score_confidence(...)` `pattern_score` | float (0.0/0.05/0.2) | iterazione `p.direction == wanted` su list[PatternHit] | Sì — flusso dati attivo, attribute access reale (no dict legacy) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 9+Doji detector + dataclass importabili | `python -c "from patterns import scan_patterns, load_pattern_config, PatternHit, PatternConfig, is_hammer, is_inverted_hammer, is_shooting_star, is_engulfing, is_morning_star, is_evening_star, is_key_reversal, is_inside_bar, is_pin_bar, is_doji"` | "all imports OK" | ✓ PASS |
| `scan_patterns([])` ritorna `[]` | runtime smoke | `[]` | ✓ PASS |
| `scan_patterns(bars*6, last_n=5, cfg=cfg)` ritorna list[PatternHit] valida con tutti i 6 campi | runtime smoke | type ok=True, fields={name,bar_index,span_bars,extreme_price,confidence,direction}=True, count=5 | ✓ PASS |
| Suite full pytest verde | `.venv/Scripts/python.exe -m pytest -q` | `402 passed, 1 skipped, 1 warning in 22.43s` (Mottl optional skip da Phase 2, baseline atteso) | ✓ PASS |
| Pattern test isolati verdi | `pytest tests/test_patterns.py tests/test_pattern_config.py -v` | `42 passed in 0.31s` (31 patterns + 11 config) | ✓ PASS |

### Requirements Coverage (PATT-01..07)

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PATT-01 | 03-02 / 03-03 | Hammer / Inverted Hammer detector | ✓ SATISFIED | `is_hammer` + `is_inverted_hammer` con firma `(matched, raw_score)`. Test: `test_is_hammer_classic`, `test_is_hammer_rejects_long_upper_shadow`, `test_is_hammer_rejects_zero_range`, `test_is_inverted_hammer`, `test_is_inverted_hammer_rejects_short_upper`. Emessi come PatternHit `direction='bullish'`. |
| PATT-02 | 03-03 | Shooting Star detector | ✓ SATISFIED | `is_shooting_star` con soglie più stringenti di inverted_hammer (body_ratio_max=0.3 vs 0.4). Test: `test_is_shooting_star_classic`, `test_is_shooting_star_rejects_large_body`. Emesso come PatternHit `direction='bearish'`. |
| PATT-03 | 03-02 / 03-03 | Bullish/Bearish Engulfing detector | ✓ SATISFIED | `is_engulfing(prev, curr, direction, cfg)` con gate `min_body_ratio` (esclude doji-like). Test: `test_is_engulfing_bullish`, `test_is_engulfing_bearish`, `test_is_engulfing_invalid_direction`, `test_is_engulfing_partial_negative`. Emesso bull/bear come PatternHit `span_bars=2`. |
| PATT-04 | 03-03 | Morning Star / Evening Star (3-bar) | ✓ SATISFIED | `is_morning_star` + `is_evening_star` con anchor su b3 (no look-ahead). Test: `test_is_morning_star_classic`, `test_is_morning_star_rejects_shallow_b3`, `test_is_evening_star_classic`, `test_is_evening_star_rejects_shallow_b3`, `test_morning_star_extreme_is_swing_low`. Emessi come PatternHit `span_bars=3`. |
| PATT-05 | 03-03 | Key Reversal Bar detector | ✓ SATISFIED | `is_key_reversal(prev, curr, direction, cfg)` outside reversal 2-bar. Test: `test_is_key_reversal_bullish`, `test_is_key_reversal_bearish`, `test_is_key_reversal_rejects_no_penetration`. Emesso come PatternHit `span_bars=2`. |
| PATT-06 | 03-02 / 03-03 | Inside Bar / Pin Bar detector | ✓ SATISFIED | `is_inside_bar` + `is_pin_bar`. Test: `test_is_inside_bar_classic`, `test_is_inside_bar_rejects_overflow`, `test_is_pin_bar_bullish`, `test_is_pin_bar_bearish`, `test_inside_and_pin_coexist` (Pitfall 4: una barra può essere inside+pin contemporaneamente). Inside emesso `direction='neutral'`. |
| PATT-07 | 03-01 / 03-03 / 03-04 | Pattern catalog ritorna confidence + structural reference points (bar index, extreme prices) | ✓ SATISFIED | Foundation 03-01 (`PatternHit` frozen + `load_pattern_config` + `_calibrate` + `config/patterns.yaml`); rebuild 03-03 (scan_patterns su 9 pattern + Doji); integrazione 03-04 (strategy.py callsite consume attribute access + IntradayStrategy._pattern_cfg cached). Test: `test_scan_patterns_returns_pattern_hit`, `test_confidence_in_unit_interval`, `test_morning_star_extreme_is_swing_low`. Commits: `42e41dd`, `e61f541`. |

**Coverage:** 7/7 PATT requirements SATISFIED. REQUIREMENTS.md riga 39-46 marcate `[x]` con commento esplicativo per ciascuno; riga 182-188 traceability table marcata Complete.

**Orphaned check:** Nessun requisito orfano. ROADMAP mappa solo PATT-01..07 a Phase 3, tutti presenti nei plan e tutti coperti da codice + test.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| - | - | Nessun TODO/FIXME/XXX/HACK/PLACEHOLDER/NotImplementedError in `patterns.py`, `config/patterns.yaml`, integrazione `strategy.py` | ℹ️ Info | Codice production-clean. Solo decorazioni `@dataclass(frozen=True)` (immutabilità voluta) e `pure functions` (zero side-effect). |

### Human Verification Required

Nessuna. Tutti i success criteria sono verificabili programmaticamente:
- SC #1 (positivo + near-miss per pattern) → conteggio test pytest
- SC #2 (PatternHit con campi specificati) → introspection dataclass + runtime smoke
- SC #3 (callers strategy.py funzionanti) → grep + suite full green

Phase 3 è una libreria pura senza UI, real-time o servizi esterni. Verification end-to-end automatizzata sufficiente.

### Gaps Summary

Nessun gap. Phase 3 raggiunge l'obiettivo end-to-end:

1. **Catalog completo:** 9 detector calibrati + Doji bool-only, tutti pure functions con firma `(matched, raw_score)`, parametrizzati via `config/patterns.yaml` (zero magic numbers, conforme regola CLAUDE.md "Tutto da .env / yaml").
2. **Schema strutturale:** `PatternHit` frozen dataclass con i 5 campi richiesti dal goal (`name`, `bar_index`, `extreme_price`, `confidence`, `direction`) + bonus `span_bars` (1/2/3) per ML feature engineering. Direction tristate (bullish/bearish/neutral) per inside_bar/doji.
3. **Calibrazione canonica:** `_calibrate` con interpolazione lineare a tratti su anchor (min, typical, max) — knee a 0.7 a `typical` lascia headroom per hit sopra-tipici. Doji emesso con confidence=1.0 (non calibrato per design, vedi 03-CONTEXT).
4. **Integrazione live atomica:** `strategy.py` consuma il nuovo schema senza shim (refactor 5 callsite + import + init), `IntradayStrategy._pattern_cfg` cached a `__init__` (D-19 — nessun reload YAML nel hot path scheduler 5 min).
5. **Regression safety:** 42 test pattern + suite globale 402 passed, baseline identico al post-Phase-2 (1 skip Mottl optional invariato).
6. **Threat surface:** T-3-10 (config malformato fail-fast a startup) e T-3-11 (cambio tipo `indicators_snapshot["patterns"]`) accettati come da plan; nessun consumer esterno upstream rotto (Phase 7 ML, MCP costruiti contro nuovo schema).

**Boomer A2 carry-over (Phase 2):** Non applicabile a Phase 3 — è concern di Phase 4 (Strategy Refactor) come indicato in input.

---

_Verified: 2026-05-08_
_Verifier: Claude (gsd-verifier)_
_Final phase commit: f008a35_
_Test baseline: 402 passed, 1 skipped (Mottl optional, da Phase 2)_
