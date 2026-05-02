# Validazione utente — Fase 15 (RSS News Sentiment Layer)

Branch: `feature/python-pure-strategy`
Suite automatizzata: **142/142 passed**.
Live checkpoint: a carico dell'utente.
Pre-requisito: validazione fase 14 completata (vedi `VALIDATION_PHASE_14.md`).

---

## Pre-requisiti

- [ ] Fase 14 validata (almeno step 1-4 di `VALIDATION_PHASE_14.md` PASS).
- [ ] `feedparser` installato: `.venv\Scripts\pip install -r requirements.txt`.
- [ ] `.env` aggiornato con sezione fase 15:
  - `ENABLE_NEWS_SENTIMENT=true`
  - `NEWS_FETCH_INTERVAL_MINUTES=15`
  - `NEWS_LOOKBACK_HOURS=2`
  - `NEWS_CACHE_MAX_HOURS=24`
  - `SENTIMENT_MIN_STRENGTH_FILTER=0.6`
  - `SENTIMENT_BOOST_FACTOR=0.15`
  - `SENTIMENT_CONFLICT_ACTION=delay` (oppure `skip` / `reduce_confidence`)
  - `SENTIMENT_CONFLICT_DELAY_MINUTES=60`
  - `RSS_FEEDS=https://www.investing.com/rss/news_25.rss,https://www.forexlive.com/feed/news`
- [ ] Connessione internet attiva (RSS feed pubblici).

---

## Step 1 — Suite automatizzata

```powershell
cd C:\trading-agent
.\.venv\Scripts\python.exe -m pytest tests/test_news_aggregator.py tests/test_sentiment.py tests/test_strategy.py -v
```

Atteso: 47 test passati (12 news + 12 sentiment + 23 strategy).

---

## Step 2 — Smoke test feedparser + fetch RSS reale

```powershell
.\.venv\Scripts\python.exe -c "
import logging; logging.basicConfig(level=logging.INFO)
from config import Config
from news_aggregator import NewsAggregator
cfg = Config()
agg = NewsAggregator(cfg, logging.getLogger('test'))
items = agg.fetch_recent_news(force=True)
print('news fetched:', len(items))
for n in items[:3]:
    print('-', n.published.isoformat(), '|', n.source, '|', n.title[:80])
"
```

Verificare:
- [ ] `news fetched: N` con N >= 1 (assumendo feed raggiungibili).
- [ ] Stampa di 3 headline recenti con timestamp.
- [ ] Nessun crash, nessun timeout > 5s.

Se nessun feed risponde (offline o feed down): output `news fetched: 0`,
nessuna eccezione — comportamento atteso, sentiment disabilitato per il ciclo.

---

## Step 3 — Smoke sentiment su simbolo

```powershell
.\.venv\Scripts\python.exe -c "
from datetime import datetime, timezone
from config import Config
from models import NewsItem
from sentiment import SimpleSentiment
cfg = Config()
s = SimpleSentiment(cfg)
news = [
    NewsItem(source='t', title='Euro rallies as ECB turns hawkish on inflation',
             summary='ecb hawkish rate hike expected', link='x',
             published=datetime.now(tz=timezone.utc)),
    NewsItem(source='t', title='Eurozone outperforms with strong data',
             summary='', link='x', published=datetime.now(tz=timezone.utc)),
]
print(s.analyze_news(news, 'EURUSD'))
print(s.analyze_news(news, 'GBPUSD'))
"
```

Verificare:
- [ ] EURUSD: `bias='BULLISH'`, `strength > 0`, `relevant_news_count == 2`.
- [ ] GBPUSD: `bias='NEUTRAL'`, `relevant_news_count == 0` (nessuna news EUR/USD-only è rilevante per GBP).

---

## Step 4 — Daemon E2E con sentiment attivo

```powershell
.\.venv\Scripts\python.exe main.py
```

Atteso a boot:
```
News sentiment enabled: feeds=2 action=delay min_strength=0.60 boost=0.15
Daemon start: tz=Europe/Rome ... strategy=python_pure timeframe=M15 ...
```

Lasciare girare almeno 1 ciclo nello slot operativo. In `logs/agent.log` cercare:
- [ ] Riga "News sentiment enabled: feeds=N ..." al boot.
- [ ] Al primo ciclo, fetch RSS effettivo (riga news_aggregator).
- [ ] Per ogni candidato top deepened, sentiment loggato (chiave `sentiment` in `setup.indicators` se applicato — visibile via dump del trade in `trades_log`).
- [ ] Se sentiment aligned forte: confidence boosted (max 0.95).
- [ ] Se sentiment conflicting forte e action=`delay`: setup downgradato a FORMING → WAIT_FOLLOW_UP.

---

## Step 5 — Toggle off

Spegnere sentiment senza ricostruire il branch:
```env
ENABLE_NEWS_SENTIMENT=false
```

Riavviare daemon. Verificare:
- [ ] Boot log NON contiene "News sentiment enabled".
- [ ] Comportamento identico a fase 14 (no fetch RSS, no sentiment).

---

## Step 6 — Toggle conflict action

Per ognuno dei 3 valori `SENTIMENT_CONFLICT_ACTION` provare almeno
una decisione manuale (forzando un setup READY contro un sentiment forte):

| Action              | Atteso                                              |
|---------------------|-----------------------------------------------------|
| `skip`              | setup → NONE, decisione = NO_TRADE                  |
| `delay`             | setup → FORMING, decisione = WAIT_FOLLOW_UP         |
| `reduce_confidence` | confidence ridotta; se sotto MIN → NO_TRADE         |

Validazione tramite test unit copre già le 3 vie; lo step manuale è facoltativo
ma raccomandato in shadow.

---

## Esito validazione

| Step | Pass/Fail | Note |
|------|-----------|------|
| 1. Suite                | [ ] |   |
| 2. Fetch RSS reale      | [ ] |   |
| 3. Smoke sentiment      | [ ] |   |
| 4. Daemon E2E con news  | [ ] |   |
| 5. Toggle off           | [ ] |   |
| 6. Toggle action (opt)  | [ ] / N/A |  |

Se tutti PASS:
1. Marcare fase 15 `phase_status: VALIDATED` in `STATE.md`.
2. Aggiornare `PHASES.md` con fase 14 + 15.
3. Merge `feature/python-pure-strategy` in `main`:
   ```powershell
   git checkout main
   git merge --no-ff feature/python-pure-strategy
   git push origin main
   ```
4. Tag: `v1.2.0` ("Python pure strategy + RSS sentiment layer").
5. Push tag: `git push origin v1.2.0`.

Se anche solo uno fallisce:
- Lasciare `phase_status: IN_PROGRESS`.
- Correggere root cause; non disabilitare sentiment per "passare" la validazione.

---

## Note operative

- I feed RSS pubblici possono cambiare URL o formato senza preavviso.
  In caso di errori frequenti su un feed, rimuoverlo da `RSS_FEEDS`
  (lista csv); il sistema isola gli errori per-feed.
- Per backtest con RSS storici archiviati, salvare lo stato di
  `NewsAggregator.cache` su disco fra le sessioni (non implementato in
  fase 15, candidato per v1.3.0).
- Sentiment non sostituisce mai la tecnica: se sentiment è NEUTRAL o
  sotto soglia, il setup tecnico passa inalterato.
