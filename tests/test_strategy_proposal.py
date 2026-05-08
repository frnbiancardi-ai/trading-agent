"""Test ProposalDraft adapter + R:R floor per profile + ATR cap (STRAT-07). Mock-free.

3 profile validati a soglia ±0.1 (CONSERVATIVE 2.5, MODERATE 1.8, AGGRESSIVE 1.3).
Field name mapping: draft.stop_loss_price → ts.stop_loss; draft.take_profit_price → ts.take_profit.
"""
from __future__ import annotations

import pytest

from strategy.proposal import (
    ProposalDraft,
    compute_levels_with_atr_cap,
    draft_to_technical_setup,
    draft_to_trade_proposal,
    rr_meets_profile_floor,
)


# --- smoke import (RED → GREEN gate) -------------------------------------


def test_smoke_import_wave1_adapters_and_helpers():
    """Tutti i 4 simboli Wave 1 + ProposalDraft importabili (smoke)."""
    assert ProposalDraft is not None
    assert draft_to_trade_proposal is not None
    assert draft_to_technical_setup is not None
    assert rr_meets_profile_floor is not None
    assert compute_levels_with_atr_cap is not None


# --- draft_to_trade_proposal ---------------------------------------------


def test_draft_to_trade_proposal_valid_ready():
    d = ProposalDraft(
        setup_type="READY",
        setup_name="A_breakout",
        direction="BUY",
        entry_price=1.10800,
        stop_loss_price=1.10700,
        take_profit_price=1.10950,
        confidence=0.72,
        reason="breakout_resistance",
    )
    from models import TradeProposal

    prop = draft_to_trade_proposal(d, "EURUSD", "M15")
    assert isinstance(prop, TradeProposal)
    assert prop.symbol == "EURUSD"
    assert prop.timeframe == "M15"
    assert prop.direction == "BUY"
    assert prop.entry_price == 1.10800
    assert prop.stop_loss_price == 1.10700
    assert prop.take_profit_price == 1.10950
    assert prop.comment == "python_strategy"
    assert prop.confidence == 0.72
    assert prop.rationale == "breakout_resistance"


def test_draft_to_trade_proposal_rejects_non_ready():
    for st in ("NONE", "FORMING"):
        d = ProposalDraft(setup_type=st, reason="weak")
        with pytest.raises(ValueError, match="setup_type=READY"):
            draft_to_trade_proposal(d, "EURUSD", "M15")


def test_draft_to_trade_proposal_rejects_missing_prices():
    # READY senza tp → deve sollevare anche se direction/entry/sl ci sono
    d = ProposalDraft(
        setup_type="READY",
        direction="BUY",
        entry_price=1.1,
        stop_loss_price=1.099,
        # take_profit_price mancante
    )
    with pytest.raises(ValueError, match="non-None"):
        draft_to_trade_proposal(d, "EURUSD", "M15")


# --- draft_to_technical_setup --------------------------------------------


def test_draft_to_technical_setup_preserves_fields():
    d = ProposalDraft(
        setup_type="READY",
        setup_name="A_breakout",
        direction="BUY",
        entry_price=1.10800,
        stop_loss_price=1.10700,
        take_profit_price=1.10950,
        confidence=0.72,
        reason="breakout",
        factors={"trend_alignment": True},
        grade="B",
        rationale_parts={"atr": "0.0010"},
    )
    from models import TechnicalSetup

    s = draft_to_technical_setup(d, "EURUSD", "M15")
    assert isinstance(s, TechnicalSetup)
    assert s.setup_type == "READY"
    assert s.direction == "BUY"
    assert s.entry_price == 1.10800
    # field name mapping: draft.stop_loss_price → ts.stop_loss
    assert s.stop_loss == 1.10700
    assert s.take_profit == 1.10950
    assert s.confidence == 0.72
    assert s.reason == "breakout"
    assert s.indicators["factors"] == {"trend_alignment": True}
    assert s.indicators["grade"] == "B"
    assert s.indicators["setup_name"] == "A_breakout"
    assert s.indicators["rationale_parts"] == {"atr": "0.0010"}


def test_draft_to_technical_setup_handles_NONE():
    d = ProposalDraft(setup_type="NONE", reason="atr_not_ready")
    from models import TechnicalSetup

    s = draft_to_technical_setup(d, "EURUSD", "M15")
    assert isinstance(s, TechnicalSetup)
    assert s.setup_type == "NONE"
    assert s.direction is None
    assert s.entry_price is None
    assert s.stop_loss is None
    assert s.take_profit is None
    assert s.reason == "atr_not_ready"


# --- rr_meets_profile_floor (3 profile + 1 SELL + 1 invalid) -------------


@pytest.mark.parametrize("rr,expected", [(2.4, False), (2.5, True), (2.6, True)])
def test_rr_floor_conservative(rr, expected):
    """CONSERVATIVE min_rr=2.5: 2.4 fail, 2.5 e 2.6 pass."""
    entry = 1.10000
    sl = 1.09900
    risk = entry - sl  # 0.00100
    tp = entry + risk * rr
    ok, rr_actual = rr_meets_profile_floor(entry, sl, tp, "BUY", "CONSERVATIVE")
    assert ok == expected, f"rr={rr} actual={rr_actual} expected={expected}"


