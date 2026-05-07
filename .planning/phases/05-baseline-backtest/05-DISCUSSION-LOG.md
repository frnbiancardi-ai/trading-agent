# Phase 5: Baseline Backtest - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 05-baseline-backtest
**Areas discussed:** Decision dataset schema (parquet), Walk-forward vs single-pass, Risk profile / config matrix, Runner + report format

---

## Decision dataset schema (parquet)

### Q1.1 — Granularità riga in `baseline_decisions.parquet`

| Option | Description | Selected |
|--------|-------------|----------|
| Una riga per trade chiuso (READY only) | Solo READY entrati nel ledger, label binary win/loss diretto | |
| Una riga per ogni Draft (READY+FORMING+NONE) | Decuplica righe (~500k+), permette ML 'should-have-traded' | |
| Doppio dataset | `baseline_decisions.parquet` (trade chiusi) + `baseline_drafts.parquet` (tutti Draft) | ✓ |

**User's choice:** Doppio dataset.
**Notes:** Storage cost accettato per coverage massima Phase 7 ML training. → D-01.

### Q1.2 — Schema feature columns `baseline_decisions.parquet`

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot completo: identità + ProposalDraft + ExtendedIndicators + ctx | Massimo signal per Phase 7, no ricalcolo indicator | ✓ |
| Minimal: solo Draft + outcome | ML deve ricalcolare indicators da bar al training | |
| Ibrido: Draft + indicator deltas selezionati | Compatto ma scelta soggettiva | |

**User's choice:** Snapshot completo.
**Notes:** → D-02. Tutti i campi `ExtendedIndicators` Phase 2 D-09 inclusi.

### Q1.3 — `baseline_drafts.parquet` granularità e content

| Option | Description | Selected |
|--------|-------------|----------|
| Solo Draft non-trade (READY-rejected + FORMING + NONE primo del bar) | Per-bar 1 riga, ~N_bar | |
| Tutti i Draft (4 detector × N_bar righe) | 4x size (~10M righe per slice M15) ma analisi per-detector contributions | ✓ |
| Solo winner per-bar (incluso READY traded) | 1 riga per bar col vincitore | |

**User's choice:** Tutti i Draft.
**Notes:** → D-03. Esplosione storage accettata, snappy compression mitiga.

### Q1.4 — Outcome label encoding

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-label: outcome + pnl_pips + pnl_money + exit_reason + bars_held | Phase 7 sceglie target adatto | ✓ |
| Binary win/loss only | Semplice ma perde info su timeout/breakeven | |
| Continuo: solo pnl_pips + bars_held | Push complessità a Phase 7 | |

**User's choice:** Multi-label.
**Notes:** → D-04.

### Q1.5 — Timeout policy

| Option | Description | Selected |
|--------|-------------|----------|
| Per-TF: M15=96 (24h), M30=96 (48h), H1=120 (5d) | Cap soft, coerente intraday/swing | ✓ |
| No timeout — chiusura solo a TP/SL/end-of-data | Skewa pnl/expectancy | |
| Universale: 200 bars per qualsiasi TF | Mescola intraday e swing | |

**User's choice:** Per-TF.
**Notes:** → D-05.

---

## Walk-forward vs single-pass

### Q2.1 — Strategia esecuzione baseline 23.5y

| Option | Description | Selected |
|--------|-------------|----------|
| Single-pass full 23.5y in-sample | Una run unica per slice, ML walk-forward arriva Phase 7 | ✓ |
| Walk-forward folded baseline (rolling 10 folds) | 10x cost, ridondante per baseline pre-ML | |
| Doppio: single-pass per report, walk-forward train/test split per dataset | Hybrid | |

**User's choice:** Single-pass full 23.5y in-sample.
**Notes:** → D-06.

### Q2.2 — Warm-up period

| Option | Description | Selected |
|--------|-------------|----------|
| Count-based: 200 bars universale | Allineato max lookback indicator | |
| Time-based: 30 giorni reali | ~2880 bar M15, ~720 H1 | |
| Adaptive: max(200, longest_lookback_required) | Auto-correct se Phase 2 aggiunge indicator con lookback>200 | ✓ |

**User's choice:** Adaptive.
**Notes:** → D-07. Question riformulata dopo user chiese chiarimento (originale aveva 2 opzioni equivalenti).

### Q2.3 — Concurrency intra-slice

| Option | Description | Selected |
|--------|-------------|----------|
| Max 1 trade aperto per slice (no overlap) | Allineato live scheduler intraday | ✓ |
| Max N>1, configurabile | Permette pyramiding/scaling, deviazione dal live | |
| Unlimited — ogni READY entra | Overstates expectancy, sconsigliato | |

**User's choice:** Max 1.
**Notes:** → D-08.

### Q2.4 — Cross-slice concurrency

| Option | Description | Selected |
|--------|-------------|----------|
| Slice indipendenti — ogni run isolato, no portfolio constraint | Misura edge intrinseco, semplice | ✓ |
| Portfolio mode — single equity curve, correlation guard attivo | Realistico ma fonde TF diversi (poco sensato) | |
| Per-pair portfolio | Mid-ground, complica metric per-slice | |

**User's choice:** Slice indipendenti.
**Notes:** → D-09. Spiegazione dettagliata fornita prima della scelta. Portfolio simulation rimandata Phase 11.

### Q2.5 — Equity iniziale + sizing

