# Guida alla Strategia Mean Reversion — Trading Agent

## Cos'è la Mean Reversion

La mean reversion è l'opposto della strategia che stai usando ora. Invece di seguire il trend, **scommetti che il prezzo è andato troppo in una direzione e tornerà indietro**.

Immagina il prezzo come un elastico: quando si allunga troppo in una direzione, tende a tornare verso il centro. Questa strategia usa proprio questo principio.

---

## Quando Usarla

### Contesto di Mercato
La mean reversion funziona bene quando:
- Il mercato è **laterale** (non c'è un trend chiaro)
- Il prezzo tocca un **estremo** (bordo esterno delle Bollinger Bands)
- L'RSI segna **ipercomprato (>75)** o **iperscotto (<25)**

### Quando EVITARLA
- In trend forti: se il trend è chiaro (>0.65 forza), non combattere il trend
- Durante notizie importanti: evita 30 min prima e dopo
- Sessioni a bassa liquidità: notte (00:00-08:00 CET)

---

## Setup di Ingresso BUY (Long)

1. **RSI ≤ 25** (iperscotto)
2. **Prezzo tocca o buca la banda inferiore di Bollinger** (20 periodi, 2 deviazioni standard)
3. **Candela di rimbalzo**: close sopra la banda inferiore, o shadow lunga verso il basso
4. **Entry**: al close della candela di conferma
5. **Stop Loss**: sotto il minimo recente (1-1.5x ATR)
6. **Target**: banda centrale di Bollinger (20 SMA)

## Setup di Ingresso SELL (Short)

1. **RSI ≥ 75** (ipercomprato)
2. **Prezzo tocca o buca la banda superiore di Bollinger**
3. **Candela di rimbalzo**: close sotto la banda, o shadow lunga verso l'alto
4. **Entry**: al close della candela di conferma
5. **Stop Loss**: sopra il massimo recente (1-1.5x ATR)
6. **Target**: banda centrale di Bollinger

---

## Parametri Consigliati (.env)

```bash
# Attiva mean reversion (default: false)
ENABLE_MEAN_REVERSION=true

# Forza massima del trend per entrare (default: 0.35)
# Se il trend è più forte di questo, non entrare
MEAN_REV_MAX_TREND_STRENGTH=0.35

# Bollinger Bands
MEAN_REV_BOLLINGER_PERIOD=20
MEAN_REV_BOLLINGER_STD=2.0

# Livelli RSI estremi
MEAN_REV_RSI_EXTREME_BUY=25
MEAN_REV_RSI_EXTREME_SELL=75

# Target sulla banda centrale
MEAN_REV_TARGET_MIDDLE_BAND=true

# R:R minimo accettato
MEAN_REV_MIN_RR=1.0
```

---

## Gestione del Trade

### Dimensione Posizione
- Rischio massimo: **1-2% del capitale per trade**
- Con R:R di 1.0, hai bisogno del 50% di win rate per pareggiare

### Trailing Stop
- Sposta SL a **breakeven** dopo il primo target
- Non usare trailing stop aggressivi (il prezzo deve tornare al centro)

### Chiusura Anticipata
- Se RSI raggiunge **50** (neutralità), chiudi manualmente
- Se il prezzo rimane bloccato >10 candele, esci in pareggio

---

## Perché Funziona

### Base Scientifica
- I prezzi oscillano attorno a una media (mean reversion)
- Gli estremi statistici tendono a rientrare (regression toward mean)
- Bollinger Bands visualizzano le deviazioni standard dalla media

### Vantaggi
- **Entry su punti definiti**: non devi indovinare dove entrare
- **R:R positivo anche con 40% WR**: il target è vicino
- **Funziona in mercati laterali**: dove il trend following fallisce

### Svantaggi
- **Non cattura trend forti**: in trend, il prezzo "cammina" sulle bande
- **Whipsaw**: false inversioni in mercati deboli
- **Risk di continuazione**: se il trend è reale, lo stop viene colpito

---

## Errori Comuni da Evitare

### ❌ Vendere solo perché RSI > 70
Il prezzo può restare ipercomprato per settimane in trend rialzista. **Aspetta la conferma di rimbalzo**.

### ❌ Non filtrare il trend
Se il trend H1 è forte (>0.65), la mean reversion è controproducente. Filtra sempre con `MEAN_REV_MAX_TREND_STRENGTH`.

### ❌ Target troppo ambiziosi
Il target realistico è la **banda centrale**, non l'altra banda. La metà del range è un buon profitto.

### ❌ Non usare stop loss
Senza stop, una continuazione di trend ti porta al disastro. Usa sempre SL dietro l'estremo.

### ❌ Entrare su candela estesa
Aspetta che la candela **chiuda dentro le bande** o mostri rejection. Non entrare su wick isolated.

---

## Differenza con Trend Following

| Aspetto | Trend Following (Attuale) | Mean Reversion |
|---------|---------------------|--------------|
| Direzione | Con il trend | Contro il trend |
| Entry | Su pullback verso MA | Su rimbalzo da estremo |
| Target | Multiplo R alto | Banda centrale |
| Win rate | Alto | Basso |
| R:R | Basso | Alto |
| Mercato ideale | Trending | Laterale |

---

## Come Testarla

### Shadow Mode (Consigliato)
1. Attiva `ENABLE_MEAN_REVERSION=true`
2. Lascia girare 1 settimana
3. Analizza i trade proposal generati
4. Se vedi pattern giusti, valuta live

### Backtest (Avanzato)
```bash
python backtest.py --strategy mean_reversion --symbol EURUSD --timeframe M15 --start 2024-01-01 --end 2024-06-30
```

---

## Checklist Prima di Entrare

- [ ] Trend H1 strength ≤ 0.35 (o no trend)
- [ ] RSI in zona extrema (≤25 o ≥75)
- [ ] Prezzo tocca/buca Bollinger band
- [ ] Candela di conferma (close dentro banda o rejection wick)
- [ ] SL ≤ 1.5x ATR
- [ ] R:R ≥ 1.0
- [ ] Nessuna news ad alto impatto nelle prossime 2 ore
- [ ] Siamo in finestra operativa (08:00-20:00 CET)

---

## Conclusione

La mean reversion è un'arma potente per mercati laterali, ma richiede disciplina. Non è per chi vuole "catturare" movimenti grandi — è per chi vuole **raccogliere piccoli ritorni consistenti** con alta probabilità.

試してください (Prova)!