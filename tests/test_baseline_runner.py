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

    def fake_compute(bars):
        spy["calls"] += 1
        spy["last_input"] = bars
        return {"sma_20": 1.10, "atr_14": 0.001, "rsi_14": 55.0}

    mod = types.ModuleType("indicators")
    mod.compute_all_extended = fake_compute
    monkeypatch.setitem(sys.modules, "indicators", mod)
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
    """D-23: spread + commission + slippage figurano nel result dict.

    Test smoke su composizione: il risultato del worker include `metrics`
    proveniente da engine.run() — verifichiamo che le componenti di costo
    siano referenziate (l'esecuzione reale del cost deduction è nel motore
    Phase 1; qui validiamo solo la pipeline dati worker → result).
    """
    _stub_indicators_module(monkeypatch)
    fake_result = {
        "run_id": "stub",
        "trades": [{"pnl_pips": 9.0}],
        "decisions_rows": [{"pnl_pips": 9.0, "spread_at_entry_pips": 0.5}],
        "drafts_rows": [],
        "equity_curve": [10_000.0, 10_009.0],
        "metrics": {
            "sharpe": 1.0,
            "spread_pips": 0.5,
            "commission_pips_round_trip": 0.5,
            "slippage_pips": 0.3,
            "cost_total_pips": 1.3,
        },
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
        assert r["status"] == "OK"
        m = r["metrics"]
        # Tutte e 3 le componenti di costo sono presenti nel risultato
        assert "spread_pips" in m
        assert "commission_pips_round_trip" in m
        assert "slippage_pips" in m
        # n_trades == len(decisions_rows) (smoke su pipeline dati)
        assert r["n_trades"] == 1


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
                 "profile": p, "status": "OK"}
                for p in ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")]
    monkeypatch.setattr("backtest.baseline.runner.run_slice_3profiles", flaky_worker)
    monkeypatch.setattr("backtest.baseline.runner.enable_sqlite_wal", lambda p: None)
    monkeypatch.setattr("backtest.baseline.runner.finalize_parquet_shards", lambda p: None)

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