| Option | Description | Selected |
|--------|-------------|----------|
| 10k EUR fissa, sizing dinamico via risk_engine + profile | Compounding intra-slice, allineato live | ✓ |
| 10k EUR fissa, lot fisso 0.10 no compounding | P&L lineare ma divaricato dal live | |
| 10k EUR fissa, sizing dinamico, compounding off | Isola edge da effetto compounding | |

**User's choice:** Dynamic sizing + compounding on.
**Notes:** → D-10. Question riformulata dopo discussione su micro-account / leva — concluso che <500 EUR introduce lot quantization tax indipendente da leva, deferred a Phase 11.

---

## Risk profile / config matrix

### Q3.1 — Quale profile guida il baseline

| Option | Description | Selected |
|--------|-------------|----------|
| Solo MODERATE (1 run per slice = 9 totali) | Profile mediano, fitta budget comodamente | |
| Tutti e 3 (CONSERVATIVE/MODERATE/AGGRESSIVE) = 27 run | Coverage completo, dataset 3x più ricco | ✓ |
| MODERATE per report, tutti e 3 per dataset | Hybrid | |

**User's choice:** Tutti e 3 in parallelo.
**Notes:** → D-11. Forces multiprocessing nel runner, budget tempo sotto pressione.

### Q3.2 — `cost.yaml` per-profile?

| Option | Description | Selected |
|--------|-------------|----------|
| Invariato per-symbol | Costi sono broker-side, profile cambia solo entry filter | ✓ |
| Per-profile override opzionale | Realismo extra ma soggettivo | |

**User's choice:** Invariato.
**Notes:** → D-12.

### Q3.3 — Run identifier schema

| Option | Description | Selected |
|--------|-------------|----------|
| `baseline_{date}_{symbol}_{tf}_{profile}` | Human-readable, deduplica re-run | ✓ |
| UUID + meta columns | Robusto multi-run analysis ma meno leggibile | |
| `git_sha + slice + profile` | Tracciabile a commit ma re-run = collision | |

**User's choice:** Schema leggibile.
**Notes:** → D-13.

### Q3.4 — Idempotenza re-run

| Option | Description | Selected |
|--------|-------------|----------|
| Skip se esiste, log warning, --force per overwrite | Default safe, re-run incrementale | ✓ |
| Overwrite sempre | Idempotente di default ma più lento | |
| Append nuovo run_id con suffix | Storico ma esplode storage | |

**User's choice:** Skip + --force.
**Notes:** → D-14.

---

## Runner + report format

### Q4.1 — Parallelism strategy

| Option | Description | Selected |
|--------|-------------|----------|
| ProcessPoolExecutor su 27 task | Max parallelism ma 27× indicator compute spreco | |
| Sequenziale + cache indicator condivisa per slice | 9× compute ma 3× più lento wall-clock | |
| Hybrid: parallel su 9 slice, sequenziale 3 profile | 9× compute + parallelism, miglior trade-off | ✓ |

**User's choice:** Opzione 3 (hybrid).
**Notes:** → D-15. User chiese chiarimento dettagliato delle 3 opzioni; deciso anche di lockare slippage seed + config hash per determinism. → D-17.

### Q4.2 — Report schema

| Option | Description | Selected |
|--------|-------------|----------|
| Header + tabella 27-row + per-slice mini-section + appendix config | Completo, audit-friendly | ✓ |
| Tabella + sezione comparativa cross-profile | Più analitico, meno per-slice | |
| Minimo: solo tabella + link PNG | Compatto | |

**User's choice:** Header + tabella + mini-section + appendix.
**Notes:** → D-18.

### Q4.3 — Equity curves PNG layout

| Option | Description | Selected |
|--------|-------------|----------|
| 27 file separati `{symbol}_{tf}_{profile}.png` | 1 PNG per run | ✓ |
| 9 file (1 per slice), 3 line per profile sovrapposte | Compatto ma legend carica | |
| Grid 3x3 per profile (3 PNG totali) | Overview-style ma perde dettaglio | |

**User's choice:** 27 file separati.
**Notes:** → D-19.

### Q4.4 — Plot library

| Option | Description | Selected |
|--------|-------------|----------|
| matplotlib plain | Zero nuove dep, allineato SC#4 PNG | ✓ |
| matplotlib + seaborn theme | Look più curato, dep nuova | |
| plotly interattivo HTML | Esplorabile ma viola SC#4 (PNG), ~80MB dep | |

**User's choice:** matplotlib plain.
**Notes:** → D-20. Spiegazione dettagliata 3 opzioni fornita prima della scelta.

---

## Claude's Discretion

- Module layout: `backtest/baseline/` package suggerito (mirror Phase 1).
- Tabella metrics ordering (default: symbol → tf → profile alfabetico).
- Equity y-axis: EUR linear vs % vs log (default: EUR linear).
- Per-slice mini-section narrative depth (default: solo statistici, no commentary).
- Snappy vs zstd parquet compression (default: snappy).
- `tqdm` progress bar console (default: yes).

## Deferred Ideas

- Walk-forward sul baseline (Phase 7 ML).
- Portfolio simulation cross-slice (Phase 11).
- Micro-account stress test <500 EUR + lot quantization realism (Phase 11).
- Per-profile cost.yaml override.
- Plot library upgrade seaborn/plotly.
- Returns log vs simple per Sharpe (Phase 1 metrics o Phase 7).
- HTML interactive report (out of SC#4).
- Vectorized backtest (Phase 5 Wave 2 se SC#1 sforata).
- `--resume` flag from checkpoint (lightweight idempotency).
- Parquet partition by symbol/tf.
- Per-symbol strategy.yaml override.
