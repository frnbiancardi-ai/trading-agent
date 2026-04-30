# Fase 14 — Python Pure Strategy Engine (Deep Analysis Intraday)

## Obiettivo
Rimuovere completamente la dipendenza da Claude API per la generazione delle proposte di trade e sostituirla con un motore di strategia Python puro, deterministico e ottimizzato per operatività intraday su timeframe brevi (M10/M15).

La strategia deve eseguire deep analysis tecnica completa basata su:
- OHLC multi-barra (fino a 200 candele per simbolo)
- Indicatori tecnici (SMA, EMA, RSI, ATR già implementati)
- Pattern candlestick
- Support/Resistance dinamici
- Breakout quality e volume analysis
- Risk/Reward ratio

Requisiti critici:
- Latenza target < 500ms per simbolo analizzato
- Timeframe operativo principale: M10 o M15 (configurabile)
- Multi-symbol scanning su array di strumenti configurato in `.env`
- Completamente testabile e backtestabile
- Nessuna dipendenza da API esterne a pagamento per il signal layer
- Mantiene integrazione con `risk_engine.py`, `execution.py`, `scheduler.py`
- Claude API relegata solo a spiegazioni post-trade opzionali

Vincoli:
- Non rompere `risk_engine.py` ed `execution.py`
- Mantieni compatibilità con `scheduler.py` fase 13
- `EXECUTION_MODE=shadow` di default
- Tutto da `.env`, zero magic numbers
- Nessun TODO, pseudocodice o placeholder incompleto

---

## Branching strategy richiesto

Prima di iniziare questa fase:
1. Assicurati di essere sul branch `main` con tutto committato e pulito
2. Crea un nuovo branch dedicato:
```powershell
git checkout -b feature/python-pure-strategy
```
3. Tutto il lavoro di Fase 14 e Fase 15 avverrà su questo branch
4. Solo dopo validazione completa si mergerà in `main`

---

## File da creare o modificare

Questa fase tocca:

1. `config.py` — estendere con parametri strategia intraday
2. `models.py` — aggiungere modelli per setup tecnico e scan results
3. `strategy.py` — **NUOVO FILE** motore principale strategia
4. `indicators.py` — estendere con funzioni helper analisi avanzata
5. `scanner.py` — **NUOVO FILE** orchestrazione multi-symbol scan
6. `patterns.py` — **NUOVO FILE** pattern candlestick recognition
7. `claude_agent.py` — ridurre a solo `explain_last_trades` (opzionale)
8. `main.py` — modificare entry point per usare strategia Python invece di Claude
9. `scheduler.py` — aggiornare per chiamare scanner Python
10. `tests/test_strategy.py` — **NUOVO FILE**
11. `tests/test_scanner.py` — aggiornare o creare
12. `tests/test_patterns.py` — **NUOVO FILE**
13. `STATE.md` — solo tracking stato

---

## Parametri `.env` richiesti

Estendere `.env` con le seguenti variabili per strategia intraday:

```env
# === Strategia Intraday ===
STRATEGY_MODE=intraday
INTRADAY_SYMBOLS=EURUSD,GBPUSD,USDJPY,XAUUSD
INTRADAY_TIMEFRAME=M15
INTRADAY_LOOKBACK_BARS=200
INTRADAY_SCAN_TOP_N=3

# === Parametri Tecnici ===
MIN_ATR_PIPS=3
MAX_ATR_PIPS=50
MIN_TREND_STRENGTH=0.65
MIN_BREAKOUT_VOLUME_RATIO=1.3
MIN_RISK_REWARD_RATIO=1.5
MAX_RSI_OVERBOUGHT=75
MIN_RSI_OVERSOLD=25

# === Pattern Recognition ===
ENABLE_CANDLESTICK_PATTERNS=true
PATTERN_CONFIRMATION_BARS=2

# === Support/Resistance ===
SR_LOOKBACK_BARS=100
SR_TOLERANCE_PIPS=5

# === Timing Intraday ===
INTRADAY_START_HOUR=8
INTRADAY_END_HOUR=20
AVOID_MAJOR_NEWS_TIMES=true

# === Existing (da preservare) ===
EXECUTION_MODE=shadow
OPERATING_TIMEZONE=Europe/Rome
# ... altre variabili esistenti
```

