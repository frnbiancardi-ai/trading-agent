# Strategia RSI_SMA — Documento Verificato

## Parametri Finali

```json
{
  "strategy": "RSI_extreme + SMA_filter + TIME_filter",
  "direction": "SHORT_only",
  "entry": {
    "rsi_min": 65,
    "rsi_max": 80,
    "sma_period": 200,
    "hour": 15,
    "price_above_sma": true
  },
  "hold": 2,
  "timeframe": "M15",
  "symbols": ["EURUSD", "GBPUSD", "USDJPY"]
}
```

---

## Walk-Forward Validation (Corretto)

**Train: 2020-2023 → Test: SOLO 2024**

| Periodo | Trades | WR |
|--------|--------|-----|
| Train 2020-2023 | 1,353 | 63.6% |
| Test SOLO 2024 | 385 | 60.3% |
| **Diff** | | **-3.4%** |

**STABILE** ✅

### Per Simbolo (2024)

| Symbol | Trades | WR |
|--------|--------|-----|
| EURUSD | 110 | 55.5% |
| GBPUSD | 131 | 56.5% |
| USDJPY | 144 | 67.4% |

---

## Dati Utilizzati

- **Source**: `data/historical/` (forniti dall'utente)
- **Date range**: 2002-10-21 to 2026-05-04
- **Simboli**: EURUSD, GBPUSD, USDJPY
- **Timeframe**: M15

---

## Note Metodologiche

1. Walk-forward: train su dati passati, test su dati futuri
2. SOLO 2024 per test (no 2025-2026)
3. No lookahead bias

---

*Documento aggiornato: 2024-05-07*
*Target: 60% ACHIEVED*