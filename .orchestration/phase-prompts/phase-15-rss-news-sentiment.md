# Fase 15 — RSS News Sentiment Layer (Opzionale)

## Obiettivo
Aggiungere un layer di sentiment analysis basato su RSS feed di news finanziarie gratuite per arricchire il contesto decisionale della strategia Python pura implementata in Fase 14.

Il sentiment **non sostituisce** l'analisi tecnica ma agisce come:
- **Filtro**: blocca trade contro sentiment forte contrario
- **Boost confidence**: aumenta confidence su trade allineati con sentiment
- **Delay trigger**: richiede follow-up se sentiment/tecnica divergono

Requisiti:
- Zero costi: solo RSS feed pubblici gratuiti
- Latenza bassa: parsing + sentiment < 1 secondo
- Deterministico: sentiment keyword-based testabile
- Opzionale: può essere disabilitato via `.env` senza rompere strategia base
- Backtest-friendly: archiviando RSS storici

Vincoli:
- Non rompere `strategy.py` o `scanner.py` fase 14
- Mantieni compatibilità con `risk_engine`, `execution`, `scheduler`
- `EXECUTION_MODE=shadow` di default

---

## File da creare o modificare

Questa fase tocca:

1. `config.py` — estendere con parametri RSS e sentiment
2. `models.py` — aggiungere modelli per news e sentiment
3. `news_aggregator.py` — **NUOVO FILE** fetch e parse RSS
4. `sentiment.py` — **NUOVO FILE** sentiment keyword-based
5. `strategy.py` — modificare per integrare sentiment nel decision workflow
6. `scanner.py` — opzionalmente integrare sentiment nel ranking preliminare
7. `tests/test_news_aggregator.py` — **NUOVO FILE**
8. `tests/test_sentiment.py` — **NUOVO FILE**
9. `STATE.md` — solo tracking stato

---

## Parametri `.env` richiesti

Estendere `.env`:

```env
# === RSS News Sentiment ===
ENABLE_NEWS_SENTIMENT=true
NEWS_FETCH_INTERVAL_MINUTES=15
NEWS_LOOKBACK_HOURS=2
NEWS_CACHE_MAX_HOURS=24
SENTIMENT_MIN_STRENGTH_FILTER=0.6
SENTIMENT_BOOST_FACTOR=0.15
SENTIMENT_CONFLICT_ACTION=delay  # 'skip', 'delay', 'reduce_confidence'

# === RSS Feed URLs ===
RSS_FEEDS=https://www.reuters.com/markets/currencies/rss,https://www.investing.com/rss/news_25.rss,https://www.forexlive.com/feed/news

# === Sentiment Keywords (opzionale override) ===
# SENTIMENT_BULLISH_KEYWORDS=rally,surge,gains,strengthen,breakout
# SENTIMENT_BEARISH_KEYWORDS=plunge,tumble,weaken,crash,dovish
```

**Note:**
- `ENABLE_NEWS_SENTIMENT`: flag on/off globale
- `NEWS_FETCH_INTERVAL_MINUTES`: ogni quanto aggiornare cache news
- `NEWS_LOOKBACK_HOURS`: quante ore di news considerare per sentiment
- `SENTIMENT_MIN_STRENGTH_FILTER`: soglia minima di strength per applicare filtro/boost
- `SENTIMENT_CONFLICT_ACTION`: comportamento quando sentiment contrasta tecnica
- `RSS_FEEDS`: array di URL separati da virgola

---

## Requisiti per `config.py`

Estendere `Config`:

```python
ENABLE_NEWS_SENTIMENT: bool
NEWS_FETCH_INTERVAL_MINUTES: int
NEWS_LOOKBACK_HOURS: int
NEWS_CACHE_MAX_HOURS: int
SENTIMENT_MIN_STRENGTH_FILTER: float
SENTIMENT_BOOST_FACTOR: float
SENTIMENT_CONFLICT_ACTION: str  # 'skip', 'delay', 'reduce_confidence'
RSS_FEEDS: list[str]
```

