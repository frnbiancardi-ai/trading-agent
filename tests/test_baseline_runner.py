"""Tests for backtest.baseline.runner (BACK-07, D-14, D-15, D-23).

Wave 0 stub: scaffolding test-first. Tutti i test sono @pytest.mark.skip
finché Plan 05-07 non implementa il modulo target. Skip rimosso al landing.
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Wave 1: 05-07 implementa runner orchestrator")
def test_single_slice_perf_budget(synthetic_bars) -> None:
    """BACK-07: single-slice perf budget <2 min after warm-up (mocked detector).

    VALIDATION.md row "BACK-07 single-slice perf <2 min". Sblocco al Plan 05-07.
    """
    raise NotImplementedError  # rimosso quando plan target imple


@pytest.mark.skip(reason="Wave 1: 05-07 implementa runner orchestrator")
def test_idempotency_skip_and_force(tmp_db_with_wal) -> None:
    """D-14: re-run senza --force skip; con --force overwrite.

    Inserisce backtest_runs row, ri-invoca runner → assert no duplicate. Sblocco 05-07.
    """
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-07 implementa runner orchestrator")
def test_indicator_cache_reused_across_profiles(synthetic_bars, synthetic_indicators_full) -> None:
    """D-15: hybrid orchestration — `compute_all_extended` chiamato 1× per slice (3 profile).

    Mock + spy su `compute_all_extended`; run 3 profile sequenziali; assert call count == 1.
    """
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-07 implementa runner orchestrator")
def test_cost_deduction(synthetic_bars) -> None:
    """D-23: spread+commission deducted on entry, slippage entry+exit.

    Closed trade pnl_pips = raw_pnl - spread - commission_rt - 2*slippage. Sblocco 05-07.
    """
    raise NotImplementedError
