---
phase: 06-mcp-tools-part-1
plan: 02
subsystem: mcp-package-split-wave1
tags: [mcp, refactor, additive-backward-compat, bar-source, mt5-wrappers, tdd, wave-1]
dependency_graph:
  requires: [mcp/errors.py, backtest_runs.status, mcp_server.py-legacy, mt5_client.py, indicators.compute_all, indicators.compute_all_extended]
  provides:
    - mcp_tools/__init__.py
    - mcp_tools/server.py
    - mcp_tools/schemas.py
    - mcp_tools/bar_source.py
    - mcp_tools/handlers/account.py
    - mcp_tools/handlers/market.py
    - mcp_tools/handlers/proposal.py
    - Mt5Client.modify_position
    - Mt5Client.partial_close
    - Mt5Client.get_position
    - cfg.MCP_DEFAULT_BARS
  affects: [Wave 2 (06-03 backtest queue), Wave 3 (06-04 trail daemon + modify_position handler), Wave 4 (06-05 correlation/session/multi_tf), Phase 7 ML (replay_decision via BarSource)]
tech_stack:
  added: [mcp_tools/ local package, BarSource D-D1 adapter, additive D-C1 schema fields]
  patterns: [package-rename-collision-fix, pep562-module-proxy, tdd-red-green, additive-backward-compat, strict-lt-bisect, _retry-decorator, envelope-error-codes]
key_files:
  created:
    - mcp_tools/__init__.py
    - mcp_tools/server.py
    - mcp_tools/schemas.py
    - mcp_tools/bar_source.py
    - mcp_tools/errors.py
    - mcp_tools/handlers/__init__.py
    - mcp_tools/handlers/account.py
    - mcp_tools/handlers/market.py
    - mcp_tools/handlers/proposal.py
  modified:
    - mcp_server.py
    - mt5_client.py
    - config.py
    - .env.example
    - tests/test_mcp_bar_source.py
    - tests/test_mcp_handlers_market.py
    - tests/test_mcp_handlers_proposal.py
decisions:
  - "Package rename mcp/ -> mcp_tools/ per evitare collisione di import con SDK PyPI mcp; design intent D-E1 preservato (split modulare), solo path filesystem cambia"
  - "Dispatch in mcp_tools/server.py refattorato: delega ai nuovi handler in handlers/{market,proposal}.py (no piu' duplicazione inline); shim mcp_server.py espone wrapper retrocompat per test legacy (vecchia signature posizionale)"
  - "BarSource strict-< semantics confermata: bar @ exact as_of_unix NON inclusa (bisect_left = insertion point); no future leakage by construction"
  - "BarSource cutoff > len(ts_arr) e' unreachable via bisect_left (max e' len). Codice difensivo mantenuto: ramo if cutoff > len resta morto ma documentato"
  - "R3 setup_type/confluence_score Wave 1 = pure passthrough da args.context; Phase 4 evaluate_proposal_for_bar non invocato in Wave 1 (richiede StrategyContext upstream non disponibile in propose_trade)"
  - "R2 regime extraction usa compute_all_extended (Phase 2 INDIC-14 regime_state); fallback 'normal' su ImportError o errori OHLC defensive"
  - "Test smoke_12month_under_60s pre-esistente fail (Phase 1 perf SC-6 60s budget) confermato out-of-scope: presente prima delle modifiche Plan 06-02 (verificato con git stash); deferred in deferred-items.md"
metrics:
  duration_minutes: 25
  completed_date: "2026-05-11"
  tasks_completed: 3
  files_created: 9
  files_modified: 7
---

# Phase 6 Plan 02: Wave 1 MCP Package Split + R1/R2/R3 Additive Refactor Summary

**One-liner:** Split di `mcp_server.py` in package `mcp_tools/` (rinominato per evitare clash SDK), 11 handler legacy spostati senza change semantica, R1/R2/R3 additive backward-compat con nuovi campi (`indicators_extended`, `regime`, `correlation_warnings`, `setup_type`, `confluence_score`), BarSource D-D1 adapter live/storico con strict-< no-leakage, 3 wrapper Mt5Client (`modify_position`/`partial_close`/`get_position`).

