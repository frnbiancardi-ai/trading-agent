"""Tests per backtest.baseline.slice_worker (BACK-07, D-14, D-15, D-23).

Plan 05-06a (split A di 05-06 originale): slice_worker only.

Strategia di mock-heavy: tutti i test mockano BacktestEngine.run, load_bars,
load_cost_model, compute_all_extended, write_*_shard, plot_equity_curve. Niente
CSV reali, niente pyarrow I/O, niente matplotlib I/O. Test fast no-engine no-CSV
così sono safe da eseguire prima del completamento Phase 1-4 (vedi
phase1_dependency_risk del plan).
"""
from __future__ import annotations

import sqlite3
import sys
import time
import types
from dataclasses import dataclass
from pathlib import Path

import pytest


# ─── Helpers / mocks condivisi ──────────────────────────────────────────────


@dataclass
class _MockBaselineCfg:
    """Dataclass minimale che mima il loader Plan 05-07 (senza dipendere da esso)."""
    equity_initial_eur: float = 10_000.0
    warm_up_min_bars: int = 200
    timeout_bars: dict = None
    training_data_dir: str = "data/training"
    equity_curves_dir: str = ".planning/research/baseline-equity-curves"

    def __post_init__(self):
        if self.timeout_bars is None:
            self.timeout_bars = {"M15": 96, "M30": 96, "H1": 120}


def _make_baseline_cfg(tmp_path: Path) -> _MockBaselineCfg:
    return _MockBaselineCfg(
        training_data_dir=str(tmp_path / "training"),
        equity_curves_dir=str(tmp_path / "equity"),
    )


