"""Test detector setup A/B/C/D puri (STRAT-01..04). Wave 2 implementa, Wave 0 stub."""
import pytest

from strategy.setups.a_breakout import detect_a_breakout  # noqa: F401
from strategy.setups.b_reversal import detect_b_reversal  # noqa: F401
from strategy.setups.c_compression import detect_c_compression  # noqa: F401
from strategy.setups.d_pullback import detect_d_pullback  # noqa: F401
from strategy.proposal import ProposalDraft  # noqa: F401


def test_detect_a_breakout_ready():
    pytest.skip("Wave 2 pending — STRAT-01")


def test_detect_a_breakout_none_no_breakout():
    pytest.skip("Wave 2 pending — STRAT-01")


def test_detect_a_breakout_forming_near_resistance():
    pytest.skip("Wave 2 pending — STRAT-01")


def test_detect_b_reversal_ready_at_support():
    pytest.skip("Wave 2 pending — STRAT-02")


def test_detect_b_reversal_counter_trend_gate():
    pytest.skip("Wave 2 pending — STRAT-02 (D-07 gate)")


def test_detect_c_compression_nr7():
    pytest.skip("Wave 2 pending — STRAT-03")


def test_detect_c_compression_squeeze():
    pytest.skip("Wave 2 pending — STRAT-03")


def test_detect_d_pullback_fib_38():
    pytest.skip("Wave 2 pending — STRAT-04")


def test_detect_d_pullback_ema20_touch():
    pytest.skip("Wave 2 pending — STRAT-04")


def test_evaluate_proposal_for_bar_multi_match_priority():
    pytest.skip("Wave 3 pending — D-06 tie-break A>C>B>D")