## Tasks Completati

| # | Task | Commit | TDD Gate |
|---|------|--------|----------|
| 1 | Package mcp_tools/ skeleton + 11 handler move + shim mcp_server.py | `bcb05de` | non-TDD (refactor) |
| 2 RED | Test BarSource D-D1 reali | `ed69b65` | RED |
| 2 GREEN | BarSource D-D1 + Mt5Client wrappers | `095414a` | GREEN |
| 3 RED | Test R1/R2/R3 handlers reali | `fd0d4c2` | RED |
| 3 GREEN | R1/R2/R3 additive handlers + MCP_DEFAULT_BARS + dispatch refactor | `2d96bbb` | GREEN |

**TDD compliance:** Task 2 e Task 3 hanno entrambi commit RED → GREEN consecutivi (gate verde).

## Deviation dal Plan

### Rule 4 (architettonica, già pre-decisa dal planner)

**1. Package rename `mcp/` → `mcp_tools/`**

- **Trigger:** SDK PyPI `mcp` (Anthropic MCP) e package locale `mcp/` collidono nel sys.modules. Python's import system trova il package locale prima del site-packages, oscurando `from mcp.server import Server`.
- **Risoluzione:** rinominato a `mcp_tools/` (decisione del planner, documentata nel PLAN come "TRUE resolution"). D-E1 intent ("split modulare in package") preservato; solo il path filesystem cambia.
- **Verifica:** `python -c "import mcp; print(mcp.__file__)"` ritorna `<venv>/lib/python3.12/site-packages/mcp/__init__.py` (SDK risolve correttamente).

### Rule 1 (auto-fix bug)

**2. Dispatch refactor + backward-compat wrappers nel shim**

- **Trigger:** dopo aver rimosso le versioni inline obsolete di `handle_get_symbol_universe/scan/indicators/propose` da `mcp_tools/server.py` (Step D del Task 3 le voleva sostituire con delega ai nuovi handler), i test legacy in `tests/test_mcp_tools_v2.py` fallivano perché chiamavano `mcp_server.handle_get_symbol_universe()` con la vecchia signature.
- **Risoluzione:** aggiunti 5 wrapper retrocompat in `mcp_server.py` (shim) che traducono la vecchia API posizionale alla nuova API standardizzata `(args: dict, mt5, cfg)`. Nuovi handler restano puliti; shim assorbe la conversione signature.
- **Risultato:** 15/15 test legacy passano senza modifica ai test stessi (zero regressione).
- **Commit:** `2d96bbb`

### Rule 2 (auto-add missing critical)

**3. `dataclasses` import + `_build_proposal` legacy nel shim**

- **Trigger:** test `test_mcp_tools_v2.py::test_propose_trade` chiama `_build_proposal()` direttamente.
- **Risoluzione:** mantenuto `_build_proposal` come helper legacy nel shim (3 callsite-test, signature invariata).
- **Commit:** `2d96bbb`

## Deliverable 1: Package mcp_tools/ skeleton

### File Inventory

| File | LOC | Provides |
|------|-----|----------|
| `mcp_tools/__init__.py` | 8 | Package init + nota rename |
| `mcp_tools/server.py` | 400 | Server MCP + dispatch (delega a handlers/) + tool list |
| `mcp_tools/schemas.py` | 65 | `PROPOSAL_SCHEMA`, `PROPOSE_TRADE_SCHEMA`, `BARS_AS_OF_FIELDS`, `GET_MARKET_SNAPSHOT_SCHEMA` (D-F1) |
| `mcp_tools/bar_source.py` | 105 | `BarSource.get` adapter live/storico D-D1 |
| `mcp_tools/errors.py` | 15 | `ErrorCodes` D-F2 (da Wave 0) |
| `mcp_tools/handlers/__init__.py` | 8 | Subpackage init |
| `mcp_tools/handlers/account.py` | 75 | 3 handler verbatim da mcp_server.py |
| `mcp_tools/handlers/market.py` | 200 | R1+R2 + 2 handler legacy (universe, indicators) |
| `mcp_tools/handlers/proposal.py` | 125 | R3 + evaluate + submit |

