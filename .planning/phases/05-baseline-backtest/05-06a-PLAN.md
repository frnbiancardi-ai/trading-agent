---
phase: 05-baseline-backtest
plan: 06a
type: execute
wave: 2
depends_on: [05-01, 05-02, 05-03, 05-04, 05-05]
files_modified:
  - backtest/baseline/slice_worker.py
  - tests/test_baseline_runner.py
  - tests/test_baseline_no_future_leakage.py
autonomous: true
requirements: [BACK-07, INT-01]
tags: [phase-5, baseline-backtest, wave-2, slice-worker]

phase1_dependency_risk: |
  REVISIONE 2026-05-08: l'INTERA dependency chain (Phase 1, 2, 3, 4) è ancora in planning.
  slice_worker invoca BacktestEngine.run() (Phase 1 plan 01-05) + risk_engine.evaluate_trade
  + LedgerWriter (Phase 1 plan 01-05) + indicators.compute_all_extended (Phase 2) +
  strategy.evaluate_proposal_for_bar (Phase 4). I test di slice_worker MOCKANO TUTTO
  (test fast no-CSV no-engine), quindi sono safe da eseguire prima del completamento
  Phase 1-4. Il check end-to-end avviene in 05-08 (smoke run) — quello bloccato dal
  preflight `scripts/preflight_phase5.py` (Plan 05-01 Task 4).

  WARNING 14 fix: questo plan è la PARTE A del split 05-06 originale (slice_worker only).
  Plan 05-06b copre report_writer.

must_haves:
  truths:
    - "run_slice_3profiles(symbol, tf, baseline_cfg, costs_cfg, strategy_cfg, force) ritorna list di 3 dict result (uno per profile)"
    - "Worker computa indicator cache UNA volta + riusa su 3 profile sequenziali (D-15)"
    - "warm_up = max(baseline_cfg.warm_up_min_bars, longest_lookback_required(strategy_cfg)); bars = bars[warm_up:] (BLOCKER 3 D-07 adaptive)"
    - "Idempotency: re-run senza --force con run_id esistente skip + warning log; con --force pulisce DELETE FROM backtest_trades WHERE run_id=? + DELETE FROM backtest_runs WHERE run_id=? prima di INSERT"
    - "Per ogni profile: write_decisions_shard + write_drafts_shard + plot_equity_curve invocati"
    - "Audit trail Phase 5: scrive cost_yaml_sha256, strategy_yaml_sha256, baseline_yaml_sha256 (full 64-char) nelle nuove colonne backtest_runs (WARNING 12 fix)"
  artifacts:
    - path: "backtest/baseline/slice_worker.py"
      provides: "run_slice_3profiles (worker entry-point per ProcessPoolExecutor)"
      contains: "matplotlib.use(\"Agg\")"
      contains: "compute_all_extended"
      contains: "longest_lookback_required"
      contains: "for profile in"
      contains: "_run_id_exists"
      contains: "_force_clear_run"
      contains: "BacktestEngine"
      contains: "write_decisions_shard"
      contains: "write_drafts_shard"
      contains: "plot_equity_curve"
      contains: "cost_yaml_sha256"
      contains: "strategy_yaml_sha256"
      contains: "baseline_yaml_sha256"
      min_lines: 100
  key_links:
    - from: "backtest/baseline/slice_worker.py::run_slice_3profiles"
      to: "backtest/baseline/runner.py (Wave 3 — Plan 05-07)"
      via: "ProcessPoolExecutor.submit(run_slice_3profiles, sym, tf, ...)"
    - from: "backtest/baseline/warmup.py::longest_lookback_required (Plan 05-01)"
      to: "backtest/baseline/slice_worker.py warm-up calc"
      via: "max(baseline_cfg.warm_up_min_bars, longest_lookback_required(strategy_cfg))"
---

<objective>
Wave 2 (parte slice_worker — split A di WARNING 14 fix). Implementa il worker per-slice
per ProcessPoolExecutor.

