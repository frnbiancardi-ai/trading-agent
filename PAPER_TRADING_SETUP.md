# PAPER TRADING SETUP

## Il Problema

La strategia RSI_SMA è stata testata **sul backtest** con TUTTI i dati alle 15:00.
In live trading, lo scheduler gira ogni **3 ore**: 8, 11, 14, 17, 20.

**Non esiste un ciclo alle 15:00!**

## Soluzioni

### Opzione 1: Cambia scheduler a 4 ore
```bash
OPERATING_START_HOUR=7
OPERATING_END_HOUR=22
MAIN_CYCLE_HOURS=4
# Gira: 7, 11, 15, 19 ✓
```

### Opzione 2: Accetta ore 14-15
La strategia accetta sia 14 che 15 (vicine a 15:00).

## Setup Consigliato

```bash
# .env
RSI_SMA_ENABLED=true
RSI_SMA_HOUR=14
MAIN_CYCLE_HOURS=4
OPERATING_START_HOUR=7
OPERATING_END_HOUR=22
```

Questo farà girare il bot a: **7, 11, 15, 19**

## Poi Esegui

```bash
EXECUTION_MODE=paper python main.py
```

Il bot scannerà alle 15:00 (orario NYC/NY) e cercherà setup RSI 65-80 + price > SMA200.