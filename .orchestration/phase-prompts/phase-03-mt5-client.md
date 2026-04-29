# Fase 3 — MT5 Client

## Obiettivo
Wrapper completo MetaTrader5: solo IO, zero risk logic.

## File da creare

### `mt5_client.py`

Classe `Mt5Client`:
- `__init__(self, cfg: Config)`
- `initialize()` → bool, logga `mt5.last_error()` se fallisce
- `login()` → bool
- `shutdown()`
- `get_account_state() -> AccountState`:
  - usa `mt5.account_info()` per balance/equity/free_margin
  - `mt5.positions_get()` mappato in `list[PositionInfo]`
  - `today_realized_pnl` e `starting_balance_of_day` calcolati con `mt5.history_deals_get(date_from, date_to)` filtrando deal con `entry == DEAL_ENTRY_OUT` per la giornata corrente in Europe/Rome
- `get_symbol_info(symbol)` → forza `mt5.symbol_select(symbol, True)` se necessario
- `get_ohlc(symbol, timeframe: str, n_bars) -> list[dict]`:
  - mapping `TIMEFRAME_MAP = {"M1": mt5.TIMEFRAME_M1, "M5":..., "M15":..., "M30":..., "H1":..., "H4":..., "D1":...}`
  - usa `mt5.copy_rates_from_pos(symbol, tf, 0, n_bars)`, restituisce list[dict] con keys `time, open, high, low, close, tick_volume`
- `calc_order_margin(symbol, direction, lots, price) -> float`:
  - usa `mt5.order_calc_margin(action, symbol, lots, price)`
- `send_order(symbol, direction, lots, sl, tp, comment) -> OrderResult`:
  - filling fallback: prova `ORDER_FILLING_IOC`, poi `FOK`, poi `RETURN`
  - usa prezzo a mercato (`SYMBOL_TRADE_EXECUTION_MARKET`)
  - tipo `ORDER_TYPE_BUY` o `ORDER_TYPE_SELL`

Decoratore interno `_retry(n=3)` per chiamate sensibili (`get_account_state`, `get_ohlc`, `calc_order_margin`, `send_order`).

Vincolo: ZERO logica di rischio. Niente check su size, SL, balance.

## Checkpoint
```powershell
# Solo se MT5 demo configurato in .env
python -c "from config import Config; from mt5_client import Mt5Client; c=Mt5Client(Config()); c.initialize(); c.login(); print(c.get_account_state()); c.shutdown()"
```

## Errori comuni
- `mt5.initialize()` ritorna False senza dettagli → loggare `mt5.last_error()` SEMPRE.
- Symbol non in Market Watch → `symbol_select(True)`.
- Filling mode rifiutato → fallback IOC → FOK → RETURN.
- Conversione tempo: usare `datetime` + `zoneinfo("Europe/Rome")`.

## Commit attesi
```
feat(mt5): implement Mt5Client wrapper with retry decorator
feat(mt5): add filling mode fallback for send_order
feat(phase-3): complete and validated
```
