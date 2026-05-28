# Phase 5: Baseline Backtest — Context

**Gathered:** 2026-05-07
**Status:** Ready for planning
**Source:** /gsd:discuss-phase 5 (interactive, 4 aree, mode=discuss)

<domain>
## Phase Boundary

Esegui il baseline backtest pre-ML completo: 23.5y × 3 pair (EURUSD, GBPUSD, USDJPY) × 3 timeframe (M15, M30, H1) × 3 risk profile (CONSERVATIVE, MODERATE, AGGRESSIVE) = **27 run**. Produrre:

- Metrics report `.planning/research/baseline-{date}.md` (header + tabella 27-row + per-slice mini-section + appendix config)
- Decision dataset doppio in `data/training/` (layout **directory** pyarrow.dataset, finalize-step concat post-run):
  - `data/training/baseline_decisions/` — directory dataset partizionata; 1 riga per trade chiuso (READY entrato nel ledger), schema completo (identità + ProposalDraft + ExtendedIndicators + ctx + outcome multi-label). Phase 7 ML reader: `pd.read_parquet("data/training/baseline_decisions/")`.
  - `data/training/baseline_drafts/` — directory dataset; 1 riga per ogni Draft (READY+FORMING+NONE × 4 setup × N_bar). 65M righe richiede streaming/sharding.
  - **Update 2026-05-08:** D-01 risolto a directory per entrambi (era ambiguo "single file vs directory" — RESEARCH §Open Question 1, decisione user). ROADMAP path letterale `data/training/baseline_decisions.parquet` riletto come dataset name.
- Equity curves PNG (27 file) in `.planning/research/baseline-equity-curves/`
- Trade ledger persistito in `logs/trades.db` tabelle `backtest_trades` + `backtest_runs` (Phase 1 D-07)

Single-pass full-range in-sample (no walk-forward — quello arriva in Phase 7 ML). Slice indipendenti (no portfolio cross-slice concurrency). Max 1 trade aperto per slice.

**In scope:** BACK-07, INT-01.

**Out of scope (deferred):**
- Walk-forward harness sul baseline (Phase 7 lo esegue sul dataset prodotto qui)
- Portfolio simulation cross-pair / cross-TF (Phase 11 paper deploy)
- Micro-account stress test (<500 EUR equity, lot quantization realism) → Phase 11
- ML filtering nel decision pipeline (Phase 7)

</domain>

<decisions>
## Implementation Decisions

### Dataset schema

- **D-01 — Doppio dataset parquet.** `baseline_decisions.parquet` = 1 riga per trade chiuso; `baseline_drafts.parquet` = 1 riga per ogni Draft (READY+FORMING+NONE) di ogni detector A/B/C/D su ogni bar. Storage cost accettato per coverage massima Phase 7 ML training.
- **D-02 — Schema `baseline_decisions.parquet` (per-trade).** Snapshot completo:
  - Identità: `run_id, slice_id, symbol, timeframe, profile, decision_ts_utc, entry_ts_utc, exit_ts_utc`
  - ProposalDraft: `setup_name, direction, grade, factors_trend_alignment, factors_setup_pattern, factors_momentum, factors_volatility_regime, factors_spread_session, confidence, entry_price, stop_loss_price, take_profit_price, rr, reason`
  - ExtendedIndicators snapshot al `decision_ts_utc` (tutti i campi numerici di Phase 2 D-09 ExtendedIndicators — atr, ema20/50/200, ema50_slope, rsi, bb_upper/lower/squeeze, adx, dmi_plus/minus, macd_line/signal/hist, stoch_k/d, donchian_hi/lo, keltner_upper/lower, vwap, fib levels, pivot, nr4, nr7, closing_score, hurst, mtf_align)
  - Context: `regime (compressed/normal/expanded), sr_dist_pips, spread_at_entry_pips, sentiment_proxy, recent_trades_outcome_5 (encoded W/L/B/-)`
  - Outcome multi-label: `outcome ∈ {WIN, LOSS, BREAKEVEN, TIMEOUT}, exit_reason ∈ {TP_HIT, SL_HIT, TIMEOUT_CLOSE, MANUAL}, pnl_pips, pnl_money, bars_held`
