---
phase: 03-patterns-catalog
plan: 04
subsystem: patterns
tags: [patterns, strategy, refactor, integration, callsite]
dependency_graph:
  requires:
    - 03-01 (load_pattern_config, PatternConfig)
    - 03-02 (scan_patterns firma cfg=)
    - 03-03 (scan_patterns rebuild → list[PatternHit])
  provides:
    - strategy.py callsite consume PatternHit attribute access
    - IntradayStrategy._pattern_cfg cached at __init__
    - indicators_snapshot["patterns"] = list[PatternHit] (tipo cambiato, assegnamento invariato)
  affects:
    - strategy.py (1 import + 1 init line + 1 call site cfg + 3 attribute access)
    - tests/test_strategy.py (2 fixture migrate da dict legacy a PatternHit)
tech-stack:
  added: []
  patterns:
    - dependency injection di PatternConfig una volta a startup (D-19, no chiamata in hot path)
    - attribute access su frozen dataclass (sostituzione dict-style, fail-fast su typo)
key-files:
  created:
    - .planning/phases/03-patterns-catalog/03-04-SUMMARY.md
  modified:
    - strategy.py
    - tests/test_strategy.py
decisions:
  - "load_pattern_config() chiamato esattamente una volta in IntradayStrategy.__init__, salvato in self._pattern_cfg (cached)"
  - "scan_patterns invocato con cfg=self._pattern_cfg per evitare reload YAML in hot path (5 min scheduler)"
  - "indicators_snapshot['patterns'] mantiene chiave invariata; il tipo cambia da list[dict] a list[PatternHit] — consumatori downstream Phase 7 ML costruiti contro nuovo schema"
  - "StrategyEnvironment.__init__ NON modificato (non costruisce IntradayStrategy)"
  - "Fixture _score_confidence in test_strategy.py migrate a PatternHit (Rule 1 bug: dict legacy incompatibile)"
metrics:
  duration: ~3 min
  completed: 2026-05-08
  tasks: 2
  files_changed: 2
  tests_added: 0
  tests_total_after: 402  # full suite, 1 skipped Mottl optional
---

# Phase 3 Plan 04: refactor strategy.py callsite + chiusura Phase 3 Summary

PATT-07 (chiusura): refactor chirurgico di `strategy.py` per consumare il nuovo schema `PatternHit` (attribute access) e iniettare `PatternConfig` tramite `IntradayStrategy.__init__`. 5 call site + 1 import + 1 init line modificati. Suite globale 402 passed verde, smoke import end-to-end pulito. Phase 3 ROADMAP success criteria #1, #2, #3 tutti soddisfatti.

## Cosa è stato costruito

### Task 1 — Refactor atomico strategy.py (commit `42e41dd`)

`strategy.py` modificato in 6 punti puntuali:

1. **Import (riga 32):**
   ```python
   from patterns import scan_patterns, load_pattern_config
   ```
2. **`IntradayStrategy.__init__` body:** aggiunta come ultima istruzione:
   ```python
   self._pattern_cfg = load_pattern_config()  # Phase 3: carica catalog cfg una volta a startup
   ```
3. **Call site `scan_patterns` (riga 230):** passa `cfg=self._pattern_cfg` al detector orchestrator.
4. **Direction check bullish (righe 314-316):** `p["direction"]` → `p.direction`
5. **Direction check bearish (righe 317-319):** `p["direction"]` → `p.direction`
6. **Direction check in `_score_confidence` (riga 621):** `p["direction"]` → `p.direction`

Linea `indicators_snapshot["patterns"] = patterns` (riga 241) **invariata** come da plan: cambia solo il TIPO contenuto (`list[PatternHit]` invece di `list[dict]`), l'assegnamento è identico.

`StrategyEnvironment.__init__` (riga 59) **non toccato** — non costruisce `IntradayStrategy`.

### Task 2 — Regression full-suite + fix fixture legacy (commit `e61f541`)