@pytest.mark.parametrize("rr,expected", [(1.7, False), (1.8, True), (1.9, True)])
def test_rr_floor_moderate(rr, expected):
    """MODERATE min_rr=1.8: 1.7 fail, 1.8 e 1.9 pass."""
    entry = 1.10000
    sl = 1.09900
    risk = entry - sl
    tp = entry + risk * rr
    ok, _ = rr_meets_profile_floor(entry, sl, tp, "BUY", "MODERATE")
    assert ok == expected


@pytest.mark.parametrize("rr,expected", [(1.2, False), (1.3, True), (1.5, True)])
def test_rr_floor_aggressive(rr, expected):
    """AGGRESSIVE min_rr=1.3: 1.2 fail, 1.3 e 1.5 pass."""
    entry = 1.10000
    sl = 1.09900
    risk = entry - sl
    tp = entry + risk * rr
    ok, _ = rr_meets_profile_floor(entry, sl, tp, "BUY", "AGGRESSIVE")
    assert ok == expected


def test_rr_floor_sell_direction():
    # SELL: risk = sl - entry; reward = entry - tp
    entry = 1.10000
    sl = 1.10100  # SL sopra entry per SELL
    tp = 1.09800  # TP sotto entry per SELL
    # risk = 0.00100, reward = 0.00200, rr = 2.0
    ok, rr = rr_meets_profile_floor(entry, sl, tp, "SELL", "MODERATE")
    assert ok and abs(rr - 2.0) < 1e-9, f"rr={rr}"


def test_rr_floor_invalid_direction():
    with pytest.raises(ValueError, match="BUY/SELL"):
        rr_meets_profile_floor(1.1, 1.09, 1.12, "FLAT", "MODERATE")


def test_rr_floor_invalid_profile():
    with pytest.raises(ValueError, match="profile_filters"):
        rr_meets_profile_floor(1.1, 1.099, 1.103, "BUY", "BALANCED")


def test_rr_floor_returns_false_on_inverted_prices():
    # BUY ma sl > entry (incoerente) → risk negativo → (False, 0.0)
    ok, rr = rr_meets_profile_floor(1.10, 1.11, 1.12, "BUY", "MODERATE")
    assert ok is False and rr == 0.0


# --- compute_levels_with_atr_cap -----------------------------------------


def test_compute_levels_atr_cap_buy_buffer_within_cap():
    # entry=1.10000, level=1.09900, atr=0.0010
    # buffer 0.4*ATR = 0.0004 → sl = 1.09900 - 0.0004 = 1.09860
    # cap 1.5*ATR = 0.00150 → entry-cap = 1.09850
    # max(1.09860, 1.09850) = 1.09860 (buffer wins, within cap)
    entry, sl = compute_levels_with_atr_cap("BUY", 1.10000, 1.09900, 0.0010, 0.4)
    assert entry == 1.10000
    assert abs(sl - 1.09860) < 1e-9, sl


def test_compute_levels_atr_cap_buy_cap_overrides_far_buffer():
    # entry=1.10000, level molto lontano = 1.09000, atr=0.0010
    # buffer 0.4*ATR sotto = 1.08960 (troppo lontano)
    # cap entry - 1.5*ATR = 1.10000 - 0.0015 = 1.09850
    # max(1.08960, 1.09850) = 1.09850 (cap wins)
    entry, sl = compute_levels_with_atr_cap("BUY", 1.10000, 1.09000, 0.0010, 0.4)
    assert abs(sl - 1.09850) < 1e-9, f"cap should win: {sl}"


def test_compute_levels_atr_cap_sell_symmetric():
    # entry=1.10000, level=1.10100, atr=0.0010
    # buffer +0.0004 → 1.10140
    # cap entry + 1.5*ATR = 1.10150
    # min(1.10140, 1.10150) = 1.10140 (buffer wins)
    entry, sl = compute_levels_with_atr_cap("SELL", 1.10000, 1.10100, 0.0010, 0.4)
    assert entry == 1.10000
    assert abs(sl - 1.10140) < 1e-9


def test_compute_levels_atr_cap_sell_cap_overrides_far_buffer():
    # entry=1.10000, level molto lontano sopra = 1.11000, atr=0.0010
    # buffer +0.4*ATR = 1.11040
    # cap entry + 1.5*ATR = 1.10150
    # min(1.11040, 1.10150) = 1.10150 (cap wins)
    entry, sl = compute_levels_with_atr_cap("SELL", 1.10000, 1.11000, 0.0010, 0.4)
    assert abs(sl - 1.10150) < 1e-9, f"cap should win: {sl}"


def test_compute_levels_atr_cap_invalid_atr():
    with pytest.raises(ValueError, match="atr"):
        compute_levels_with_atr_cap("BUY", 1.1, 1.099, 0.0, 0.4)


def test_compute_levels_atr_cap_invalid_direction():
    with pytest.raises(ValueError, match="BUY/SELL"):
        compute_levels_with_atr_cap("FLAT", 1.1, 1.099, 0.0010, 0.4)