- **D-03 — Schema `baseline_drafts.parquet` (per-bar per-detector).** Tutti i Draft di ogni detector su ogni bar:
  - `run_id, slice_id, symbol, timeframe, profile, bar_ts_utc, detector_name (A_breakout|B_reversal|C_compression|D_pullback), setup_type (READY|FORMING|NONE), grade, factors (5 bool), confidence, reason, regime, was_winner (bool), entered_ledger (bool)`
  - 4 detector × N_bar righe per slice. Esplosione storage: M15 23.5y ≈ 600k bar × 4 = 2.4M righe/slice × 27 run ≈ 65M righe totali. Compressione parquet snappy.
- **D-04 — Outcome multi-label encoding.** Campi separati `outcome` + `exit_reason` + `pnl_pips` + `pnl_money` + `bars_held`. Phase 7 ML sceglie target appropriato (binary win/loss, regression pnl, multiclass). Non collassare in label singola.
- **D-05 — Timeout policy per-TF.** Trade ancora aperto a:
  - M15: 96 bar (≈ 24h)
  - M30: 96 bar (≈ 48h)
  - H1: 120 bar (≈ 5 giorni)
  - Esce a market price dell'ultima bar del cap. Outcome=TIMEOUT, exit_reason=TIMEOUT_CLOSE.

### Strategia esecuzione

- **D-06 — Single-pass in-sample.** Una run unica per (slice, profile) sull'intera serie 23.5y. No walk-forward folding sul baseline. Walk-forward è territorio Phase 7 (ML training su dataset Phase 5).
- **D-07 — Warm-up adaptive.** Skip `max(200, longest_lookback_required)` bar iniziali prima di iniziare detection. `longest_lookback_required` calcolato runtime dal config indicator (Phase 2). Auto-correct se Phase 2 aggiunge indicator con lookback >200.
- **D-08 — Concurrency intra-slice: max 1 trade aperto.** Detector ignora nuovo READY se posizione già aperta nello stesso (symbol, tf, profile). Allineato live scheduler intraday. Semplifica P&L attribution. Nessun pyramiding/scaling-in nel baseline.
- **D-09 — Cross-slice indipendente.** 27 run isolati. Nessun portfolio constraint cross-pair/TF/profile. Equity curve, MaxDD, Sharpe per-slice puri (edge intrinseco). Portfolio simulation rimandata a Phase 11.
- **D-10 — Equity iniziale 10k EUR per slice + sizing dinamico.** Account simulato resetta a 10k start di ogni slice. Sizing = `profile.risk_pct × equity / SL_distance` via `risk_engine`. Compounding intra-slice attivo (equity cresce → lot cresce). Allineato live behavior.

### Profile matrix

- **D-11 — Run tutti e 3 i profile in parallelo.** 9 slice × 3 profile = 27 run paralleli. Profile cambia entry filter (`min_grade`, `min_rr`, `min_confidence` da Phase 4 D-08), non costi né indicator. Profile column nel dataset → feature ML Phase 7.
- **D-12 — `cost.yaml` invariato per-symbol.** Schema `data/configs/costs.yaml` da Phase 1 D-05 sufficiente. Costi sono broker-side, non profile-side. Non introdurre per-profile cost override.
- **D-13 — `run_id` schema leggibile.** Format: `baseline_{date}_{symbol}_{tf}_{profile}` (es. `baseline_2026-05-07_EURUSD_M15_MODERATE`). 27 run_id distinti per esecuzione del giorno. Match diretto a slice_id sul dataset.
- **D-14 — Idempotenza: skip se `run_id` esiste, `--force` per overwrite.** Default safe. Re-run incrementale possibile (es. solo USDJPY-H1-AGGRESSIVE fallita). `--force` flag per refresh tutto. Skip emette log warning con `run_id`.

### Runner orchestration

