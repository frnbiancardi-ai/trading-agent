# `.planning/archive/` — codice storicizzato

Contiene file rimossi dal tree ma preservati per provenance / revert / confronto
A/B futuro. Non viene più caricato runtime (zero import dal codice di produzione).

## Inventario

### `strategy_legacy.py`

- **Archiviato:** 2026-05-08, plan 04-08 Phase 4 cleanup (option-a applied)
- **Sostituito da:** package `strategy/` (orchestratore `evaluate_proposal_for_bar`
  + 4 detector pure-fn `strategy/setups/{a_breakout,b_reversal,c_compression,d_pullback}.py`
  + scorer `strategy/confluence.py` + adapters `strategy/adapters/{live,backtest}.py`
  + shim `strategy/_shim.py` `IntradayStrategy`).
- **Motivo archive (vs delete):** Phase 5 baseline backtest deve validare la
  nuova calibrazione 5-factor con metriche aggregate (PF, drawdown, hit-rate,
  expectancy) prima di paper deploy (Phase 11). Se il backtest invalida la
  scelta option-a, è possibile revert a:
  - **option-b** — alzare gate `trend_strength > 0.65` sui detector
  - **option-c** — feature flag `gate_min_trend_strength` in `config/strategy.yaml`
  - **option-d** — env flag `STRATEGY_ENGINE=legacy|pure`, default legacy

  Per qualunque di queste opzioni serve avere il legacy come riferimento
  funzionante. Archiviato (non deletato) preserva la possibilità senza
  inquinare il top-level del repo.
- **Re-import esplicito (debug only, NON in produzione):**
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent / ".planning" / "archive"))
  from strategy_legacy import IntradayStrategy as LegacyIntradayStrategy  # noqa
  ```
  L'import richiede sys.path manipulation deliberata — non c'è risk di accidental
  re-activation del legacy.
- **Stato di provenienza:** ultimo commit prima dell'archive: `575b484`
  (test re-baseline post option-a). Il file è bit-identical alla versione che
  girava in produzione fino al cutover Wave 3 (`35d53d8`, plan 04-07).
- **Riferimenti:**
  - `.planning/phases/04-strategy-refactor/04-08-PLAN.md` Task 3 (cleanup)
  - `.planning/phases/04-strategy-refactor/04-08-RECONCILIATION.md` (decisione)
  - `.planning/phases/04-strategy-refactor/04-08-SUMMARY.md` (esecuzione finale)
  - Plan 04-07 SUMMARY (cutover dettagliato)

## Regole

- **NESSUN import** dal codice di produzione su file in questa cartella.
  Il purity gate `tests/test_strategy_purity.py` verifica solo `strategy/**`,
  non quest'archivio. Aggiungere import da qui significa silenziosamente
  bypassare il gate.
- **NESSUN test** nuovo lancia codice da questa cartella se non è esplicitamente
  contrassegnato come "regression A/B comparativo Phase 5". Marker pytest
  `archived_legacy` consigliato per tali test.
- **Diff comparativo Phase 5:** se serve confrontare nuova vs legacy su un
  campione di scenari, scrivere uno script ad-hoc in `tests/archive/` (NON
  in `tests/test_*.py`) che importa entrambi e produce un report.