def _seed_backtest_runs_table(db_path: Path, run_id: str | None = None) -> None:
    """Crea schema minimale e popola un run pre-esistente per test idempotency."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS backtest_runs ("
            "run_id TEXT PRIMARY KEY, symbol TEXT, timeframe TEXT, "
            "date_start TEXT, date_end TEXT, cost_yaml_hash TEXT, "
            "profile TEXT, n_folds INTEGER, fold_mode TEXT, train_ratio INTEGER, "
            "started_at TEXT, finished_at TEXT, total_trades INTEGER, "
            "sharpe REAL, sortino REAL, max_dd_pct REAL, hit_rate REAL, "
            "expectancy_usd REAL, profit_factor REAL, avg_r REAL, "
            "total_pnl_usd REAL, "
            "slippage_seed_effective INTEGER, strategy_yaml_hash TEXT, "
            "baseline_yaml_hash TEXT, git_sha TEXT, "
            "cost_yaml_sha256 TEXT, strategy_yaml_sha256 TEXT, "
            "baseline_yaml_sha256 TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS backtest_trades ("
            "trade_id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "run_id TEXT NOT NULL REFERENCES backtest_runs(run_id), "
            "fold_index INTEGER, entry_time TEXT, exit_time TEXT, "
            "symbol TEXT, timeframe TEXT, direction TEXT, "
            "entry_price REAL, exit_price REAL, sl REAL, tp REAL, "
            "lot_size REAL, pnl_pips REAL, pnl_usd REAL, risk_usd REAL, "
            "exit_reason TEXT, setup_type TEXT, confidence REAL, "
            "decision_context_json TEXT)"
        )
        if run_id is not None:
            conn.execute(
                "INSERT INTO backtest_runs (run_id, symbol, timeframe, "
                "date_start, date_end, started_at) VALUES (?,?,?,?,?,?)",
                (run_id, "EURUSD", "M15", "2024-01-01", "2024-12-31", "now"),
            )
            conn.execute(
                "INSERT INTO backtest_trades (run_id, entry_time, exit_time, "
                "symbol, timeframe, direction, entry_price, exit_price, lot_size) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (run_id, "2024-01-01", "2024-01-02", "EURUSD", "M15",
                 "BUY", 1.10, 1.11, 0.1),
            )
        conn.commit()
    finally:
        conn.close()


def _stub_indicators_module(monkeypatch) -> dict:
    """Iniettare un modulo `indicators` in sys.modules con compute_all_extended.

    Ritorna il dict-spy che traccia call_count.
    """
    spy = {"calls": 0, "last_input": None}

    def fake_compute(bars, *, regime_cfg=None, **kwargs):
        # Backward-compat stub Plan 05-09: il vero compute_all_extended ora
        # accetta `regime_cfg=None` (e potenzialmente altri kwargs futuri).
        # Il modulo dataset_writer chiama questa funzione a import-time via
        # `_build_required_keys_v2()`. Stub deve accettare la signature
        # estesa per non rompere i 4 test pre-Plan 05-09 che usano
        # `_patch_worker_io` (= import indiretto di dataset_writer).
        # Lo stub ignora regime_cfg (test pre-esistenti non lo usano).
        spy["calls"] += 1
        spy["last_input"] = bars
        spy["last_regime_cfg"] = regime_cfg
        return {"sma_20": 1.10, "atr_14": 0.001, "rsi_14": 55.0}

    mod = types.ModuleType("indicators")
    mod.compute_all_extended = fake_compute
    monkeypatch.setitem(sys.modules, "indicators", mod)

    # Backward-compat stub Plan 05-09: il vero codice ora fa anche
    # `from indicators.volatility import load_regime_config` (slice_worker
    # post FIX 1 iter 1). Lo stub deve esporre un submodule `volatility`
    # con load_regime_config(symbol, yaml_path) -> dict.
    vol_mod = types.ModuleType("indicators.volatility")

    def fake_load_regime_config(symbol, yaml_path=None):
        # Test pre-esistenti non usano regime_cfg, ritorna config minimale
        # vuota (matcha la firma `dict` che lo stub utilizza).
        return {}

    vol_mod.load_regime_config = fake_load_regime_config
    monkeypatch.setitem(sys.modules, "indicators.volatility", vol_mod)
    # `indicators.volatility` accessibile anche via attribute lookup (es. `import indicators; indicators.volatility.load_regime_config`).
    mod.volatility = vol_mod
    return spy


def _patch_worker_io(monkeypatch, tmp_path: Path, *, fake_engine_result=None):
    """Patcha I/O fisico nel modulo slice_worker.

    Ritorna dict spy con keys: engine_calls, write_dec_calls, write_drf_calls,
    plot_calls.
    """
    from backtest.baseline import slice_worker as sw

    # Fake bars non-vuoto (l'unico vincolo è warm_up < len(bars))
    from backtest.loader import Bar
    fake_bars = [
        Bar(time=i * 900, open=1.1, high=1.1002, low=1.0998, close=1.1001,
            volume=100, symbol="EURUSD", timeframe="M15")
        for i in range(250)
    ]

    spy = {
        "engine_calls": 0,
        "write_dec_calls": 0,
        "write_drf_calls": 0,
        "plot_calls": 0,
        "audit_calls": 0,
    }

    monkeypatch.setattr(sw, "load_bars", lambda *a, **kw: fake_bars)

    fake_cost = types.SimpleNamespace(
        spread_pips=0.5, slippage_pips=0.3, commission_pips_round_trip=0.5,
        pip_size=0.0001, pip_value_usd=10.0,
    )
    monkeypatch.setattr(sw, "load_cost_model", lambda *a, **kw: fake_cost)

    # warmup → fissato basso così bars[warm_up:] ha contenuto
    monkeypatch.setattr(sw, "longest_lookback_required", lambda cfg: 50)

    # determinism + git: deterministic, no real subprocess/file
    monkeypatch.setattr(sw, "file_sha256", lambda p: "a" * 64)
    monkeypatch.setattr(sw, "_git_sha", lambda: "deadbeef")

    class _FakeLedgerWriter:
        def __init__(self, db):
            self.db = db
        def record_run(self, *a, **kw): pass
        def insert_trades(self, *a, **kw): pass
        def ensure_schema(self): pass

    monkeypatch.setattr(sw, "LedgerWriter", _FakeLedgerWriter)

    default_result = {
        "run_id": "stub",
        "trades": [],
        "decisions_rows": [{"foo": 1}],
        "drafts_rows": [],
        "equity_curve": [10_000.0, 10_010.0],
        "metrics": {"sharpe": 1.5, "spread_pips": 0.5,
                    "commission_pips_round_trip": 0.5, "slippage_pips": 0.3,
                    "cost_total": 1.3},
        "bars_processed": 200,
    }

    class _FakeEngine:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
        def run(self):
            spy["engine_calls"] += 1
            return fake_engine_result if fake_engine_result is not None else default_result

    monkeypatch.setattr(sw, "BacktestEngine", _FakeEngine)

    def _fake_write_dec(rows, run_id, shard_dir):
        spy["write_dec_calls"] += 1
        return Path(shard_dir) / f"baseline_decisions_{run_id}.parquet"

    def _fake_write_drf(rows, run_id, shard_dir):
        spy["write_drf_calls"] += 1
        return Path(shard_dir) / f"baseline_drafts_{run_id}.parquet"

    monkeypatch.setattr(sw, "write_decisions_shard", _fake_write_dec)
    monkeypatch.setattr(sw, "write_drafts_shard", _fake_write_drf)

    def _fake_plot(equity, out_path):
        spy["plot_calls"] += 1
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).touch()

    monkeypatch.setattr(sw, "plot_equity_curve", _fake_plot)

    def _fake_audit(db, rid, seed, cs, ss, bs, git):
        spy["audit_calls"] += 1

    monkeypatch.setattr(sw, "_audit_update_run", _fake_audit)

    return spy


# ─── Test 1: D-15 indicator cache reuse ───────────────────────────────────


def test_indicator_cache_reused_across_profiles(monkeypatch, tmp_path):
    """D-15: hybrid orchestration — `compute_all_extended` chiamato 1× per slice (3 profile).

    Un singolo run_slice_3profiles deve ricalcolare gli indicator UNA volta
    sola (non 3) anche se il loop esegue 3 profile sequenziali.
    """
    spy = _stub_indicators_module(monkeypatch)
    _patch_worker_io(monkeypatch, tmp_path)
    db = tmp_path / "trades.db"
    _seed_backtest_runs_table(db)

    # Reset counter post-import: `_build_required_keys_v2()` di dataset_writer
    # chiama compute_all_extended UNA volta a import-time per costruire la
    # whitelist v2 (FIX 3 plan-checker iter 1 Plan 05-09). Quella chiamata
    # NON e' parte del flow D-15 (cache reuse runtime). Reset per misurare
    # solo le chiamate da run_slice_3profiles.
    spy["calls"] = 0
    spy["last_input"] = None

    from backtest.baseline.slice_worker import run_slice_3profiles

    cfg = _make_baseline_cfg(tmp_path)
    results = run_slice_3profiles(
        symbol="EURUSD",
        tf="M15",
        baseline_cfg=cfg,
        costs_cfg_path=tmp_path / "costs.yaml",
        strategy_cfg_path=tmp_path / "strategy.yaml",
        force=False,
        ledger_db_path=db,
        csv_path=tmp_path / "fake.csv",
    )

    assert spy["calls"] == 1, (
        f"D-15 violato: compute_all_extended chiamato {spy['calls']} volte (atteso 1)"
    )
    assert len(results) == 3, "atteso un result per ognuno dei 3 profile"
    assert all(r["status"] == "OK" for r in results), [r for r in results]


# ─── Test 2: D-14 idempotency skip + force ────────────────────────────────


def test_idempotency_skip_and_force(monkeypatch, tmp_path):
    """D-14: re-run senza --force skip; con --force overwrite (cancella + reinsert).

    1) Pre-popolo backtest_runs con run_id MODERATE → senza --force quel
       profile ritorna SKIPPED, gli altri 2 OK (totale 2 OK + 1 SKIPPED).
    2) Re-call con force=True → tutti e 3 OK + cancellazione delle righe
       backtest_trades pre-esistenti (test su DELETE FROM backtest_trades).
    """
    _stub_indicators_module(monkeypatch)
    spy = _patch_worker_io(monkeypatch, tmp_path)
    db = tmp_path / "trades.db"

    # Plan dichiara DATE today; il worker costruisce run_id = baseline_<date>_<sym>_<tf>_<profile>
    from backtest.baseline.slice_worker import _build_run_id, run_slice_3profiles
    run_date = "2024-01-15"
    rid_mod = _build_run_id("EURUSD", "M15", "MODERATE", run_date)
    _seed_backtest_runs_table(db, run_id=rid_mod)

    # Sanity: la riga seedata esiste prima del test
    conn = sqlite3.connect(db)
    pre_count = conn.execute(
        "SELECT count(*) FROM backtest_trades WHERE run_id=?", (rid_mod,),
    ).fetchone()[0]
    conn.close()
    assert pre_count == 1, "fixture seed mancante"

    cfg = _make_baseline_cfg(tmp_path)

    # 1) senza --force → MODERATE skipped
    results_skip = run_slice_3profiles(
        symbol="EURUSD",
        tf="M15",
        baseline_cfg=cfg,
        costs_cfg_path=tmp_path / "costs.yaml",
        strategy_cfg_path=tmp_path / "strategy.yaml",
        force=False,
        ledger_db_path=db,
        run_date=run_date,
        csv_path=tmp_path / "fake.csv",
    )
    by_profile = {r["profile"]: r["status"] for r in results_skip}
    assert by_profile["MODERATE"] == "SKIPPED"
    assert by_profile["CONSERVATIVE"] == "OK"
    assert by_profile["AGGRESSIVE"] == "OK"

    # La riga pre-esistente in backtest_trades è ancora intatta (no force).
    conn = sqlite3.connect(db)
    n_after_skip = conn.execute(
        "SELECT count(*) FROM backtest_trades WHERE run_id=?", (rid_mod,),
    ).fetchone()[0]
    conn.close()
    assert n_after_skip == 1, "skip non deve toccare backtest_trades pre-esistenti"

    # 2) force=True → MODERATE cancellato + ri-inserito (tutti e 3 OK)
    spy["engine_calls"] = 0  # reset
    results_force = run_slice_3profiles(
        symbol="EURUSD",
        tf="M15",
        baseline_cfg=cfg,
        costs_cfg_path=tmp_path / "costs.yaml",
        strategy_cfg_path=tmp_path / "strategy.yaml",
        force=True,
        ledger_db_path=db,
        run_date=run_date,
        csv_path=tmp_path / "fake.csv",
    )
    statuses = sorted(r["status"] for r in results_force)
    assert statuses == ["OK", "OK", "OK"], statuses

    # _force_clear_run ha cancellato la riga pre-esistente di backtest_trades.
    conn = sqlite3.connect(db)
    n_after_force = conn.execute(
        "SELECT count(*) FROM backtest_trades WHERE run_id=?", (rid_mod,),
    ).fetchone()[0]
    conn.close()
    # Il fake engine non inserisce nuove righe trades (mock LedgerWriter no-op),
    # quindi ci aspettiamo 0: la riga seedata è stata cancellata da DELETE.
    assert n_after_force == 0, (
        "DELETE FROM backtest_trades non eseguito con --force "
        f"(post-force trades count = {n_after_force})"
    )


# ─── Test 3: BACK-07 perf budget (mocked) ─────────────────────────────────


def test_single_slice_perf_budget(monkeypatch, tmp_path):
    """BACK-07 SC#1 sane upper bound: con engine mocked, slice_worker < 5s wall-clock.

    Test smoke: il sovraccarico di slice_worker (warm-up calc, audit, file ops
    su tmp) deve restare sotto 5s. Non è il vero SC#1 (<2 min/slice su CSV reale)
    ma garantisce che il worker non abbia regressioni macroscopiche.
    """
    _stub_indicators_module(monkeypatch)
    _patch_worker_io(monkeypatch, tmp_path)
    db = tmp_path / "trades.db"
    _seed_backtest_runs_table(db)

    from backtest.baseline.slice_worker import run_slice_3profiles

    cfg = _make_baseline_cfg(tmp_path)
    t0 = time.time()
    results = run_slice_3profiles(
        symbol="EURUSD",
        tf="M15",
        baseline_cfg=cfg,
        costs_cfg_path=tmp_path / "costs.yaml",
        strategy_cfg_path=tmp_path / "strategy.yaml",
        force=False,
        ledger_db_path=db,
        csv_path=tmp_path / "fake.csv",
    )
    elapsed = time.time() - t0

    assert elapsed < 5.0, (
        f"slice_worker mocked impiega {elapsed:.2f}s (sane upper bound 5s superato)"
    )
    assert len(results) == 3


# ─── Test 4: D-23 cost deduction visibile nei result ──────────────────────


def test_cost_deduction(monkeypatch, tmp_path):
    """D-23: pipeline trade → metrics post Plan 05-08 deviation Rule 3.

    Plan 05-08 deviation Rule 3 (D-21 contract gap fix): engine.run() ritorna
    `{run_id, trades, equity_curve, bars_processed}` (NON `decisions_rows` /
    `drafts_rows` / `metrics` come supponeva il mock originale del Plan 05-06a).
    slice_worker bridgia: `decisions_rows ← trades`, `metrics ← compute_metrics(
    trades, tf)` (BacktestMetrics dataclass: sharpe / sortino / hit_rate /
    expectancy_usd / profit_factor / total_pnl_usd / longest_dd_days / ...).

    Spread/commission/slippage NON sono campi di `BacktestMetrics`: vengono
    dedotti dentro engine.run() su `pnl_usd` (T-05-23 Phase 1) prima del
    record di trade. Quindi questo test verifica solo la pipeline post-engine
    (worker non duplica calcolo costi).
    """
    _stub_indicators_module(monkeypatch)
    fake_result = {
        "run_id": "stub",
        # Schema reale `_row_for_ledger` Phase 1: trade chiusi con pnl_usd / risk_usd.
        "trades": [
            {"pnl_usd": 90.0, "risk_usd": 100.0, "exit_time": "2024-01-02T10:00:00+00:00"},
        ],
        "equity_curve": [10_000.0, 10_090.0],
        "bars_processed": 200,
    }
    _patch_worker_io(monkeypatch, tmp_path, fake_engine_result=fake_result)
    db = tmp_path / "trades.db"
    _seed_backtest_runs_table(db)

    from backtest.baseline.slice_worker import run_slice_3profiles

    cfg = _make_baseline_cfg(tmp_path)
    results = run_slice_3profiles(
        symbol="EURUSD",
        tf="M15",
        baseline_cfg=cfg,
        costs_cfg_path=tmp_path / "costs.yaml",
        strategy_cfg_path=tmp_path / "strategy.yaml",
        force=False,
        ledger_db_path=db,
        csv_path=tmp_path / "fake.csv",
    )
    assert len(results) == 3
    for r in results:
        assert r["status"] == "OK", r
        m = r["metrics"]
        # BacktestMetrics fields prodotti da compute_metrics (worker bridge).
        assert "sharpe" in m
        assert "hit_rate" in m
        assert "total_pnl_usd" in m
        assert "longest_dd_days" in m
        # n_trades == len(trades) (1-1 con decisions_rows post-bridge).
        assert r["n_trades"] == 1
        # Single trade con pnl_usd>0 → hit_rate 1.0
        assert m["hit_rate"] == 1.0
        assert m["total_pnl_usd"] == 90.0


# ── Wave 3 additions: orchestrator-level tests (Plan 05-07) ────────────────


def test_load_baseline_config(tmp_path):
    """Plan 05-07 Task 1 Test 3: load_baseline_config -> frozen dataclass."""
    from backtest.baseline.runner import load_baseline_config, BaselineConfig
    yaml_path = tmp_path / "baseline.yaml"
    yaml_path.write_text(
        "equity_initial_eur: 10000\n"
        "slippage_seed: 42\n"
        "timeout_bars: {M15: 96, M30: 96, H1: 120}\n"
        "warm_up_min_bars: 200\n"
        "max_workers: 9\n"
        "parquet_compression: snappy\n"
        "force_rerun: false\n"
        "progress_bar: true\n"
        'training_data_dir: "data/training"\n'
        'report_dir: ".planning/research"\n'
        'equity_curves_dir: ".planning/research/baseline-equity-curves"\n',
        encoding="utf-8",
    )
    cfg = load_baseline_config(yaml_path)
    assert isinstance(cfg, BaselineConfig)
    assert cfg.equity_initial_eur == 10000.0
    assert cfg.slippage_seed == 42
    assert cfg.timeout_bars == {"M15": 96, "M30": 96, "H1": 120}
    assert cfg.max_workers == 9
    assert cfg.parquet_compression == "snappy"
    assert cfg.progress_bar is True


def test_run_baseline_orchestrates_27_runs(monkeypatch, tmp_path):
    """Plan 05-07 Task 1 Test 1: run_baseline raccoglie 9*3=27 result, invoca finalize+report."""
    baseline_path = tmp_path / "baseline.yaml"
    baseline_path.write_text(
        "equity_initial_eur: 10000\nslippage_seed: 42\n"
        "timeout_bars: {M15: 96, M30: 96, H1: 120}\n"
        "warm_up_min_bars: 200\nmax_workers: 2\n"  # ridotto per test
        "parquet_compression: snappy\nforce_rerun: false\nprogress_bar: false\n"
        f'training_data_dir: "{tmp_path.as_posix()}"\n'
        f'report_dir: "{tmp_path.as_posix()}"\n'
        f'equity_curves_dir: "{tmp_path.as_posix()}"\n',
        encoding="utf-8",
    )
    costs_path = tmp_path / "costs.yaml"
    costs_path.write_text("EURUSD: {spread_pips: 0.5}\n", encoding="utf-8")
    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text("dummy: 1\n", encoding="utf-8")
    ledger_db = tmp_path / "trades.db"

    finalize_calls = {"n": 0}
    wal_calls = {"n": 0}

    def fake_worker(sym, tf, *args, **kwargs):
        return [{"run_id": f"r_{sym}_{tf}_{p}", "symbol": sym, "timeframe": tf,
                 "profile": p, "status": "OK", "metrics": None,
                 "n_trades": 0, "n_drafts": 0, "equity_path": ""}
                for p in ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")]

    def fake_finalize(p):
        finalize_calls["n"] += 1

    def fake_wal(p):
        wal_calls["n"] += 1

    monkeypatch.setattr("backtest.baseline.runner.run_slice_3profiles", fake_worker)
    monkeypatch.setattr("backtest.baseline.runner.enable_sqlite_wal", fake_wal)
    monkeypatch.setattr("backtest.baseline.runner.finalize_parquet_shards", fake_finalize)
    # I mock locali NON sono pickleable da spawn ProcessPoolExecutor —
    # sostituisci la factory con un ThreadPoolExecutor (in-process).
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(
        "backtest.baseline.runner._make_pool_executor",
        lambda mw, ctx: ThreadPoolExecutor(max_workers=mw),
    )

    from backtest.baseline.runner import run_baseline
    results = run_baseline(
        force=False, baseline_yaml=baseline_path, costs_yaml=costs_path,
        strategy_yaml=strategy_path, ledger_db=ledger_db,
    )
    assert len(results) == 27, f"atteso 27 result (9 sym/tf × 3 profile), got {len(results)}"
    assert finalize_calls["n"] == 1, "finalize_parquet_shards deve essere chiamato 1 volta post-pool"
    assert wal_calls["n"] == 1, "enable_sqlite_wal deve essere chiamato 1 volta pre-pool"
    # Report MD scritto?
    import datetime as _dt
    report_path = tmp_path / f"baseline-{_dt.date.today().isoformat()}.md"
    assert report_path.exists(), f"report MD mancante: {report_path}"


def test_run_baseline_handles_worker_failure(monkeypatch, tmp_path):
    """Plan 05-07 Task 1 Test 2: worker exception -> status=FAILED nel result list, pool continua."""
    baseline_path = tmp_path / "baseline.yaml"
    baseline_path.write_text(
        "equity_initial_eur: 10000\nslippage_seed: 42\n"
        "timeout_bars: {M15: 96, M30: 96, H1: 120}\n"
        "warm_up_min_bars: 200\nmax_workers: 2\nparquet_compression: snappy\n"
        "force_rerun: false\nprogress_bar: false\n"
        f'training_data_dir: "{tmp_path.as_posix()}"\nreport_dir: "{tmp_path.as_posix()}"\n'
        f'equity_curves_dir: "{tmp_path.as_posix()}"\n',
        encoding="utf-8",
    )
    (tmp_path / "costs.yaml").write_text("EURUSD: {}\n", encoding="utf-8")
    (tmp_path / "strategy.yaml").write_text("x: 1\n", encoding="utf-8")

    def flaky_worker(sym, tf, *args, **kwargs):
        if sym == "EURUSD" and tf == "M15":
            raise RuntimeError("synthetic worker failure")
        return [{"run_id": f"r_{sym}_{tf}_{p}", "symbol": sym, "timeframe": tf,
                 "profile": p, "status": "OK", "metrics": None,
                 "n_trades": 0, "n_drafts": 0, "equity_path": ""}
                for p in ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")]
    monkeypatch.setattr("backtest.baseline.runner.run_slice_3profiles", flaky_worker)
    monkeypatch.setattr("backtest.baseline.runner.enable_sqlite_wal", lambda p: None)
    monkeypatch.setattr("backtest.baseline.runner.finalize_parquet_shards", lambda p: None)
    # ThreadPoolExecutor in-process — mock locali non pickleable da spawn.
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(
        "backtest.baseline.runner._make_pool_executor",
        lambda mw, ctx: ThreadPoolExecutor(max_workers=mw),
    )

    from backtest.baseline.runner import run_baseline
    results = run_baseline(
        baseline_yaml=baseline_path,
        costs_yaml=tmp_path / "costs.yaml",
        strategy_yaml=tmp_path / "strategy.yaml",
        ledger_db=tmp_path / "trades.db",
    )
    # 27 totali, 3 di EURUSD/M15 sono FAILED, altri 24 OK
    assert len(results) == 27
    failed = [r for r in results if r.get("status") == "FAILED"]
    ok = [r for r in results if r.get("status") == "OK"]
    assert len(failed) == 3, f"atteso 3 FAILED (1 slice × 3 profile), got {len(failed)}"
    assert len(ok) == 24, f"atteso 24 OK (8 slice × 3 profile), got {len(ok)}"
    assert all(r["symbol"] == "EURUSD" and r["timeframe"] == "M15" for r in failed)


# ── Plan 05-09 — wrapper + regime_cfg + only-runs (FIX 1/2/6 + FIX A/B/E iter 3) ──


def test_regime_cfg_resolved_per_symbol() -> None:
    """FIX 1 Plan 05-09 iter 1: load_regime_config invocato con symbol.

    SINGOLA definizione (FIX E iter 3 — Task 2 NON definisce un test
    omonimo; questo e' l'unico).

    Verifica che la signature reale (symbol, yaml_path) sia rispettata
    dal nuovo codice slice_worker.
    """
    import inspect
    from indicators.volatility import load_regime_config

    sig = inspect.signature(load_regime_config)
    params = list(sig.parameters.keys())
    assert params == ["symbol", "yaml_path"], (
        f"load_regime_config signature inattesa: {params}"
    )

    # Verifica che la firma e' invocabile con i 2 args attesi
    # (test di compatibilita' staticamente verificato).
    cfg = load_regime_config("EURUSD", "data/configs/regime.yaml")
    assert isinstance(cfg, dict)
    assert "window" in cfg


def test_smoke_05_09_wrapper_runs(tmp_path) -> None:
    """Plan 05-09 D-09-D + FIX 2 + FIX B iter 3: scripts/run_baseline_05_09.py --smoke completa in <240s.

    Smoke con range allargato (3 mesi) + csv_path via _csv_path_for() +
    tolerant validation:
      - exit 0 anche se 0 trade (raro caso edge — smoke-tolerant FIX 2B)
      - exit 0 con schema check completo se >=1 trade (caso atteso
        per 3 mesi window MODERATE/AGGRESSIVE)
    """
    import subprocess
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent.parent
    script = ROOT / "scripts/run_baseline_05_09.py"
    assert script.exists(), f"script mancante: {script}"

    # Skip se CSV non disponibile (CI environment).
    # FIX B iter 3: path canonical via convenzione _csv_path_for
    # (data/historical/{SYMBOL}/{TF}.csv).
    csv_path = ROOT / "data" / "historical" / "EURUSD" / "M15.csv"
    if not csv_path.exists():
        pytest.skip(f"CSV non disponibile: {csv_path}")

    # Deviation Rule 1 (auto-fix, env gate): CLAUDE.md vincola lo stack a
    # Python 3.12 64-bit Windows + MetaTrader5. Su Linux/codespace MT5 manca
    # e l'import indiretto di backtest.engine -> risk_engine -> mt5_client
    # fa fallire l'import all'avvio dello smoke wrapper. NB: tests/conftest.py
    # stubba MetaTrader5 in sys.modules per i test in-process; il subprocess
    # Python invece non vede lo stub. Probiamo l'import via subprocess "dry"
    # PRIMA di lanciare lo smoke, e skip se manca (l'esecuzione effettiva
    # avviene sul PC secondario Windows in STEP 3 RESUME-PLAN.md).
    probe = subprocess.run(
        [sys.executable, "-c", "import MetaTrader5"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if probe.returncode != 0:
        pytest.skip(
            "MetaTrader5 non installato nel Python di sistema (env Linux/codespace) — "
            "smoke gira sul PC secondario Windows con MT5 demo TenTrade"
        )

    result = subprocess.run(
        [sys.executable, str(script), "--smoke"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=240,  # smoke target <180s; margine 60s OS overhead
    )
    assert result.returncode == 0, (
        f"smoke exit={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "SMOKE OK" in result.stdout, (
        f"manca marker 'SMOKE OK' in stdout:\n{result.stdout}"
    )


def test_only_runs_pre_delete_and_relaunch(tmp_path, monkeypatch) -> None:
    """FIX 6 + FIX A iter 3: --only-runs implementato via riuso _force_clear_run.

    Test scenario:
      1. Crea tmp SQLite con schema REALE Phase 5: `backtest_runs` +
         `backtest_trades` (matcha _DDL_BACKTEST_TRADES di
         backtest/ledger.py:56-78). NO `trades_log` (quello e' live
         trader, schema senza run_id — verificato in FIX A iter 3).
      2. Seed: 1 riga in `backtest_runs(run_id='abc', status='done')` +
         1 riga in `backtest_trades(run_id='abc', ...)`.
      3. Invoca _run_full(args=Namespace(only_runs='abc', force=False, ...))
         con run_baseline monkeypatched (no-op che ritorna []).
      4. Verifica:
         - PRE-run: entrambe le tabelle hanno 1 riga per run_id='abc'
         - POST-pre-delete (eseguito da _only_runs_pre_delete che
           riusa slice_worker._force_clear_run): ENTRAMBE 0 righe
         - run_baseline chiamato esattamente 1 volta con force=False
    """
    import sqlite3
    import sys
    import types
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))

    # Setup tmp db con schema REALE (FIX A iter 3 — NO trades_log fittizio)
    tmp_db = tmp_path / "trades.db"
    with sqlite3.connect(tmp_db) as conn:
        # Schema reale Phase 5 (subset minimo per il test, matcha DDL).
        # backtest/ledger.py:19-79 e' la fonte canonica.
        conn.execute(
            "CREATE TABLE backtest_runs ("
            "run_id TEXT PRIMARY KEY, "
            "symbol TEXT NOT NULL DEFAULT 'EURUSD', "
            "timeframe TEXT NOT NULL DEFAULT 'M15', "
            "date_start TEXT NOT NULL DEFAULT '2020-01-01', "
            "date_end TEXT NOT NULL DEFAULT '2020-12-31', "
            "started_at TEXT NOT NULL DEFAULT 'now', "
            "status TEXT NOT NULL DEFAULT 'running'"
            ")"
        )
        conn.execute(
            "CREATE TABLE backtest_trades ("
            "trade_id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "run_id TEXT NOT NULL, "
            "entry_time TEXT NOT NULL DEFAULT '2020-01-01', "
            "exit_time TEXT NOT NULL DEFAULT '2020-01-02', "
            "symbol TEXT NOT NULL DEFAULT 'EURUSD', "
            "timeframe TEXT NOT NULL DEFAULT 'M15', "
            "direction TEXT NOT NULL DEFAULT 'BUY', "
            "entry_price REAL NOT NULL DEFAULT 1.0, "
            "exit_price REAL NOT NULL DEFAULT 1.0, "
            "lot_size REAL NOT NULL DEFAULT 0.01"
            ")"
        )
        conn.execute(
            "INSERT INTO backtest_runs (run_id, status) VALUES ('abc', 'done')"
        )
        conn.execute(
            "INSERT INTO backtest_trades (run_id) VALUES ('abc')"
        )
        conn.commit()

    # Sanity check pre-run: entrambe le tabelle hanno la riga
    with sqlite3.connect(tmp_db) as conn:
        n_runs = conn.execute(
            "SELECT COUNT(*) FROM backtest_runs WHERE run_id='abc'"
        ).fetchone()[0]
        n_trades = conn.execute(
            "SELECT COUNT(*) FROM backtest_trades WHERE run_id='abc'"
        ).fetchone()[0]
        assert n_runs == 1 and n_trades == 1, (
            f"seed fallito: runs={n_runs}, trades={n_trades}"
        )

    # Monkeypatch run_baseline (no-op tracker)
    run_baseline_calls: list[bool] = []

    def _fake_run_baseline(force=False):
        run_baseline_calls.append(force)
        return []

    # Fake ROOT con tmp_db come logs/trades.db
    tmp_root = tmp_path / "fake_root"
    (tmp_root / "logs").mkdir(parents=True)
    (tmp_root / "data" / "configs").mkdir(parents=True)
    (tmp_root / "data" / "training" / "baseline_decisions").mkdir(parents=True)
    # Copy tmp_db -> tmp_root/logs/trades.db (preserva schema reale)
    (tmp_root / "logs" / "trades.db").write_bytes(tmp_db.read_bytes())

    fake_runner = types.SimpleNamespace(
        run_baseline=_fake_run_baseline,
        load_baseline_config=lambda *a, **k: types.SimpleNamespace(
            training_data_dir=str(tmp_root / "data/training"),
        ),
    )
    monkeypatch.setitem(
        sys.modules, "backtest.baseline.runner", fake_runner
    )

    # Import _run_full + stub validazione parquet
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "rb05", ROOT / "scripts/run_baseline_05_09.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    monkeypatch.setattr(m, "_validate_parquet_schema", lambda *a, **k: (True, "stub OK"))

    args = types.SimpleNamespace(
        only_runs="abc",
        force=False,
        max_wall_clock=14400,
        no_time_gate=False,
    )
    exit_code = m._run_full(args, tmp_root)

    # Verifica post-run: entrambe le tabelle ripulite (FIX A iter 3)
    with sqlite3.connect(tmp_root / "logs/trades.db") as conn:
        n_runs_after = conn.execute(
            "SELECT COUNT(*) FROM backtest_runs WHERE run_id='abc'"
        ).fetchone()[0]
        n_trades_after = conn.execute(
            "SELECT COUNT(*) FROM backtest_trades WHERE run_id='abc'"
        ).fetchone()[0]
    assert n_runs_after == 0, (
        f"FIX A iter 3 violato: riga backtest_runs 'abc' NON eliminata "
        f"(rimaste {n_runs_after})"
    )
    assert n_trades_after == 0, (
        f"FIX A iter 3 violato: riga backtest_trades 'abc' NON eliminata "
        f"(rimaste {n_trades_after}) — _force_clear_run pattern violato"
    )
    assert run_baseline_calls == [False], (
        f"run_baseline call inattesi: {run_baseline_calls}"
    )
    assert exit_code == 0
