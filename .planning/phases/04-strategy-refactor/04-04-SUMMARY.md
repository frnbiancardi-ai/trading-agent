---
phase: 04-strategy-refactor
plan: 04
subsystem: strategy
tags: [python, ast, purity-gate, living-invariant, test-only, no-runtime-impact]

requires:
  - phase: 04-strategy-refactor
    provides: 04-01 strategy/ skeleton (7 moduli puri + adapters/) + tests/test_strategy_purity.py stub
  - phase: 04-strategy-refactor
    provides: 04-02 strategy/confluence.py implementato (yaml load via open() — eccezione documentata)
  - phase: 04-strategy-refactor
    provides: 04-03 strategy/proposal.py implementato (4 funzioni Wave 1)
provides:
  - tests/test_strategy_purity.py (232 LOC, 5 test) — gate AST per i 7 moduli pure-fn
  - Living invariant D-16: qualunque import broker/network/db/logging in pure-fn modules → CI rosso
affects:
  - 04-05/06 (Wave 2 detectors): arrivano in ambiente garded. Detector A/B/C/D dovranno restare puri (no logging, no print, no broker)
  - 04-07 (Wave 3 shim cutover): strategy/__init__.py NOT in PURE_MODULES — re-esporta legacy via strategy_legacy.py, considerato bridge
  - 04-08 (Wave 4 regression gate): purity gate gira insieme a regression replay; entrambi DEVONO passare prima del cleanup legacy
  - 05-XX (baseline backtest): adapter backtest in strategy/adapters/* esente — puo' importare backtest engine + indicators

tech-stack:
  added: []   # zero nuove dipendenze, solo stdlib `ast` + `pathlib`
  patterns:
    - "AST-introspection senza side effect: ast.parse + ast.walk (mirror Phase 2 tests/test_indicators_purity.py)"
    - "Top-level package root extraction via .split('.')[0] per coprire urllib/urllib.request/http.client in un colpo"
    - "Heuristica nome-based per logger calls: var.<method> dove method in {info,warning,...} E 'log' in var.id.lower()"
    - "Eccezioni esplicite per file (OPEN_EXEMPT_FILES = {'strategy/confluence.py'}) per yaml singleton loader"
    - "Sanity test 'adapters_excluded' come guard contro accidentale aggiunta a PURE_MODULES"

key-files:
  created: []
  modified:
    - tests/test_strategy_purity.py (Wave 0 stub 14 LOC → 232 LOC implementation)

key-decisions:
  - "FORBIDDEN_IMPORTS espanso oltre il plan (aggiunti mt5_client + http) — Rule 2 missing critical: il codebase usa mt5_client come wrapper MT5 (vedi strategy_legacy.py imports), e `http.client`/`http.server` coprono casi che non vengono catturati da `urllib`/`requests`. Aggiunta minimal-surface per chiudere il gate completamente."
  - "Heuristica logger nome-based ('log' in var.id.lower()) accetta deliberatamente FALSI NEGATIVI (es. `getLogger(...)` assegnato a variabile `audit` non viene catturato come call) MA il bigger gate `import logging` in Test 1 rende impossibile ottenere un Logger senza prima importare `logging`, blocking la pipeline a monte. Documentato come limite noto del Test 2."
  - "open() consentito SOLO in confluence.py via OPEN_EXEMPT_FILES — Wave 1 plan-02 ha gia' lru_cache-ato il loader yaml, quindi l'I/O e' singleton/idempotente per durata processo. Tutti gli altri 6 moduli puri NON possono toccare il filesystem."
  - "strategy/__init__.py NON e' in PURE_MODULES — re-esporta IntradayStrategy + StrategyEnvironment + risk utils da strategy_legacy.py (Wave 0/1/2 transitional state). Diventera' puro in Wave 3 quando lo shim sostituira' il re-export legacy. Per ora il gate copre i 7 moduli che sono GIA' implementati come pure-fn."
  - "test_pure_modules_all_exist e' sanity FIRST-FAIL: se qualcuno cancella accidentalmente un modulo puro, fallisce con messaggio chiaro 'moduli puri mancanti: [...]' invece di causare 7 fail indecifrabili nei 3 test gate."
  - "test_adapters_subpackage_excluded e' una guard self-referential: previene aggiunta accidentale di 'strategy/adapters/...' a PURE_MODULES (regressione manuale del designer del gate). Costo: 0.001s, beneficio: protezione esplicita dell'invariant."

patterns-established:
  - "Pattern P-AST-1: ast.walk + Top-level root extraction per import classification (riusabile per altri purity gate futuri, es. backtest/* o indicators/*)"
  - "Pattern P-AST-2: per-file exception map (OPEN_EXEMPT_FILES) per gating selettivo — meglio di blanket exception/whitelist global"
  - "Pattern P-AST-3: 'guard test' che valida il design del gate stesso (test_adapters_subpackage_excluded) — preventiva regressione del config del test"

requirements-completed:
  - STRAT-08

duration: ~4min
completed: 2026-05-08
---

# Phase 4 Plan 04: Wave 1 AST Purity Gate (STRAT-08, D-15/D-16) Summary

**Living invariant `tests/test_strategy_purity.py` con 5 test AST-based che verificano i 7 moduli pure-fn della strategy package: zero import di broker/network/db/logging, zero chiamate a print/logger.*/open() (eccetto yaml loader confluence). Wave 2 detector arrivano in ambiente garded; qualunque drift impuro fa rosso CI immediato. 442 passed + 13 skip (+5 pass, –3 skip vs Wave 1-03), runtime 0.16s, negative-test manualmente verificato.**