Esecuzione iniziale `pytest -q` ha rivelato 2 fallimenti pre-esistenti in `tests/test_strategy.py` (`test_confidence_higher_with_aligned_pattern`, `test_confidence_above_threshold_for_strong_setup`): le fixture passavano `[{"pattern": "hammer", "bar_index": -1, "direction": "bullish"}]` (formato dict legacy) a `_score_confidence`, ma il nuovo contratto post-03-03 richiede `list[PatternHit]`. Questo è esattamente lo scenario previsto dal plan ("se qualche test su tests/test_strategy.py fallisce per dict→attribute residuo, identifica il sito mancante e applicare la stessa attribute migration localmente").

Applicato fix Rule 1 (bug):
- `tests/test_strategy.py:11` aggiunto `from patterns import PatternHit`
- 2 fixture migrate a `PatternHit(name="hammer", bar_index=-1, span_bars=1, extreme_price=1.1000, confidence=0.8, direction="bullish")`
- `tests/test_strategy_runner.py` verificato: nessuna occorrenza dict-shape su pattern hits

Post-fix la suite globale è verde: **402 passed, 1 skipped** (Mottl optional, identico al baseline post 03-03).

## Verifica

| Check | Risultato |
|-------|-----------|
| `python -c "import strategy; print('OK')"` | OK |
| `grep -q "from patterns import scan_patterns, load_pattern_config" strategy.py` | OK |
| `grep -q "self._pattern_cfg = load_pattern_config()" strategy.py` | OK |
| `grep -q "cfg=self._pattern_cfg" strategy.py` | OK (riga 230) |
| `grep -c "p\.direction" strategy.py` | 15 (≥3 atteso; le 3 chiamate pattern + altri usi su Position/Setup) |
| `! grep -E 'p\["(direction\|pattern\|bar_index)"\]' strategy.py tests/test_patterns.py tests/test_pattern_config.py tests/test_strategy.py` | OK (zero residui) |
| Smoke import end-to-end (`patterns + strategy`, `scan_patterns(bars, last_n=5, cfg=cfg)` ritorna list[PatternHit]) | OK ("all PatternHit OK") |
| `pytest tests/test_patterns.py -q` | 31 passed (regression Wave 3) |
| `pytest tests/test_pattern_config.py -q` | 11 passed (regression Wave 1) |
| `pytest tests/test_strategy.py -q` | passed (post-fix fixture) |
| `pytest -q` (full suite) | **402 passed, 1 skipped** |
| `grep -q "@dataclass(frozen=True)" patterns.py` | OK (12 dataclass frozen) |
| `grep -q "load_pattern_config" strategy.py` | OK |
| `grep -q "PatternHit" patterns.py` | OK |

## Truth-set verifica (must_haves dal plan)

- [x] strategy.py imports load_pattern_config from patterns module
- [x] IntradayStrategy.__init__ instantiates self._pattern_cfg = load_pattern_config()
- [x] scan_patterns call at line ~230 passes cfg=self._pattern_cfg
- [x] All three dict-style accesses (lines ~316, ~319, ~621) replaced with attribute access (.direction)
- [x] indicators_snapshot["patterns"] is now list[PatternHit] (consumers receive dataclass instances)
- [x] Existing strategy.py tests pass after refactor (regression-clean, 2 fixture aggiornate)
- [x] Full pytest -q suite green (402 passed + 1 skipped Mottl, era 402 + 1 post 03-03 — stesso baseline)

## Phase 3 ROADMAP success criteria (tutti soddisfatti)

1. **Each pattern: hand-crafted positive + near-miss negative test** ✓ — coperto in 03-02 (4 detector + 2 near-miss) e 03-03 (5 detector + 5 near-miss + bearish key_reversal)
2. **PatternHit dataclass returned with all 6 fields** ✓ — implementato in 03-01 (frozen schema), `name/bar_index/span_bars/extreme_price/confidence/direction`, emesso da `scan_patterns` post 03-03 rebuild
3. **Existing scan_patterns callers updated (no shim)** ✓ — questo plan: `strategy.py` callsite refactor end-to-end, zero adapter shim, attribute access nativo

## Deviations from Plan