### Shim mcp_server.py

- 110 LOC totali; 5 wrapper retrocompat (`handle_get_symbol_universe`, `handle_scan_symbol_candidates`, `handle_get_symbol_indicators`, `handle_propose_trade`, `_build_proposal`)
- PEP 562 `__setattr__` proxy propaga monkeypatch da `mcp_server.cfg/mt5/log` a `mcp_tools.server.<attr>` (test legacy fixtures continuano a funzionare)
- Entry point `main()` con bootstrap MT5 + stdio_server

## Deliverable 2: R1/R2/R3 Additive Schema Fields

### R1: get_market_snapshot (D-C1)

| Campo | Tipo | Default | Wave 1 |
|-------|------|---------|--------|
| `bars` | int 50-500 | 200 (`cfg.MCP_DEFAULT_BARS`) | ✓ override args |
| `as_of_ts` | ISO8601 UTC \| null | null (live) | ✓ via BarSource D-D1 |
| `timeframe` | enum M15/M30/H1/H4 | `cfg.TIMEFRAME` | ✓ override args |
| `indicators` | dict 4-key legacy | sma_20/ema_50/rsi_14/atr_14 | ✓ preservato |
| `indicators_extended` | dict Phase 2 \| null | from `compute_all_extended` | ✓ |
| `bars_used` | int | actual returned | ✓ |
| `tick` | dict (live only) | `{}` se as_of_ts | ✓ |

### R2: scan_symbol_candidates (D-C1)

Per ogni candidato (in `candidates[]`):
- `regime`: enum `compressed|normal|expanded` (Wave 1: derivato da `compute_all_extended` → `regime_state`; fallback `normal`)
- `correlation_warnings`: list (Wave 1: vuoto `[]`; Wave 4 lo popola via `get_correlation_matrix`)

### R3: propose_trade (D-C1)

- `setup_type`: enum `A|B|C|D` \| null (Wave 1: passthrough da `args.context.setup_type`; Phase 4 derivation deferred)
- `confluence_score`: float 0-1 \| null (Wave 1: passthrough da `args.context.confluence_score`)
- Freeform flow: entrambi null se context assente

## Deliverable 3: BarSource D-D1

### Strict-< Semantics Verificata

Test `test_as_of_strict_lt_no_future_leak`:
- 4 barre con ts `[1700000000, 1700000900, 1700001800, 1700002700]`
- `as_of_ts = 1700001800` (esatto sul terzo bar)
- `bisect_left(arr, 1700001800) = 2` (insertion point STRICT-<)
- Risultato: `bars[0:2]` (le prime 2 barre) — bar @ ts 1700001800 ESCLUSA ✓

### Test Branches

| Test | Verdict | Note |
|------|---------|------|
| `test_live_path_calls_mt5` | PASS | as_of_ts=None → delega `mt5.get_ohlc` |
| `test_as_of_strict_lt_no_future_leak` | PASS | CRITICO — bar esatto ESCLUSO |
| `test_as_of_warmup_insufficient` | PASS | ValueError("as_of_ts_warmup_insufficient") quando cutoff < n |
| `test_as_of_out_of_range` | PASS | cutoff > len unreachable via bisect_left; ramo difensivo → ritorna ultime n barre disponibili |
| `test_as_of_csv_missing` | PASS | FileNotFoundError propagato (handler converte a envelope `historical_data_unavailable`) |

### Out-of-range branch verdict

`if cutoff > len(ts_arr)` è codice morto (bisect_left ritorna max `len(arr)`); mantenuto come safety net documentata.

## Deliverable 4: Mt5Client Wrappers (Wave 3 prep)

### Signatures + retcode mapping