**`backtest/baseline/slice_worker.py`** — funzione `run_slice_3profiles(symbol, tf, ...)`
eseguita dentro ProcessPoolExecutor worker. Carica CSV, calcola warm-up adattivo (D-07
BLOCKER 3 fix), calcola indicator cache UNA volta, itera 3 profile sequenziali riusando
cache (D-15), gestisce idempotency D-14 (skip/--force), invoca writer parquet + plot per
ogni profile. Scrive audit trail Phase 5 (sha256 full-64) nelle nuove colonne backtest_runs.

**Test additional:** implementa `test_decision_dataset_temporal_ordering` e
`test_entry_at_next_bar_open` (D-22) in test_baseline_no_future_leakage.py — questi test
ora hanno il modulo target disponibile. Implementa anche 4 test di
`test_baseline_runner.py` su mocked engine (idempotency, cache reuse, perf, cost).

Output:
- `backtest/baseline/slice_worker.py` (NEW)
- 4 test in `test_baseline_runner.py` implementati (skip rimossi)
- 2 test in `test_baseline_no_future_leakage.py` implementati
</objective>

<execution_context>
@C:/trading-agent/.claude/get-shit-done/workflows/execute-plan.md
@C:/trading-agent/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@C:/trading-agent/.planning/phases/05-baseline-backtest/05-CONTEXT.md
@C:/trading-agent/.planning/phases/05-baseline-backtest/05-RESEARCH.md
@C:/trading-agent/.planning/phases/05-baseline-backtest/05-PATTERNS.md
@C:/trading-agent/.planning/phases/05-baseline-backtest/05-VALIDATION.md
@C:/trading-agent/.planning/phases/04-strategy-refactor/04-CONTEXT.md
@C:/trading-agent/backtest/engine.py
@C:/trading-agent/backtest/loader.py
@C:/trading-agent/backtest/costs.py
@C:/trading-agent/backtest/baseline/dataset_writer.py
@C:/trading-agent/backtest/baseline/plot_writer.py
@C:/trading-agent/backtest/baseline/determinism.py
@C:/trading-agent/backtest/baseline/wal_setup.py
@C:/trading-agent/backtest/baseline/warmup.py

<interfaces>
From backtest/baseline/dataset_writer.py (05-04):
  - write_decisions_shard(rows, run_id, shard_dir) → Path
  - write_drafts_shard(rows, run_id, shard_dir) → Path

From backtest/baseline/plot_writer.py (05-04):
  - plot_equity_curve(equity_df, out_path) → None

From backtest/baseline/determinism.py (05-03):
  - seed_for_run_id(run_id) → int
  - file_sha256(path) → str (full 64-char hex)

From backtest/baseline/wal_setup.py (05-03):
  - open_worker_connection(db_path) → sqlite3.Connection
  - with_retry(fn, n=5) → T

From backtest/baseline/warmup.py (05-01 Task 3b):
  - longest_lookback_required(strategy_cfg) → int (D-07 BLOCKER 3)

From backtest/engine.py (05-05 esteso):
  - BacktestEngine(bars, symbol, timeframe, cost_model, cfg, run_id, ledger,
                   cost_yaml_hash, indicators_full, risk_profile, timeout_bars, equity_initial)
  - .run() → dict {trades, drafts, equity_curve, ...}

