"""Per-symbol transaction cost model (BACK-03, D-05)."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class CostModel:
    spread_pips: float
    slippage_pips: float
    commission_pips_round_trip: float
    pip_size: float
    pip_value_usd: float

    @property
    def total_cost_pips(self) -> float:
        return self.spread_pips + self.slippage_pips + self.commission_pips_round_trip

    def cost_usd(self, lots: float) -> float:
        """Total round-trip fill cost in USD (open + close, all components)."""
        return lots * self.total_cost_pips * self.pip_value_usd


def _pip_params(symbol: str, price: float) -> tuple[float, float]:
    """Return (pip_size, pip_value_per_standard_lot_in_usd).

    EUR/USD, GBP/USD: pip_size=0.0001, value=10 USD per pip per lot.
    USD/JPY: pip_size=0.01, value = 100_000 * 0.01 / price USD per pip per lot.
    """
    if "JPY" in symbol:
        pip_size = 0.01
        if price <= 0:
            raise ValueError(f"price must be > 0 for JPY pair, got {price}")
        pip_value = 1_000.0 / price   # 100_000 * 0.01 / price
    else:
        pip_size = 0.0001
        pip_value = 10.0              # 100_000 * 0.0001 = 10 USD
    return pip_size, pip_value


def load_cost_model(symbol: str, entry_price: float, yaml_path: Path) -> CostModel:
    """Load per-symbol cost params from costs.yaml (D-05)."""
    with open(yaml_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    sym_cfg = cfg.get(symbol)
    if sym_cfg is None:
        sym_cfg = cfg.get("default")
    if sym_cfg is None:
        raise KeyError(f"no cost config for symbol {symbol!r} in {yaml_path}")

    pip_size, pip_value = _pip_params(symbol, entry_price)
    return CostModel(
        spread_pips=float(sym_cfg["spread_pips"]),
        slippage_pips=float(sym_cfg["slippage_pips"]),
        commission_pips_round_trip=float(sym_cfg["commission_pips_round_trip"]),
        pip_size=pip_size,
        pip_value_usd=pip_value,
    )