**Note:**
- `INTRADAY_SYMBOLS` è un array separato da virgole
- `INTRADAY_TIMEFRAME` supporta `M10` o `M15` (ottimale per intraday)
- Tutti i parametri tecnici devono essere leggibili da `Config` senza hardcoding

---

## Requisiti per `config.py`

Estendere la classe `Config` per leggere tutte le nuove variabili sopra.

Aggiunte richieste:
- `STRATEGY_MODE: str`
- `INTRADAY_SYMBOLS: list[str]` — parsing con split su virgola e strip
- `INTRADAY_TIMEFRAME: str`
- `INTRADAY_LOOKBACK_BARS: int`
- `INTRADAY_SCAN_TOP_N: int`
- `MIN_ATR_PIPS: float`
- `MAX_ATR_PIPS: float`
- `MIN_TREND_STRENGTH: float`
- `MIN_BREAKOUT_VOLUME_RATIO: float`
- `MIN_RISK_REWARD_RATIO: float`
- `MAX_RSI_OVERBOUGHT: int`
- `MIN_RSI_OVERSOLD: int`
- `ENABLE_CANDLESTICK_PATTERNS: bool`
- `PATTERN_CONFIRMATION_BARS: int`
- `SR_LOOKBACK_BARS: int`
- `SR_TOLERANCE_PIPS: float`
- `INTRADAY_START_HOUR: int`
- `INTRADAY_END_HOUR: int`
- `AVOID_MAJOR_NEWS_TIMES: bool`

Default conservativi dove sensato.
Validazione: `INTRADAY_TIMEFRAME` deve essere in `['M1', 'M5', 'M10', 'M15', 'M30']`

---

## Requisiti per `models.py`

Aggiungere dataclass nuove senza rompere quelle esistenti:

### `TechnicalSetup`
```python
@dataclass
class TechnicalSetup:
    symbol: str
    timeframe: str
    setup_type: str  # 'READY', 'FORMING', 'NONE'
    direction: str | None  # 'BUY', 'SELL', None
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    confidence: float  # 0.0 - 1.0
    reason: str
    indicators: dict  # snapshot indicatori al momento analisi
    support_resistance: dict | None
```

### `ScanResult`
```python
@dataclass
class ScanResult:
    symbol: str
    trend_bias: str  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    momentum_bias: str
    volatility_state: str  # 'LOW', 'NORMAL', 'HIGH'
    spread_state: str  # 'ACCEPTABLE', 'WIDE'
    regime: str  # 'TREND', 'RANGE', 'BREAKOUT'
    candidate_score: float  # 0.0 - 1.0
    warnings: list[str]
```

### `DelayedFollowUpRequest` (se non già presente da fase 13)
```python
@dataclass
class DelayedFollowUpRequest:
    symbol: str
    timeframe: str
    delay_minutes: int
    reason: str
    focus_prompt: str
    created_at: datetime
    expires_at: datetime
    already_delayed: bool = False
```

### `StrategyOutcome`
```python
@dataclass
class StrategyOutcome:
    outcome_type: str  # 'TRADE', 'NO_TRADE', 'WAIT_FOLLOW_UP'
    proposal: TradeProposal | None
    follow_up: DelayedFollowUpRequest | None
    scan_results: list[ScanResult]
    timestamp: datetime
```

Tutte serializzabili via `dataclasses.asdict`.

---

## Requisiti per `indicators.py`

