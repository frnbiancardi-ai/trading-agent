# FASE 6 — Execution layer + EXECUTION_MODE

## Obiettivo
Orchestrare il flow `proposal → risk_engine → mt5_client → logger`, rispettando `EXECUTION_MODE`.

## File da creare

### 1. `execution.py`

```python
def run_once(symbol: str, proposal: TradeProposal | None,
             cfg: Config, mt5_client: Mt5Client, logger: logging.Logger) -> RiskDecision | None
```

**Flow:**
1. Se `proposal is None` → return None (sarà chiamato con proposal valido da claude_agent o MCP).
2. `account_state = mt5_client.get_account_state()`
3. `decision = risk_engine.evaluate_trade(proposal, account_state, mt5_client)`
4. `logger.log_trade_decision(proposal, decision, account_state)`
5. Se `decision.approved` AND `cfg.EXECUTION_MODE != "shadow"`:
   - `result = mt5_client.send_order(symbol, proposal.direction, decision.size_lots, decision.adjusted_stop_loss, decision.adjusted_take_profit, proposal.comment)`
   - `logger.log_order_result(result, proposal)`
6. Return `decision`.

**Vincoli:**
- Mai chiamare `mt5_client.send_order` se non passa dal risk engine.
- `shadow` = mai `send_order`, solo log.
- `paper` = `send_order` su demo (la differenza è nel `.env`).
- `live` = `send_order` su conto reale (richiede flag esplicito utente).

### 2. `main.py`

Entry point minimale:
```python
def main():
    cfg = Config()
    logger = init_logger(cfg)
    mt5 = Mt5Client(cfg)
    if not mt5.initialize() or not mt5.login():
        logger.error("MT5 initialization/login failed")
        return
    try:
        for symbol in cfg.SYMBOLS:
            account = mt5.get_account_state()
            agent = ClaudeAgent(cfg, mt5, logger)
            proposal = agent.run_cycle(symbol, account)
            if proposal:
                run_once(symbol, proposal, cfg, mt5, logger)
            else:
                logger.info(f"NO_TRADE for {symbol}")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()
```

**Note:**
- `claude_agent` non esiste ancora in Fase 6: lascia un TODO commentato e crea uno stub `ClaudeAgent` minimale (oppure rimanda a Fase 8 e per ora testa con proposal hardcoded). **Decisione consigliata**: in Fase 6 testa `run_once` con una proposal hardcoded; in Fase 8 sostituisci con `ClaudeAgent`.

## Checkpoint

**Test shadow** (con proposal hardcoded in uno script di test):
```powershell
python -c "
from config import Config
from logger import init_logger
from mt5_client import Mt5Client
from models import TradeProposal
from execution import run_once
cfg = Config()
log = init_logger(cfg)
mt5 = Mt5Client(cfg); mt5.initialize(); mt5.login()
p = TradeProposal('EURUSD','BUY',1.10,1.0970,1.1060,'M15','test',0.7,'manual test')
print(run_once('EURUSD', p, cfg, mt5, log))
mt5.shutdown()
"
```
- In `EXECUTION_MODE=shadow` → nessun ordine in MT5, una riga in `trades.db`.
- In `EXECUTION_MODE=paper` (cambiando `.env`) → ordine visibile nel terminale MT5.

## Errori comuni
- `EXECUTION_MODE` letto via `os.getenv` invece che da `Config`.
- Bypass del risk engine.
- `main.py` senza `try/finally` → connessione MT5 lasciata aperta.

## Commit attesi
```
feat(execution): add run_once with EXECUTION_MODE handling
feat(execution): add main.py entry point with mt5 lifecycle
feat(phase-6): complete and validated
```
