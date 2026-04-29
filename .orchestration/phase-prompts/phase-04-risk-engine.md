# Fase 4 — Risk Engine (CORE)

## Obiettivo
Unico cancello di approvazione dei trade. Deterministico. Coperto da test.

## File da creare

### 1. `risk_engine.py`

Funzione principale:
```python
def evaluate_trade(proposal: TradeProposal, account: AccountState, mt5_client: Mt5Client) -> RiskDecision
```

Ordine controlli (interrompere al primo reject):

1. **Kill switch giornaliero**:
   `if account.balance <= account.starting_balance_of_day * (1 - cfg.MAX_DAILY_DRAWDOWN_PERCENT/100): reject`

2. **Filtro sessione** (solo se `cfg.USE_SESSION_FILTER`):
   `now = datetime.now(ZoneInfo("Europe/Rome")); if not (cfg.SESSION_START_HOUR <= now.hour < cfg.SESSION_END_HOUR): reject`

3. **Limiti SL in pips**:
   - leggi `symbol_info.point` e `symbol_info.digits`
   - `pip_size = point*10` se digits in (3, 5) altrimenti `point` (regola standard 5/3 decimali, JPY a 2/3)
   - `distance_pips = abs(entry - sl) / pip_size`
   - se fuori `[cfg.MIN_SL_PIPS, cfg.MAX_SL_PIPS]` → reject

4. **Risk amount**:
   - `PERCENT` → `account.balance * cfg.RISK_PER_TRADE_PERCENT/100`
   - `FIXED_AMOUNT` → `cfg.RISK_PER_TRADE_AMOUNT`

5. **Profilo CONSERVATIVE/MODERATE/AGGRESSIVE**:
   - I valori espliciti del `.env` hanno SEMPRE precedenza.
   - I default del profilo riempiono solo i campi `None`.
   - Esempio: CONSERVATIVE = max_lots 0.3, max_drawdown 1.5%; MODERATE = 0.5, 2.5%; AGGRESSIVE = 1.0, 4.0%.

6. **Calcolo size**:
   - `pip_value` ground truth via `mt5.order_calc_profit(...)` per 1 lotto e movimento di 1 pip; in alternativa `tick_value * pip_size / tick_size`.
   - `size = risk_amount / (pip_value * distance_pips)`
   - clamp a `cfg.MAX_LOTS_PER_TRADE`
   - normalizza al `volume_step` del simbolo (`floor(size / step) * step`)

7. **Margin check**:
   - `margin = mt5_client.calc_order_margin(symbol, direction, size, entry)`
   - `while margin > account.free_margin * 0.9 and size >= 0.01: size *= 0.8; size = floor(size/step)*step; margin = ...`
   - se `size < 0.01` → reject

8. **Ritorna** `RiskDecision(approved=True, size_lots=size, reason="OK", adjusted_stop_loss=proposal.stop_loss_price, adjusted_take_profit=proposal.take_profit_price)`.

Ogni reject scrive un `reason` chiaro in italiano (es. "Kill switch giornaliero attivo: drawdown 2.1% > 2.0%").

NESSUNA chiamata diretta a `mt5.*`: tutto via `mt5_client`.

Retry 3 volte sulle chiamate `mt5_client` con try/except.

### 2. `tests/test_risk.py`

`pytest` con `unittest.mock.MagicMock` per `Mt5Client`. Casi obbligatori:
- trade accettato standard
- kill switch attivato (balance basso)
- SL troppo stretto (sotto MIN_SL_PIPS)
- SL troppo largo (sopra MAX_SL_PIPS)
- ridimensionamento margine fino al limite minimo
- filtro sessione fuori orario (mock di `datetime.now`)

Usa fixture `pytest` per Config, AccountState e proposal di base.

## Checkpoint
```powershell
pytest tests/test_risk.py -v
```
Tutti verdi.

## Errori comuni
- `pip_value` errato su cross/JPY/XAUUSD → testare con `order_calc_profit` come ground truth.
- Profilo che sovrascrive `.env` → invertire la logica.
- Dimenticare di normalizzare size al `volume_step` → broker rifiuta l'ordine.
- Mockare `Mt5Client` ma chiamare `mt5.*` direttamente → niente bypass.

## Commit attesi
```
feat(risk): implement evaluate_trade with kill switch and session filter
feat(risk): add pip_value, size sizing, margin downsize loop
test(risk): cover accept, kill switch, SL bounds, margin downsize, session
feat(phase-4): complete and validated
```