Estendere con funzioni helper analisi avanzata. Non rompere le funzioni esistenti (`sma`, `ema`, `rsi`, `atr`, `compute_all`).

Aggiunte richieste:

### 1. Trend strength
```python
def calculate_trend_strength(bars: list[dict], sma_fast: float, sma_slow: float) -> float:
    """
    Ritorna un valore 0.0-1.0 che rappresenta la forza del trend.
    - Separazione SMA veloce/lenta
    - Coerenza direzionale ultimi N close
    """
    pass
```

### 2. Support/Resistance dinamici
```python
def find_support_resistance(bars: list[dict], lookback: int = 100) -> dict:
    """
    Ritorna {'support': float, 'resistance': float} calcolati su swing high/low.
    """
    pass
```

### 3. Breakout quality
```python
def check_breakout_quality(bars: list[dict], sr: dict, volume_threshold: float = 1.3) -> str:
    """
    Ritorna 'CLEAN', 'WEAK', 'NONE'.
    Controlla se prezzo ha rotto support/resistance con volume adeguato.
    """
    pass
```

### 4. Average volume
```python
def avg_volume(bars: list[dict], period: int = 20) -> float:
    """
    Media semplice di tick_volume su N barre.
    """
    pass
```

### 5. Risk/Reward calculator
```python
def calculate_risk_reward(entry: float, sl: float, tp: float) -> float:
    """
    Ritorna rapporto reward/risk. Es: 2.0 significa R:R 1:2
    """
    pass
```

### 6. Divergence RSI/Price
```python
def check_rsi_divergence(bars: list[dict], rsi_values: list[float], lookback: int = 20) -> str:
    """
    Ritorna 'BULLISH_DIVERGENCE', 'BEARISH_DIVERGENCE', 'NONE'.
    Controlla divergenza classica tra price highs/lows e RSI.
    """
    pass
```

Tutti i return devono gestire edge case (liste vuote, valori None) in modo sicuro.

---

## Requisiti per `patterns.py` (NUOVO FILE)

Implementare riconoscimento pattern candlestick base in Python puro.

Pattern minimi richiesti:
- Hammer / Inverted Hammer
- Engulfing (bullish/bearish)
- Doji
- Pin Bar (bullish/bearish)

Struttura consigliata:
```python
def is_hammer(bar: dict) -> bool:
    """Riconosce pattern hammer (bullish reversal)"""
    pass

def is_engulfing(prev_bar: dict, current_bar: dict, direction: str) -> bool:
    """Riconosce engulfing bullish o bearish"""
    pass

def is_doji(bar: dict, tolerance: float = 0.1) -> bool:
    """Riconosce doji (indecisione)"""
    pass

def is_pin_bar(bar: dict, direction: str) -> bool:
    """Riconosce pin bar bullish/bearish"""
    pass

def scan_patterns(bars: list[dict], last_n: int = 5) -> list[dict]:
    """
    Scansiona ultimi N candele e ritorna pattern riconosciuti.
    Return: [{'pattern': 'hammer', 'bar_index': -2, 'direction': 'bullish'}, ...]
    """
    pass
```

Logica pattern:
- Hammer: long lower shadow (2x body), small body, no/small upper shadow
- Engulfing: body corrente ingloba completamente body precedente
- Doji: open ≈ close (tolleranza)
- Pin Bar: long wick opposto alla direzione, small body

---

## Requisiti per `strategy.py` (NUOVO FILE — CORE)

Questo è il cuore della fase 14. Deve sostituire `ClaudeAgent` per la generazione proposte.

### Struttura principale

