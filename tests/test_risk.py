from unittest.mock import MagicMock, patch

import pytest

from models import AccountState, TradeProposal
from risk_engine import evaluate_trade


@pytest.fixture
def cfg():
    c = MagicMock()
    c.RISK_MODE = "CONSERVATIVE"
    c.MAX_DAILY_DRAWDOWN_PERCENT = 2.0
    c.USE_SESSION_FILTER = False
    c.SESSION_START_HOUR = 8
    c.SESSION_END_HOUR = 20
    c.MIN_SL_PIPS = 8
    c.MAX_SL_PIPS = 80
    c.RISK_AMOUNT_MODE = "PERCENT"
    c.RISK_PER_TRADE_PERCENT = 1.0
    c.RISK_PER_TRADE_AMOUNT = 100.0
    c.MAX_LOTS_PER_TRADE = 0.0  # usa default profilo CONSERVATIVE = 0.3
    return c


@pytest.fixture
def proposal():
    return TradeProposal(
        symbol="EURUSD",
        direction="BUY",
        entry_price=1.10000,
        stop_loss_price=1.09800,   # 20 pips
        take_profit_price=1.10400,
        timeframe="H1",
        comment="test",
        confidence=0.8,
        rationale="test trade",
    )


@pytest.fixture
def account():
    return AccountState(
        balance=10000.0,
        equity=10000.0,
        free_margin=9000.0,
        open_positions=[],
        today_realized_pnl=0.0,
        starting_balance_of_day=10000.0,
    )


def _sym_info(point=0.00001, digits=5, tick_value=1.0, tick_size=0.00001, volume_step=0.01):
    si = MagicMock()
    si.point = point
    si.digits = digits
    si.trade_tick_value = tick_value
    si.trade_tick_size = tick_size
    si.volume_step = volume_step
    return si


def _client(sym_info=None, margin=100.0):
    c = MagicMock()
    c.get_symbol_info.return_value = sym_info or _sym_info()
    c.calc_order_margin.return_value = margin
    return c


# ── happy path ────────────────────────────────────────────────────────────────

def test_trade_accepted(cfg, proposal, account):
    decision = evaluate_trade(proposal, account, _client(margin=100.0), cfg)
    assert decision.approved
    assert decision.size_lots >= 0.01
    assert decision.reason == "OK"


# ── kill switch ───────────────────────────────────────────────────────────────

def test_kill_switch_activates(cfg, proposal, account):
    account.balance = 9700.0                # -3% dal giorno, limite è 2%
    account.starting_balance_of_day = 10000.0
    decision = evaluate_trade(proposal, account, _client(), cfg)
    assert not decision.approved
    assert "Kill switch" in decision.reason


def test_kill_switch_not_triggered(cfg, proposal, account):
    account.balance = 9810.0               # -1.9%, sotto il limite 2%
    account.starting_balance_of_day = 10000.0
    decision = evaluate_trade(proposal, account, _client(margin=50.0), cfg)
    assert decision.approved


# ── SL bounds ─────────────────────────────────────────────────────────────────

def test_sl_too_tight(cfg, proposal, account):
    proposal.stop_loss_price = 1.09970     # 3 pip < MIN_SL_PIPS=8
    decision = evaluate_trade(proposal, account, _client(), cfg)
    assert not decision.approved
    assert "stretto" in decision.reason


def test_sl_too_wide(cfg, proposal, account):
    proposal.stop_loss_price = 1.09000     # 100 pip > MAX_SL_PIPS=80
    decision = evaluate_trade(proposal, account, _client(), cfg)
    assert not decision.approved
    assert "largo" in decision.reason


# ── margin downsize ───────────────────────────────────────────────────────────

def test_margin_downsize_recovers(cfg, proposal, account):
    account.free_margin = 100.0
    # Prima chiamata margine alto (95 > 90), seconda bassa (70 ≤ 90) → ok
    client = _client()
    client.calc_order_margin.side_effect = [95.0, 70.0]
    decision = evaluate_trade(proposal, account, client, cfg)
    assert decision.approved


def test_margin_downsize_to_minimum_rejects(cfg, proposal, account):
    account.free_margin = 1.0              # limite = 0.9; margine sempre 999
    client = _client()
    client.calc_order_margin.return_value = 999.0
    decision = evaluate_trade(proposal, account, client, cfg)
    assert not decision.approved
    assert "Margine" in decision.reason or "size" in decision.reason.lower()


# ── session filter ────────────────────────────────────────────────────────────

def test_session_filter_outside_hours(cfg, proposal, account):
    cfg.USE_SESSION_FILTER = True
    cfg.SESSION_START_HOUR = 8
    cfg.SESSION_END_HOUR = 20
    fake_now = MagicMock()
    fake_now.hour = 22
    fake_now.minute = 30
    with patch("risk_engine.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        decision = evaluate_trade(proposal, account, _client(), cfg)
    assert not decision.approved
    assert "sessione" in decision.reason.lower() or "Fuori" in decision.reason


def test_session_filter_inside_hours(cfg, proposal, account):
    cfg.USE_SESSION_FILTER = True
    cfg.SESSION_START_HOUR = 8
    cfg.SESSION_END_HOUR = 20
    fake_now = MagicMock()
    fake_now.hour = 14
    fake_now.minute = 0
    with patch("risk_engine.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        decision = evaluate_trade(proposal, account, _client(margin=50.0), cfg)
    assert decision.approved
