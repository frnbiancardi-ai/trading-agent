# Testing Patterns

**Analysis Date:** 2026-05-07

## Test Framework

**Runner:**
- `pytest` (unpinned in `requirements.txt:9`)
- Config: `pytest.ini` — sets `pythonpath = .` so tests can `import` flat modules (`from risk_engine import evaluate_trade`).

**Assertion Library:**
- Plain `assert` statements (no `unittest.TestCase`, no `pytest-assert` plugins).

**Run Commands:**
```bash
pytest                                   # Run all tests
pytest tests/test_risk.py                # Single file
pytest tests/test_phase16.py -k "drawdown"  # Match keyword
pytest -x                                # Stop on first failure
pytest --tb=short                        # Concise tracebacks
```

## Test File Organization

**Location:**
- Separate `tests/` directory at repo root (NOT co-located with source). Source modules live at repo root; tests mirror them by name.

**Naming:**
- `tests/test_<module>.py` mirrors the module under test: `risk_engine.py` ↔ `tests/test_risk.py`, `strategy.py` ↔ `tests/test_strategy.py`, `mt5_client.py` ↔ `tests/test_mt5.py`, `scheduler.py` ↔ `tests/test_scheduler.py`, `scanner.py` ↔ `tests/test_scanner.py`, `news_aggregator.py` ↔ `tests/test_news_aggregator.py`, `sentiment.py` ↔ `tests/test_sentiment.py`, `patterns.py` ↔ `tests/test_patterns.py`.
- Phase-specific aggregate suites: `tests/test_phase16.py` (771 lines), `tests/test_daily_orchestrator.py` (290 lines).

**Structure:**
```
tests/
├── test_daily_orchestrator.py  (290 lines)
├── test_mcp_tools_v2.py        (230 lines)
├── test_mt5.py                 (E2E, auto-skip when no MT5)
├── test_news_aggregator.py     (180 lines)
├── test_patterns.py             (99 lines)
├── test_pdf_to_markdown_ocr.py  (77 lines)
├── test_phase16.py             (771 lines, fase 16 H24 update)
├── test_risk.py                (158 lines)
├── test_scanner.py             (333 lines)
├── test_scheduler.py           (497 lines, fase 13)
├── test_sentiment.py           (142 lines)
├── test_strategy.py            (441 lines, fase 14)
└── test_strategy_runner.py     (166 lines)
```
Total: 13 files, ~3,439 lines of tests.

## Test Structure

**Suite Organization:**
- Flat function-style tests, no class wrappers. Visual section dividers using box-drawing characters group related tests:
```python
# ── happy path ────────────────────────────────────────────────────────────────

def test_trade_accepted(cfg, proposal, account):
    decision = evaluate_trade(proposal, account, _client(margin=100.0), cfg)
    assert decision.approved
    assert decision.size_lots >= 0.01
    assert decision.reason == "OK"


# ── kill switch ───────────────────────────────────────────────────────────────

def test_kill_switch_activates(cfg, proposal, account):
    account.balance = 9700.0
    account.starting_balance_of_day = 10000.0
    decision = evaluate_trade(proposal, account, _client(), cfg)
    assert not decision.approved
    assert "Kill switch" in decision.reason
```
(see `tests/test_risk.py:70-86`)

**Patterns:**
- Test names describe behavior in snake_case English: `test_kill_switch_activates`, `test_sl_too_tight`, `test_margin_downsize_recovers`, `test_session_filter_outside_hours`.
- Assertions check both the boolean outcome (`assert decision.approved`) AND a substring of the Italian `reason` (`assert "Kill switch" in decision.reason`, `assert "stretto" in decision.reason`).
- Test files start with an Italian module docstring describing scope: `tests/test_phase16.py:1-12`, `tests/test_scheduler.py:1-9`.

## Mocking

**Framework:** `unittest.mock.MagicMock` and `unittest.mock.patch` (stdlib only — no `pytest-mock`).

**Patterns:**
```python
# Config mock built fresh per test via factory
def _make_cfg(**overrides):
    cfg = MagicMock()
    cfg.INTRADAY_TIMEFRAME = "M15"
    cfg.MIN_TREND_STRENGTH = 0.65
    cfg.ENABLE_NEWS_SENTIMENT = False
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg
```
(`tests/test_strategy.py:19-44`, `tests/test_phase16.py:46-89`, `tests/test_scheduler.py:53-60`)

```python
# MT5 client mock with helpers for symbol_info and margin
def _sym_info(point=0.00001, digits=5, tick_value=1.0,
              tick_size=0.00001, volume_step=0.01):
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
```
(`tests/test_risk.py:53-67`)

```python
# Side effects for sequential calls (e.g. retry / downsize loops)
client.calc_order_margin.side_effect = [95.0, 70.0]
```
(`tests/test_risk.py:118`)

```python
# Patch module-level datetime to control wall clock
fake_now = MagicMock()
fake_now.hour = 22
with patch("risk_engine.datetime") as mock_dt:
    mock_dt.now.return_value = fake_now
    decision = evaluate_trade(proposal, account, _client(), cfg)
```
(`tests/test_risk.py:138-145`)

