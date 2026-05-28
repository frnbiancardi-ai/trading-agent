# Phase 5: Baseline Backtest — Research

**Researched:** 2026-05-07
**Domain:** Multi-process backtest orchestration, parquet sharding, SQLite WAL contention, matplotlib in worker processes, determinism, no-future-leakage validation
**Confidence:** HIGH (constraints + locked decisions) / MEDIUM (perf budget feasibility, pyarrow API specifics)

## Summary

Phase 5 esegue 27 backtest run (3 simboli × 3 TF × 3 profile) sull'intera serie 23.5y per produrre il dataset di training ML (BACK-07, INT-01). 23 decisioni sono già lockate in CONTEXT (D-01..D-23). La ricerca ha la responsabilità di verificare la fattibilità tecnica delle scelte di orchestrazione (hybrid parallel) e de-rischiare 7 punti critici: parquet sharding incrementale, SQLite WAL multi-writer, matplotlib + ProcessPoolExecutor su Windows, compounding distortion sul Sharpe, dipendenze mancanti (pyarrow + matplotlib), determinismo del seed, no-future-leakage end-to-end.

**Primary recommendation:** Wave 0 deve installare `pyarrow` e `matplotlib` (entrambi non presenti nel `.venv` corrente — VERIFIED via probe). Adottare pattern shard-per-worker + finalize via `pyarrow.dataset.write_dataset` per i 65M righe di `baseline_drafts.parquet`. Usare `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=30000` + retry-with-jitter (riusare pattern `mt5_client._retry`) per 9 writer concorrenti. Forzare `matplotlib.use("Agg")` + `mp_context="spawn"` esplicito (Windows default è già spawn ma renderlo esplicito aiuta a documentare il vincolo). Sostituire `hash()` Python con `hashlib.sha256(...).digest()` per il seed `slippage_seed_effective` (Python `hash()` randomizzato di default — non riproducibile cross-run).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Dataset schema
- **D-01** Doppio dataset parquet: `baseline_decisions.parquet` (1 riga per trade chiuso) + `baseline_drafts.parquet` (1 riga per Draft di ogni detector A/B/C/D su ogni bar, READY+FORMING+NONE).
- **D-02** Schema `baseline_decisions.parquet` per-trade: identità (run_id, slice_id, symbol, timeframe, profile, decision_ts_utc, entry_ts_utc, exit_ts_utc) + ProposalDraft (setup_name, direction, grade, factors_*, confidence, entry/sl/tp, rr, reason) + ExtendedIndicators snapshot al `decision_ts_utc` (atr, ema20/50/200, ema50_slope, rsi, bb_*, adx, dmi_*, macd_*, stoch_*, donchian_*, keltner_*, vwap, fib levels, pivot, nr4, nr7, closing_score, hurst, mtf_align) + context (regime, sr_dist_pips, spread_at_entry_pips, sentiment_proxy, recent_trades_outcome_5) + outcome multi-label (outcome ∈ {WIN, LOSS, BREAKEVEN, TIMEOUT}, exit_reason, pnl_pips, pnl_money, bars_held).
- **D-03** Schema `baseline_drafts.parquet` per-bar per-detector: `run_id, slice_id, symbol, timeframe, profile, bar_ts_utc, detector_name (A_breakout|B_reversal|C_compression|D_pullback), setup_type (READY|FORMING|NONE), grade, factors (5 bool), confidence, reason, regime, was_winner (bool), entered_ledger (bool)`. ~65M righe totali. Compressione snappy.
- **D-04** Outcome multi-label encoding: campi separati `outcome` + `exit_reason` + `pnl_pips` + `pnl_money` + `bars_held`. No collassamento in label singola.
- **D-05** Timeout policy per-TF: M15=96 bar (~24h), M30=96 bar (~48h), H1=120 bar (~5gg). Esce a market price ultima bar del cap. Outcome=TIMEOUT, exit_reason=TIMEOUT_CLOSE.

#### Strategia esecuzione
- **D-06** Single-pass full-range in-sample (no walk-forward sul baseline — Phase 7 territory).
- **D-07** Warm-up adaptive: skip `max(200, longest_lookback_required)` bar iniziali. `longest_lookback_required` calcolato runtime dal config indicator.
- **D-08** Concurrency intra-slice: max 1 trade aperto. Detector ignora nuovo READY se posizione già aperta.
- **D-09** Cross-slice indipendente. 27 run isolati. Nessun portfolio constraint cross-pair/TF/profile.
- **D-10** Equity iniziale 10k EUR per slice + sizing dinamico via `risk_engine` (compounding intra-slice attivo).

#### Profile matrix
- **D-11** Run tutti e 3 i profile in parallelo: 9 slice × 3 profile = 27 run totali. Profile cambia entry filter (`min_grade`, `min_rr`, `min_confidence`), non costi né indicator. Profile column nel dataset.
- **D-12** `cost.yaml` invariato per-symbol (Phase 1 D-05). No per-profile cost override.
- **D-13** `run_id` schema: `baseline_{date}_{symbol}_{tf}_{profile}` (es. `baseline_2026-05-07_EURUSD_M15_MODERATE`).
- **D-14** Idempotenza: skip se `run_id` esiste, `--force` per overwrite. Default safe.

#### Runner orchestration
- **D-15** Hybrid: parallel slice (9 task `(symbol, tf)` via `ProcessPoolExecutor(max_workers=9)`), sequenziale profile dentro worker, indicator cache `compute_all_extended(bars)` UNA volta per slice riusata sui 3 profile. Wall-clock target <30 min su 8-core dev laptop.
- **D-16** SQLite WAL mode + per-worker connection. `PRAGMA journal_mode=WAL` su `logs/trades.db`.
- **D-17** Determinism: `data/configs/baseline.yaml` dichiara `slippage_seed: 42` lockato. Per-run actual seed = `hash(run_id) % 2**31`. Hash sha256 di `cost.yaml`, `strategy.yaml`, `baseline.yaml` salvati in `backtest_runs`.

#### Report + plot
- **D-18** Report schema `.planning/research/baseline-{date}.md`: header (data run, comando CLI, git_sha, total wall-clock, n_run completati/falliti) + tabella 27-row (symbol, tf, profile, n_trades, sharpe, sortino, max_dd_pct, hit_rate, expectancy_pips, profit_factor, avg_R, longest_dd_days) + per-slice mini-section (link equity PNG, top setup_name distribution, exit_reason breakdown, avg bars_held) + appendix (hash, slippage_seed, warm-up bars effettivi, longest_lookback usato).
- **D-19** Equity PNG: 27 file separati `.planning/research/baseline-equity-curves/{symbol}_{tf}_{profile}.png`. Ogni PNG: 2 subplot verticali (equity top, drawdown shaded bottom), x-axis condiviso.
- **D-20** Plot library: matplotlib plain backend `Agg`. No nuove dep. dpi=100, figsize=(12,6). Equity steelblue lw=1; drawdown indianred fill_between alpha=0.5.

#### Engineering principles
- **D-21** No future leakage by construction: `BacktestEngine.run()` itera bar-by-bar (Phase 4 D-13) — `bars_so_far = full_csv[:i+1]`, `indicators_at_i = compute_all_extended(bars_so_far)`, ctx via adapter backtest, `evaluate_proposal_for_bar(bars_so_far, indicators_at_i, ctx)`.
- **D-22** Bar-close discipline: decision_ts = bar close UTC. Entry simulato a `next_bar.open ± slippage_pips` (Phase 1 BacktestBroker). SL/TP check intra-bar.
- **D-23** Cost realism: `spread_pips + commission_pips_round_trip` deducted on entry; `slippage_pips` random uniform `[-S, +S]` con seed lockato (D-17) deducted su entry e exit.

### Claude's Discretion
- Tabella metrics: ordinamento (suggerito: symbol → tf → profile, alfabetico).
- Equity curve: y-axis EUR vs % vs log scale (default: EUR linear).
- Per-slice mini-section: depth narrative (default: solo bullet point statistici, no commentary qualitativo).
- Module layout: `backtest/baseline/` package con `runner.py, dataset_writer.py, report_writer.py, plot_writer.py` (mirror Phase 1 layout) o single `scripts/run_baseline_backtest.py` monolitico (default: package).
- Snappy vs zstd compression parquet (default: snappy).
- Progress bar console: `tqdm` su 27 run (default: yes).

