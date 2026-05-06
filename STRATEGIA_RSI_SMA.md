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

## 1. Walk-Forward Validation

**Train: 2020-2023 → Test: SOLO 2024**

| Periodo | Trades | WR |
|--------|--------|-----|
| Train 2020-2023 | 1,353 | 63.6% |
| Test SOLO 2024 | 385 | 60.3% |
| **Diff** | | **-3.4%** |

✅ **STABILE**

### Per Simbolo (2024)

| Symbol | Trades | WR |
|--------|--------|-----|
| EURUSD | 110 | 55.5% |
| GBPUSD | 131 | 56.5% |
| USDJPY | 144 | 67.4% |

---

## 2. Monte Carlo Simulation

10,000 simulazioni shuffle trade outcomes

| Metric | Valore |
|--------|--------|
| Mean WR | 62.9% |
| Std Dev | 2.2% |
| **95% CI** | **58.7% - 67.3%** |
| P(WR > 50%) | 100% |
| P(WR > 55%) | 100% |
| P(WR > 60%) | 89.8% |
| Worst 1% | 57.7% |

✅ **ROBUSTA** - Anche worst case > 50%

---

## Dati Utilizzati

- **Source**: `data/historical/` (forniti dall'utente)
- **Date range**: 2002-10-21 to 2026-05-04
- **Simboli**: EURUSD, GBPUSD, USDJPY
- **Timeframe**: M15

---

## Prossimi Passi

- [ ] Paper trading reale
- [ ] Live small account

---

*Documento aggiornato: 2024-05-07*
*Target: 60% ACHIEVED ✅*
*Monte Carlo: ROBUST ✅*