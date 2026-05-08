r"""Phase 5 preflight: contract probe Phase 1-4 dependency chain.

Esegue PRIMA dello smoke run (Plan 05-08). Fail-fast con error chiaro se uno
qualsiasi dei moduli upstream non risponde alla signature attesa.

Coperture:
  - backtest.engine.BacktestEngine: __init__ kwargs (Phase 5 additions)
  - backtest.broker.BacktestBroker: virtual_positions attr OR equivalente, force_close
  - backtest.ledger.LedgerWriter: insert_trades + record_run
  - backtest.metrics.compute_metrics + BacktestMetrics fields
  - strategy.evaluate_proposal_for_bar
  - strategy.adapters.backtest.build_ctx_backtest
  - indicators.compute_all_extended: shape probe (dict-of-lists | dataclass con slice_until)

Exit 0 = preflight verde. Exit 1 = qualcosa manca (stderr lista i punti critici).

Uso:
    .\.venv\Scripts\python.exe scripts\preflight_phase5.py
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REPORT: list[str] = []
FAILED: list[str] = []


def _ok(msg: str) -> None:
    REPORT.append(f"  OK    {msg}")


def _fail(msg: str) -> None:
    REPORT.append(f"  FAIL  {msg}")
    FAILED.append(msg)


def _check_engine() -> None:
    try:
        from backtest.engine import BacktestEngine
    except Exception as exc:  # noqa: BLE001
        _fail(f"import backtest.engine.BacktestEngine: {exc}")
        return
    try:
        sig = inspect.signature(BacktestEngine.__init__)
        params = set(sig.parameters)
        required_phase1 = {"bars", "symbol", "timeframe", "cost_model"}
        missing = required_phase1 - params
        if missing:
            _fail(f"BacktestEngine.__init__ manca params Phase 1: {missing}")
        else:
            _ok("BacktestEngine.__init__ ha parametri base Phase 1")
        # Phase 5 additions — opzionali se Plan 05-05 non ancora landed
        phase5 = {"indicators_full", "risk_profile", "timeout_bars", "equity_initial"}
        present_p5 = phase5 & params
        if present_p5 == phase5:
            _ok("BacktestEngine.__init__ ha tutti gli additions Phase 5")
        else:
            _fail(f"BacktestEngine.__init__ Phase 5 additions mancanti: {phase5 - params}")
    except Exception as exc:  # noqa: BLE001
        _fail(f"BacktestEngine.__init__ signature inspect: {exc}")


def _check_broker() -> None:
    try:
        from backtest.broker import BacktestBroker
    except Exception as exc:  # noqa: BLE001
        _fail(f"import backtest.broker.BacktestBroker: {exc}")
        return
    # virtual_positions: attr OR property OR method-equivalent (Phase 1 D-04)
    has_vp = (hasattr(BacktestBroker, "virtual_positions")
              or hasattr(BacktestBroker, "open_positions")
              or hasattr(BacktestBroker, "_positions"))
    if has_vp:
        _ok("BacktestBroker espone virtual_positions/open_positions/_positions")
    else:
        _fail("BacktestBroker non espone collezione di posizioni open (virtual_positions)")
    # force_close: serve per timeout enforcement Phase 5
    if hasattr(BacktestBroker, "force_close"):
        _ok("BacktestBroker.force_close presente")
    else:
        _fail("BacktestBroker.force_close MANCA — Plan 05-05 deve aggiungere il metodo "
              "(signature: force_close(position_id, exit_price, exit_reason: str) -> ClosedTrade)")


def _check_ledger() -> None:
    try:
        from backtest.ledger import LedgerWriter, _BT_RUNS_COLUMNS  # type: ignore  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        _fail(f"import backtest.ledger.LedgerWriter / _BT_RUNS_COLUMNS: {exc}")
        return
    for col in ("slippage_seed_effective", "strategy_yaml_hash", "baseline_yaml_hash",
                "git_sha", "cost_yaml_sha256", "strategy_yaml_sha256",
                "baseline_yaml_sha256"):
        if col in _BT_RUNS_COLUMNS:
            _ok(f"_BT_RUNS_COLUMNS contiene {col}")
        else:
            _fail(f"_BT_RUNS_COLUMNS manca {col} (Phase 5 schema migration)")


def _check_metrics() -> None:
    try:
        from backtest.metrics import BacktestMetrics, compute_metrics  # noqa: F401
        from dataclasses import fields
    except Exception as exc:  # noqa: BLE001
        _fail(f"import backtest.metrics: {exc}")
        return
    names = {f.name for f in fields(BacktestMetrics)}
    for f in ("sharpe", "sortino", "max_drawdown_pct", "hit_rate",
              "expectancy_usd", "profit_factor", "avg_r", "total_pnl_usd",
              "longest_dd_days"):
        if f in names:
            _ok(f"BacktestMetrics.{f}")
        else:
            _fail(f"BacktestMetrics manca campo: {f}")


def _check_strategy() -> None:
    try:
        from strategy import evaluate_proposal_for_bar  # type: ignore
        _ok(f"strategy.evaluate_proposal_for_bar callable={callable(evaluate_proposal_for_bar)}")
    except Exception as exc:  # noqa: BLE001
        _fail(f"import strategy.evaluate_proposal_for_bar: {exc}")
    try:
        from strategy.adapters.backtest import build_ctx_backtest  # type: ignore
        _ok(f"strategy.adapters.backtest.build_ctx_backtest callable={callable(build_ctx_backtest)}")
    except Exception as exc:  # noqa: BLE001
        _fail(f"import strategy.adapters.backtest.build_ctx_backtest: {exc}")


def _check_indicators() -> None:
    try:
        from indicators import compute_all_extended  # type: ignore
    except Exception as exc:  # noqa: BLE001
        _fail(f"import indicators.compute_all_extended: {exc}")
        return
    _ok(f"indicators.compute_all_extended callable={callable(compute_all_extended)}")
    # Shape probe: chiamata con bars sintetici minimi → output deve essere dict-of-lists
    # OPPURE oggetto con .slice_until(i). Branch documentato.
    try:
        from backtest.loader import Bar  # type: ignore
        bars = [Bar(time=i*900, open=1.0, high=1.001, low=0.999, close=1.0,
                    tick_volume=10, spread=2, real_volume=0) for i in range(50)]
        out = compute_all_extended(bars)
        if hasattr(out, "slice_until"):
            _ok("compute_all_extended output ha slice_until() → engine usa branch slice_until")
        elif isinstance(out, dict):
            # Verifica almeno una chiave punta a list (dict-of-lists)
            has_list = any(isinstance(v, list) for v in out.values())
            if has_list:
                _ok("compute_all_extended output dict-of-lists → engine usa branch slicing dict")
            else:
                _fail("compute_all_extended output dict ma nessuna chiave list — "
                      "Phase 2 contract incerto, slice_worker engine adapter da rivedere")
        else:
            _fail(f"compute_all_extended output type {type(out).__name__} non riconosciuto "
                  "(atteso dict-of-lists OR oggetto con slice_until())")
    except Exception as exc:  # noqa: BLE001
        _fail(f"compute_all_extended shape probe: {exc}")


def main() -> int:
    print("=== Phase 5 Preflight Contract Probe ===")
    print(f"ROOT = {ROOT}")
    print()
    for fn in (_check_engine, _check_broker, _check_ledger, _check_metrics,
               _check_strategy, _check_indicators):
        fn()
    for line in REPORT:
        print(line)
    print()
    if FAILED:
        print(f"FAILED: {len(FAILED)} check non passati. Risolvi prima dello smoke run.",
              file=sys.stderr)
        for f in FAILED:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("SUCCESS: tutti i contract probe Phase 1-4 verdi. Wave 4 sblocca.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