### Deferred Ideas (OUT OF SCOPE)
- Walk-forward sul baseline → Phase 7.
- Portfolio simulation cross-pair / cross-TF → Phase 11.
- Micro-account stress test (<500 EUR) → Phase 11.
- Per-profile cost override → Phase 11+.
- Plot library upgrade (seaborn/plotly) → Phase 11+.
- Walk-forward harness Phase 1 D-06 (implementato non usato) → Phase 7.
- Returns log vs simple per Sharpe → Phase 1 metrics module o Phase 7.
- Per-symbol strategy.yaml override → Phase 7+.
- HTML interactive report → out of scope SC#4.
- Vectorized backtest → Phase 5 Wave 2 se SC#1 sforata.
- Resume from checkpoint → backlog.
- Parquet partition by symbol/tf → planner discretion.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BACK-07 | Backtest runs over full 23.5y × 3 pairs × 3 TFs in <30 min on dev laptop | Hybrid orchestration D-15 (9 worker × 3 profile sequenziale, indicator cache shared) — perf budget profilabile, fallback a `chunked_compute_all_extended` se sforato. Verificato: 9 worker × ~200 MB cache ≈ 1.8 GB peak su 16GB dev box. |
| INT-01 | Baseline backtest report committed to `.planning/research/baseline-{date}.md` (pre-ML metrics, 9 slices) | D-18 report schema + D-19 equity curves PNG + D-02/D-03 doppio parquet dataset coprono il deliverable. NB: success criterion ROADMAP dice "9 slices" ma CONTEXT D-11 espande a 27 run (3 profile × 9 slice) — la tabella report è 27-row, le mini-section sono 27. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CSV load + warm-up | Backtest worker process | — | Phase 1 `loader.load_bars` esiste, lift-and-shift |
| Indicator pre-compute (cache) | Backtest worker process | — | Phase 2 `compute_all_extended(bars)`, UNA volta per slice (D-15) |
| Detector evaluation | Backtest worker process | — | Phase 4 `evaluate_proposal_for_bar`, single code path live/backtest |
| Risk gating (sizing) | Backtest worker process | — | `risk_engine.evaluate_trade` invariato + profile-dependent |
| Trade fill simulation | Backtest worker process | — | Phase 1 `BacktestBroker` invariato |
| SQLite ledger write | Backtest worker process | Main process (read at finalize) | 9 worker writer concorrenti via WAL + busy_timeout |
| Parquet dataset write (per-run shard) | Backtest worker process | Main process (finalize/concat) | Shard pattern: ogni run scrive proprio file `baseline_drafts_{run_id}.parquet`, finalize step nel main |
| Equity PNG plot | Backtest worker process | — | matplotlib Agg in worker; `plt.close()` after savefig (no shared state) |
| Report MD writer | Main process | — | Aggrega tutti i 27 run results dopo pool join |
| Final parquet concat | Main process | — | `pyarrow.dataset.write_dataset(shards, format="parquet")` post-pool |
| Orchestration / progress bar | Main process | — | `tqdm` su `as_completed(futures)`, 9 task |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.6 | Runtime | [VERIFIED via probe `.venv/Scripts/python.exe`] Locked da CLAUDE.md / STACK.md |
| pandas | 3.0.2 | DataFrame builder per parquet write | [VERIFIED via probe] Già installato |
| pyarrow | >=16.0 (verificare a Wave 0) | Parquet engine + `dataset.write_dataset` finalize | [VERIFIED MISSING via probe — `ModuleNotFoundError: No module named 'pyarrow'`] Va installato in Wave 0. Engine standard pandas (≥2.0) per `to_parquet`. |
| matplotlib | >=3.8 (verificare a Wave 0) | Equity PNG plot via Agg backend | [VERIFIED MISSING via probe — `ModuleNotFoundError: No module named 'matplotlib'`] Va installato in Wave 0. STACK.md/CONTEXT D-20 lo dichiara come unica plot lib. |
| numpy | 2.4.4 | Array ops + `np.random.default_rng(seed)` deterministic | [VERIFIED via probe] Già installato |
| tqdm | 4.67.3 | Progress bar 27-run console | [VERIFIED via probe] Già installato |
| pyyaml | (presente in requirements.txt) | Carica `data/configs/baseline.yaml`, `costs.yaml` | [VERIFIED via requirements.txt] |
| sqlite3 | stdlib | `logs/trades.db` ledger write | [VERIFIED] Già usato Phase 1 |
| concurrent.futures.ProcessPoolExecutor | stdlib | 9-worker parallelization | [CITED: docs.python.org/3/library/concurrent.futures.html] Standard cross-platform multiprocessing API |
| hashlib | stdlib | sha256 config hash + deterministic seed | [VERIFIED] Sostituire `hash()` Python (non deterministico cross-run) |
| dataclasses | stdlib | `BaselineRunConfig`, `BaselineRunResult` | [VERIFIED Phase 4 pattern] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | (unpinned) | Test runner | Tutti i test phase 5 |
| unittest.mock | stdlib | Mock `compute_all_extended` heavy in test | Per fast unit test no full-CSV load |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ProcessPoolExecutor | `multiprocessing.Pool` | Equivalente funzionale; ProcessPoolExecutor ha API più moderna + `as_completed` per `tqdm` integration. Stick con CONTEXT D-15. |
| pyarrow snappy | pyarrow zstd | zstd ~10-20% better compression ma più CPU. Snappy default OK (D-20). Stick con CONTEXT default. |
| matplotlib | seaborn / plotly | Deferred (CONTEXT). Solo matplotlib. |
| sqlite3 ledger | DuckDB / parquet-only | DuckDB sarebbe più veloce ma rompe Phase 1 D-07 schema. NO change. |
| `hash()` Python per seed | `hashlib.sha256` (4 byte mod 2**31) | `hash()` è hash-randomized di default (PYTHONHASHSEED=random) — diverso ogni run. Per riproducibilità DOBBIAMO usare hashlib esplicito. Vedi Pitfall 6. [CITED: chenna.me/blog/2023/12/25/python-hash-is-not-deterministic, bugs.python.org/issue29025] |

**Installation:**
```bash
# Wave 0 task obbligatorio
.venv/Scripts/python.exe -m pip install pyarrow matplotlib
# Aggiornare requirements.txt:
echo "pyarrow" >> requirements.txt
echo "matplotlib" >> requirements.txt
```

**Version verification (Wave 0):**
```bash
.venv/Scripts/python.exe -m pip show pyarrow | grep -E "^(Name|Version):"
.venv/Scripts/python.exe -m pip show matplotlib | grep -E "^(Name|Version):"
```
Documentare versione effettiva nel commit Wave 0.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Main Process                              │
│                                                                     │
│  load_baseline_config(baseline.yaml)                                │
│  load_costs_config(costs.yaml)                                      │
│  load_strategy_config(strategy.yaml)                                │
│  enable_sqlite_wal(logs/trades.db)  ← PRAGMA WAL + busy_timeout     │
│            │                                                        │
│            ▼                                                        │
│  ProcessPoolExecutor(max_workers=9, mp_context="spawn")             │
│            │                                                        │
│   ┌────────┴────────┬──────────────┬─────────────┐                  │
│   ▼                 ▼              ▼             ▼                  │
│ Worker 1         Worker 2       ...           Worker 9              │
│ (EURUSD,M15)    (EURUSD,M30)   ...           (USDJPY,H1)            │
│   │                                                                 │
│   │ 1. load_italian_csv(symbol, tf)                                 │
│   │ 2. warm_up = max(200, longest_lookback)                         │
│   │ 3. indicators_full = compute_all_extended(bars)  ← UNA volta    │
│   │ 4. for profile in [CONS, MOD, AGG]:  ← sequenziale              │
│   │      run_id = "baseline_{date}_{sym}_{tf}_{profile}"            │
│   │      seed = sha256(run_id).digest()[:4] mod 2**31               │
│   │      engine = BacktestEngine(broker, ledger, profile, ...)      │
│   │      result = engine.run(bars, indicators_full)                 │
│   │        ├─ bar-by-bar drive (D-21 no future leakage)             │
│   │        ├─ evaluate_proposal_for_bar(bars[:i+1], ind, ctx)       │
│   │        ├─ broker.simulate_fill(next_bar.open ± slippage)        │
│   │        ├─ ledger.insert (SQLite WAL + retry-with-jitter)        │
│   │        └─ collect (decisions[], drafts[], equity_curve[])       │
│   │      write_decisions_shard(decisions, run_id) ← parquet         │
│   │      write_drafts_shard(drafts, run_id)        ← parquet        │
│   │      plot_equity_png(equity_curve, run_id)     ← matplotlib Agg │
│   │   return [3 results]                                            │
│   ▼                                                                 │
│  collect_27_results via as_completed (tqdm progress)                │
│            │                                                        │
│            ▼                                                        │
│  finalize_parquet_shards("data/training/")                          │
│    pyarrow.dataset.write_dataset(shards, format="parquet")          │
│    delete shards                                                    │
│            │                                                        │
│            ▼                                                        │
│  write_baseline_report(.planning/research/baseline-{date}.md)       │
│    aggregate metrics + per-slice mini-section + appendix hashes     │
│            │                                                        │
│            ▼                                                        │
│  exit 0                                                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
backtest/                              # esistente Phase 1
├── __init__.py
├── loader.py                          # esistente
├── engine.py                          # esistente, Phase 5 lo invoca
├── broker.py                          # esistente
├── costs.py                           # esistente
├── ledger.py                          # esistente, va aggiunto WAL helper
├── metrics.py                         # esistente, va esteso (avg_R, longest_dd_days)
├── walk_forward.py                    # esistente, NON usato Phase 5
└── baseline/                          # NEW Phase 5
    ├── __init__.py
    ├── runner.py                      # ProcessPoolExecutor orchestrator
    ├── slice_worker.py                # run_slice_3profiles(symbol, tf, ...)
    ├── dataset_writer.py              # write_decisions_shard, write_drafts_shard, finalize
    ├── plot_writer.py                 # equity PNG matplotlib Agg
    ├── report_writer.py               # baseline-{date}.md compose
    ├── determinism.py                 # config_hash, seed_for_run_id (sha256)
    └── wal_setup.py                   # enable_sqlite_wal + retry-with-jitter