**What to Mock:**
- `Config` → `MagicMock` with overrides (avoids reading `.env`).
- `Mt5Client` → `MagicMock` with method-level `return_value`/`side_effect`.
- External time via `patch("module.datetime")`.
- `anthropic.Anthropic` client and MCP transports in agent/MCP tests.
- HTTP/RSS in `tests/test_news_aggregator.py` (mock `feedparser.parse`).

**What NOT to Mock:**
- Pure-Python domain logic: `indicators.py`, `patterns.py`, dataclasses in `models.py`, `risk_engine.evaluate_trade` (tested with real arithmetic against mocked I/O).
- `datetime.timedelta` arithmetic, `zoneinfo.ZoneInfo`.
- `apscheduler` triggers (constructed for real but the scheduler is never `start()`ed — see `tests/test_scheduler.py:6-9`).

## Fixtures and Factories

**Test Data:**
```python
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


@pytest.fixture
def proposal():
    return TradeProposal(
        symbol="EURUSD", direction="BUY",
        entry_price=1.10000, stop_loss_price=1.09800,
        take_profit_price=1.10400, timeframe="H1",
        comment="test", confidence=0.8, rationale="test trade",
    )
```
(`tests/test_risk.py:9-50`)

**Factory helpers** (private, file-scoped, prefixed `_`):
- `_make_cfg(**overrides)` — `tests/test_strategy.py:19`, `tests/test_phase16.py:46`, `tests/test_scheduler.py:53`.
- `_account(positions=None, balance=10_000.0)` — `tests/test_phase16.py:92`.
- `_bar(close, idx, vol=100, ...)` — synthetic OHLC bar (`tests/test_strategy.py:55`).
- `_bullish_breakout_bars(n=100)` — full price series fixture (`tests/test_strategy.py:71`).
- `_sym_info(...)`, `_client(...)` — MT5 mock builders (`tests/test_risk.py:53-67`).

**Location:**
- Fixtures live inline in each test file. No `conftest.py` detected. No shared fixtures across files — each suite is self-contained.

## Coverage

**Requirements:** None enforced. No `coverage.py`/`pytest-cov` config in `requirements.txt` or `pytest.ini`.

**View Coverage:**
```bash
pip install pytest-cov
pytest --cov=. --cov-report=term-missing --cov-report=html
```

## Test Types

**Unit Tests:**
- Dominant style. Pure-Python deterministic tests over `risk_engine`, `strategy`, `scanner`, `indicators`, `patterns`, `sentiment`, `news_aggregator` with all I/O mocked.
- Each test sets up a complete-but-minimal scenario via fixtures/factories, exercises one decision path, and asserts both the outcome flag and a substring of the human-readable Italian reason.

**Integration Tests:**
- `tests/test_phase16.py` exercises the full H24 cycle: `IntradayLoopScheduler.run_one_cycle` orchestrates `StrategyEnvironment`, `IntradayStrategy`, `MultiSymbolScanner`, `HeartbeatStore`, `Mt5Client.close_position` together with mocked MT5 boundary.
- `tests/test_scheduler.py` exercises `Orchestrator` with the real `apscheduler.BlockingScheduler` (never `start()`ed) plus real `CronTrigger`/`DateTrigger` objects.
- `tests/test_daily_orchestrator.py` and `tests/test_strategy_runner.py` cover end-to-end agent loops with mocked Claude client.

**E2E Tests:**
- `tests/test_mt5.py` hits the real MT5 terminal (FP Markets demo). Auto-skipped via module-level marker when credentials are missing or the terminal is closed:
```python
pytestmark = pytest.mark.skipif(
    not os.getenv("MT5_LOGIN") or not os.getenv("MT5_PASSWORD"),
    reason="MT5 credentials non configurate, skip test ambiente reale",
)
```
(`tests/test_mt5.py:14-17`). Module-scoped `client` fixture also calls `pytest.skip(...)` if `initialize()`/`login()` fail (`tests/test_mt5.py:20-27`).

## Common Patterns

**Synthetic bar series:**
- Helper `_bar(close, idx, vol=100, hi_off=0.0003, lo_off=0.0003)` returns a `dict` matching the MT5 OHLC shape (`time`, `open`, `high`, `low`, `close`, `tick_volume`). Series builders compose these for trend / breakout / range scenarios (`tests/test_strategy.py:55-94`).

**Time control:**
- Build a `datetime` with `ZoneInfo("Europe/Rome")` for in-window assertions (`tests/test_phase16.py:43`, `tests/test_scheduler.py:39`).
- For functions that call `datetime.now()`, patch the module's bound `datetime` symbol: `with patch("risk_engine.datetime") as mock_dt: mock_dt.now.return_value = fake_now` (`tests/test_risk.py:141`).

**Error Testing:**
- Force the mocked client to raise: `client.get_symbol_info.side_effect = RuntimeError("boom")`. The function under test must convert this into a `reject(...)` outcome rather than propagating (asserted by checking the `reason` substring).

**Async Testing:**
- Not applicable. Code is synchronous (apscheduler runs jobs on its own thread; tests never start the scheduler).

**Conditional skip pattern:**
- Module-level `pytestmark = pytest.mark.skipif(...)` for environment gating (see `tests/test_mt5.py:14`).
- In-fixture `pytest.skip("reason")` when runtime preconditions fail (see `tests/test_mt5.py:25`).

---

*Testing analysis: 2026-05-07*
