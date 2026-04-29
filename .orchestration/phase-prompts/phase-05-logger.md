# Fase 5 — Logger

## Obiettivo
Audit trail completo: ogni decisione (approvata o rifiutata) persistita su SQLite più file rotante.

## File da creare

### `logger.py`

Setup:
- `logging.handlers.RotatingFileHandler(cfg.AGENT_LOG_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8")`
- format: `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`
- crea `logs/` se non esiste

SQLite:
```sql
CREATE TABLE IF NOT EXISTS trades_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,
  size_lots REAL,
  entry_price REAL,
  stop_loss REAL,
  take_profit REAL,
  decision_reason TEXT,
  approved INTEGER NOT NULL,
  pnl_realized REAL
);
```
- `PRAGMA journal_mode=WAL` per concorrenza con MCP server.
- Connessione context-managed in ogni funzione (`with sqlite3.connect(...) as conn`).

Funzioni:
- `init_logger(cfg: Config) -> logging.Logger`
- `log_trade_decision(proposal: TradeProposal, decision: RiskDecision, account: AccountState)`:
  - INSERT con timestamp ISO, `pnl_realized=NULL`, `approved=int(decision.approved)`
  - logga anche su file: `"DECISION symbol=... approved=... reason=..."`
- `log_order_result(order_result: OrderResult, proposal: TradeProposal)`:
  - log su file con `success`, `order_id`, `error_message`
  - opzionale: UPDATE riga corrispondente con `order_id`; per semplicità log solo testuale

## Checkpoint
```powershell
python -c "from config import Config; from logger import init_logger; init_logger(Config()); print('logger OK')"
sqlite3 logs/trades.db ".schema trades_log"   # se sqlite3 CLI disponibile, altrimenti ignora
```

## Errori comuni
- Connessione SQLite non chiusa → context manager.
- Concorrenza tra agent e MCP → `journal_mode=WAL`.
- Timestamp non ISO → `datetime.now(ZoneInfo("Europe/Rome")).isoformat()`.
- Dimenticare encoding UTF-8 sul file handler → caratteri accentati corrotti.

## Commit attesi
```
feat(logger): rotating file handler + sqlite schema with WAL
feat(logger): add log_trade_decision and log_order_result
feat(phase-5): complete and validated
```
