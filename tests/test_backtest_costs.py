"""Tests for backtest.costs (BACK-03, success criterion 3)."""
from __future__ import annotations
from pathlib import Path
import pytest

from backtest.costs import CostModel, load_cost_model, _pip_params


def test_eurusd_1pip_1lot() -> None:
    """SC-3: 1-pip spread on 1-lot EUR/USD = exactly $10.00."""
    pip_size, pip_value = _pip_params("EURUSD", 1.10000)
    model = CostModel(
        spread_pips=1.0,
        slippage_pips=0.0,
        commission_pips_round_trip=0.0,
        pip_size=pip_size,
        pip_value_usd=pip_value,
    )
    cost = model.cost_usd(lots=1.0)
    assert abs(cost - 10.0) < 1e-9, f"expected $10.00, got ${cost:.6f}"


def test_usdjpy_pip_value() -> None:
    """USD/JPY 1 pip = 1000 JPY / price; at 150 ≈ $6.667."""
    pip_size, pip_value = _pip_params("USDJPY", 150.0)
    assert pip_size == 0.01
    assert abs(pip_value - 1000.0 / 150.0) < 1e-9


def test_yaml_load(costs_yaml_path: Path) -> None:
    model = load_cost_model("EURUSD", 1.10000, costs_yaml_path)
    assert model.spread_pips == 0.5
    assert model.slippage_pips == 0.3
    assert model.commission_pips_round_trip == 0.5
    assert abs(model.total_cost_pips - 1.3) < 1e-9
    # 1.3 pips * $10/pip * 1 lot = $13
    assert abs(model.cost_usd(1.0) - 13.0) < 1e-9


def test_yaml_unknown_symbol_raises(costs_yaml_path: Path) -> None:
    with pytest.raises(KeyError):
        load_cost_model("XAUUSD", 2000.0, costs_yaml_path)


def test_total_cost_pips_property() -> None:
    m = CostModel(0.5, 0.3, 0.5, 0.0001, 10.0)
    assert m.total_cost_pips == 1.3