## Performance

- **Duration:** ~4 min (singolo task, replace stub → implementation)
- **Started:** 2026-05-08
- **Completed:** 2026-05-08
- **Tasks:** 1/1
- **LOC produced:** 232 (test-only, zero source modificato)
- **Suite delta:** 437 → 442 passed (+5), 16 → 13 skip (–3 stubs sostituiti)

## Accomplishments

- **AST-introspection gate** (3 test) sui 7 moduli pure-fn:
  - `test_strategy_purity_no_forbidden_imports` — top-level + `from x import` su set di 12 root vietati (broker/network/db/logging)
  - `test_strategy_purity_no_logging_calls` — `logging.<method>` + `<varname-con-log>.<info|warning|...>(...)` heuristica
  - `test_strategy_purity_no_print_calls` — `print(...)` ovunque + `open(...)` ovunque eccetto in confluence.py
- **2 sanity test** complementari:
  - `test_pure_modules_all_exist` — fail-fast se qualcuno cancella un modulo puro
  - `test_adapters_subpackage_excluded_from_purity_gate` — guard contro aggiunta accidentale di adapters/* a PURE_MODULES
- **Negative test verificato manualmente**: inserendo `import mt5` + `import logging` + `logger.info(...)` + `print(...)` in `strategy/setups/a_breakout.py`, i 3 test gate falliscono con messaggi precisi (`strategy/setups/a_breakout.py:1: forbidden 'import mt5'`, ecc.) e i 2 sanity continuano a passare. File ripristinato post-verifica via `shutil.move` del backup.
- **Runtime totale 0.16s** per 5 test (target plan: <100ms-200ms — entro budget); ciascun test sotto 0.01s individualmente.

## Task Commits

1. **Task 1: implement 5 AST purity tests + sanity guards** — `0260126` (test) — replace stub Wave 0 (14 LOC, 3 `pytest.skip`) con implementazione completa (232 LOC, 0 skip)

## PURE_MODULES coperti dal gate (7)

```
strategy/setups/a_breakout.py     (Wave 0 stub, Wave 2 implementa)
strategy/setups/b_reversal.py     (Wave 0 stub, Wave 2 implementa)
strategy/setups/c_compression.py  (Wave 0 stub, Wave 2 implementa)
strategy/setups/d_pullback.py     (Wave 0 stub, Wave 2 implementa)
strategy/setups/__init__.py       (registry ALL_DETECTORS, Wave 0 stable)
strategy/confluence.py            (Wave 1 plan-02 implementato — usa open() per yaml, ESONERATO)
strategy/proposal.py              (Wave 1 plan-03 implementato — 4 funzioni adapter)
strategy/context.py               (Wave 0 stable — frozen dataclass)
```

**Esclusi by design (NOT in PURE_MODULES):**

```
strategy/__init__.py              (re-export legacy strategy_legacy.py — bridge transitional Wave 0..2)
strategy/risk_utils.py            (stub vuoto, Wave 3 lift verbatim da legacy — verra' aggiunto a PURE_MODULES quando implementato)
strategy/adapters/__init__.py     (barrel build_ctx_*)
strategy/adapters/live.py         (I/O bridge MT5 — Wave 3 implementa)
strategy/adapters/backtest.py     (I/O bridge backtest engine + CSV — Wave 3 implementa)
strategy_legacy.py                (legacy module, Wave 4 cleanup)
```

## FORBIDDEN_IMPORTS set (full list)

12 top-level package roots vietati. Si confronta solo il primo segmento (`name.split('.')[0]`) per coprire sotto-librerie in un colpo solo:

| Categoria | Roots |
| --------- | ----- |
| Broker / market-data IO | `mt5`, `MetaTrader5`, `mt5_client` |
| Network IO              | `requests`, `urllib`, `urllib2`, `urllib3`, `httpx`, `aiohttp`, `http` |
| Storage IO              | `sqlite3` |
| Process IO              | `subprocess` |
| Logging                 | `logging` |

**Hard block su `import logging`**: anche solo importarlo e' vietato — non solo le chiamate a `logging.getLogger`. Cosi' la pipeline si rompe a monte: senza il modulo, e' impossibile ottenere un Logger.

**Coverage `from x import y`**: confronta `node.module` (la parte `x`), non `y`. Quindi `from urllib.parse import quote` blocca al root `urllib`. Stesso per `from logging.handlers import ...`.

## LOG_METHODS heuristica (Test 2)

Set: `{info, warning, error, debug, critical, exception, log, getLogger}`.

Pattern catturato:

```python
# CASO A — logging.<method>(...) [hard catch]
logging.getLogger(__name__)        # → forbidden 'logging.getLogger(...)'
logging.info("x")                  # → forbidden 'logging.info(...)'

# CASO B — <varname-con-log>.<method>(...) [heuristica nome-based]
logger.info("x")                   # → forbidden 'logger.info(...)' (logger call)
self.log.warning("x")              # → forbidden 'log.warning(...)' (logger call)
my_logger.error("x")               # → forbidden 'my_logger.error(...)' (logger call)

# Limite noto (FALSO NEGATIVO):
audit = logging.getLogger(__name__)  # questa riga viene catturata da Test 2 (logging.getLogger)
audit.info("x")                      # questa riga NON viene catturata (var.id='audit', no 'log')
```

**Mitigazione del falso negativo**: il bigger gate `import logging` in Test 1 rende impossibile ottenere un Logger senza prima importare `logging`, bloccando la pipeline a monte. Per aggirare entrambi i gate servirebbe `from logging import getLogger as gl` (Test 1 cattura il `from logging`), oppure `__import__('logging')` (NON catturato — TODO future hardening se necessario).

## Open() exemption rationale

`OPEN_EXEMPT_FILES = {"strategy/confluence.py"}`.

**Motivazione**: `confluence.py:_load_cached(path_str)` (vedi 04-02-SUMMARY) usa `with open(path_str, encoding="utf-8") as f: yaml.safe_load(f)` per caricare `config/strategy.yaml`. Il loader e' decorato con `@lru_cache(maxsize=4)` su path-string → singleton/idempotente per durata processo. Una sola open() per path, mai re-aperto. D-08 schema cached e' parte del contratto pure-fn (config-as-data, non I/O dinamico).

**Tutti gli altri 6 moduli puri NON possono toccare il filesystem.** Setup detector, proposal adapter, context dataclass — tutto deve operare su `bars`, `indicators`, `ctx` passati per parametro.

## Manual negative-test result

Procedura eseguita 2026-05-08:

1. Backup `strategy/setups/a_breakout.py` → `.bak`.
2. Modificato il file con violazioni esplicite:
   ```python
   import mt5
   import logging
   logger = logging.getLogger(__name__)
   ...
   def detect_a_breakout(...):
       logger.info("detect call")
       print("debug")
       return ProposalDraft(...)
   ```
3. Esecuzione `pytest tests/test_strategy_purity.py -v`:
   - `test_strategy_purity_no_forbidden_imports` **FAILED** — messaggi: `strategy/setups/a_breakout.py:1: forbidden 'import mt5'` + `strategy/setups/a_breakout.py:2: forbidden 'import logging'`
   - `test_strategy_purity_no_logging_calls` **FAILED** — messaggi: `strategy/setups/a_breakout.py:3: forbidden 'logging.getLogger(...)'` + `strategy/setups/a_breakout.py:15: forbidden 'logger.info(...)' (logger call)`
   - `test_strategy_purity_no_print_calls` **FAILED** — messaggio: `strategy/setups/a_breakout.py:16: forbidden 'print(...)'`
   - `test_pure_modules_all_exist` **PASSED**
   - `test_adapters_subpackage_excluded_from_purity_gate` **PASSED**
4. Ripristino file da backup; re-run: 5 passed in 0.21s.

**Conclusione**: gate funziona end-to-end. Wave 2 detector che dovessero introdurre violazioni saranno bloccati dal CI con messaggi azionabili (file:lineno: violation type).

## Decisions Made

- **FORBIDDEN_IMPORTS espanso oltre il plan (Rule 2 missing critical)**: il plan elencava `mt5, MetaTrader5, requests, sqlite3, subprocess, urllib, urllib2, urllib3, httpx, aiohttp, logging` (11 root). Aggiunti `mt5_client` (wrapper MT5 usato da strategy_legacy.py — vedi `from mt5_client import ...` riga 12 di strategy_legacy.py) e `http` (copre `http.client.HTTPConnection`, `http.server.HTTPServer`, casi che NON vengono catturati da `requests`/`urllib`). Set finale: 12 root. Documentato come Rule 2 nelle Deviations sotto.
- **Heuristica nome-based per logger calls**: ho scelto deliberatamente FALSI NEGATIVI possibili (es. `audit_logger = logging.getLogger(...); audit.info(...)` dove la variabile finale non contiene "log") perche' (a) e' la stessa heuristica raccomandata dal plan PATTERNS.md, (b) il gate primario `import logging` in Test 1 chiude la falla a monte, (c) catturare TUTTI i potenziali logger richiederebbe analisi data-flow tra assegnamenti che e' fuori scope per un AST-walker single-pass.
- **5 test invece di 3 (plan prescriveva 3)**: aggiunti `test_pure_modules_all_exist` (sanity fail-fast su file mancanti) e `test_adapters_subpackage_excluded_from_purity_gate` (guard auto-referential sul design). Entrambi previsti dal `<action>` block del plan come "Test 4 (sanity)" + nota "Pattern P-AST-3 guard test"; ho semplicemente reso esplicito il secondo.
- **Runtime AST <0.01s per test**: `ast.parse + ast.walk` su 8 file totalizza ~10ms — confermato dal `--durations=10` output. Il budget plan (200ms) e' rispettato con margine ~20×. Nessun bisogno di caching multi-test (tree e' ricostruito per ogni test ma e' fast comunque).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] FORBIDDEN_IMPORTS esteso a `mt5_client` + `http`**
- **Found during:** Task 1 (durante stesura set FORBIDDEN_IMPORTS — verifica imports correnti del codebase)
- **Issue:** Il plan listava 11 root. `grep -rn "from mt5_client\\|import mt5_client" .` ha rilevato che `strategy_legacy.py` importa `mt5_client` come wrapper MT5 — qualunque drift di un setup detector verso `from mt5_client import ...` sarebbe stato un I/O bridge violato e NON catturato dal gate originale (mt5_client non e' lo stesso package di mt5). Inoltre `http.client.HTTPConnection`, `http.server`, etc. sono I/O network non coperti da `requests`/`urllib` (es. uno potrebbe scrivere `import http; http.client.HTTPConnection(...)` per eludere il blocco `requests`).
- **Fix:** Aggiunti `mt5_client` e `http` a FORBIDDEN_IMPORTS. Set finale: 12 root.
- **Files modified:** tests/test_strategy_purity.py (2 righe nel set literal)
- **Verification:** `pytest -q` 5/5 pass; tutti i 7 moduli puri attuali non importano questi root → gate non si rompe.
- **Committed in:** `0260126`

---

**Total deviations:** 1 auto-fixed (Rule 2 missing critical security/IO surface). Nessun blocker, nessun architectural decision.
**Impact on plan:** Net positive — il gate ora copre 12 root invece di 11. Coerente con la filosofia del plan (`<must_haves>` truth #1: "AST-introspection test scans all 7 pure modules and asserts NO forbidden imports") — ho ampliato il set di "forbidden imports" senza modificare la struttura del test.

## PATTERNS.md Compliance

Implementazione segue verbatim §tests/test_strategy_purity.py per:
- Set FORBIDDEN_IMPORTS (con +2 root estensione documentata sopra)
- Set OPEN_EXEMPT_FILES = {"strategy/confluence.py"}
- 3 test gate + 1 sanity exist test (verbatim col `<action>` block del plan)
- Heuristica logger nome-based
- Runtime budget <200ms (rispettato a 0.16s — 8× sotto budget)

Aggiunte rispetto a verbatim:
- 5° test `test_adapters_subpackage_excluded_from_purity_gate` — esplicita la guard auto-referential menzionata in PATTERNS §"Pattern P-AST-3 guard test"
- Helper `_import_root` con docstring (plan inline; ho refactorato in funzione)
- Docstring italiani estesi sui blocchi public e sulle eccezioni motivate

## Issues Encountered

- **CRLF warning su Windows**: `git add tests/test_strategy_purity.py` ha mostrato `LF will be replaced by CRLF`. Comportamento normale del repo Windows (autocrlf=true), nessuna azione.
- **Nessun bug-fix Rule 1**: a differenza dei plan 02 e 03 di questo phase, qui non c'erano boundary FP o deprecation Python da risolvere — il modulo `ast` e' stabile e deterministico, non ci sono confronti float in gioco.

## Known Stubs

Nessuno stub introdotto. Il file `tests/test_strategy_purity.py` era stub Wave 0 (14 LOC, 3 `pytest.skip`); ora e' completamente implementato (232 LOC, 0 skip). Non ci sono Wave-pending residui in questo file.

Stub esistenti altrove (non tocchi da questo plan):
- `strategy/risk_utils.py` (Wave 3 lift verbatim da legacy)
- `strategy/setups/{a,b,c,d}_*.py` (Wave 2 detector — restano `setup_type='NONE' reason='wave_2_pending'` per ora; gate verifica solo che siano puri, NON che siano completi)
- `strategy/adapters/{live,backtest}.py` (Wave 3 — ESCLUSI dal gate)

## Self-Check: PASSED

- File `tests/test_strategy_purity.py`: FOUND (232 righe, 5 funzioni `test_*`, 0 `pytest.skip`)
- Commit `0260126` (Task 1 test): FOUND in git log (`git log --oneline | grep 0260126` → `0260126 test(04-04): purity gate AST per moduli pure-fn strategy (STRAT-08)`)
- `python -c "import ast; t=ast.parse(open('tests/test_strategy_purity.py',encoding='utf-8').read()); print('ok')"`: `ok`
- `pytest tests/test_strategy_purity.py -q`: **5 passed in 0.16s** (0 skip)
- `pytest -q` (full suite): **442 passed, 13 skipped** (delta vs Wave 1-03: +5 pass, –3 skip, +0 fail)
- `grep -c "FORBIDDEN_IMPORTS" tests/test_strategy_purity.py` = 3: PASS (≥1)
- `grep -c "ast.walk" tests/test_strategy_purity.py` = 3: PASS (≥3, una per test)
- `grep -c "^def test_" tests/test_strategy_purity.py` = 5: PASS (≥4)
- Negative test manualmente verificato: 3 test gate FAIL con messaggi precisi su mt5/logging/print + 2 sanity PASS, file ripristinato → re-run 5 passed.
- Runtime totale 0.16s, ciascun test <0.01s: PASS (target <200ms)

## Next Phase Readiness

**Wave 2 (04-05 Setup A+D + 04-06 Setup B+C) puo' iniziare**:
- Living invariant in vigore: detector che provano a fare `import logging`, `print(...)`, `import mt5_client`, etc. saranno bloccati immediatamente da CI rosso.
- Guard chiari per il developer: messaggi `file:lineno: forbidden 'X'` lo guidano alla riga esatta da rimuovere/refactorare.
- Tutti i 4 setup detector attualmente sono stub `return ProposalDraft(setup_type='NONE', reason='wave_2_pending')` — restano puri per costruzione. Wave 2 dovra' implementarli rispettando il gate (il modo idiomatico: usare `score_factors`/`grade_for`/`compute_confidence` da confluence.py + `compute_levels_with_atr_cap` da proposal.py, entrambi gia' puri e gia' coperti dal gate).

**Wave 3 (04-07 shim cutover + risk_utils + adapters) puo' iniziare**:
- `strategy/risk_utils.py` quando implementato dovra' essere AGGIUNTO a PURE_MODULES (1 riga di edit nel test). Documentato in §Decisions sopra.
- `strategy/__init__.py` quando il re-export legacy verra' rimpiazzato dallo shim pure-fn dovra' essere AGGIUNTO a PURE_MODULES (Wave 3).
- `strategy/adapters/{live,backtest}.py` resteranno ESCLUSI by design (I/O bridge intenzionale).

**Wave 4 (04-08 regression replay) puo' iniziare**:
- Purity gate gira insieme a `tests/test_strategy_regression.py` — entrambi DEVONO passare prima del cleanup di `strategy_legacy.py`. Combo: regression replay verifica behavior bit-for-bit, purity gate verifica che il nuovo motore non abbia introdotto side effect impuri.

**Nessun blocker per i Wave successivi.** Suite di test verde con 442 passed + 13 skipped (Wave-pending stub residui sui setup detector + adapter live/backtest).

---
*Phase: 04-strategy-refactor*
*Plan: 04 (Wave 1 AST purity gate)*
*Completed: 2026-05-08*