- **D-15 — Orchestration hybrid: parallel slice, sequenziale profile (Opzione 3).** `scripts/run_baseline_backtest.py`:
  - `ProcessPoolExecutor(max_workers=9)` su 9 task `(symbol, tf)`.
  - Ogni worker: load CSV, `compute_all_extended(bars)` UNA volta, poi gira 3 profile sequenziali con cache `(bars, indicators)` condivisa.
  - Indicator compute 9× totale (vs 27× se profile parallelo). Wall-clock target <30 min su 8-core dev laptop (SC#1).
  - Memory peak: 9 cache concorrenti ≈ 1.8 GB. OK su 16GB.
- **D-16 — SQLite WAL mode + per-worker connection.** `PRAGMA journal_mode=WAL` su `logs/trades.db` per permettere 9 writer concorrenti senza `database is locked`. Ogni worker apre propria connection, no sharing cross-process. Schema `backtest_trades` + `backtest_runs` da Phase 1 D-07 invariato.
- **D-17 — Determinism: slippage seed + config hash in `backtest_runs`.**
  - `data/configs/baseline.yaml` dichiara `slippage_seed: 42` (lockato).
  - Per-run actual seed = `hash(run_id) % 2**31` → riproducibile, distinto per run.
  - `backtest_runs.cost_yaml_hash` (sha256 di `data/configs/costs.yaml` UTF-8 bytes).
  - `backtest_runs.strategy_yaml_hash` (sha256 di `config/strategy.yaml`).
  - `backtest_runs.baseline_yaml_hash` (sha256 di `data/configs/baseline.yaml`).
  - Hash committati nel report appendix per audit trail.

### Report + plot

- **D-18 — Report schema `.planning/research/baseline-{date}.md`.** Struttura:
  1. **Header**: data run, comando CLI, git_sha, total wall-clock, n_run completati/falliti.
  2. **Tabella 27-row**: colonne `symbol, tf, profile, n_trades, sharpe, sortino, max_dd_pct, hit_rate, expectancy_pips, profit_factor, avg_R, longest_dd_days`.
  3. **Per-slice mini-section** (27 sezioni): link a equity PNG, top setup_name distribution (es. `A_breakout: 45%, D_pullback: 30%, ...`), exit_reason breakdown (TP/SL/TIMEOUT %), avg bars_held.
  4. **Appendix**: `cost.yaml` hash, `strategy.yaml` hash, `baseline.yaml` hash, `slippage_seed`, warm-up bars effettivi per slice, longest_lookback usato.
- **D-19 — Equity PNG: 27 file separati.** Path: `.planning/research/baseline-equity-curves/{symbol}_{tf}_{profile}.png` (es. `EURUSD_M15_MODERATE.png`). Ogni PNG: 2 subplot verticali (equity curve top, drawdown shaded bottom), x-axis condiviso (timestamp).
- **D-20 — Plot library: matplotlib plain con backend `Agg`.** No nuove dep. Backend `Agg` headless obbligatorio per multiprocessing (no GUI nei worker). Style default matplotlib: sfondo bianco, sans-serif, gridlines `alpha=0.3`. Equity linewidth=1 color=`steelblue`; drawdown `fill_between` color=`indianred` alpha=0.5. `dpi=100`, `figsize=(12,6)`. ~50-100 KB per PNG.

### Engineering principles

- **D-21 — No future leakage by construction.** `BacktestEngine.run()` itera bar-by-bar (Phase 4 D-13): `bars_so_far = full_csv[:i+1]`, `indicators_at_i = compute_all_extended(bars_so_far)`, ctx via adapter backtest, `evaluate_proposal_for_bar(bars_so_far, indicators_at_i, ctx)`. Detector vede solo storia chiusa.
- **D-22 — Bar-close discipline.** Decision_ts = bar close timestamp UTC. Entry simulato a `next_bar.open ± slippage_pips` (limit/stop semantics da Phase 1 BacktestBroker). SL/TP check intra-bar usando high/low della next bar(s).
- **D-23 — Cost realism.** `spread_pips + commission_pips_round_trip` deducted on entry; `slippage_pips` random uniform `[-S, +S]` con seed lockato (D-17) deducted su entry e exit.

### Claude's Discretion

- Tabella metrics: ordinamento (suggerito: symbol → tf → profile, alfabetico).
- Equity curve: y-axis EUR vs % vs log scale (default: EUR linear).
- Per-slice mini-section: depth narrative (default: solo bullet point statistici, no commentary qualitativo).
- Module layout: `backtest/baseline/` package con `runner.py, dataset_writer.py, report_writer.py, plot_writer.py` (mirror Phase 1 layout) o single `scripts/run_baseline_backtest.py` monolitico (default: package, scalability).
- Snappy vs zstd compression parquet (default: snappy, balance).
- Progress bar console: `tqdm` su 27 run (default: yes, già dep transitiva).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project locked specs
- `.planning/PROJECT.md` — milestone scope, 23.5y data, cost defaults, fold cap, performance budget <30min
- `.planning/REQUIREMENTS.md` §Backtest Engine — BACK-07; §Integration — INT-01
- `.planning/ROADMAP.md` §Phase 5 — goal, 4 success criteria, requirement mapping

### Prior phase carry-forward (MUST READ)
- `.planning/phases/01-backtest-engine/01-CONTEXT.md` — D-01/02 BrokerProtocol, D-05 cost.yaml schema, D-06 walk-forward harness (NOT used here, locked Phase 7), D-07 SQLite tabelle `backtest_trades`/`backtest_runs`, D-08 GMT-6→UTC, D-09 bar-close decision
- `.planning/phases/02-indicators-library/02-CONTEXT.md` — D-04 dataclass-of-lists ExtendedIndicators (schema feature columns Phase 5 D-02), D-09 no future leakage, D-15/16 regime config
- `.planning/phases/03-patterns-catalog/03-CONTEXT.md` — `PatternHit` dataclass (consumato da Setup B detector via Phase 4 D-04 ctx)
- `.planning/phases/04-strategy-refactor/04-CONTEXT.md` — D-02 detector signature, D-03 ProposalDraft, D-04 StrategyContext, D-08 5-factor + profile_filters (`min_grade`/`min_rr`/`min_confidence`), D-13 drive-bar pattern, D-15 engineering principles

### Codebase maps
- `.planning/codebase/STRUCTURE.md` — flat root layout, `backtest/` package convention da Phase 1
- `.planning/codebase/ARCHITECTURE.md` — strategy/scanner/scheduler/broker layering
- `.planning/codebase/STACK.md` — Python 3.12 (Anaconda), pandas, MetaTrader5, **matplotlib (no seaborn, no plotly)**
- `.planning/codebase/CONVENTIONS.md` — snake_case, dataclass, leading-underscore, italiano commenti
- `.planning/codebase/TESTING.md` — pytest layout `tests/test_backtest_*.py`

### Existing code (touch / extend)
- `backtest/` package (Phase 1) — `loader.py, engine.py, costs.py, broker.py, walk_forward.py, metrics.py, ledger.py`. Phase 5 aggiunge `baseline/` subpackage o `scripts/run_baseline_backtest.py` come orchestrator.
- `strategy/` package (Phase 4) — `evaluate_proposal_for_bar`, `ProposalDraft`, `StrategyContext`, `adapters/backtest.py::build_ctx_backtest`. Single code path detector.
- `indicators/` package (Phase 2) — `compute_all_extended` per warm-up cache hybrid orchestrator.
- `risk_engine.py` — `evaluate_trade`, `PROFILES` (CONSERVATIVE/MODERATE/AGGRESSIVE) — invocato unchanged dal backtest engine per sizing dinamico (D-10).
- `logger.py` — `_trades_db_path`, `CREATE TABLE IF NOT EXISTS` pattern. WAL mode pragma da aggiungere (D-16).
- `models.py` — `TradeProposal`, `OrderResult`, `RiskDecision` — ledger row composes from these.

### Configs (creare/estendere in questa fase)
- `data/configs/baseline.yaml` (NEW) — orchestration knobs:
  - `equity_initial_eur: 10000`
  - `slippage_seed: 42`
  - `timeout_bars: {M15: 96, M30: 96, H1: 120}`
  - `warm_up_min_bars: 200`
  - `max_workers: 9`
  - `parquet_compression: snappy`
  - `force_rerun: false`
  - `progress_bar: true`
- `data/configs/costs.yaml` (Phase 1, invariato) — per-symbol cost.

### Output paths (creare in questa fase)
- `data/training/baseline_decisions.parquet`
- `data/training/baseline_drafts.parquet`
- `.planning/research/baseline-{date}.md`
- `.planning/research/baseline-equity-curves/{symbol}_{tf}_{profile}.png` (27 file)
- `logs/trades.db` tabelle `backtest_trades` + `backtest_runs` (Phase 1 schema, no migration)

### Skills
- `forex-algo-dev` — bar boundary discipline, no future leakage, transaction-cost realism, calibration. Critico per validation D-21/22/23.
- `forex-trader-pro` — A/B/C/D setup definitions, 5-factor confluence (semantica feature columns dataset).

### External libs
- Nessuna nuova dep runtime. `pandas`, `pyarrow` (parquet), `matplotlib`, `numpy`, `lightgbm` (Phase 7), `tqdm` (probabile transitiva). Verificare `pyarrow` esplicito in `requirements.txt`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backtest.engine.BacktestEngine` (Phase 1) — drive-bar loop. Phase 5 lo orchestra su 27 run, non lo riscrive.
- `backtest.loader.load_italian_csv` (Phase 1) — già con timezone GMT-6→UTC validation D-08/D-10. Usato come-is.
- `backtest.metrics` (Phase 1) — Sharpe/Sortino/MaxDD/hit_rate/expectancy/profit_factor calc. Estendere con `avg_R` e `longest_dd_days` se non già presente.
- `backtest.ledger` (Phase 1) — schema `backtest_trades`/`backtest_runs`. Aggiungere colonne `cost_yaml_hash`, `strategy_yaml_hash`, `baseline_yaml_hash`, `slippage_seed_effective` se non già presenti.
- `strategy.evaluate_proposal_for_bar` (Phase 4) — detector orchestrator. Single code path live/backtest.
- `strategy.adapters.backtest.build_ctx_backtest` (Phase 4 D-05) — costruisce StrategyContext da engine state. Phase 5 lo usa come-is.
- `risk_engine.evaluate_trade` + `PROFILES` — sizing dinamico, invocato per ogni trade entry.
- `indicators.compute_all_extended` (Phase 2) — cache per slice (D-15 hybrid orchestration).

### Established Patterns
- `data/configs/<name>.yaml` + `load_<name>_config()` + frozen dataclass + env override (Phase 1 D-05, Phase 3, Phase 4 D-08).
- `CREATE TABLE IF NOT EXISTS` su module init, single shared `logs/trades.db`.
- Atomic commit per task (gsd-executor).
- Snake_case modules, PascalCase dataclass, italiano commenti/log.

### Hot Spots / Risks
- **Memory peak 1.8 GB** — 9 worker × ~200 MB cache. Su 8GB laptop richiede swap (degrada wall-clock). Verificare RAM dev box prima di run.
- **SQLite WAL contention** — 9 writer concorrenti su `logs/trades.db`. Anche con WAL, retry con backoff su `OperationalError: database is locked`. Pattern da `mt5_client.Mt5Client._retry`.
- **Parquet write granularity** — scrivere 65M righe `baseline_drafts` in singolo file → memory blow. Strategia: ogni worker scrive proprio parquet shard `baseline_drafts_{slice_id}_{profile}.parquet` durante il loop, finalize step concatena/partiziona via `pyarrow.dataset`. Decisione finale a planner.
- **Indicator cache invalidation** — se Phase 2 modifica `ExtendedIndicators` schema dopo Phase 5 run, dataset diventa schema-incompatibile. Hash `strategy_yaml_hash` + `git_sha` nel `backtest_runs` permettono detect.
- **Compounding amplifica varianza Sharpe** — slice con sequence lucky early-trade ha equity più alto → lot più grande → varianza non stationary. Sharpe calcolato su returns `equity[t]/equity[t-1] - 1` (returns log preferibili?). Decisione a planner / metrics module Phase 1.
- **Performance SC#1 (<30 min)** — stima D-15 ~15-20 min su 8-core 16GB. Margine sottile. Profilare Wave 1 prima di assumere.

### Integration Points
- `BacktestEngine.__init__(broker, strategy, ledger, ...)` — orchestrator passa `BacktestBroker` + cache `(bars, indicators)` per worker.
- `risk_engine.evaluate_trade(proposal, account_state, profile)` — invocato dal `BacktestEngine` per ogni `READY` Draft → restituisce sizing + accept/reject.
- `logs/trades.db` — extension, no schema rewrite. Phase 1 owns schema.
- `pytest.ini` — nuovi test `tests/test_baseline_*.py`.

</code_context>

<specifics>
## Specific Ideas

### Runner orchestrator skeleton

```python
# scripts/run_baseline_backtest.py
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product

PAIRS = ["EURUSD", "GBPUSD", "USDJPY"]
TFS = ["M15", "M30", "H1"]
PROFILES = ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]