**[Rule 1 - Bug] Fix fixture dict legacy in tests/test_strategy.py**
- **Found during:** Task 2 (regression suite)
- **Issue:** 2 test (`test_confidence_higher_with_aligned_pattern`, `test_confidence_above_threshold_for_strong_setup`) fornivano `_score_confidence` con `patterns=[{"pattern": "hammer", "bar_index": -1, "direction": "bullish"}]` (formato dict legacy pre-03-03). Post-Task-1 con `p.direction` AttributeError su dict.
- **Fix:** Importato `PatternHit` da `patterns` module, sostituite le 2 fixture con `PatternHit(...)` complete (6 campi). Esattamente la migration prevista dal plan come fallback opzionale.
- **Files modified:** `tests/test_strategy.py`
- **Commit:** `e61f541`

Nessun'altra deviazione. Tasks 1 e 2 eseguiti come scritto; il "fix fixture" rientra nel perimetro di Task 2 (regression con migration locale prevista esplicitamente dal plan).

## Threat surface scan

Nessun threat flag introdotto. T-3-10 (config malformato fa crashare avvio strategy) **accept** come da plan: comportamento desiderato fail-fast a startup; loader fail-closed di 03-01 espone errori YAML/anchor in stack trace. T-3-11 (cambio tipo `indicators_snapshot["patterns"]`) **accept** come da plan: documentato qui; consumatori esterni (Phase 7 ML, MCP) costruiti contro il nuovo schema; nessun adapter shim necessario.

## Note di handoff per Phase 3 verification e Phase 4

- **Phase 3 chiusa**: tutti i 4 piani eseguiti (03-01 → 03-02 → 03-03 → 03-04). Pronta per `/gsd-verify-phase 3` che valuterà ROADMAP success criteria e PATT-01..07 disposition definitiva.
- **`patterns.py` API finale**: 9 detector calibrati (`is_hammer`, `is_inverted_hammer`, `is_shooting_star`, `is_engulfing`, `is_morning_star`, `is_evening_star`, `is_key_reversal`, `is_inside_bar`, `is_pin_bar`) + `is_doji` bool-only + `scan_patterns(bars, last_n, cfg) -> list[PatternHit]` + dataclass frozen (`PatternHit`, `PatternConfig`, sub-cfg) + `_calibrate` + `load_pattern_config`.
- **`strategy.py` integration**: `IntradayStrategy._pattern_cfg` cached (D-19), passato esplicitamente a `scan_patterns`. `_score_confidence` legge `p.direction` direttamente (no shim).
- **`indicators_snapshot["patterns"]` type contract**: ora `list[PatternHit]` (tuple frozen, hashable). Phase 4 (Strategy Refactor) e Phase 7 (ML Classifier) costruiranno feature engineering contro questo schema (es. `confidence` come feature numerica, `name` come categoria).
- **Test footprint**: 31 `test_patterns.py` + 11 `test_pattern_config.py` + tutti i test pre-esistenti `test_strategy.py` aggiornati = 402 passed in suite globale.
- **Regression sicura**: nessuna deviazione su `is_doji`, `StrategyEnvironment`, `compute_all`, `analyze_symbol` external behavior — il refactor è puramente di shape interna (callsite + tipo).

## Self-Check

Verificato con git e filesystem:
- `strategy.py` MODIFIED (import + init + 1 callsite + 3 attribute access)
- `tests/test_strategy.py` MODIFIED (import PatternHit + 2 fixture migrate)
- `.planning/phases/03-patterns-catalog/03-04-SUMMARY.md` FOUND
- Commit `42e41dd` (Task 1 — refactor strategy.py) FOUND
- Commit `e61f541` (Task 2 — fixture migration) FOUND
- `pytest tests/test_patterns.py -q`: 31 passed
- `pytest tests/test_pattern_config.py -q`: 11 passed
- `pytest tests/test_strategy.py -q`: passed
- `pytest -q` full suite: 402 passed, 1 skipped (Mottl optional)
- Smoke import end-to-end: OK ("all PatternHit OK")
- Zero residui `p["direction|pattern|bar_index"]` su strategy.py + tests/test_*.py

## Self-Check: PASSED
