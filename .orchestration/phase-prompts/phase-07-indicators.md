# Fase 7 — Indicators

## Obiettivo
Indicatori tecnici in Python puro su array OHLC. Niente pandas/ta-lib.

## File da creare

### `indicators.py`

```python
def sma(values: list[float], period: int) -> list[float]
def ema(values: list[float], period: int) -> list[float]    # seed = SMA(values[:period])
def rsi(closes: list[float], period: int = 14) -> list[float]   # Wilder smoothing
def atr(highs, lows, closes, period: int = 14) -> list[float]   # Wilder smoothing

def compute_all(ohlc: list[dict]) -> dict:
    """Ritorna {sma_20, ema_50, rsi_14, atr_14} dell'ultima barra."""
```

Dettagli:
- Le liste output hanno `None` (o `float('nan')`) nelle prime `period-1` posizioni.
- `ema`: dopo il seed iniziale (SMA dei primi `period` valori), `ema[t] = alpha*value[t] + (1-alpha)*ema[t-1]` con `alpha = 2/(period+1)`.
- `rsi` Wilder:
  - `gains[i] = max(0, close[i]-close[i-1])`, `losses[i] = max(0, close[i-1]-close[i])`
  - prima media = SMA dei primi `period` (gains, losses)
  - poi smoothing Wilder: `avg = (avg*(period-1) + new) / period`
  - `rs = avg_gain/avg_loss`, `rsi = 100 - 100/(1+rs)`
- `atr` Wilder:
  - `tr[i] = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))`
  - poi smoothing Wilder come RSI

`compute_all`:
- estrae `closes`, `highs`, `lows` dal `list[dict]`
- calcola sma_20, ema_50, rsi_14, atr_14
- ritorna l'ultimo valore non-None di ogni serie

## Checkpoint
```powershell
python -c "
from indicators import sma, ema, rsi, atr, compute_all
closes = [1+0.001*i for i in range(100)]
print('sma:', sma(closes,20)[-1])
print('ema:', ema(closes,50)[-1])
print('rsi:', rsi(closes,14)[-1])
"
```

Validazione manuale: confrontare con TradingView su EURUSD M15 (50-100 barre), tolleranza ±0.1%.

## Errori comuni
- `ema` senza seed → diverge.
- `rsi` con SMA invece di Wilder → valori diversi dai broker.
- Liste con `None` → propagano. Filtrare a monte.

## Commit attesi
```
feat(indicators): pure python sma, ema, rsi (wilder), atr (wilder)
feat(indicators): compute_all helper for ohlc input
feat(phase-7): complete and validated
```
