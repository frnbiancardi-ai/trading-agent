"""Phase 6 Wave 2 SC#4: end-to-end round-trip run_backtest -> get_backtest_metrics.

Riferimento: 06-03-PLAN.md Task 3.

Due test:
- test_run_backtest_writes_db: submit reale + poll fino a done + verifica DB row.
- test_round_trip_metrics: stesso submit + confronto con BacktestEngine.run()
  in-process diretto (parity).

Entrambi gated da skipif su CSV presence: assenza di
data/historical/EURUSD/M15.csv -> SKIP (mai FAIL).
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest
from backtest.ledger import LedgerWriter

# Import lazy: il modulo dovrebbe esistere dopo Task 2.
pytest.importorskip("mcp_tools.handlers.backtest")
from mcp_tools.handlers.backtest import (  # noqa: E402
    handle_get_backtest_metrics,
    handle_run_backtest,
)
from mcp_tools.job_queue import JobQueue  # noqa: E402


HISTORICAL_CSV = Path("data/historical/EURUSD/M15.csv")
COSTS_YAML = Path("data/configs/costs.yaml")

# Range piccolo: 1 settimana ~672 barre M15 -> backtest in <30s su laptop dev.
_DATE_START = "2024-01-01T00:00:00Z"
_DATE_END = "2024-01-08T00:00:00Z"


def _poll_until_terminal(handle_get, run_id, q, cfg, *, timeout_s: int = 60):
    """Polla get_backtest_metrics finché lo status diventa terminale.

    Ritorna l'ultimo payload (done/failed/cancelled) o None su timeout.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        m = handle_get({"run_id": run_id}, q, cfg)
        if m.get("status") in ("done", "failed", "cancelled"):
            return m
        time.sleep(0.5)
    return None


@pytest.mark.skipif(
    not HISTORICAL_CSV.exists(),
    reason="data/historical/EURUSD/M15.csv non presente: smoke skippato",
)
@pytest.mark.skipif(
    not COSTS_YAML.exists(),
    reason="data/configs/costs.yaml non presente: smoke skippato",
)
def test_run_backtest_writes_db(tmp_path):
    """SC#4 parte A: submit reale -> backtest_runs.status='done' in <60s."""
    db = tmp_path / "trades.db"
    LedgerWriter(db)
    q = JobQueue(max_workers=1, db_path=str(db))
    cfg = type("Cfg", (), {})()
    args = {
        "symbol": "EURUSD",
        "timeframe": "M15",
        "date_start": _DATE_START,
        "date_end": _DATE_END,
        "profile": "MODERATE",
    }
    out = handle_run_backtest(
        args, q, cfg, str(db), str(COSTS_YAML),
    )
    assert out["ok"] is True, out
    run_id = out["run_id"]

    final = _poll_until_terminal(
        handle_get_backtest_metrics, run_id, q, cfg, timeout_s=120,
    )
    assert final is not None, "timeout 120s — worker non finito"
    assert final["status"] == "done", f"unexpected payload: {final}"

    with sqlite3.connect(str(db)) as c:
        row = c.execute(
            "SELECT run_id, status FROM backtest_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
    assert row is not None
    assert row[1] == "done"


@pytest.mark.skipif(
    not HISTORICAL_CSV.exists(),
    reason="data/historical/EURUSD/M15.csv non presente: smoke skippato",
)
@pytest.mark.skipif(
    not COSTS_YAML.exists(),
    reason="data/configs/costs.yaml non presente: smoke skippato",
)
def test_round_trip_metrics(tmp_path):
    """SC#4 parte B: confronto metrics handler vs BacktestEngine in-process.

    Le due esecuzioni devono produrre lo stesso trade_count (la metrics dict
    riflette esattamente cosa la BacktestEngine ha generato; Sharpe può variare
    di poco per via di arrotondamenti durante il dataclasses.asdict + persistenza
    SQLite, tolleranza 0.01).
    """
    db = tmp_path / "trades.db"
    LedgerWriter(db)
    q = JobQueue(max_workers=1, db_path=str(db))
    cfg = type("Cfg", (), {})()
    args = {
        "symbol": "EURUSD",
        "timeframe": "M15",
        "date_start": _DATE_START,
        "date_end": _DATE_END,
        "profile": "MODERATE",
    }
    out = handle_run_backtest(
        args, q, cfg, str(db), str(COSTS_YAML),
    )
    assert out["ok"] is True
    rid = out["run_id"]

    final = _poll_until_terminal(
        handle_get_backtest_metrics, rid, q, cfg, timeout_s=120,
    )
    assert final is not None and final["status"] == "done", final
    handler_metrics = final["metrics"]
    assert "sharpe" in handler_metrics

    # ── Equivalente in-process ──────────────────────────────────────────────
    from datetime import datetime, timezone
    from config import Config
    from backtest.costs import load_cost_model
    from backtest.engine import BacktestEngine
    from backtest.loader import load_bars
    from backtest.metrics import compute_metrics

    ds = datetime.fromisoformat(_DATE_START.replace("Z", "+00:00"))
    de = datetime.fromisoformat(_DATE_END.replace("Z", "+00:00"))
    bars = load_bars(HISTORICAL_CSV, "EURUSD", "M15", ds, de)
    assert bars, "load_bars vuoto: range/CSV inconsistenti"
    cost_model = load_cost_model("EURUSD", bars[0].close, COSTS_YAML)
    direct_cfg = Config()
    direct_cfg.RISK_MODE = "MODERATE"
    eng = BacktestEngine(
        bars=bars,
        symbol="EURUSD",
        timeframe="M15",
        cost_model=cost_model,
        cfg=direct_cfg,
    )
    result = eng.run()
    direct_metrics = compute_metrics(result["trades"], timeframe="M15")

    # Trade count deve essere identico (worker e in-process eseguono lo stesso
    # set di bar con la stessa strategia).
    assert direct_metrics.total_trades == handler_metrics.get("trade_count"), (
        f"direct={direct_metrics.total_trades} vs handler={handler_metrics.get('trade_count')}"
    )

    # Sharpe può differire per via di rounding interni (BacktestMetrics arrotonda
    # a 4 decimali); tolleranza 0.01 più che sufficiente.
    if (
        direct_metrics.sharpe is not None
        and handler_metrics.get("sharpe") is not None
    ):
        assert abs(direct_metrics.sharpe - handler_metrics["sharpe"]) < 0.01