def run_slice_3profiles(symbol: str, tf: str, baseline_cfg, costs_cfg, strategy_cfg, force: bool):
    # 1. Load CSV + warm-up calc
    bars = load_italian_csv(symbol, tf)
    longest_lookback = compute_longest_lookback(strategy_cfg, indicators_cfg)
    warm_up = max(baseline_cfg.warm_up_min_bars, longest_lookback)
    bars = bars[warm_up:]
    # 2. Indicator cache (UNA volta per slice)
    indicators_full = compute_all_extended(bars)
    # 3. Sequenziale 3 profile riusando cache
    results = []
    for profile in PROFILES:
        run_id = f"baseline_{date.today().isoformat()}_{symbol}_{tf}_{profile}"
        if not force and run_exists(run_id):
            log.warning(f"skip {run_id}: already exists, use --force")
            continue
        seed_effective = hash(run_id) & 0x7FFFFFFF
        engine = BacktestEngine(
            broker=BacktestBroker(costs_cfg, slippage_seed=seed_effective),
            ctx_builder=build_ctx_backtest,
            risk_profile=profile,
            equity_initial=baseline_cfg.equity_initial_eur,
            timeout_bars=baseline_cfg.timeout_bars[tf],
            ledger_db="logs/trades.db",
            run_id=run_id,
        )
        result = engine.run(bars, indicators_full)
        write_decision_rows(result.trades, run_id, ...)
        write_draft_rows(result.drafts, run_id, ...)  # 4 detector × N_bar
        plot_equity_curve(result.equity_series, f".planning/research/baseline-equity-curves/{symbol}_{tf}_{profile}.png")
        results.append(result)
    return results

