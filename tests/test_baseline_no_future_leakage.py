"""Tests for no future leakage invariants (D-21, D-22).

Wave 0 stub: scaffolding test-first. Sblocco al Plan 05-05/05-06.
BLOCKER 4 fix: il primo test verifica l'invariante REAL (compute_all_extended con
prefix slice == compute_all_extended full slice indexed) anziché un sentinel artificiale.
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(reason="awaits Phase 2 D-04 ExtendedIndicators API + Plan 05-05 reactivation")
def test_indicator_full_slice_equals_recompute(synthetic_bars) -> None:
    """D-21: invariante REAL no-future-leakage.

    compute_all_extended(bars[:i+1]).atr[-1] == compute_all_extended(bars).atr[i] per ogni i ≥ warm_up.
    BLOCKER 4 user-locked: indicatore deve essere causale → recompute prefix == slice full ad index i.
    """
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-06 implementa engine bar-close + ledger row")
def test_decision_dataset_temporal_ordering() -> None:
    """D-21 row invariant: ogni riga di baseline_decisions.parquet ha decision_ts ≤ entry_ts < exit_ts."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-05 implementa BacktestBroker entry semantics")
def test_entry_at_next_bar_open(synthetic_bars) -> None:
    """D-22: entry_price == next_bar.open ± slippage (no decision-bar close).

    BacktestBroker semantica: decision_ts = bar_close, entry_ts = next_bar.open.
    """
    raise NotImplementedError
