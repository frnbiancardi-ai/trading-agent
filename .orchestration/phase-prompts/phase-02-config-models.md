# Fase 2 — Config e modelli base

## Obiettivo
Sistema di configurazione tipizzato letto da `.env` più tutte le dataclasses condivise.

## File da creare

### 1. `.env.example`
Sezioni con commenti italiani: MT5, Risk, Symbols/Session, Logging, Claude, Execution.
Default conservativi: `RISK_PER_TRADE_PERCENT=0.5`, `MAX_DAILY_DRAWDOWN_PERCENT=2.0`, `MIN_SL_PIPS=8`, `MAX_SL_PIPS=80`, `EXECUTION_MODE=shadow`, `RISK_PROFILE=CONSERVATIVE`, `CLAUDE_MODEL=claude-sonnet-4-20250514`.

### 2. `.env`
Copia di `.env.example` (NON committare: già in `.gitignore`).

### 3. `config.py`
- `from dotenv import load_dotenv` + `load_dotenv()` a livello modulo.
- Helper privati `_get_bool(name, default)`, `_get_list(name, default)` (split su `,`, strip, scarta vuoti).
- Classe `Config` con tutte le proprietà del brief, tipizzate (`int`, `float`, `bool`, `str`, `list[str]`).
- Default ragionevoli ovunque.
- NIENTE Pydantic in `config.py`.

### 4. `models.py`
Dataclasses con `@dataclass`:
- `TradeProposal(symbol: str, direction: str, entry_price: float, stop_loss_price: float, take_profit_price: float, timeframe: str, comment: str, confidence: float, rationale: str)`
- `PositionInfo(symbol, lots, direction, entry_price, stop_loss, take_profit, profit)`
- `AccountState(balance, equity, free_margin, open_positions: list[PositionInfo], today_realized_pnl, starting_balance_of_day)`
- `RiskDecision(approved: bool, size_lots: float, reason: str, adjusted_stop_loss: float, adjusted_take_profit: float)`
- `OrderResult(success: bool, order_id: int | None, error_message: str | None)`

Tutte serializzabili via `dataclasses.asdict`.

## Checkpoint

```powershell
python -c "from config import Config; c = Config(); print(c.RISK_MODE, c.SYMBOLS, c.EXECUTION_MODE)"
python -c "from models import TradeProposal, AccountState, RiskDecision, PositionInfo, OrderResult; print('models OK')"
```

## Errori comuni
- Variabili lette come stringa invece che castate.
- `_get_list` che non gestisce stringa vuota o trailing comma.
- Default troppo aggressivi.

## Commit attesi
```
feat(config): add .env.example with italian comments
feat(config): add Config class with typed properties
feat(models): add TradeProposal, AccountState, RiskDecision, PositionInfo, OrderResult
feat(phase-2): complete and validated
```