def main(force: bool = False):
    baseline_cfg = load_baseline_config("data/configs/baseline.yaml")
    costs_cfg = load_costs_config("data/configs/costs.yaml")
    strategy_cfg = load_strategy_config("config/strategy.yaml")
    enable_sqlite_wal("logs/trades.db")
    tasks = [(s, tf) for s in PAIRS for tf in TFS]  # 9 task
    all_results = []
    with ProcessPoolExecutor(max_workers=baseline_cfg.max_workers) as pool:
        futures = {pool.submit(run_slice_3profiles, s, tf, baseline_cfg, costs_cfg, strategy_cfg, force): (s, tf) for s, tf in tasks}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="slice"):
            all_results.extend(fut.result())
    write_baseline_report(all_results, f".planning/research/baseline-{date.today().isoformat()}.md")
    finalize_parquet_shards("data/training/")
```

### Dataset writer pattern (per-worker shard)

```python
# backtest/baseline/dataset_writer.py
def write_decision_rows(trades: list[ClosedTrade], run_id: str, out_dir: Path):
    rows = [trade_to_row(t, run_id) for t in trades]
    df = pd.DataFrame(rows)
    shard_path = out_dir / f"baseline_decisions_{run_id}.parquet"
    df.to_parquet(shard_path, compression="snappy", index=False)