```python
class IntradayStrategy:
    def __init__(self, cfg: Config, mt5_client: Mt5Client, logger):
        self.cfg = cfg
        self.mt5 = mt5_client
        self.log = logger

    def analyze_symbol(self, symbol: str, account_state: AccountState) -> TechnicalSetup:
        """
        Esegue deep analysis tecnica completa su un singolo simbolo.

        Workflow:
        1. Fetch OHLC (INTRADAY_LOOKBACK_BARS)
        2. Compute indicatori
        3. Find support/resistance
        4. Check trend strength
        5. Check breakout quality
        6. Scan candlestick patterns
        7. Calculate risk/reward
        8. Decide: READY / FORMING / NONE

        Return: TechnicalSetup
        """
        pass

    def identify_entry_setup(self, bars, indicators, sr, patterns) -> dict:
        """
        Logica decisionale core.

        Condizioni READY per BUY (esempio):
        - Trend strength > MIN_TREND_STRENGTH
        - Prezzo > SMA20 > SMA50
        - RSI tra 40-70 (non ipercomprato)
        - Breakout sopra resistance con volume > threshold
        - Pattern bullish presente (opzionale se ENABLE_CANDLESTICK_PATTERNS)
        - R:R > MIN_RISK_REWARD_RATIO

        Return: {'type': 'READY'/'FORMING'/'NONE', 'direction': 'BUY'/'SELL'/None, ...}
        """
        pass

    def build_trade_proposal(self, symbol, setup, bars, indicators, account_state) -> TradeProposal:
        """
        Costruisce TradeProposal da TechnicalSetup READY.

        - entry_price: ultimo close o ask/bid da tick
        - stop_loss: supporto - buffer o ATR-based
        - take_profit: R:R target
        - confidence: basata su forza segnali multipli
        - rationale: stringa italiana sintetica
        """
        pass

    def build_delayed_followup(self, symbol, delay_minutes, reason) -> DelayedFollowUpRequest:
        """
        Crea richiesta follow-up per setup FORMING.
        """
        pass
```

### Logica decisionale dettagliata richiesta

Per setup **READY BUY**:
1. `trend_strength > cfg.MIN_TREND_STRENGTH`
2. `close > sma_20 > sma_50` (trend rialzista confermato)
3. `rsi > cfg.MIN_RSI_OVERSOLD and rsi < cfg.MAX_RSI_OVERBOUGHT`
4. Breakout confermato sopra resistance con `volume_ratio > cfg.MIN_BREAKOUT_VOLUME_RATIO`
5. Se `ENABLE_CANDLESTICK_PATTERNS=true`, almeno un pattern bullish nelle ultime `PATTERN_CONFIRMATION_BARS` barre
6. `risk_reward > cfg.MIN_RISK_REWARD_RATIO`
7. ATR compreso tra `MIN_ATR_PIPS` e `MAX_ATR_PIPS`

Per setup **FORMING**:
- Trend strength > 0.6 ma breakout non ancora confermato
- Prezzo vicino a resistance (entro `SR_TOLERANCE_PIPS`)
- Volume normale ma non spike
→ Ritorna `DelayedFollowUpRequest(delay_minutes=30, reason="approaching resistance, waiting breakout")`

Per setup **NONE**:
- Trend debole o ambiguo
- RSI estremo (>75 o <25) senza conferme
- Spread troppo largo
- Volatilità fuori range

### Confidence scoring

La `confidence` deve essere calcolata combinando:
- Trend strength: 0-0.3
- Pattern match: 0-0.2
- Volume quality: 0-0.2
- Risk/reward ratio: 0-0.2
- Multi-timeframe alignment (opzionale): 0-0.1

Range finale: 0.0 - 1.0. Proponi solo se confidence >= 0.60.

---

## Requisiti per `scanner.py` (NUOVO FILE)

Orchestrazione multi-symbol scanning e ranking.