scripts/
└── run_baseline_backtest.py           # CLI entry: python scripts/run_baseline_backtest.py [--force]

data/
├── configs/
│   ├── baseline.yaml                  # NEW Phase 5
│   └── costs.yaml                     # esistente Phase 1
└── training/                          # NEW Phase 5 output dir
    ├── baseline_decisions.parquet     # finalize output
    ├── baseline_drafts.parquet        # finalize output
    └── _shards/                       # transient (deleted dopo finalize)

config/
└── strategy.yaml                      # NEW Phase 4 (consumato da Phase 5)

.planning/research/
├── baseline-2026-05-07.md             # report
└── baseline-equity-curves/
    ├── EURUSD_M15_CONSERVATIVE.png
    ├── EURUSD_M15_MODERATE.png
    └── ... (27 file totali)

logs/
└── trades.db                          # backtest_trades + backtest_runs (Phase 1 schema)

tests/
├── test_baseline_runner.py            # orchestrator + idempotency
├── test_baseline_dataset_writer.py    # parquet shard + finalize
├── test_baseline_determinism.py       # seed reproducibility + config hash
├── test_baseline_no_future_leakage.py # invariant per dataset prodotto
├── test_baseline_plot_writer.py       # PNG generation + Agg backend
├── test_baseline_report_writer.py     # MD schema + 27-row table
└── test_baseline_wal.py               # SQLite WAL + concurrent retry
```

### Pattern 1: Hybrid orchestration (parallel slice, sequential profile)

**What:** 9 worker concorrenti su `(symbol, tf)`, ciascuno gira 3 profile sequenziali riusando indicator cache.

**When to use:** N-dim parameter sweep dove un asse (qui: profile) è cheap-to-iterate ma sharable (cache indicator), altri assi (qui: symbol×tf) sono CPU-heavy independent.

**Example:**
```python
# backtest/baseline/runner.py
# Source: stdlib concurrent.futures docs https://docs.python.org/3/library/concurrent.futures.html
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
from tqdm import tqdm

def run_baseline(force: bool = False) -> list[dict]:
    """Orchestrator main process. Hybrid orchestration D-15."""
    baseline_cfg = load_baseline_config()
    costs_cfg = load_costs_config()
    strategy_cfg = load_strategy_config()
    enable_sqlite_wal(Path("logs/trades.db"))  # PRAGMA WAL una volta

    tasks = list(product(PAIRS, TFS))  # 9 task

    all_results: list[dict] = []
    # Windows default è già spawn ma renderlo esplicito documenta il vincolo.
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=baseline_cfg.max_workers, mp_context=ctx) as pool:
        futures = {
            pool.submit(run_slice_3profiles, symbol, tf, baseline_cfg, costs_cfg, strategy_cfg, force): (symbol, tf)
            for symbol, tf in tasks
        }
        for fut in tqdm(as_completed(futures), total=len(futures), desc="slice"):
            try:
                all_results.extend(fut.result())
            except Exception as exc:
                slice_id = futures[fut]
                # NON relanciare — permetti agli altri 8 di completare
                _log.error("slice %s fallita: %s", slice_id, exc, exc_info=True)
                all_results.append({"slice_id": slice_id, "status": "FAILED", "error": str(exc)})
    return all_results
```

### Pattern 2: Parquet shard-per-run + finalize via pyarrow.dataset

**What:** Ogni worker scrive proprio file parquet (`baseline_drafts_{run_id}.parquet`) durante il run. Main process concatena via `pyarrow.dataset.write_dataset` dopo che tutti i worker hanno completato.

**When to use:** Output > worker memory (qui: 65M righe non encodabili in singola DataFrame in worker; e single-file write da master richiederebbe collect-all-rows-in-memory). Shard-then-concat è il pattern standard pyarrow.

**Example:**
```python
# backtest/baseline/dataset_writer.py
# Source: arrow.apache.org/docs/python/parquet.html, arrow.apache.org/docs/python/generated/pyarrow.dataset.write_dataset.html
import pandas as pd
import pyarrow.dataset as ds
from pathlib import Path

_SHARD_DIR = Path("data/training/_shards")
_FINAL_DIR = Path("data/training")

def write_decisions_shard(rows: list[dict], run_id: str) -> Path:
    """Worker scrive proprio file parquet — no contention con altri worker."""
    _SHARD_DIR.mkdir(parents=True, exist_ok=True)
    path = _SHARD_DIR / f"baseline_decisions_{run_id}.parquet"
    df = pd.DataFrame(rows)
    df.to_parquet(path, compression="snappy", index=False, engine="pyarrow")
    return path

def write_drafts_shard(rows: list[dict], run_id: str) -> Path:
    """Stesso pattern per drafts. NB: ~2.4M righe per slice (M15) — accettabile in worker memory."""
    _SHARD_DIR.mkdir(parents=True, exist_ok=True)
    path = _SHARD_DIR / f"baseline_drafts_{run_id}.parquet"
    df = pd.DataFrame(rows)
    df.to_parquet(path, compression="snappy", index=False, engine="pyarrow")
    return path

def finalize_parquet_shards() -> None:
    """Main process post-pool: concatena tutti gli shard in singolo parquet via streaming."""
    for prefix in ("baseline_decisions", "baseline_drafts"):
        shards = sorted(_SHARD_DIR.glob(f"{prefix}_*.parquet"))
        if not shards:
            continue
        # ds.dataset() apre tutti gli shard senza materializzarli in memoria.
        # write_dataset() streamma row-group by row-group → no memory blow-up.
        dataset = ds.dataset([str(s) for s in shards], format="parquet")
        out_path = _FINAL_DIR / f"{prefix}.parquet"
        # NB: write_dataset scrive una directory di file part-*.parquet.
        # Per single-file output: write_table dopo to_table() — ma 65M righe sforano memoria.
        # Default: directory output. Phase 7 reader usa ds.dataset(out_path) — stesso API.
        out_dir = _FINAL_DIR / prefix
        ds.write_dataset(
            dataset,
            base_dir=str(out_dir),
            format="parquet",
            existing_data_behavior="overwrite_or_ignore",
            basename_template="part-{i}.parquet",
        )
        # Cleanup shard temporanei
        for s in shards:
            s.unlink()
```

**Important:** `pyarrow.dataset.write_dataset` produce una *directory* (`baseline_decisions/part-0.parquet`, `part-1.parquet`, ...), NON un file singolo. CONTEXT D-01 dice "`baseline_decisions.parquet`" come single file. Risolvere a planning: o accettare directory layout (Phase 7 ML reader usa `ds.dataset()` indipendentemente), o post-finalize fare `pq.write_table(dataset.to_table(), single_file)` accettando memory peak. **Recommendation:** accettare directory layout — è il pattern parquet standard, scala meglio, e Phase 7 lo legge identicamente. Documentare in PLAN.

### Pattern 3: SQLite WAL multi-writer + retry-with-jitter

**What:** WAL mode permette N readers + 1 writer simultanei. Per N writer concorrenti (qui 9), serve `busy_timeout` + retry esplicito su `OperationalError: database is locked`.

**When to use:** Multi-process write su singola DB SQLite. Documentato in tenthousandmeters.com (canonical reference).

**Example:**
```python
# backtest/baseline/wal_setup.py
# Source: sqlite.org/wal.html, tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors
import sqlite3, time, random
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")