# Finalize concatena via pyarrow.dataset (no full-load memory):
def finalize_parquet_shards(out_dir: Path):
    import pyarrow.dataset as ds
    for prefix in ["baseline_decisions", "baseline_drafts"]:
        shards = list(out_dir.glob(f"{prefix}_*.parquet"))
        dataset = ds.dataset(shards, format="parquet")
        ds.write_dataset(dataset, out_dir / f"{prefix}.parquet", format="parquet")
        for s in shards: s.unlink()
```

### baseline.yaml schema

```yaml
# data/configs/baseline.yaml
equity_initial_eur: 10000
slippage_seed: 42

timeout_bars:
  M15: 96    # ~24h
  M30: 96    # ~48h
  H1: 120    # ~5 giorni

warm_up_min_bars: 200

max_workers: 9
parquet_compression: snappy

force_rerun: false
progress_bar: true

# Output paths
training_data_dir: "data/training"
report_dir: ".planning/research"
equity_curves_dir: ".planning/research/baseline-equity-curves"
```

### Equity plot snippet

```python
# backtest/baseline/plot_writer.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def plot_equity_curve(equity_series: pd.DataFrame, out_path: Path):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True,
                                     gridspec_kw={"height_ratios": [3, 1]})
    ax1.plot(equity_series["timestamp"], equity_series["equity_eur"],
             color="steelblue", linewidth=1)
    ax1.set_ylabel("Equity (EUR)")
    ax1.set_title(out_path.stem.replace("_", " "))
    ax1.grid(True, alpha=0.3)
    ax2.fill_between(equity_series["timestamp"], equity_series["drawdown_pct"], 0,
                     color="indianred", alpha=0.5)
    ax2.set_ylabel("DD %")
    ax2.set_xlabel("Date")
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=100)
    plt.close()