```python
class MultiSymbolScanner:
    def __init__(self, cfg: Config, mt5_client: Mt5Client, strategy: IntradayStrategy, logger):
        self.cfg = cfg
        self.mt5 = mt5_client
        self.strategy = strategy
        self.log = logger

    def light_scan(self, symbol: str) -> ScanResult | None:
        """
        Scan preliminare veloce per filtrare universo simboli.

        Workflow:
        1. Fetch solo 50 barre (veloce)
        2. Compute indicatori base
        3. Calcola score preliminare
        4. Filtra spread, volatilità, regime

        Return: ScanResult o None se scartato
        """
        pass

    def scan_universe(self, symbols: list[str]) -> list[ScanResult]:
        """
        Applica light_scan a tutti i simboli e ritorna top N candidati ordinati per score.
        """
        pass

    def deep_analyze_top_candidates(self, scan_results: list[ScanResult], account_state: AccountState) -> StrategyOutcome:
        """
        Esegue deep analysis sui top INTRADAY_SCAN_TOP_N candidati.

        Workflow:
        1. Per ogni candidato: strategy.analyze_symbol()
        2. Confronta setup trovati
        3. Seleziona il migliore (highest confidence)
        4. Return StrategyOutcome con proposta o NO_TRADE o WAIT_FOLLOW_UP
        """
        pass

    def calculate_scan_score(self, bars, indicators) -> float:
        """
        Score semplice 0.0-1.0 per ranking preliminare.

        Fattori:
        - Trend clarity (SMA separation)
        - RSI in zona operabile (non estremi)
        - ATR in range
        - Spread acceptable
        """
        pass
```

---

## Requisiti per `main.py`

Modificare entry point per usare strategia Python invece di Claude.

Nuovo workflow:
1. Inizializza `Config`, `logger`, `Mt5Client`
2. Inizializza `IntradayStrategy`
3. Inizializza `MultiSymbolScanner`
4. Inizializza `scheduler` (se fase 13 già implementata) oppure loop semplice
5. Ad ogni ciclo:
   - `scanner.scan_universe(cfg.INTRADAY_SYMBOLS)`
   - `scanner.deep_analyze_top_candidates(...)`
   - Se proposta → passa a `risk_engine.evaluate_trade` → `execution.run_once`
   - Log risultato in `trades.db`
6. Shutdown pulito

Compatibilità:
- Se `scheduler.py` fase 13 esiste, usarlo
- Altrimenti loop semplice con `time.sleep` ogni N minuti (configurable)

---

## Requisiti per `scheduler.py` (modifiche se già presente da fase 13)

Se fase 13 implementata:
- Sostituire chiamata a `ClaudeAgent.run_market_scan(...)` con `MultiSymbolScanner.scan_universe(...)` + `deep_analyze_top_candidates(...)`
- Mantenere logica follow-up ritardato
- Mantenere target giornaliero 5 decisioni
- Aggiornare slot timing per intraday: cicli più frequenti (ogni 1-2 ore invece di 3)

Se fase 13 non implementata:
- Implementare loop semplice con `time.sleep` o `schedule` library
- Ciclo ogni 30-60 minuti durante finestra intraday

---

## Requisiti per `claude_agent.py` (opzionale riduzione scope)

Opzione 1 (consigliata): **Mantieni solo `explain_last_trades`**
- Rimuovi `run_cycle`, `run_market_scan`, `build_tools` relativi a proposal
- Mantieni solo helper per spiegazione a posteriori
- Claude diventa strumento di analisi post-trade, non decision-maker

Opzione 2: **Commenta tutto** e tieni file per riferimento storico

Opzione 3: **Elimina file** se sicuro di non volerlo più

Decisione a scelta durante implementazione, ma `explain_last_trades` può restare utile.

---

## Test richiesti

### `tests/test_strategy.py`

Casi minimi:
- `test_analyze_symbol_ready_buy`: setup tecnico chiaro bullish → TechnicalSetup.setup_type == 'READY'
- `test_analyze_symbol_ready_sell`: setup tecnico chiaro bearish → TechnicalSetup.setup_type == 'READY'
- `test_analyze_symbol_forming`: setup in formazione → TechnicalSetup.setup_type == 'FORMING'
- `test_analyze_symbol_none`: mercato ambiguo → TechnicalSetup.setup_type == 'NONE'
- `test_build_trade_proposal_valid`: proposta valida con SL/TP corretti
- `test_confidence_calculation`: score ragionevole 0.6-0.9
- Mock `Mt5Client` per non dipendere da connessione reale