Validazione:
- `SENTIMENT_CONFLICT_ACTION` deve essere in `['skip', 'delay', 'reduce_confidence']`
- `RSS_FEEDS` parsing con split virgola e strip
- Default: `ENABLE_NEWS_SENTIMENT=false` per non rompere setup esistente

---

## Requisiti per `models.py`

Aggiungere dataclass:

### `NewsItem`
```python
@dataclass
class NewsItem:
    source: str
    title: str
    summary: str
    link: str
    published: datetime
```

### `SentimentAnalysis`
```python
@dataclass
class SentimentAnalysis:
    symbol: str
    bias: str  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    strength: float  # 0.0 - 1.0
    relevant_news_count: int
    sample_headlines: list[str]  # max 3 per audit
    timestamp: datetime
```

---

## Requisiti per `news_aggregator.py` (NUOVO FILE)

Responsabilità:
- Fetch RSS feed periodicamente
- Parse e cache news recenti
- Expire news vecchie

```python
import feedparser
from datetime import datetime, timedelta

class NewsAggregator:
    def __init__(self, cfg: Config, logger):
        self.cfg = cfg
        self.log = logger
        self.cache = []  # list[NewsItem]
        self.last_fetch = None

    def fetch_recent_news(self, force: bool = False) -> list[NewsItem]:
        """
        Fetch news dai feed RSS configurati.

        - Se ultimo fetch < NEWS_FETCH_INTERVAL_MINUTES fa, usa cache
        - Altrimenti fetch nuovo batch
        - Filtra news più vecchie di NEWS_LOOKBACK_HOURS
        - Ritorna lista NewsItem ordinata per published desc
        """
        pass

    def parse_feed(self, feed_url: str) -> list[NewsItem]:
        """
        Parse singolo RSS feed.
        Usa feedparser library.
        Gestisce errori HTTP, timeout, parse errors gracefully.
        """
        pass

    def clean_cache(self):
        """
        Rimuove news più vecchie di NEWS_CACHE_MAX_HOURS dalla cache.
        """
        pass

    @staticmethod
    def parse_date(date_str: str) -> datetime | None:
        """
        Parse robusta di date RSS (vari formati).
        """
        pass
```

Librerie richieste:
- `feedparser` (aggiungere a `requirements.txt`)

Gestione errori:
- Feed non raggiungibile → log warning, skip quel feed
- Parse fallito → log error, skip entry
- Timeout → retry 1 volta con timeout 5 secondi, poi skip

---

## Requisiti per `sentiment.py` (NUOVO FILE)

Sentiment keyword-based semplice ma efficace.

```python
class SimpleSentiment:
    # Keyword lists (possono essere override da cfg se implementato)
    BULLISH_KEYWORDS = [
        'rally', 'surge', 'breakout', 'gains', 'strengthen', 
        'upbeat', 'optimistic', 'hawkish', 'rate hike', 'strong data',
        'outperform', 'bullish', 'boost', 'rise', 'jump'
    ]

    BEARISH_KEYWORDS = [
        'plunge', 'tumble', 'crash', 'weaken', 'dovish', 
        'rate cut', 'recession', 'weak data', 'concerns', 'risk-off',
        'bearish', 'drop', 'fall', 'slump', 'decline'
    ]

    # Currency keyword mapping
    CURRENCY_MAP = {
        'EUR': ['euro', 'eur', 'ecb', 'eurozone', 'lagarde'],
        'USD': ['dollar', 'usd', 'fed', 'federal reserve', 'powell'],
        'GBP': ['pound', 'sterling', 'gbp', 'bank of england', 'boe'],
        'JPY': ['yen', 'jpy', 'boj', 'bank of japan'],
        'XAU': ['gold', 'xau', 'bullion']
    }

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def analyze_news(self, news_items: list[NewsItem], symbol: str) -> SentimentAnalysis:
        """
        Calcola sentiment per un simbolo forex (es. EURUSD).

        Workflow:
        1. Estrai base currency (primi 3 char) e quote currency (char 4-6)
        2. Filtra news rilevanti per base o quote usando CURRENCY_MAP
        3. Per ogni news rilevante:
           - Conta keyword bullish e bearish
           - Assegna sentiment a base e quote separatamente
        4. Combina sentiment netto per la coppia
        5. Calcola strength basato su numero match e coerenza
        6. Return SentimentAnalysis
        """
        pass

    def calculate_sentiment_score(self, text: str) -> int:
        """
        Ritorna score netto: (count bullish keywords) - (count bearish keywords)
        Text deve essere lowercase.
        """
        pass

    def is_relevant_for_currency(self, text: str, currency: str) -> bool:
        """
        Controlla se text contiene keyword per currency.
        """
        pass
```