```

### Determinism enforcement

```python
# slippage seed per-trade derived da run_id (D-17)
seed_effective = hash(run_id) & 0x7FFFFFFF
rng = np.random.default_rng(seed_effective)
slippage = rng.uniform(-cfg.slippage_pips, cfg.slippage_pips)

# config hashes scritti in backtest_runs
import hashlib
def file_sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

backtest_runs.insert(
    run_id=run_id,
    cost_yaml_hash=file_sha256("data/configs/costs.yaml"),
    strategy_yaml_hash=file_sha256("config/strategy.yaml"),
    baseline_yaml_hash=file_sha256("data/configs/baseline.yaml"),
    slippage_seed_effective=seed_effective,
    git_sha=subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
    started_at=datetime.utcnow().isoformat(),
)
```

</specifics>

<deferred>
## Deferred Ideas

- **Walk-forward sul baseline** — Phase 7 lo esegue sul dataset prodotto qui (single-pass garantisce coverage massimo per training set ML). Non duplicare in Phase 5.
- **Portfolio simulation cross-pair / cross-TF** — Phase 11 paper deploy realism. Single equity, correlation guard, exposure limits.
- **Micro-account stress test (<500 EUR)** — Phase 11. Lot quantization realism: SL larghi non sizable a 0.01 lot minimum, expectancy distorted da quantization tax. Leva 1:500 non compensa (margine cambia, lot minimum no).
- **Per-profile cost override** — AGGRESSIVE potrebbe meritare slippage +20%, CONSERVATIVE -10%. Soggettivo, rinviato finché Phase 11 non genera dati live per calibrare.
- **Plot library upgrade (seaborn / plotly)** — matplotlib plain sufficiente per audit interno. Upgrade solo se Phase 11 deploy report serve presentation.
- **Walk-forward harness Phase 1 D-06** — implementato in Phase 1, NON usato qui. Phase 7 lo invoca per ML train/test folds.
- **Returns log vs simple per Sharpe** — `equity[t]/equity[t-1] - 1` vs `log(equity[t]/equity[t-1])`. Decisione a Phase 1 metrics module o Phase 7 ML evaluation.
- **Per-symbol strategy.yaml override** — se baseline rivela edge differente per pair, Phase 7+ valuta. Per ora single config.
- **HTML interactive report** — plotly per debug equity granular. Pesante in repo, fuori scope SC#4 (PNG).
- **Vectorized backtest** — numpy/pandas batch invece di event-driven loop. Se SC#1 (<30 min) sforata, Phase 5 Wave 2 valuta.
- **Resume from checkpoint** — se run di 25 min crasha al 20º, dover ripartire da zero è painful. `--resume` flag che skip run_id già scritti completamente. Versione lightweight di D-14 idempotency. Backlog se utile.
- **Parquet partition by symbol/tf** — invece di file singolo, partition ds.dataset. Migliora query Phase 7. Decisione a planner.

</deferred>

---

*Phase: 05-baseline-backtest*
*Context gathered: 2026-05-07 via /gsd:discuss-phase*
*Mode: discuss (4 aree, ~16 question)*