### `tests/test_scanner.py`

Casi minimi:
- `test_light_scan_filters_low_quality`: simboli con spread alto o volatilità fuori range vengono scartati
- `test_scan_universe_returns_top_n`: ritorna max INTRADAY_SCAN_TOP_N candidati ordinati
- `test_deep_analyze_selects_best`: tra più setup READY, sceglie quello con confidence maggiore
- `test_no_trade_if_all_none`: se tutti i setup sono NONE → StrategyOutcome.outcome_type == 'NO_TRADE'

### `tests/test_patterns.py`

Casi minimi:
- `test_is_hammer`: riconosce hammer pattern
- `test_is_engulfing_bullish`: riconosce engulfing bullish
- `test_is_doji`: riconosce doji
- `test_scan_patterns_multiple`: trova pattern multipli in sequenza barre

Mock dati OHLC sintetici.

---

## Checkpoint di fase

Comandi di checkpoint:

```powershell
pytest tests/test_strategy.py -v
pytest tests/test_scanner.py -v
pytest tests/test_patterns.py -v
pytest tests/test_indicators.py -v
```

Tutti devono passare.

Validazione manuale:
```powershell
python main.py
```

Deve eseguire almeno un ciclo completo in modalità shadow:
1. Scan universo simboli
2. Deep analysis su top candidati
3. Proposta valida o NO_TRADE
4. Log in `trades.db`
5. Nessun crash, nessuna eccezione non gestita

Se fallisce:
- Non marcare fase VALIDATED
- Correggere file responsabile
- Rieseguire checkpoint

---

## Errori comuni da evitare

- Indicatori che ritornano None non gestiti → crash in strategy
- OHLC fetch fallisce ma non c'è retry/fallback
- Support/Resistance calcolati su troppo poche barre → valori inaffidabili
- Confidence hardcoded invece che calcolata da scoring
- Pattern recognition troppo rigido → zero match su dati reali
- Non verificare posizioni aperte prima di proporre nuovo trade
- Timeframe hardcoded invece che letto da `cfg.INTRADAY_TIMEFRAME`
- Array `INTRADAY_SYMBOLS` non parsato correttamente (trailing spaces, case sensitivity)
- Risk/Reward ratio calcolato invertito
- Breakout confermato senza controllo volume
- Non gestire simboli non disponibili in MT5 (crash invece di skip)

---

## Commit attesi

Alla fine della fase, a test verdi:

- `feat(config): add intraday strategy parameters`
- `feat(models): add TechnicalSetup, ScanResult, StrategyOutcome`
- `feat(indicators): add trend strength, SR, breakout, divergence helpers`
- `feat(patterns): add candlestick pattern recognition`
- `feat(strategy): implement IntradayStrategy core engine`
- `feat(scanner): implement MultiSymbolScanner orchestration`
- `refactor(main): switch to Python pure strategy from Claude agent`
- `refactor(scheduler): update to use MultiSymbolScanner`
- `test(strategy): add comprehensive strategy tests`
- `test(scanner): add scanner and ranking tests`
- `test(patterns): add pattern recognition tests`
- `feat(phase-14): complete and validated`

---

## Note finali fase 14

Questa fase è **obbligatoria** e propedeutica alla fase 15 (RSS). Completare e validare prima di procedere.

Al completamento:
- Hai un motore strategia Python puro, veloce (<500ms), testabile
- Nessuna dipendenza da LLM nel loop critico
- Pronto per operatività intraday su M10/M15
- Compatibile con `risk_engine`, `execution`, `scheduler`
- Claude opzionale solo per explain