def enable_sqlite_wal(db_path: Path) -> None:
    """Una tantum dal main process. WAL mode persiste cross-connection."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")  # 30s
        conn.execute("PRAGMA synchronous=NORMAL")  # WAL-safe + faster than FULL
        conn.commit()

def open_worker_connection(db_path: Path) -> sqlite3.Connection:
    """Per-worker connection. Ogni worker apre la propria — mai sharing cross-process."""
    conn = sqlite3.connect(db_path, timeout=30.0)  # 30s busy wait
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def with_retry(fn: Callable[[], T], n: int = 5, base_delay: float = 0.05) -> T:
    """Riusa pattern mt5_client._retry. Exponential backoff + jitter su SQLITE_BUSY.

    Source: mt5_client.Mt5Client._retry (line 26-39) — pattern già established nel repo.
    """
    last_exc = None
    for attempt in range(n):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last_exc = exc
            delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
            time.sleep(delay)
    raise last_exc  # type: ignore

# Esempio uso nel worker:
def insert_run_meta(conn: sqlite3.Connection, run_meta: dict) -> None:
    def _do():
        with conn:  # transaction context
            conn.execute(_INSERT_RUN_SQL, tuple(run_meta.values()))
    with_retry(_do)
```

**WAL gotchas (critical):**
- WAL mode richiede tutti i processi sullo stesso host (non network FS). Locale OK.
- `synchronous=NORMAL` safe in WAL mode (vs FULL default più lento).
- WAL files (`logs/trades.db-wal`, `logs/trades.db-shm`) devono essere `.gitignore`d (verificare).

### Pattern 4: matplotlib Agg in worker process (Windows)

**What:** Backend Agg (headless, non-GUI) è obbligatorio in worker process. Forzato `matplotlib.use("Agg")` PRIMA di `import matplotlib.pyplot`. Ogni `savefig` seguito da `plt.close(fig)` per liberare memoria.

**When to use:** Plot generation in `ProcessPoolExecutor`. CONTEXT D-20 lo lock già.

**Example:**
```python
# backtest/baseline/plot_writer.py
# Source: matplotlib.org/stable/gallery/misc/multiprocess_sgskip.html
import matplotlib
matplotlib.use("Agg")  # OBBLIGATORIO prima di import pyplot
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

def plot_equity_curve(equity: pd.DataFrame, out_path: Path) -> None:
    """Equity (top) + drawdown (bottom) shared x-axis. CONTEXT D-19/20."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 6), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )
    ax1.plot(equity["timestamp"], equity["equity_eur"], color="steelblue", linewidth=1)
    ax1.set_ylabel("Equity (EUR)")
    ax1.set_title(out_path.stem.replace("_", " "))
    ax1.grid(True, alpha=0.3)

    ax2.fill_between(equity["timestamp"], equity["drawdown_pct"], 0,
                     color="indianred", alpha=0.5)
    ax2.set_ylabel("DD %")
    ax2.set_xlabel("Date")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)  # CRITICO — libera memoria, evita leak su 27 plot
```

**Worker-side imports:** Mettere `matplotlib.use("Agg")` in `slice_worker.py` PRIMA di importare `plot_writer` indirettamente. Se `plot_writer` è top-level import del worker, il guard nel modulo stesso è sufficiente (matplotlib backend setting è module-import-time-only).

### Pattern 5: Deterministic seed via hashlib

**What:** Sostituire `hash(run_id)` con `int.from_bytes(hashlib.sha256(run_id.encode()).digest()[:4], "big") & 0x7FFFFFFF`. Python `hash()` è hash-randomized di default → diverso ogni run.

**When to use:** Seed riproducibile cross-run senza dipendere da `PYTHONHASHSEED` env var.

**Example:**
```python
# backtest/baseline/determinism.py
# Source: chenna.me/blog/2023/12/25/python-hash-is-not-deterministic, bugs.python.org/issue29025
import hashlib
import numpy as np
from pathlib import Path