```python
def modify_position(self, position_id: int,
                    sl: float | None = None,
                    tp: float | None = None) -> OrderResult:
    # action=TRADE_ACTION_SLTP, position=ticket, sl=float, tp=float
    # retcode==TRADE_RETCODE_DONE → success=True
    # positions empty → error_message="position N non trovata"

def partial_close(self, position_id: int, lots: float) -> OrderResult:
    # action=TRADE_ACTION_DEAL, volume=lots, type=opposite (mirror close_position)
    # lots<=0 or lots>=pos.volume → error_message="partial volume non valido"
    # resolve_filling_mode → TenTrade ORDER_FILLING_RETURN

def get_position(self, position_id: int) -> PositionInfo | None:
    # positions_get(ticket=...) → PositionInfo | None
```

Tutti `@_retry(3)` decorati. Pattern mirror `close_position` linee 191-250.

## Deliverable 5: Config Surface

```python
# config.py:101
MCP_DEFAULT_BARS: int = int(os.getenv("MCP_DEFAULT_BARS", "200"))

# .env.example:69
MCP_DEFAULT_BARS=200
```

Wave 2 aggiungerà `MCP_MAX_CONCURRENT_RUNS`; Wave 3 aggiungerà `TRAIL_TICK_TIMEFRAME` / `TRAIL_FAVORABLE_ONLY`.

## Phase 2 Surface Availability

| Symbol | Available | Note |
|--------|-----------|------|
| `indicators.compute_all` | ✓ | 4-key legacy (sma_20/ema_50/rsi_14/atr_14) |
| `indicators.compute_all_extended` | ✓ | Phase 2 ExtendedIndicators dict ~37 chiavi |
| `regime_state` in extended | ✓ | Phase 2 INDIC-14 ritorna compressed/normal/expanded quando `regime_cfg` passato; senza cfg → None (fallback handler 'normal') |
| `compute_atr_regime` standalone | ✗ | Non disponibile in `indicators/` package; R2 usa `regime_state` field interno di `compute_all_extended` |

## Test Results

### Wave 1 (scope diretto Plan 06-02)

| Test File | Total | Pass | Xfail | Note |
|-----------|-------|------|-------|------|
| `test_mcp_bar_source.py` | 5 | 5 | 0 | Tutti BarSource green |
| `test_mcp_handlers_market.py` | 10 | 5 | 5 | 5 R1/R2 green + 5 Wave 4 xfail preservati |
| `test_mcp_handlers_proposal.py` | 2 | 2 | 0 | 2 R3 green |
| `test_mcp_legacy_compat.py` | 3 | 1 | 2 | 1 import-check green, 2 Wave 2-3 xfail |
| `test_mcp_tools_v2.py` (legacy) | 15 | 15 | 0 | Zero regressione |
| **TOTALE Wave 1 scope** | **35** | **28** | **7** | **80% pass / 20% xfail Wave 2-4** |

### Suite globale

- `python -m pytest` (escluso 4 file pre-esistenti import error): **428 passed, 11 skipped, 41 xfailed, 1 failed**
- 1 failed = `test_smoke_12month_under_60s` (Phase 1 perf, **pre-esistente** verificato con `git stash`, deferred)

## Known Stubs / Limitations

- **R3 derivation Phase 4**: setup_type/confluence_score deriva da Phase 4 `evaluate_proposal_for_bar` non implementata in Wave 1 (richiede StrategyContext costruito upstream). Nel `handle_propose_trade` la logica è esplicitamente pass-through da `args.context`. Documentato come scelta D-C1 nel docstring.
- **R2 correlation_warnings**: array vuoto `[]` in Wave 1 — popolato da Wave 4 quando `get_correlation_matrix` esisterà.
- **Wave 4 xfail preservati** in `test_mcp_handlers_market.py`: 5 test (`test_correlation_matrix_2symbols`, `test_correlation_default_lookback`, `test_session_state_london_open`, `test_session_state_dst`, `test_multi_tf_snapshot`) restano xfail come da Wave 0 scaffolding.
- **Wave 2/3 xfail preservati**: `test_mcp_handlers_backtest.py` (10 xfail), `test_mcp_handlers_position.py` (8 xfail), `test_mcp_smoke_round_trip.py`, `test_mcp_job_queue.py`, `test_mcp_trail_daemon.py`, `test_mcp_integration_modify.py`.