From CONTEXT.md §D-13 (run_id schema):
  baseline_{date}_{symbol}_{tf}_{profile}
  Es: baseline_2026-05-08_EURUSD_M15_MODERATE
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: backtest/baseline/slice_worker.py — worker entry per ProcessPoolExecutor</name>
  <files>backtest/baseline/slice_worker.py, tests/test_baseline_runner.py, tests/test_baseline_no_future_leakage.py</files>
  <read_first>
    - C:/trading-agent/.planning/phases/05-baseline-backtest/05-PATTERNS.md §`slice_worker.py` lines 97-159
    - C:/trading-agent/.planning/phases/05-baseline-backtest/05-CONTEXT.md §specifics lines 210-264 (runner skeleton)
    - C:/trading-agent/.planning/phases/05-baseline-backtest/05-RESEARCH.md §Pitfall su `--force` (DELETE FROM backtest_trades)
    - C:/trading-agent/backtest/engine.py (signature estesa 05-05)
    - C:/trading-agent/backtest/loader.py (load_bars / load_italian_csv)
    - C:/trading-agent/backtest/baseline/warmup.py (longest_lookback_required, BLOCKER 3)
  </read_first>
  <behavior>
    - Test runner.py::test_idempotency_skip_and_force(tmp_db_with_wal, monkeypatch) —
      Mocka BacktestEngine.run a ritornare result dummy. Pre-popola backtest_runs con
      run_id `baseline_2026-05-08_EURUSD_M15_MODERATE`. Chiama run_slice_3profiles senza
      --force → verifica che ledger NON contiene nuove righe (skip). Re-call con force=True
      → verifica che righe vecchie cancellate + nuove inserite.
    - Test runner.py::test_indicator_cache_reused_across_profiles — Spy su
      `compute_all_extended`. Esegue run_slice_3profiles per (EURUSD, M15) → assert
      `compute_all_extended` chiamato ESATTAMENTE 1 volta (non 3).
    - Test runner.py::test_single_slice_perf_budget(monkeypatch, synthetic_bars) — Mocka
      load_bars + compute_all_extended + BacktestEngine.run con result fast (~10ms ognuno).
      Esegue run_slice_3profiles → wall-clock < 5s (sane upper bound test perf, non SC#1).
    - Test runner.py::test_cost_deduction(monkeypatch) — Mocka engine.run a ritornare 1
      trade con pnl_pips noto. Verifica che il cost (spread + commission + slippage)
      figura nel result dict (test smoke su composizione).
    - Test no_future_leakage::test_decision_dataset_temporal_ordering — Esegue worker
      mocked, leggi parquet decisions output, verifica `decision_ts_utc <= entry_ts_utc < exit_ts_utc` per ogni riga.
    - Test no_future_leakage::test_entry_at_next_bar_open — Mocka broker.send_order;
      verifica che il prezzo di entry registrato corrisponde a `next_bar.open ± slippage`,
      non a `current_bar.close`.
  </behavior>
  <action>
    **Sub-task 1a — Crea `backtest/baseline/slice_worker.py`:**

    ```python
    """Worker per-slice per ProcessPoolExecutor (Phase 5 D-15).

    Ogni worker carica CSV, calcola warm-up adattivo (D-07 BLOCKER 3), calcola indicator
    cache UNA volta, gira 3 profile sequenziali riusando cache. Idempotency D-14: skip se
    run_id esiste, --force pulisce prima.

    CRITICO: matplotlib.use("Agg") DEVE precedere QUALSIASI import che catena a pyplot.
    Su Windows spawn ctx, il backend non si propaga dal main → re-set qui.

    Source: PATTERNS.md §slice_worker.py, CONTEXT.md §specifics.
    """
    from __future__ import annotations

    # CRITICO: backend Agg PRIMA di import indiretti pyplot
    import matplotlib
    matplotlib.use("Agg")

    import logging
    import sqlite3
    import subprocess
    from datetime import date, datetime, timezone
    from pathlib import Path

    from backtest.loader import load_bars
    from backtest.costs import load_cost_model
    from backtest.ledger import LedgerWriter
    from backtest.engine import BacktestEngine
    from backtest.baseline.determinism import seed_for_run_id, file_sha256
    from backtest.baseline.dataset_writer import write_decisions_shard, write_drafts_shard
    from backtest.baseline.plot_writer import plot_equity_curve
    from backtest.baseline.wal_setup import open_worker_connection, with_retry
    from backtest.baseline.warmup import longest_lookback_required  # BLOCKER 3 D-07

    _log = logging.getLogger(__name__)

    PROFILES = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")


    def _build_run_id(symbol: str, tf: str, profile: str, run_date: str | None = None) -> str:
        """D-13: run_id = baseline_{date}_{symbol}_{tf}_{profile}."""
        d = run_date or date.today().isoformat()
        return f"baseline_{d}_{symbol}_{tf}_{profile}"


    def _run_id_exists(db_path: Path, run_id: str) -> bool:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM backtest_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return row is not None


    def _force_clear_run(db_path: Path, run_id: str) -> None:
        """RESEARCH §Pitfall: AUTOINCREMENT su backtest_trades duplica righe in --force.

        DELETE FROM backtest_trades + backtest_runs PRIMA di re-insert. Single connection
        con busy_timeout — WARNING 8 fix: non wrappare con `with_retry` (riapre conn ogni
        retry); usa busy_timeout built-in.
        """
        # WARNING 8 fix: single connection, busy_timeout, no with_retry wrapper.
        conn = sqlite3.connect(db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("DELETE FROM backtest_trades WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM backtest_runs WHERE run_id=?", (run_id,))
            conn.commit()
        finally:
            conn.close()


    def _git_sha() -> str:
        """Best-effort git rev-parse HEAD per audit trail (D-17)."""
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=str(Path(__file__).resolve().parents[2]),
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except Exception:
            return "unknown"


    def run_slice_3profiles(
        symbol: str,
        tf: str,
        baseline_cfg,         # BaselineConfig (frozen dataclass — Plan 05-07 definisce loader)
        costs_cfg,            # dict per-symbol caricato da load_cost_model
        strategy_cfg_path: Path,
        force: bool = False,
        ledger_db_path: Path | None = None,
        run_date: str | None = None,
    ) -> list[dict]:
        """Worker entry per ProcessPoolExecutor. Esegue 3 run sequenziali su (symbol, tf).

        Returns: list[dict] di 3 result, ciascuno con keys: run_id, profile, status,
        metrics, n_trades, n_drafts, equity_path, error (se status=FAILED).
        """
        ledger_db = Path(ledger_db_path) if ledger_db_path else Path("logs/trades.db")
        # 1. Load CSV (Phase 1 loader)
        bars = load_bars(symbol, tf)

        # 2. Warm-up adaptive (D-07 BLOCKER 3 fix): max(warm_up_min_bars, longest_lookback)
        # Reads strategy.yaml indicator config; fallback 200 se non parseable.
        try:
            import yaml
            with open(strategy_cfg_path, encoding="utf-8") as f:
                strategy_cfg = yaml.safe_load(f) or {}
        except Exception:  # noqa: BLE001
            strategy_cfg = {}
        warm_up = max(baseline_cfg.warm_up_min_bars,
                      longest_lookback_required(strategy_cfg))
        bars = bars[warm_up:]
        _log.info("slice %s %s warm_up=%d (cfg=%d, longest_lookback=%d)",
                  symbol, tf, warm_up, baseline_cfg.warm_up_min_bars,
                  longest_lookback_required(strategy_cfg))

        # 3. Indicator cache UNA volta per slice (D-15)
        from indicators import compute_all_extended  # import lazy — Phase 2 dependency
        indicators_full = compute_all_extended(bars)

        # 4. Cost model
        cost = load_cost_model(symbol, costs_cfg)

        # 5. Hashes audit trail (D-17 + WARNING 12 fix: full 64-char sha256)
        cost_sha256 = file_sha256(Path("data/configs/costs.yaml"))
        strategy_sha256 = file_sha256(strategy_cfg_path)
        baseline_sha256 = file_sha256(Path("data/configs/baseline.yaml"))
        git = _git_sha()

        results: list[dict] = []
        timeout = baseline_cfg.timeout_bars[tf]  # D-05

        for profile in PROFILES:
            run_id = _build_run_id(symbol, tf, profile, run_date)
            # Idempotency D-14
            if _run_id_exists(ledger_db, run_id):
                if not force:
                    _log.warning("skip %s: già esistente, usa --force per overwrite", run_id)
                    results.append({"run_id": run_id, "profile": profile,
                                    "symbol": symbol, "timeframe": tf,
                                    "status": "SKIPPED"})
                    continue
                else:
                    _log.info("force: pulisco run_id %s prima di re-insert", run_id)
                    # WARNING 8 fix: NO with_retry wrapper — _force_clear_run è già
                    # single-connection con busy_timeout interno.
                    _force_clear_run(ledger_db, run_id)

            try:
                seed_eff = seed_for_run_id(run_id)
                ledger = LedgerWriter(ledger_db)
                engine = BacktestEngine(
                    bars=bars, symbol=symbol, timeframe=tf, cost_model=cost,
                    initial_balance=baseline_cfg.equity_initial_eur,
                    run_id=run_id, ledger=ledger,
                    cost_yaml_hash=cost_sha256[:16],  # legacy column md5[:16]-style — backwards compat
                    indicators_full=indicators_full,
                    risk_profile=profile,
                    timeout_bars=timeout,
                    equity_initial=baseline_cfg.equity_initial_eur,
                )
                engine_result = engine.run()

                # Persist parquet shards (D-01/D-02/D-03)
                shard_dir = Path(baseline_cfg.training_data_dir)
                write_decisions_shard(engine_result.get("decisions_rows", []), run_id, shard_dir)
                write_drafts_shard(engine_result.get("drafts_rows", []), run_id, shard_dir)

                # Plot equity (D-19)
                png_path = (Path(baseline_cfg.equity_curves_dir)
                            / f"{symbol}_{tf}_{profile}.png")
                plot_equity_curve(engine_result["equity_curve"], png_path)

                # Audit trail extra: aggiorna backtest_runs con campi Phase 5
                # WARNING 7 fix: helper esplicito (no lambda truthiness con `and conn.commit()`).
                # WARNING 12 fix: scrivi sha256 FULL 64-char nelle nuove colonne; legacy
                # cost_yaml_hash mantiene formato md5[:16] per backwards compat Phase 1.
                def _do_audit_update(_db=ledger_db, _rid=run_id, _seed=seed_eff,
                                     _cs=cost_sha256, _ss=strategy_sha256,
                                     _bs=baseline_sha256, _git=git):
                    _conn = sqlite3.connect(_db, timeout=30.0)
                    try:
                        _conn.execute("PRAGMA busy_timeout=30000")
                        _conn.execute(
                            "UPDATE backtest_runs SET slippage_seed_effective=?, "
                            "strategy_yaml_hash=?, baseline_yaml_hash=?, git_sha=?, "
                            "cost_yaml_sha256=?, strategy_yaml_sha256=?, baseline_yaml_sha256=? "
                            "WHERE run_id=?",
                            (_seed, _ss[:16], _bs[:16], _git, _cs, _ss, _bs, _rid),
                        )
                        _conn.commit()
                    finally:
                        _conn.close()
                with_retry(_do_audit_update)

                results.append({
                    "run_id": run_id,
                    "profile": profile,
                    "status": "OK",
                    "metrics": engine_result.get("metrics"),
                    "n_trades": len(engine_result.get("decisions_rows", [])),
                    "n_drafts": len(engine_result.get("drafts_rows", [])),
                    "equity_path": str(png_path),
                    "symbol": symbol,
                    "timeframe": tf,
                })
            except Exception as exc:
                _log.error("run_id=%s fallito: %s", run_id, exc, exc_info=True)
                results.append({
                    "run_id": run_id, "profile": profile,
                    "status": "FAILED", "error": str(exc),
                    "symbol": symbol, "timeframe": tf,
                })

        return results
    ```

    **Sub-task 1b — Implementa 4 test in `tests/test_baseline_runner.py`:**

    Tutti i test mockano BacktestEngine.run via monkeypatch (no CSV reale, no full run).
    Pattern usa `monkeypatch.setattr("backtest.baseline.slice_worker.BacktestEngine", MockEngine)`.

    Vedi PATTERNS.md per fixture _patch_worker_io() helper. Test names:
    `test_indicator_cache_reused_across_profiles`, `test_idempotency_skip_and_force`,
    `test_single_slice_perf_budget`, `test_cost_deduction`. Pattern verbatim Plan 05-06
    originale (non riscrivere — già splitati questi 4 test).

    Per la verifica BACK-07 SC#1 perf <5s, il test mocked deve completare con
    `time.time() - t0 < 5.0`.

    **Sub-task 1c — Implementa 2 test in `tests/test_baseline_no_future_leakage.py`** (rimuove skip):

    `test_decision_dataset_temporal_ordering`: scrivi 2 row in parquet shard con
    decision_ts < entry_ts < exit_ts; assert ordine dopo round-trip.

    `test_entry_at_next_bar_open`: synthetic check su 2 bar consecutivi —
    entry_price == bar_next.open (NON bar_current.close); D-22 semantica.

    Italiano docstring, inglese function name.
  </action>
  <verify>
    <automated>.venv\Scripts\python.exe -m pytest tests/test_baseline_runner.py tests/test_baseline_no_future_leakage.py -x --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - File `backtest/baseline/slice_worker.py` esiste, ≥100 righe
    - `grep -c "matplotlib.use(\"Agg\")" backtest/baseline/slice_worker.py` == 1
    - `grep -c "_force_clear_run" backtest/baseline/slice_worker.py` ≥ 2 (def + call)
    - `grep -c "_run_id_exists" backtest/baseline/slice_worker.py` ≥ 2
    - `grep -c "DELETE FROM backtest_trades" backtest/baseline/slice_worker.py` ≥ 1
    - `grep -c "indicators_full" backtest/baseline/slice_worker.py` ≥ 1
    - `grep -c "for profile in PROFILES" backtest/baseline/slice_worker.py` == 1
    - `grep -c "longest_lookback_required" backtest/baseline/slice_worker.py` ≥ 1 (BLOCKER 3 fix)
    - `grep -c "cost_yaml_sha256" backtest/baseline/slice_worker.py` ≥ 1 (WARNING 12 fix)
    - `grep -c "strategy_yaml_sha256" backtest/baseline/slice_worker.py` ≥ 1
    - `grep -c "baseline_yaml_sha256" backtest/baseline/slice_worker.py` ≥ 1
    - **WARNING 7 fix**: `grep -c "with_retry(lambda" backtest/baseline/slice_worker.py` == 0
      (NESSUNA chiamata `with_retry` con lambda; solo helper espliciti)
    - **WARNING 8 fix**: `grep -c "with_retry(lambda: _force_clear_run" backtest/baseline/slice_worker.py` == 0
    - `pytest tests/test_baseline_runner.py -x` exit 0 (4 test pass)
    - `pytest tests/test_baseline_no_future_leakage.py -x` exit 0 (test_indicator_full_slice
      può essere skipped se Phase 2 non landed; gli altri 2 pass)
  </acceptance_criteria>
  <done>
    Slice worker implementato. Idempotency + cache reuse + force clear + warmup adattivo
    + audit trail full sha256 verificati. 6 test verdi (eccetto test condizionale Phase 2).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| ProcessPoolExecutor worker → main | Worker ritorna dict serializable (pickle). Errori catturati e ritornati come `status="FAILED"`. |
| Subprocess git rev-parse | Best-effort, ritorna "unknown" su failure — no auth/network call |
| strategy.yaml YAML loader | yaml.safe_load (no custom tags) — input non-trusted ammesso ma confinato |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-15 | Tampering | --force DELETE FROM backtest_trades | mitigate | DELETE WHERE run_id=? parametrizzato — no SQL injection. Idempotency D-14 garantisce safe replay. |
| T-05-17 | Denial of Service | worker exception kills pool | mitigate | try/except in worker → ritorna `status="FAILED"` invece di propagare; runner log error e continua |
| T-05-25 | Tampering | strategy.yaml warmup parsing | mitigate | longest_lookback_required (whitelisted keys, fallback 200) — input malformati safe |
</threat_model>

<verification>
- 1 modulo core implementato (slice_worker)
- 6 test totali pass (4 runner + 2 no_future_leakage; il 3o no_future_leakage è
  condizionale Phase 2)
- D-14 idempotency, D-15 cache reuse, D-07 adaptive warmup verificati
- WARNING 7 + 8 (lambda truthiness) fix applicati
- WARNING 12 (sha256 full-64) audit trail verificato
- VALIDATION.md rows D-07, D-14, D-15, D-22, D-22 spostate a green
</verification>

<success_criteria>
- Plan 05-06b può consumare i result dict generati per costruire il report MD
- D-15 hybrid orchestration completa: cache 1×/slice, 3 profile sequenziali
- D-07 BLOCKER 3 chiuso: warmup adattivo wired in slice_worker
- WARNING 7/8/12 chiusi
- Phase 1-4 dependency risk: tutti i test mockano dependency chain — vero E2E in 05-08
</success_criteria>

<output>
Dopo completamento: `.planning/phases/05-baseline-backtest/05-06a-SUMMARY.md`.
Sezioni: Files Created, Tests Passing, D-07/D-14/D-15 Verification, BLOCKER 3 + WARNING 7/8/12
Closures, Mock Strategy for Phase 1-4 Pending, Next: Plan 05-06b (report_writer).
</output>
</content>
</invoke>