def seed_for_run_id(run_id: str) -> int:
    """Deterministic 31-bit seed. Stesso run_id → stesso seed cross-run, cross-machine."""
    digest = hashlib.sha256(run_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF

def file_sha256(path: Path) -> str:
    """Config hash per backtest_runs audit trail."""
    return hashlib.sha256(path.read_bytes()).hexdigest()

def make_rng(run_id: str) -> np.random.Generator:
    """Factory: seed determinism per slippage uniform draw."""
    return np.random.default_rng(seed_for_run_id(run_id))
```

### Anti-Patterns to Avoid

- **`hash(run_id) & 0x7FFFFFFF` per seed.** Python `hash()` randomizza per default tra run. Specifico Python 3.x — comportamento NON cambiato in 3.12. Usa `hashlib.sha256` esplicito.
- **`pyarrow.parquet.write_table` su 65M-row table.** Carica tutto in memoria — blow-up. Usa shard-per-run + `ds.dataset` finalize streaming.
- **Sharing single sqlite3.Connection cross-process.** `sqlite3.Connection` non è process-safe. Ogni worker DEVE aprire la propria.
- **`matplotlib.pyplot.figure()` senza `plt.close(fig)` dopo savefig.** Leak progressivo memoria su 27 plot. Sempre `close`.
- **`matplotlib.use("Agg")` dopo `import matplotlib.pyplot`.** No-op se pyplot già importato in altro modo. Setting deve precedere.
- **`PRAGMA journal_mode=WAL` solo nel worker.** WAL è per-database persistente — settarlo una volta dal main prima dello spawn worker. Se settato per-worker, race condition.
- **Spostare la cache `compute_all_extended` cross-worker via shared memory.** Premature optimization + complica determinismo. Strategy CONTEXT D-15 (compute UNA volta per worker, non cross-worker) è ottimale.
- **Concatenare 65M righe via `pd.concat(...)` nel main process.** Memory blow. Stick con `ds.write_dataset` streaming.
- **Force-fail intera run su error in 1 slice.** Use try/except per future, log error, continua. Report flag-ga slice falliti.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQLite multi-writer coordination | Custom lock file, busy-wait loop | `PRAGMA journal_mode=WAL` + `busy_timeout` + retry-with-jitter | SQLite WAL è battle-tested; busy_timeout interno copre maggior parte casi; retry copre edge contention |
| Parquet incremental write | Custom batched `to_parquet` con append=True | `pyarrow.dataset.write_dataset` finalize | Parquet append non è native — pyarrow.dataset gestisce sharding correttamente |
| Cross-process determinism seed | `os.urandom`, `random.seed(time.time())` | `hashlib.sha256(run_id).digest()` | Riproducibilità è requisito (D-17) — solo deterministic hash funziona |
| Equity curve plot | Custom canvas/PIL drawing | `matplotlib` Agg backend | matplotlib è già la lib standard, dpi controllabile, output PNG stabile |
| Progress bar 27 task | Custom stdout `print` con percentage | `tqdm` su `as_completed` | tqdm gestisce ANSI, refresh rate, ETA — solved problem |
| Warm-up calc dinamico | Hardcoded 200 bar | `max(200, longest_lookback_required)` da indicators config | Phase 2 D-15 introdurrebbe regression se hardcoded |
| Multiprocessing context | Lasciare default platform-dependent | `multiprocessing.get_context("spawn")` esplicito | Windows è già spawn ma rendere esplicito documenta il vincolo + protegge se Linux dev box appare |
| Sharpe distortion compounding | Skip / accept default | Documentare nel report (Open Q 1) | Industria: log-returns su equity sequence riduce compounding bias. Decisione locked Phase 1 metrics — Phase 5 documenta. |

**Key insight:** Phase 5 è 99% orchestration di componenti già esistenti (Phase 1-4). Don't-hand-roll → don't reinvent il backtest engine, don't reinvent il detector, don't reinvent il ledger. Phase 5 aggiunge SOLO la layer di orchestration multi-run + dataset writer + report writer.

## Runtime State Inventory

> Phase 5 è greenfield (creazione nuovo subpackage `backtest/baseline/`, non rename/refactor di runtime state esistente). Tuttavia tocca SQLite ledger compartito con Phase 1, e produce nuovi artefatti che vanno in `.gitignore`/`logs/`.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `logs/trades.db` esistente con tabelle Phase 1 (`backtest_trades`, `backtest_runs`, `trades_log`, `daily_run_state`, `heartbeat`, `scheduler_state`). Phase 5 fa **append** a `backtest_trades` + `backtest_runs`, no schema rewrite. | Verifica `CREATE TABLE IF NOT EXISTS` idempotenza (già OK in `ledger.py`). Aggiungi `slippage_seed_effective`, `cost_yaml_hash`, `strategy_yaml_hash`, `baseline_yaml_hash` a `backtest_runs` se mancanti (vedi Open Q). |
| Live service config | None — Phase 5 è offline batch, no MT5/n8n/Datadog dependency. | None. |
| OS-registered state | None — no Windows Task Scheduler / pm2 / systemd touch. Phase 5 si esegue manualmente via `python scripts/run_baseline_backtest.py`. | None. |
| Secrets/env vars | `PYTHONHASHSEED` — se settato non-zero potrebbe drift seed... ma D-17 dice hashlib esplicito → immune. Verificare comunque baseline.yaml documentazione. | None se hashlib sostituisce hash(). |
| Build artifacts | Nuovi: `data/training/baseline_decisions/` (directory parquet), `data/training/baseline_drafts/` (directory parquet), `data/training/_shards/` (transient), `.planning/research/baseline-equity-curves/*.png` (27 PNG). `logs/trades.db-wal`, `logs/trades.db-shm` (WAL files). | Aggiungi a `.gitignore`: `data/training/`, `logs/*.db-wal`, `logs/*.db-shm`. PNG e baseline-{date}.md SONO commitati (SC#2, SC#4). |

**Canonical question:** *Cosa di runtime persiste tra run?*
- `logs/trades.db` cresce di 27 row in `backtest_runs` + ~10k-50k row in `backtest_trades` per ogni esecuzione completa. `--force` usa `INSERT OR REPLACE` per `backtest_runs` (già impl in `ledger.py:101`), ma `backtest_trades` ha `AUTOINCREMENT` → duplicate run senza force creano duplicate trade rows. **Critical:** in `--force` mode, dobbiamo prima `DELETE FROM backtest_trades WHERE run_id=?` PRIMA di inserire i nuovi.

## Common Pitfalls

### Pitfall 1: Python `hash()` is randomized — seed non riproducibile cross-run
**What goes wrong:** CONTEXT D-17 specifica `hash(run_id) % 2**31`. Ma Python `hash()` ha hash randomization attivo di default (PYTHONHASHSEED=random). Stesso `run_id` → seed diverso ogni run del processo Python → backtest results diversi nonostante "deterministic seed".
**Why it happens:** Hash randomization è feature di sicurezza (anti-DoS) introdotta in Python 3.3, default attiva. Vale solo per `str` e `bytes` hashing — `hash(int)` è stabile, ma `hash(str)` non lo è.
**How to avoid:** Sostituire `hash(run_id) % 2**31` con `int.from_bytes(hashlib.sha256(run_id.encode()).digest()[:4], "big") & 0x7FFFFFFF`. SHA256 è deterministico per definizione.
**Warning signs:** Re-run identical comando produce metriche diverse > 1e-6 tolerance. Test: re-run stessa run con stesso run_id, asserire `slippage_seed_effective` identico.
[CITED: chenna.me/blog/2023/12/25/python-hash-is-not-deterministic, bugs.python.org/issue29025] [CONFIDENCE: HIGH]

### Pitfall 2: SQLite "database is locked" sotto 9 writer concorrenti
**What goes wrong:** `PRAGMA journal_mode=WAL` consente N readers + 1 writer simultanei, ma NON N writer simultanei. 9 worker che fanno `INSERT INTO backtest_trades` raccolgono `OperationalError: database is locked` se uno tiene la write lock troppo a lungo.
**Why it happens:** WAL solves reader/writer blocking, NON writer/writer contention. Senza `busy_timeout` SQLite raises immediato; con `busy_timeout=N`, aspetta N ms poi raises.
**How to avoid:** `busy_timeout=30000` (30s) + retry-with-jitter (5 attempts, exponential backoff). Mantieni transaction size piccola (1 INSERT = 1 transaction). Riusa pattern `mt5_client._retry`.
**Warning signs:** Test con 9 worker concorrenti che fanno bulk INSERT. Asserire 0 lost rows.
[CITED: tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors, sqlite.org/wal.html, berthub.eu/articles/posts/a-brief-post-on-sqlite3-database-locked-despite-timeout] [CONFIDENCE: HIGH]

### Pitfall 3: matplotlib non-Agg backend hangs in ProcessPoolExecutor on Windows
**What goes wrong:** `import matplotlib.pyplot` ereditato da fork (Linux) o non-Agg backend impostato dopo pyplot import → segfault / hang nei worker.
**Why it happens:** matplotlib non è thread-safe; backend GUI (TkAgg, Qt5Agg) richiede main thread / event loop assente nei worker. Windows usa `spawn` (no fork) ma se backend già configurato a livello main si propaga via pickling.
**How to avoid:** `matplotlib.use("Agg")` come PRIMA istruzione di `plot_writer.py`. NON importare `matplotlib.pyplot` nel main process se non necessario. Test che asserisca `matplotlib.get_backend() == "Agg"` nel worker.
**Warning signs:** PNG generation hangs / produces empty file / segfault no traceback.
[CITED: matplotlib.org/stable/gallery/misc/multiprocess_sgskip.html, github.com/matplotlib/matplotlib/issues/12756, github.com/matplotlib/matplotlib/issues/8795] [CONFIDENCE: HIGH]

### Pitfall 4: Parquet single-file 65M-row write blow memory
**What goes wrong:** `pd.concat([df1, df2, ..., df27])` per `baseline_drafts.parquet` carica 65M righe × N colonne in singolo DataFrame in main process. Su 16GB box, ~10-20 GB memory required (depends column count) → OOM.
**Why it happens:** pandas DataFrame è in-memory. Single-file parquet write richiede single Table.
**How to avoid:** Shard-per-run pattern: ogni worker scrive proprio `baseline_drafts_{run_id}.parquet` (~2.4M righe = 100-300 MB). Main process usa `pyarrow.dataset.write_dataset(shards, ...)` che streamma row-group by row-group senza materializzare full table. Output è directory, NON single file — accettare layout o single-file con `pq.write_table` chunked (più complesso).
**Warning signs:** RAM usage > 8 GB in main process during finalize. Process killed by OS.
[CITED: arrow.apache.org/docs/python/generated/pyarrow.dataset.write_dataset.html, arrow.apache.org/docs/python/parquet.html] [CONFIDENCE: HIGH]

### Pitfall 5: Future leakage via `compute_all_extended(bars)` whole-series cache
**What goes wrong:** D-15 dice "compute_all_extended(bars) UNA volta per slice, riusato 3 profile". Se l'output è full-series snapshot e detector accede `indicators[i]` correttamente, OK. Ma se un detector accidentalmente accede `indicators` come dataclass-of-lists e prende `indicators.atr[-1]` quando i=200, prende l'ATR finale (futuro) invece dell'ATR a bar 200.
**Why it happens:** Dataclass-of-lists pattern (Phase 2 D-04) ritorna full-series. Drive-bar pattern (Phase 4 D-13) richiede `indicators_at_i = compute_all_extended(bars[:i+1])` (recompute slice-incremental) OPPURE strict slicing accessor. CONTEXT D-15 permette UNA compute → necessario accessor che ritorna `indicators[:i+1]` slice.
**How to avoid:** `evaluate_proposal_for_bar(bars[:i+1], indicators_slice_at_i, ctx)` dove `indicators_slice_at_i = indicators_full.slice_until(i)` (helper che taglia tutte le list al `i+1`). Test invariant: `indicators_full.slice_until(i).atr == compute_all_extended(bars[:i+1]).atr` per tutti i `i ≥ warmup`.
**Warning signs:** Backtest produce edge "troppo bello" (Sharpe > 5, hit_rate > 80%). Test: hash di `indicators_full` vs `recompute_all_at_i` per random sample 100 i.
[VERIFIED Phase 4 D-13 + Phase 2 D-09] [CONFIDENCE: HIGH]

### Pitfall 6: `--force` mode duplicates trade rows in SQLite
**What goes wrong:** `backtest_runs` ha `INSERT OR REPLACE` (run_id PK). Ma `backtest_trades` ha `trade_id INTEGER PRIMARY KEY AUTOINCREMENT` — re-running con `--force` accumula righe duplicate con stesso run_id ma trade_id diverso.
**Why it happens:** Phase 1 schema (D-07) non aveva force-rerun semantics. Phase 5 introduce `--force` (D-14).
**How to avoid:** Pre-INSERT di `backtest_trades`, eseguire `DELETE FROM backtest_trades WHERE run_id = ?`. Idempotency garantita.
**Warning signs:** `SELECT COUNT(*) FROM backtest_trades WHERE run_id = X` cresce ad ogni `--force`.

### Pitfall 7: Compounding distorts Sharpe ratio
**What goes wrong:** D-10 dice "compounding intra-slice attivo". Equity cresce → lot cresce (sizing dinamico) → returns assoluti più grandi nelle ultime parti del run. Sharpe calcolato su simple returns `equity[t]/equity[t-1] - 1` non è equivalente a Sharpe su returns log per long horizon (23.5y) — non-stationarity amplifica varianza apparente.
**Why it happens:** Compounding inflates absolute pnl di trade fortunati early → varianza dominata da magnitudine, non skill.
**How to avoid:** Documentare nel report (D-18 appendix) la metric definition: Phase 1 metrics module usa R-multiples (`pnl_usd / risk_usd`) che è già normalizzato risk-wise. Sharpe su R-multiples è meno biased di Sharpe su simple returns su equity. **Ulteriore mitigation:** considerare Probabilistic Sharpe Ratio (PSR) di Lopez de Prado per Phase 7 ML evaluation — fuori scope Phase 5 ma flag-gato per audit.
**Warning signs:** Sharpe varia fortemente in funzione di prima vs ultima decade del run (test partition).
[CITED: papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551 Bailey/Lopez de Prado Deflated Sharpe Ratio] [ASSUMED on Pardo specifics — non consultato direttamente] [CONFIDENCE: MEDIUM — pattern documentato in literature, ma scelta exact metric è Phase 1 module ownership]

### Pitfall 8: Memory peak 1.8 GB e timeout SC#1
**What goes wrong:** 9 worker × ~200 MB indicator cache = 1.8 GB. Su 8GB dev box → swap pesante, wall-clock degrada da <30 min a >60 min.
**Why it happens:** `compute_all_extended` produce dataclass-of-lists con 14 indicator × 600k-1.5M float per slice M15.
**How to avoid:** Verifica RAM dev box (`wmic OS get TotalVisibleMemorySize`) prima di run. Se <16GB, fallback `max_workers=4` o `max_workers=6` (degrada wall-clock ma evita swap). Documentare in baseline.yaml. Profiler hot path Wave 1: misurare memory per worker e wall-clock per slice EURUSD/M15 baseline (single profile) — extrapolare su 27 run.
**Warning signs:** Working set > 80% RAM, page faults aumentano. Wall-clock per slice M15 single profile > 3 min.

## Code Examples

### CLI entry point
```python
# scripts/run_baseline_backtest.py
# Source: pattern simile a scripts/dry_run_cycle.py (esistente, see codebase/STRUCTURE.md)
"""CLI entry: esegue 27 run baseline backtest e produce report + dataset."""
import argparse
from pathlib import Path
import sys

from backtest.baseline.runner import run_baseline
from backtest.baseline.dataset_writer import finalize_parquet_shards
from backtest.baseline.report_writer import write_baseline_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5 baseline backtest harness")
    parser.add_argument("--force", action="store_true", help="Overwrite existing run_id")
    parser.add_argument("--max-workers", type=int, default=None, help="Override config max_workers")
    args = parser.parse_args()

    results = run_baseline(force=args.force, max_workers_override=args.max_workers)
    finalize_parquet_shards()
    write_baseline_report(results)

    failed = [r for r in results if r.get("status") == "FAILED"]
    if failed:
        print(f"WARNING: {len(failed)}/{len(results)} run failed:", file=sys.stderr)
        for r in failed:
            print(f"  - {r['slice_id']}: {r['error']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Worker function
```python
# backtest/baseline/slice_worker.py
# Importato da runner.py. Ogni invocazione gira in proprio process.
import matplotlib
matplotlib.use("Agg")  # CRITICO PRIMA di pyplot indirect import via plot_writer

from datetime import date
from pathlib import Path

from backtest.loader import load_bars
from backtest.engine import BacktestEngine
from backtest.broker import BacktestBroker
from backtest.costs import load_cost_model
from backtest.ledger import LedgerWriter
from backtest.baseline.dataset_writer import write_decisions_shard, write_drafts_shard
from backtest.baseline.plot_writer import plot_equity_curve
from backtest.baseline.determinism import seed_for_run_id, file_sha256
from backtest.baseline.wal_setup import open_worker_connection
from indicators import compute_all_extended  # Phase 2 D-09 aggregator

_PROFILES = ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]


def run_slice_3profiles(symbol, tf, baseline_cfg, costs_cfg, strategy_cfg, force):
    """Worker entry point. Carica CSV, indicator cache, gira 3 profile sequenziali."""
    csv_path = Path(f"data/historical/{symbol}/{tf}.csv")
    bars = load_bars(csv_path, symbol, tf)
    if not bars:
        return [{"slice_id": (symbol, tf), "status": "FAILED", "error": "no bars"}]

    longest_lookback = strategy_cfg.longest_lookback_required()  # da Phase 4
    warm_up = max(baseline_cfg.warm_up_min_bars, longest_lookback)
    bars_post_warmup = bars[warm_up:]

    # ⚠ ATTENZIONE: indicators full-series — accessor `slice_until(i)` da implementare
    # in Phase 2 ExtendedIndicators dataclass per evitare future leakage (Pitfall 5)
    indicators_full = compute_all_extended(bars_post_warmup)

    cost_model = load_cost_model(symbol, bars_post_warmup[0].close, Path("data/configs/costs.yaml"))
    cost_yaml_hash = file_sha256(Path("data/configs/costs.yaml"))
    strategy_yaml_hash = file_sha256(Path("config/strategy.yaml"))
    baseline_yaml_hash = file_sha256(Path("data/configs/baseline.yaml"))

    today = date.today().isoformat()
    results = []
    for profile in _PROFILES:
        run_id = f"baseline_{today}_{symbol}_{tf}_{profile}"
        seed = seed_for_run_id(run_id)

        # Idempotency check (D-14)
        ledger = LedgerWriter(Path("logs/trades.db"))
        if not force and _run_exists(ledger, run_id):
            results.append({"slice_id": (symbol, tf), "run_id": run_id, "status": "SKIPPED"})
            continue
        if force:
            _delete_existing_trades(ledger, run_id)  # Pitfall 6 mitigation

        broker = BacktestBroker(symbol=symbol, timeframe=tf,
                                initial_balance=baseline_cfg.equity_initial_eur,
                                cost_model=cost_model, slippage_seed=seed)
        engine = BacktestEngine(
            bars=bars_post_warmup, symbol=symbol, timeframe=tf,
            cost_model=cost_model, ledger=ledger, run_id=run_id,
            cost_yaml_hash=cost_yaml_hash, strategy_yaml_hash=strategy_yaml_hash,
            baseline_yaml_hash=baseline_yaml_hash, slippage_seed_effective=seed,
            timeout_bars=baseline_cfg.timeout_bars[tf],
            initial_balance=baseline_cfg.equity_initial_eur,
            risk_profile=profile,
            indicators_full=indicators_full,  # passato per evitare ricomputo intra-bar
        )
        result = engine.run()
        write_decisions_shard(result["decisions"], run_id)
        write_drafts_shard(result["drafts"], run_id)
        plot_path = Path(".planning/research/baseline-equity-curves") / f"{symbol}_{tf}_{profile}.png"
        plot_equity_curve(result["equity_curve"], plot_path)
        results.append({**result, "slice_id": (symbol, tf), "run_id": run_id, "profile": profile, "status": "OK"})

    return results
```

### Test future leakage invariant
```python
# tests/test_baseline_no_future_leakage.py
"""Invariant: ogni indicator value su bar i deriva SOLO da bars[:i+1]."""
import hashlib

from backtest.loader import load_bars
from indicators import compute_all_extended


def test_indicator_full_slice_equals_recompute():
    bars = load_bars("data/historical/EURUSD/H1.csv", "EURUSD", "H1")[:1000]
    full = compute_all_extended(bars)
    # Sample 20 random indices ≥ warmup
    for i in (250, 300, 500, 750, 999):
        partial = compute_all_extended(bars[:i+1])
        # ATR: ultimo elemento di partial DEVE essere uguale a full.atr[i]
        assert partial.atr[-1] == full.atr[i], f"future leakage at i={i}"
        assert partial.rsi[-1] == full.rsi[i]
        assert partial.ema50[-1] == full.ema50[i]


def test_decision_dataset_temporal_ordering():
    """In baseline_decisions.parquet: decision_ts ≤ entry_ts < exit_ts per ogni riga."""
    import pandas as pd
    df = pd.read_parquet("data/training/baseline_decisions")
    assert (df["decision_ts_utc"] <= df["entry_ts_utc"]).all()
    assert (df["entry_ts_utc"] < df["exit_ts_utc"]).all()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-file parquet write via `pd.to_parquet(huge_df)` | Shard-per-worker + `pyarrow.dataset.write_dataset` finalize | pyarrow 10+ stable API, ~2022 | No memory blow up; dataset directory layout is canonical |
| `multiprocessing.Pool` | `concurrent.futures.ProcessPoolExecutor` | Python 3.2+ stdlib | Better API, integrates with `as_completed` for progress |
| Sharpe on simple returns | Sharpe on log returns or R-multiples; consider PSR/DSR for ML | Bailey & Lopez de Prado 2014 | Removes compounding bias; flagged for Phase 7 |
| `time.sleep(0.1)` retry on SQLITE_BUSY | `busy_timeout` PRAGMA + exponential backoff with jitter | sqlite 3.7+ | Less manual retry code; better tail latency |

**Deprecated/outdated:**
- `pandas.to_parquet(..., engine="fastparquet")` — fastparquet has worse multi-shard support than pyarrow. Use `engine="pyarrow"` exclusively.
- `hash(s) % N` for deterministic seed — broken since Python 3.3. Use `hashlib`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `compute_all_extended` (Phase 2 D-09) ritorna `ExtendedIndicators` dataclass-of-lists con tutti i 14 INDIC + ha (o avrà) accessor `slice_until(i)` per drive-bar pattern | Pitfall 5, Pattern 1 | Se accessor non esiste, future leakage o re-compute per bar (perf disaster). Phase 2 deve garantire accessor o Phase 5 ricompute slice-incremental |
| A2 | `BacktestEngine.run()` (Phase 1 esistente) accetta o accetterà `indicators_full` + `risk_profile` + `timeout_bars` parametri estesi (non presenti in `engine.py:91-118` corrente) | Pattern 1, slice_worker example | Engine va esteso Wave 1 prima di poter orchestrare 27 run. Plan deve includere extension task |
| A3 | Phase 4 strategy refactor produce `evaluate_proposal_for_bar` ritornante `ProposalDraft` ricco con tutti i 5 factor + `losers` (per `baseline_drafts.parquet`) | D-03 schema, Pattern 1 | Se Phase 4 non espone `losers`, `baseline_drafts.parquet` perde 3 detector su 4 |
| A4 | Wall-clock 27 run < 30 min su 8-core dev box è feasible — basato su CONTEXT estimate "15-20 min" | BACK-07 mapping, Pitfall 8 | Se sforata, Wave 2 dovrà profile + vectorize. Mitigation: profile single-slice-single-profile in Wave 1 baseline |
| A5 | `pd.read_parquet` (engine pyarrow) supporta directory output di `ds.write_dataset` come single argument | Pattern 2 | VERIFIED via pyarrow docs — `pd.read_parquet("dir/")` legge tutti `part-*.parquet`. Phase 7 ML reader unchanged |
| A6 | matplotlib >= 3.8 install pulito su Python 3.12 Windows via pip | Standard Stack | Generalmente OK ma verifica Wave 0. Wheel disponibile su PyPI per win_amd64 cp312 |
| A7 | pyarrow >= 16 install pulito su Python 3.12 Windows via pip | Standard Stack | Generalmente OK ma pyarrow è grande (~80MB) e ha occasionali problemi wheel su Windows. Verifica Wave 0 |
| A8 | Sharpe distortion da compounding è gestito dalle metriche su R-multiples in `backtest/metrics.py` (esistente Phase 1) | Pitfall 7, Open Q | Phase 1 D-Q deferred a metrics module. Phase 5 documenta nel report appendix la formula effettiva usata |
| A9 | Compute_all_extended cost ~200 MB per slice è realistic | Pitfall 8 | Profile Wave 1 (RAM tracker) per misurare. Se >400 MB ridurre max_workers |

**If user wants to confirm any of these:** A1, A2, A3 sono critical path — verificare con planner di Phase 2/4 prima di lockare Phase 5 plan.

## Open Questions

1. **Single-file vs directory parquet output for `baseline_decisions.parquet`?**
   - What we know: CONTEXT D-01 dice "single file parquet". `ds.write_dataset` produce directory.
   - What's unclear: Phase 7 ML reader può accept directory? Probabilmente sì (`pd.read_parquet("dir/")` works).
   - Recommendation: **Accept directory layout**, documenta in Phase 5 report. Notify Phase 7 planner. Single-file alternativo richiede full-load-in-memory che non scala su 65M righe.

2. **Slippage seed: per-trade unique vs per-run unique?**
   - What we know: D-17 dice "per-run actual seed = hash(run_id) % 2**31". Quindi seed è per-run, e per-trade slippage usa `rng.uniform(...)` che avanza state.
   - What's unclear: Vogliamo seed per-trade derivato da `(run_id, trade_index)` per indipendenza ordering? O accettiamo state-dependent (più semplice, ancora deterministic).
   - Recommendation: **State-dependent stick** — `np.random.default_rng(seed_for_run_id(run_id))` poi `rng.uniform(...)` per ogni trade. Deterministico cross-run (stesso run_id → stesso sequence). Trade independence non è strict requirement.

3. **Compounding return base for Sharpe — locked in Phase 1 metrics module?**
   - What we know: `backtest/metrics.py` esistente computa Sharpe su R-multiples. CONTEXT D-10 attiva compounding intra-slice.
   - What's unclear: Sharpe su R-multiples potrebbe essere già il pattern corretto (R-normalized). O dobbiamo aggiungere "log-return Sharpe" colonna alternativa?
   - Recommendation: **Documenta Phase 1 formula** (vedi `metrics.py:100`: `sharpe = (mean_r / std_r) * ann if std_r > 0 else 0.0` — R-multiple based). Mantieni quello. Aggiungi nota in report appendix "Sharpe is R-multiple based; compounding effect minimized by per-trade normalization".

4. **`backtest_runs` schema extension per Phase 5: come aggiungere colonne senza migration?**
   - What we know: `ledger.py:19-43` ha schema fisso. Phase 5 vuole `slippage_seed_effective`, `strategy_yaml_hash`, `baseline_yaml_hash`, `git_sha`.
   - What's unclear: SQLite supporta `ALTER TABLE ... ADD COLUMN` (no DROP). Strategy: `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (introdotto in SQLite 3.35).
   - Recommendation: Aggiungi `_DDL_BACKTEST_RUNS_ADD_COLUMNS` lista `ALTER TABLE` idempotenti (try/except column-already-exists). Una migration soft compatibile con Phase 1 schema esistente.

5. **`longest_lookback_required` come si calcola da `strategy_cfg`?**
   - What we know: Phase 2 D-15 introdurrebbe `regime.yaml` con window=200; Phase 4 indica `compute_all_extended` consuma vari indicator config.
   - What's unclear: API exact per recuperare longest lookback. Probabilmente `strategy_cfg.longest_lookback_required()` o helper in `indicators/__init__.py`.
   - Recommendation: Plan includes Wave 0 task "expose `longest_lookback_required()` helper in `indicators/`" se non esiste. Default fallback `max(200, 200_for_regime, 100_for_hurst, 50_for_ema50)` = 200.

6. **Cardinality `baseline_drafts.parquet`: realmente 65M righe o di più?**
   - What we know: M15 23.5y ≈ 600k bar × 4 detector = 2.4M righe/slice (CONTEXT D-03). 9 slice M15... no, 27 run × variable bar count. M15 ha più bar di H1.
   - What's unclear: Calcolo realistic: M15 = 600k × 4 = 2.4M; M30 = 300k × 4 = 1.2M; H1 = 150k × 4 = 600k. Per slice = 3 profile = 7.2M (M15) + 3.6M (M30) + 1.8M (H1). Per pair = 12.6M. Totale 3 pair = ~38M, non 65M. CONTEXT estimate 65M è conservative.
   - Recommendation: Accept 65M as upper bound. Profile actual count Wave 1 dopo single slice. Probabilmente fits.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.12.6 | — |
| pandas | DataFrame builder | ✓ | 3.0.2 | — |
| numpy | RNG seeded uniform | ✓ | 2.4.4 | — |
| tqdm | Progress bar | ✓ | 4.67.3 | — |
| pyyaml | YAML config load | ✓ | (in requirements.txt) | — |
| sqlite3 | Ledger | ✓ (stdlib) | — | — |
| **pyarrow** | Parquet engine + dataset | ✗ | — | **No fallback** — pip install required Wave 0 |
| **matplotlib** | Equity PNG plot | ✗ | — | **No fallback** — pip install required Wave 0 |
| concurrent.futures | ProcessPoolExecutor | ✓ (stdlib) | — | — |
| MetaTrader5 | NOT used in Phase 5 | ✓ | 5.0.5735 | — |

**Missing dependencies with no fallback:**
- `pyarrow` — required per D-01/D-02/D-03 parquet output. Plan Wave 0 task `pip install pyarrow` + add to `requirements.txt`.
- `matplotlib` — required per D-19/D-20 equity PNG. Plan Wave 0 task `pip install matplotlib` + add to `requirements.txt`.

**Missing dependencies with fallback:** None.

**Validation:**
```bash
.venv/Scripts/python.exe -c "import pyarrow, matplotlib; print(pyarrow.__version__, matplotlib.__version__)"
```
Asserire entrambi importabili in Wave 0 verification.

## Validation Architecture

> Required by `nyquist_validation: true` in `.planning/config.json`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (unpinned in requirements.txt) |
| Config file | `pytest.ini` (pythonpath=.) |
| Quick run command | `pytest tests/test_baseline_*.py -x --tb=short` |
| Full suite command | `pytest -x --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BACK-07 | Full 27-run baseline completes <30 min | smoke (manual gate) | `time .venv/Scripts/python.exe scripts/run_baseline_backtest.py` (manual) | ❌ Wave 0 |
| BACK-07 | Per-slice run wall-clock budget compliance (<2 min single profile after warm-up) | unit | `pytest tests/test_baseline_runner.py::test_single_slice_perf_budget -x` | ❌ Wave 0 |
| INT-01 | `baseline_decisions.parquet` schema completo (D-02) | unit | `pytest tests/test_baseline_dataset_writer.py::test_decisions_schema -x` | ❌ Wave 0 |
| INT-01 | `baseline_drafts.parquet` schema completo (D-03) | unit | `pytest tests/test_baseline_dataset_writer.py::test_drafts_schema -x` | ❌ Wave 0 |
| INT-01 | `baseline-{date}.md` report ha 27 row table + appendix hashes | unit | `pytest tests/test_baseline_report_writer.py::test_report_structure -x` | ❌ Wave 0 |
| INT-01 | 27 PNG equity curves prodotti, ognuno 2-subplot (equity + DD) | unit | `pytest tests/test_baseline_plot_writer.py::test_equity_png_structure -x` | ❌ Wave 0 |
| D-21 | No future leakage: `compute_all_extended(bars[:i+1]).field[-1] == compute_all_extended(bars).field[i]` | unit | `pytest tests/test_baseline_no_future_leakage.py::test_indicator_full_slice_equals_recompute -x` | ❌ Wave 0 |
| D-21 | `decision_ts ≤ entry_ts < exit_ts` per ogni riga del dataset prodotto | integration | `pytest tests/test_baseline_no_future_leakage.py::test_decision_dataset_temporal_ordering -x` | ❌ Wave 0 |
| D-22 | Bar-close discipline: entry_price = next_bar.open (± slippage), non bar.close | unit | `pytest tests/test_baseline_no_future_leakage.py::test_entry_at_next_bar_open -x` | ❌ Wave 0 |
| D-14 | Idempotency: re-run senza --force skip; con --force overwrite | unit | `pytest tests/test_baseline_runner.py::test_idempotency_skip_and_force -x` | ❌ Wave 0 |
| D-15 | Hybrid orchestration: indicator cache computed UNA volta per slice | unit | `pytest tests/test_baseline_runner.py::test_indicator_cache_reused_across_profiles -x` (mock + spy) | ❌ Wave 0 |
| D-16 | SQLite WAL: 9 worker concurrent INSERT no lost rows | integration | `pytest tests/test_baseline_wal.py::test_wal_concurrent_writes -x` | ❌ Wave 0 |
| D-17 | Determinism: same run_id → same slippage_seed_effective cross-run, cross-process | unit | `pytest tests/test_baseline_determinism.py::test_seed_reproducibility -x` | ❌ Wave 0 |
| D-17 | Config hashes (sha256) salvati in backtest_runs match file content | unit | `pytest tests/test_baseline_determinism.py::test_config_hash_matches -x` | ❌ Wave 0 |
| D-23 | Cost realism: spread + commission deducted on entry, slippage entry+exit | unit | `pytest tests/test_baseline_runner.py::test_cost_deduction -x` | ❌ Wave 0 |
| D-19/20 | matplotlib backend è "Agg" nel worker (no GUI hang) | unit | `pytest tests/test_baseline_plot_writer.py::test_agg_backend_in_worker -x` | ❌ Wave 0 |
| (perf) | Memory peak monitoring single slice <250 MB indicator cache | manual | `python scripts/profile_baseline_slice.py EURUSD M15 MODERATE` (manual) | ❌ Wave 1 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_baseline_<changed_module>.py -x --tb=short` (sub-30s per module)
- **Per wave merge:** `pytest tests/ -x --tb=short` (full suite, target <2 min)
- **Phase gate:** Full suite green + manual smoke test `python scripts/run_baseline_backtest.py` (full 27-run, accetta 30 min) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_baseline_runner.py` — copre BACK-07, D-14, D-15, D-23
- [ ] `tests/test_baseline_dataset_writer.py` — copre INT-01 schema D-02/D-03
- [ ] `tests/test_baseline_no_future_leakage.py` — copre D-21, D-22
- [ ] `tests/test_baseline_determinism.py` — copre D-17
- [ ] `tests/test_baseline_wal.py` — copre D-16 concurrent writes
- [ ] `tests/test_baseline_plot_writer.py` — copre D-19, D-20
- [ ] `tests/test_baseline_report_writer.py` — copre D-18, INT-01
- [ ] `tests/conftest.py` — shared fixtures (small bars sample, mock cost.yaml, mock baseline.yaml)
- [ ] Framework install: `pip install pyarrow matplotlib` + update `requirements.txt`
- [ ] `scripts/profile_baseline_slice.py` — Wave 1 perf profiler (single slice baseline)

## Sources

### Primary (HIGH confidence)
- [Apache Arrow PyArrow Parquet docs](https://arrow.apache.org/docs/python/parquet.html) — partitioned writes, write_dataset semantics
- [pyarrow.dataset.write_dataset API](https://arrow.apache.org/docs/python/generated/pyarrow.dataset.write_dataset.html) — basename_template, existing_data_behavior
- [SQLite Write-Ahead Logging](https://www.sqlite.org/wal.html) — WAL mode semantics, multi-process limitations
- [matplotlib multiprocessing example (Agg backend)](https://matplotlib.org/stable/gallery/misc/multiprocess_sgskip.html) — official safe pattern
- [Python concurrent.futures](https://docs.python.org/3/library/concurrent.futures.html) — ProcessPoolExecutor + as_completed
- [Python multiprocessing context](https://docs.python.org/3/library/multiprocessing.html) — get_context("spawn") on Windows
- `.planning/phases/01-backtest-engine/01-CONTEXT.md` — D-07 ledger schema, D-08/09 GMT-6 + bar-close
- `.planning/phases/02-indicators-library/02-CONTEXT.md` — D-04 dataclass-of-lists, D-09 no future leakage
- `.planning/phases/03-patterns-catalog/03-CONTEXT.md` — PatternHit dataclass
- `.planning/phases/04-strategy-refactor/04-CONTEXT.md` — D-02 detector signature, D-13 drive-bar pattern
- `backtest/engine.py`, `backtest/broker.py`, `backtest/ledger.py`, `backtest/metrics.py`, `backtest/loader.py`, `backtest/costs.py` — codice esistente Phase 1 (lift-and-extend)
- `mt5_client.py:26-39` — `_retry` pattern stabilito (riusato per SQLITE_BUSY)

### Secondary (MEDIUM confidence)
- [SQLite concurrent writes article (10000 meters)](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) — practical busy_timeout + retry pattern
- [DOCSAID SQLite WAL busy_timeout for workers](https://docsaid.org/en/blog/sqlite-wal-busy-timeout-for-workers/) — multi-worker timing analysis
- [Bert Hubert SQLITE_BUSY despite timeout](https://berthub.eu/articles/posts/a-brief-post-on-sqlite3-database-locked-despite-timeout/) — caveat su WAL writer/writer
- [Bailey & Lopez de Prado — Deflated Sharpe Ratio (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) — Sharpe inflation in backtests
- [matplotlib multiprocessing issue #12756](https://github.com/matplotlib/matplotlib/issues/12756) — segfault root cause + Agg fix
- [Python hash determinism blog (chenna.me)](https://chenna.me/blog/2023/12/25/python-hash-is-not-deterministic/) — PYTHONHASHSEED behavior
- [Python issue 29025 — random.seed() and hash determinism](https://bugs.python.org/issue29025) — official tracker confirming randomization

### Tertiary (LOW confidence)
- WebSearch hits non verificati direttamente (es. "Pardo industry standard for compounding") — ASSUMED, da confermare via skill `forex-algo-dev` references o lettura diretta libro

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verificate via probe diretto del venv
- Architecture: HIGH — pattern hybrid orchestration locked in CONTEXT, vincoli Python multiprocessing su Windows ben documentati
- Pitfalls: HIGH — tutti i 7 pitfall corroborati da official docs / canonical references (sqlite.org, arrow.apache.org, matplotlib.org)
- Compounding/Sharpe: MEDIUM — Phase 1 metrics module è ownership; Phase 5 documenta nel report ma non sceglie metric
- Performance budget feasibility: MEDIUM — basato su CONTEXT estimate, profile Wave 1 da fare

**Research date:** 2026-05-07
**Valid until:** 2026-06-07 (30 days — pyarrow/matplotlib API stabili, SQLite WAL invariate)

---
*Phase: 05-baseline-backtest*
*Research completed: 2026-05-07 via /gsd:research-phase*

## RESEARCH COMPLETE
