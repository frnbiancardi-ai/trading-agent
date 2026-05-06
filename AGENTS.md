# Trading Agent — AGENTS.md

## Quick Start

```bash
# Run single test
python -m pytest tests/test_strategy.py::test_identify_entry_setup_ready_buy -v

# Run backtest
python backtest.py --strategy pullback --symbol EURUSD --timeframe M15 --start 2024-01-01 --end 2024-06-30

# Run daemon (shadow mode)
python main.py
```

## Core Files

| File | Purpose |
|------|---------|
| `strategy.py` | Entry setup logic (`identify_entry_setup`, `build_trade_proposal`) |
| `indicators.py` | Technical indicators (RSI, SMA, EMA, ATR, Bollinger Bands) |
| `risk_engine.py` | Position sizing, SL bounds, drawdown checks |
| `scanner.py` | Symbol scanning + decision cycle |
| `config.py` | All .env params (no magic numbers) |
| `backtest.py` | Historical testing engine |

## Config Params (key ones)

```bash
# Execution
EXECUTION_MODE=shadow  # NEVER change to live without explicit request

# Strategy
INTRADAY_TIMEFRAME=M15
MIN_TREND_STRENGTH=0.65
MIN_RSI_OVERSOLD=25
MAX_RSI_OVERBOUGHT=75

# Risk
RISK_PER_TRADE_PERCENT=0.5
MIN_SL_PIPS=8
MAX_SL_PIPS=80
```

## Recent Changes (feature/mean-reversion-strategy)

- Added `bollinger_bands()` in `indicators.py`
- Added mean reversion config in `config.py`:
  - `ENABLE_MEAN_REVERSION`
  - `MEAN_REV_MAX_TREND_STRENGTH=0.35`
  - `MEAN_REV_BOLLINGER_PERIOD=20`
  - `MEAN_REV_RSI_EXTREME_BUY=25`
  - `MEAN_REV_RSI_EXTREME_SELL=75`
- Added `backtest.py` for historical testing
- Added `STRATEGIA_MEAN_REVERSION.md` docs

## Testing

- All tests: `python -m pytest tests/ -v`
- Mock MT5Client (no real connection needed)
- Test files in `tests/test_*.py`

## Common Gotchas

- CSV data: headers have leading spaces (` Ora`, ` Open`)
- Date format in CSV: `dd/mm/YYYY HH:MM:SS`
- JPY pairs: pip_size = 0.01, others = 0.0001
- MT5 filling: use `ORDER_FILLING_RETURN` only
- Always use `.env` via `config.py`, never read `.env` directly