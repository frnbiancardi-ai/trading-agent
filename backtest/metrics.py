"""Backtest metrics (BACK-06).

Pure metrics module: ``compute_metrics(trades, timeframe)`` over a list of
closed-trade dicts returns a :class:`BacktestMetrics` dataclass.

Implements RESEARCH §Pattern 6 verbatim. Hand-verified by the 5-trade
fixture in :mod:`tests.test_backtest_metrics` (success criterion 5).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Annualization factor by timeframe (bars/year, 252 trading days).
# H1 = 24*252 = 6048; M30 = 24*2*252 = 12096; M15 = 24*4*252 = 24192.
BARS_PER_YEAR: dict[str, int] = {
    "H1": 24 * 252,
    "M30": 24 * 2 * 252,
    "M15": 24 * 4 * 252,
}


@dataclass
class BacktestMetrics:
    """Aggregate stats over a closed-trade ledger."""

    sharpe: float
    sortino: float
    max_drawdown_pct: float
    # Phase 5 D-18: lunghezza massima della run "underwater" (equity < running peak)
    # misurata in BAR UNITS. Caller (report_writer) converte in giorni via
    # bars_per_day del timeframe (M15→0.0104, M30→0.0208, H1→0.0416).
    longest_dd_days: float
    hit_rate: float
    expectancy_usd: float
    profit_factor: float
    avg_r: float
    total_trades: int
    total_pnl_usd: float


def _empty_metrics() -> BacktestMetrics:
    """Zero/inf-safe metrics for an empty ledger — no ZeroDivisionError."""
    return BacktestMetrics(
        sharpe=0.0,
        sortino=0.0,
        max_drawdown_pct=0.0,
        longest_dd_days=0.0,
        hit_rate=0.0,
        expectancy_usd=0.0,
        profit_factor=0.0,
        avg_r=0.0,
        total_trades=0,
        total_pnl_usd=0.0,
    )


def _longest_underwater_run(equity_curve: list[float]) -> int:
    """Conta la lunghezza massima di run consecutivo dove equity[t] < running_peak.

    Phase 5 D-18: l'equity_curve passato è la sequenza dei livelli post-trade
    (cumulativa). Un sample è "underwater" se è stretto al di sotto del peak
    corrente. Il run termina quando l'equity supera il peak (nuovo high).
    Restituisce il run più lungo in BAR UNITS (qui 1 unit = 1 trade chiuso;
    il caller può rimappare a bar di mercato moltiplicando per bars/trade
    medio o per bars-per-day del timeframe).
    """
    if not equity_curve:
        return 0
    peak = equity_curve[0]
    current_run = 0
    max_run = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
            current_run = 0
        else:
            # Sample = peak conta come "underwater run length 1" — coerente
            # con la convenzione "non-strict": dopo un peak, ogni sample non
            # nuovo-high estende la run.
            current_run += 1
            if current_run > max_run:
                max_run = current_run
    return max_run


def _std(values: list[float], mean: float) -> float:
    """Population standard deviation; 0.0 on n<2 (single-trade guard)."""
    if len(values) < 2:
        return 0.0
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(var)


def compute_metrics(trades: list[dict], timeframe: str = "H1") -> BacktestMetrics:
    """Compute aggregate metrics from a list of closed-trade dicts.

    Each trade dict must contain ``pnl_usd``; ``risk_usd`` is used for
    R-multiple. If ``risk_usd`` is missing or 0, falls back to 1.0.

    Edge cases:
        - Empty ledger → all-zero :class:`BacktestMetrics` (no exception).
        - All winners → ``profit_factor = float('inf')`` (gross_loss == 0).
        - Single trade or zero std → ``sharpe = sortino = 0.0``.
    """
    if not trades:
        return _empty_metrics()

    n = len(trades)
    pnl = [float(t["pnl_usd"]) for t in trades]

    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]

    total_pnl = sum(pnl)
    hit_rate = len(wins) / n
    expectancy = total_pnl / n

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss == 0:
        profit_factor = float("inf") if gross_win > 0 else 0.0
    else:
        profit_factor = gross_win / gross_loss

    # R-multiples: pnl / risk; risk falls back to 1.0 if missing/zero.
    r_multiples = [
        float(t["pnl_usd"]) / (float(t.get("risk_usd") or 0.0) or 1.0)
        for t in trades
    ]
    mean_r = sum(r_multiples) / n
    std_r = _std(r_multiples, mean_r)
    ann = math.sqrt(BARS_PER_YEAR.get(timeframe, BARS_PER_YEAR["H1"]))
    sharpe = (mean_r / std_r) * ann if std_r > 0 else 0.0

    downside = [r for r in r_multiples if r < 0]
    if downside:
        down_mean = sum(downside) / len(downside)
        down_std = _std(downside, down_mean) if len(downside) >= 2 else 0.0
        sortino = (mean_r / down_std) * ann if down_std > 0 else 0.0
    else:
        sortino = 0.0

    # Max drawdown on cumulative-PnL equity curve, running peak subtraction.
    # Costruisco la curva esplicita per riusarla in _longest_underwater_run.
    equity_curve_values: list[float] = []
    equity = 0.0
    peak = 0.0
    max_dd_pct = 0.0
    for p in pnl:
        equity += p
        equity_curve_values.append(equity)
        if equity > peak:
            peak = equity
        if peak > 0:
            dd_pct = (peak - equity) / peak * 100.0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

    # Phase 5 D-18: longest underwater run sulla curva equity cumulativa.
    # NB: il campo si chiama "_days" ma qui restituiamo BAR UNITS (=trade
    # chiusi). report_writer Phase 5 (Plan 05-06) applica la conversione
    # bar→days via bars_per_day del timeframe.
    longest_dd_bars = _longest_underwater_run(equity_curve_values)
    longest_dd_days_value = float(longest_dd_bars)

    return BacktestMetrics(
        sharpe=round(sharpe, 4),
        sortino=round(sortino, 4),
        max_drawdown_pct=round(max_dd_pct, 4),
        longest_dd_days=longest_dd_days_value,
        hit_rate=round(hit_rate, 4),
        expectancy_usd=round(expectancy, 2),
        profit_factor=profit_factor if math.isinf(profit_factor) else round(profit_factor, 4),
        avg_r=round(mean_r, 4),
        total_trades=n,
        total_pnl_usd=round(total_pnl, 2),
    )