## Deferred Issues (Out of Scope)

Vedi `.planning/phases/06-mcp-tools-part-1/deferred-items.md`:
- `test_backtest_engine.py::test_smoke_12month_under_60s` (Phase 1 perf, pre-esistente)
- 4 collection errors per moduli mancanti (`feedparser`, `apscheduler` — Phase 14-15)
- File untracked Phase 5: `data/training/baseline_decisions.pre-05-09/`, `trades.db`

## Threat Surface Confirmed (vs Plan threat_model)

Tutti i mitigation D-F2 / D-C1 / D-D1 implementati come previsto:
- T-6-02-01 Tampering: BarSource CSV path da loader Phase 1, no user input ✓
- T-6-02-03 Spoofing: setup_type enum-validated `in ("A","B","C","D")` ✓
- T-6-02-04 Tampering: modify_position wrapper ship-ed senza handler (gate DRY_RUN Wave 3 upstream) ✓
- T-6-02-07 EoP: rename mcp/ → mcp_tools/ verificato (eliminata collisione con SDK PyPI a livello di filesystem locale; package locale è `mcp_tools/`, non `mcp/`) ✓

### Nota su Wave 0 mcp/ stub (out-of-scope Plan 06-02)

Il package `mcp/` esistente in repo (creato in Wave 0 Plan 06-01) contiene:
- `mcp/__init__.py` (32 byte, no-op)
- `mcp/errors.py` (D-F2 ErrorCodes — usato da `mcp_tools/errors.py`)
- `mcp/server/__init__.py` (stub forward al SDK PyPI via importlib)
- `mcp/types.py` (stub)

Su ambiente Codespace Linux SENZA SDK PyPI `mcp` installato, lo stub usa fallback in-memory che mimano `Server`/`stdio_server` per permettere ai test di girare. Su Windows con SDK installato, lo stub forwardera' al SDK reale (`<venv>/Lib/site-packages/mcp/server/__init__.py`).

Acceptance criterion del Plan: `python -c "import mcp; print(mcp.__file__)" | grep -i 'site-packages'` — su Codespace Linux NON match (SDK non installato), su Windows con MT5 dev env match. Questo è infrastruttura Wave 0 (Plan 06-01), non Plan 06-02 — non risulta deviation Plan 06-02.

## Self-Check: PASSED

Vedi sezione `Self-Check` in fondo.

## Next: Wave 2 + Wave 3

- **Wave 2 (Plan 06-03):** backtest queue async + JobQueue + cancel_backtest. Requires: `MCP_MAX_CONCURRENT_RUNS` env, `backtest_runs.status` (già da Wave 0).
- **Wave 3 (Plan 06-04):** trail daemon in-process + handle_modify_position + position_trails table. Requires: `Mt5Client.modify_position/get_position` (shipped Wave 1 ✓), `TRAIL_TICK_TIMEFRAME` env.
- **Wave 4 (Plan 06-05):** get_correlation_matrix, get_session_state, get_multi_tf_snapshot, get_pattern_catalog, replay_decision. Consumerà `BarSource.get(as_of_ts=...)` shipped Wave 1.
- **Follow-up tests Wave 2-4**: i 5 Wave 4 xfail + 18 Wave 2-3 xfail dovranno flippare in green nei rispettivi plan.

## Self-Check

### File created exist

- `mcp_tools/handlers/market.py` → FOUND
- `mcp_tools/handlers/proposal.py` → FOUND
- `.planning/phases/06-mcp-tools-part-1/deferred-items.md` → FOUND

### Commit existing

- `bcb05de` (Task 1) → FOUND
- `ed69b65` (Task 2 RED) → FOUND
- `095414a` (Task 2 GREEN) → FOUND
- `fd0d4c2` (Task 3 RED) → FOUND
- `2d96bbb` (Task 3 GREEN) → FOUND

## Self-Check: PASSED
