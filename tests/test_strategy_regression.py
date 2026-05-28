"""Test regression replay 10 fixture pre-refactor (STRAT-09 + SC-5).

Tolleranza: 1e-5 sui prezzi, 1e-4 sulla confidence. Failure = bug del nuovo
codice O calibrazione intenzionale (in quel caso eseguire reconciliation
via plan 04-08 task 2 checkpoint).

I 10 scenari baseline sono stati catturati pre-refactor da
tests/capture_regression_baseline.py (commit 8324d5f, Wave 0). Il replay
costruisce mock MT5 da CSV identici a quelli del capture e replay-a
attraverso il NUOVO IntradayStrategy shim (post Wave 3 cutover).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "strategy_regression_baseline.json"
PRICE_TOL = 1e-5
CONFIDENCE_TOL = 1e-4


def _load_fixture():
    """Carica i 10 scenari baseline. Skip se mancante (no-op safe in Wave 0)."""
    if not FIXTURE_PATH.exists():
        pytest.skip(f"fixture mancante: {FIXTURE_PATH} — eseguire tests/capture_regression_baseline.py")
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _import_capture_helpers():
    """Importa helpers da capture_regression_baseline.py (riuso logica mock MT5)."""
    tests_dir = str(Path(__file__).resolve().parent)
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    from capture_regression_baseline import (  # noqa: E402
        _mock_mt5_from_csv,
        _capture_cfg,
        _capture_account,
    )
    return _mock_mt5_from_csv, _capture_cfg, _capture_account


# ---------------------------------------------------------------------------

def test_regression_fixture_loads():
    """Il fixture esiste, ha 10 entries, ognuna con schema atteso."""
    scenarios = _load_fixture()
    assert len(scenarios) == 10, f"atteso 10 scenari, trovati {len(scenarios)}"
    for s in scenarios:
        assert "scenario_id" in s, f"missing scenario_id in {s}"
        assert "symbol" in s, f"scenario {s.get('scenario_id')}: missing symbol"
        assert "csv" in s, f"scenario {s.get('scenario_id')}: missing csv"
        assert "bar_offset" in s, f"scenario {s.get('scenario_id')}: missing bar_offset"
        assert "output" in s, f"scenario {s.get('scenario_id')}: missing output"
        out = s["output"]
        for key in ("setup_type", "direction", "entry_price", "stop_loss",
                    "take_profit", "confidence", "reason"):
            assert key in out, f"scenario {s.get('scenario_id')}: missing output.{key}"


@pytest.mark.parametrize(
    "scenario",
    _load_fixture() if FIXTURE_PATH.exists() else [],
    ids=lambda s: f"scen_{s['scenario_id']}_{s['symbol']}",
)
def test_regression_replay_all_scenarios(scenario):
    """Replay scenario attraverso il NUOVO shim IntradayStrategy → output identico a baseline.

    Tolleranze (D-14 contract):
      - setup_type, direction: EXACT match
      - entry_price, stop_loss, take_profit: abs(new - baseline) < 1e-5
      - confidence: abs(new - baseline) < 1e-4

    Una failure su confidence (CONFIDENCE_DELTA marker) può essere drift
    intenzionale dovuto al nuovo motore 5-factor; il checkpoint plan 04-08
    task 2 valuta accept (re-baseline) o reject (fix).
    """
    from strategy import IntradayStrategy

    _mock_mt5_from_csv, _capture_cfg, _capture_account = _import_capture_helpers()

    mt5 = _mock_mt5_from_csv(scenario["csv"], scenario["symbol"], scenario["bar_offset"])
    cfg = _capture_cfg()
    strategy_obj = IntradayStrategy(cfg, mt5)
    setup = strategy_obj.analyze_symbol(scenario["symbol"], _capture_account(), sentiment=None)

    expected = scenario["output"]

    # Exact-match fields
    assert setup.setup_type == expected["setup_type"], (
        f"scenario {scenario['scenario_id']}: setup_type "
        f"baseline={expected['setup_type']} new={setup.setup_type}"
    )
    assert setup.direction == expected["direction"], (
        f"scenario {scenario['scenario_id']}: direction "
        f"baseline={expected['direction']} new={setup.direction}"
    )

    # Tolleranza prezzi (1e-5) — solo se entrambi non-None
    for fld_new, fld_base, label in [
        ("entry_price", "entry_price", "entry"),
        ("stop_loss", "stop_loss", "sl"),
        ("take_profit", "take_profit", "tp"),
    ]:
        new_v = getattr(setup, fld_new)
        base_v = expected[fld_base]
        if base_v is None:
            assert new_v is None, (
                f"scenario {scenario['scenario_id']}: {label} baseline=None new={new_v}"
            )
        else:
            assert new_v is not None and abs(new_v - base_v) < PRICE_TOL, (
                f"scenario {scenario['scenario_id']}: {label} "
                f"baseline={base_v} new={new_v} delta={(new_v or 0) - base_v}"
            )

    # Tolleranza confidence (1e-4) — failure qui può essere intenzionale (calibrazione nuova)
    delta = abs(setup.confidence - expected["confidence"])
    assert delta < CONFIDENCE_TOL, (
        f"CONFIDENCE_DELTA scenario {scenario['scenario_id']}: "
        f"baseline={expected['confidence']} new={setup.confidence} delta={delta:.6f} "
        f"— supera tolleranza {CONFIDENCE_TOL}. Eseguire plan 04-08 task 2 reconciliation checkpoint."
    )