Logica scoring:
- Per ogni news rilevante: `bullish_score - bearish_score = net_sentiment`
- Se base currency: `base_sentiment += net_sentiment`
- Se quote currency: `quote_sentiment -= net_sentiment` (invertito)
- `pair_sentiment = base_sentiment + quote_sentiment`
- Se `pair_sentiment > threshold`: BULLISH
- Se `pair_sentiment < -threshold`: BEARISH
- Altrimenti: NEUTRAL
- `strength = min(1.0, abs(pair_sentiment) / (relevant_news_count * 2))`

---

## Requisiti per `strategy.py` (modifiche per integrazione sentiment)

Modificare `IntradayStrategy.analyze_symbol`:

```python
def analyze_symbol(self, symbol: str, account_state: AccountState, sentiment: SentimentAnalysis | None = None) -> TechnicalSetup:
    """
    Aggiungere parametro opzionale sentiment.

    Workflow aggiornato:
    1-7: (come fase 14, invariati)
    8. Se sentiment presente e ENABLE_NEWS_SENTIMENT:
       - Se setup READY:
         - Sentiment allineato → boost confidence
         - Sentiment contrario forte → action based on SENTIMENT_CONFLICT_ACTION
       - Se setup FORMING:
         - Sentiment forte può anticipare o ritardare
    """
    pass
```

Logica integrazione sentiment:

### Setup READY + Sentiment ALIGNED
```python
if setup['type'] == 'READY' and sentiment and sentiment.strength > cfg.SENTIMENT_MIN_STRENGTH_FILTER:
    if is_aligned(setup['direction'], sentiment.bias):
        # Boost confidence
        setup['confidence'] = min(0.95, setup['confidence'] + cfg.SENTIMENT_BOOST_FACTOR * sentiment.strength)
        setup['reason'] += f" | Sentiment {sentiment.bias.lower()} conferma ({sentiment.relevant_news_count} news)"
```

### Setup READY + Sentiment CONFLICTING
```python
if setup['type'] == 'READY' and sentiment and sentiment.strength > cfg.SENTIMENT_MIN_STRENGTH_FILTER:
    if not is_aligned(setup['direction'], sentiment.bias):
        if cfg.SENTIMENT_CONFLICT_ACTION == 'skip':
            setup['type'] = 'NONE'
            setup['reason'] = f"Tecnico {setup['direction']} ma sentiment {sentiment.bias} forte, skip"

        elif cfg.SENTIMENT_CONFLICT_ACTION == 'delay':
            setup['type'] = 'FORMING'
            setup['delay_minutes'] = 60
            setup['reason'] = f"Tecnico {setup['direction']} vs sentiment {sentiment.bias}, attendo conferma"

        elif cfg.SENTIMENT_CONFLICT_ACTION == 'reduce_confidence':
            setup['confidence'] *= (1 - sentiment.strength * 0.3)
            setup['reason'] += f" | Sentiment {sentiment.bias} contrario, confidence ridotta"
```

---

## Requisiti per `scanner.py` (modifiche opzionali)

Opzionalmente, modificare `MultiSymbolScanner.deep_analyze_top_candidates`:

```python
def deep_analyze_top_candidates(self, scan_results: list[ScanResult], account_state: AccountState, news_aggregator: NewsAggregator | None = None) -> StrategyOutcome:
    """
    Se news_aggregator presente e ENABLE_NEWS_SENTIMENT:
    1. Fetch news recenti
    2. Per ogni candidato top, calcola sentiment
    3. Passa sentiment a strategy.analyze_symbol()
    """
    pass
```

---

## Requisiti per `main.py` (modifiche)

Se `ENABLE_NEWS_SENTIMENT=true`:
1. Inizializza `NewsAggregator`
2. Inizializza `SimpleSentiment`
3. Passa `news_aggregator` a `scanner.deep_analyze_top_candidates`

Se `ENABLE_NEWS_SENTIMENT=false`:
- Tutto resta come fase 14, nessuna modifica necessaria

---

## Test richiesti

### `tests/test_news_aggregator.py`

Casi minimi:
- `test_parse_feed_valid`: parse RSS feed mock valido
- `test_parse_feed_invalid_url`: gestisce errore HTTP gracefully
- `test_fetch_uses_cache`: non re-fetch se interval non passato
- `test_clean_cache`: rimuove news vecchie correttamente

Mock `feedparser.parse` per non dipendere da internet nei test.

### `tests/test_sentiment.py`

Casi minimi:
- `test_sentiment_eurusd_bullish`: news pro-EUR → sentiment BULLISH
- `test_sentiment_eurusd_bearish`: news pro-USD → sentiment BEARISH
- `test_sentiment_neutral`: news irrilevanti o bilanciate → NEUTRAL
- `test_sentiment_strength_calculation`: strength proporzionale a keyword match
- `test_is_relevant_for_currency`: filtra news corrette

Usa news mock sintetiche con keyword controllate.

---

## Checkpoint di fase

Comandi di checkpoint:

```powershell
pytest tests/test_news_aggregator.py -v
pytest tests/test_sentiment.py -v
pytest tests/test_strategy.py -v  # ri-eseguire per verificare integrazione
```

Tutti devono passare.

Validazione manuale con `ENABLE_NEWS_SENTIMENT=true`:
```powershell
python main.py
```

Verifica log che mostri:
- Fetch news ogni N minuti
- Sentiment calcolato per simboli analizzati
- Confidence boosted/reduced in base a sentiment
- Nessun crash

Se fallisce:
- Non marcare fase VALIDATED
- Correggere
- Rieseguire checkpoint

---

## Errori comuni da evitare

- RSS feed fetch bloccante → usa timeout brevi
- Parse RSS fallisce su un feed → blocca tutto (deve skipare singolo feed)
- Sentiment calcolato su currency sbagliata (invertire base/quote)
- Strength sempre 0 o 1 invece di graduale
- Keyword case-sensitive invece di lowercase
- News duplicate da feed diversi non gestite
- Sentiment applicato anche quando `ENABLE_NEWS_SENTIMENT=false`
- Confidence > 1.0 dopo boost
- Non archiviare sample headlines per audit/debug

---

## Commit attesi

Alla fine della fase:

- `feat(config): add news sentiment parameters`
- `feat(models): add NewsItem and SentimentAnalysis`
- `feat(news): implement RSS feed aggregator`
- `feat(sentiment): implement keyword-based sentiment analysis`
- `feat(strategy): integrate sentiment into decision workflow`
- `refactor(scanner): add optional sentiment support`
- `test(news): add news aggregator tests`
- `test(sentiment): add sentiment analysis tests`
- `feat(phase-15): complete and validated`

---

## Note finali fase 15

Questa fase è **opzionale** ma fortemente consigliata per arricchire contesto decisionale senza costi o latenza significativa.

Al completamento:
- Hai sentiment layer deterministico, testabile, gratuito
- Integrato con strategia Python pura fase 14
- Può essere disabilitato senza rompere nulla
- Pronto per backtest con RSS storici archiviati

---

## Merge in main

Al completamento e validazione di **entrambe** Fase 14 e Fase 15:

```powershell
git checkout main
git merge feature/python-pure-strategy
git push origin main
```

Se solo Fase 14 completata e validata, puoi fare merge parziale e continuare fase 15 in branch.
