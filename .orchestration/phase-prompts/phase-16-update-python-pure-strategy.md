

## Prompt completo per Claude Code – Phase 16 (H24 Strategy Update)

Voglio che lavori su un progetto già esistente, strutturato per fasi (phase‑02 config/models, phase‑04 risk_engine, phase‑06 execution, phase‑07 indicators, phase‑08 claude_agent, phase‑09 mcp_server, phase‑14 strategy intraday). I file di specifica delle fasi precedenti sono già presenti (phase‑02‑config‑models.md, phase‑04-risk-engine.md, phase‑06-execution.md, phase‑07-indicators.md, phase‑08-claude-agent.md, phase‑09-mcp-server.md, phase‑14-strategy.md o equivalente).

### Obiettivo Phase 16 – Update della Phase 14 per funzionamento quasi H24

Aggiornare la strategia Python pura (IntradayStrategy + MultiSymbolScanner) e lo scheduler interno per:

- Funzionare in modo continuo 24/5: da apertura FX domenica sera a chiusura venerdì sera, se lo script Python è in esecuzione.
- Mantenere logica intraday: **mai posizioni overnight** (nessun trade lasciato aperto oltre la fine della finestra operativa giornaliera).
- Fare cicli frequenti (ogni 5–15 minuti) con il **primo ciclo 5 minuti dopo l’avvio**.
- Usare un **scheduler interno Python** (loop infinito e controlli orari), non cron/Task Scheduler esterni.
- Avere un controllo rischio basato su bilancio/kill‑switch giornaliero + controllo rolling (drawdown su finestra mobile) in modo coerente con il risk_engine esistente.
- Gestire h24 con carico ragionevole su un PC di casa (Asus N551JX), facendo deep analysis solo sui top N candidati per ciclo.
- Integrare in futuro feed news via RSS (fase 15): per ora prevedere gli hook, non l’implementazione.

In più, crea:

- un **nuovo file di specifica Phase 16** che documenta tutte queste modifiche,

***

### Vincoli e contesto già definiti

- Config, models, risk_engine, execution, indicators, claude_agent e mcp_server sono già implementati secondo le specifiche delle rispettive fasi. (6,8,9,2,4,7)
- Phase 14 ha introdotto:
    - `IntradayStrategy` in `strategy.py`.
    - `MultiSymbolScanner` in `scanner.py`.
    - Nuove dataclass in `models.py`: `TechnicalSetup`, `ScanResult`, `DelayedFollowUpRequest`, `StrategyOutcome`.
    - Nuovi parametri in `config.py` per la strategia intraday.
- risk_engine ed execution non devono essere rotti:
    - risk_engine è l’unico cancello di approvazione deterministico (`evaluate_trade_proposal`).
    - execution (`run_once`) è l’unico punto che chiama MT5 per gli ordini, rispettando EXECUTION_MODE.
- EXECUTION_MODE=shadow di default; paper/live già gestiti da execution/risk_engine.

***

### Decisioni specifiche (scelte dall’utente) da implementare

1. **Orari e sessioni**

- Operatività: **24/5**, con script sempre attivo da domenica sera a venerdì sera.
- Logica intraday: **nessuna posizione overnight**; a fine finestra operativa giornaliera non devono restare posizioni aperte generate da questa strategia.
- Weekend: logica trading spenta (niente scan operative, niente trade) tra chiusura venerdì e riapertura domenica; eventuali test/dry‑run devono essere possibili a mercati chiusi (vedi Test weekend).

2. **Scheduling e frequenza cicli**

- Scheduler interno Python, nessun sistema esterno.
- Primo ciclo: **5 minuti dopo l’avvio** dello script.
- Poi intervallo configurabile: usa una variabile `.env` tipo `INTRADAY_SCAN_INTERVAL_MINUTES` (default 15) letta da `Config`.
- Deep analysis solo sui **top N** candidati (`INTRADAY_SCAN_TOP_N`) ogni ciclo, anche di notte.

3. **News e finestre “no‑trade”**

- `AVOID_MAJOR_NEWS_TIMES=true` indica che non si devono aprire nuovi trade durante finestre di news importanti.
- L’integrazione reale via RSS arriverà in Fase 15; ora serve:
    - un hook/metodo `StrategyEnvironment.is_news_window(now_local: datetime) -> bool`,
    - prima implementazione minimale (può restituire sempre False o usare solo config fisse), ma il loop e la strategia devono rispettare il flag:
        - se `is_news_window` True: nessuna nuova proposal eseguita (no ordini), ma light scan / logging continuano.

4. **Rischio, posizioni multiple e rolling drawdown**

- Nessun limite hardcoded sul numero totale di posizioni aperte; la limitazione deve derivare da:
    - il risk_engine (size per trade, risk per trade, limiti SL, margine, MAX_DAILY_DRAWDOWN_PERCENT).
    - un controllo aggiuntivo sulla **somma del rischio potenziale**: se tutte le posizioni aperte in giornata andassero a SL, il drawdown non deve superare MAX_DAILY_DRAWDOWN_PERCENT.
- Implementare un helper a livello di strategy/scheduler che:
    - legge posizioni aperte e relativi SL,
    - stima il loss potenziale totale (in percentuale su starting balance/day o su un riferimento coerente),
    - valuta se aggiungere il nuovo trade violerebbe il vincolo di drawdown massimo giornaliero.
    - Se sì: il nuovo trade non viene proposto (StrategyOutcome.outcome_type = 'NO_TRADE' con reason chiaro), oppure viene passato al risk_engine con un flag per rifiuto esplicito.
- Posizioni multiple sullo stesso simbolo:
    - consentiti add‑on / scale‑in:
        - se esiste già una posizione su un simbolo, nuovi segnali possono portare ad aprire ulteriori posizioni nella stessa direzione, ma sempre nel rispetto del vincolo di drawdown potenziale.
    - Distinguere chiaramente nei log/rationale quando un trade è un add‑on vs una nuova posizione iniziale.
- Kill switch:
    - mantenere il kill switch giornaliero su balance nel risk_engine come definito in Phase 4.
    - introdurre un controllo **rolling** a livello strategy/scheduler (es. su 24h o su finestra configurabile) che, se superato, mette la strategia in modalità `NO_TRADE` fino a reset (nuovo giorno o intervento umano).

5. **Scheduler interno e process manager soft**

- `scheduler.py` deve:
    - leggere ad ogni ciclo `PAUSE_TRADING` da Config:
        - se True, non esegue deep analysis né execution, ma continua heart‑beat e magari light scan.
    - mantenere uno stato in SQLite (es. tabella `scheduler_state` con:
        - timestamp ultimo ciclo avviato/completato,
        - durata ultimo ciclo,
        - outcome (`OK`, `NO_TRADE`, `ERROR`, `PAUSED`),
        - ultimo errore (tipo, messaggio),
        - eventuali contatori (NO_TRADE consecutivi, errori consecutivi).
    - in caso di overrun (un ciclo dura troppo e invade lo slot successivo), saltare uno slot, non creare cicli sovrapposti.
    - in caso di errori di ambiente (MT5 down, rete, eccezioni non critiche), loggare e segnare `ERROR`, ma non tentare retry aggressivi nello stesso slot: attendere il prossimo intervallo.

6. **Set simboli e volatilità di notte**

- Usare sempre lo stesso set `INTRADAY_SYMBOLS` per giorno e notte.
- In condizioni di bassa liquidità (tipicamente notturne):
    - applicare soglie più stringenti su ATR, spread, regime (usando già i campi di `ScanResult` e parametri `MIN_ATR_PIPS`, `MAX_ATR_PIPS`, etc.).
    - in caso di condizioni non accettabili:
        - ritornare `StrategyOutcome.outcome_type = 'NO_TRADE'` con `reason` esplicito (es. spread troppo largo, ATR troppo basso, regime non chiaro).

7. **Logging, pausa e heart‑beat**

- Logging:
    - rotazione log **settimanale** (non giornaliera) per logger principale.
    - nessun log operativo su stdout (compatibile con MCP stdio), solo su file/stderr.
- Flag di pausa:
    - aggiungere in `.env` e `Config` un flag `PAUSE_TRADING: bool` (default False).
    - se `PAUSE_TRADING=true`, la strategia non deve aprire nuovi trade, ma può comunque:
        - fare light scan,
        - aggiornare heart‑beat,
        - eventualmente valutare posizioni aperte ma senza eseguire chiusure automatiche (comportamento da definire: per semplicità puoi evitare azioni in PAUSE).
- Heart‑beat:
    - creare una tabella `heartbeat` in SQLite che registra:
        - timestamp ultimo ciclo iniziato/completato,
        - outcome (`OK`, `NO_TRADE`, `ERROR`, `PAUSED`),
        - eventualmente contatori.
    - utile per monitorare dall’esterno se il bot è vivo o bloccato.

***

### Gestione posizioni aperte a ogni ciclo (nuovo requisito)

Integra i seguenti punti nella Phase 16:

#### A. Gestione posizioni aperte (prima di nuovi trade)

Prima di valutare nuovi setup e nuove proposte di trade, ogni ciclo dello scheduler deve:

1. Recuperare la lista aggiornata di posizioni aperte (`AccountState.open_positions`) tramite `Mt5Client` / `AccountState` (già definiti in models/mt5_client).
2. Per ogni posizione aperta su simboli in `INTRADAY_SYMBOLS`, eseguire una **mini‑analisi di mantenimento** usando la strategia:
    - usare `IntradayStrategy.analyze_symbol(symbol, account_state)` o un helper dedicato (es. `evaluate_open_position(symbol, position, account_state)`),
    - questa analisi deve verificare se il contesto tecnico è diventato **negativo** rispetto alla direzione della posizione (trend, momentum, indicatori, pattern).
3. Se la nuova analisi tecnica è **negativa** e la posizione è attualmente in **profitto ragionevole** (non in loss):
    - chiudere la posizione per proteggere il profitto ed evitare la potenziale inversione.

La definizione di “profitto ragionevole” deve essere parametrica:
    - aggiungi in `.env` / `Config` una variabile tipo `MIN_PROTECT_PROFIT_R_MULTIPLIER` (float, default es. 1.0–1.5), interpretata come:
        - `R` = distanza entry→SL,
        - chiudi anticipatamente se profitto attuale ≥ `MIN_PROTECT_PROFIT_R_MULTIPLIER * R`.
4. Se la posizione è in leggero loss ma il contesto non è chiaramente negativo (es. trend ancora coerente), mantienila; SL/TP restano gestiti da risk_engine/execution.

Questa gestione posizioni **va eseguita prima** di proporre nuovi trade, così la valutazione sul drawdown potenziale è aggiornata allo stato reale del portafoglio.

***

### Metodo esplicito per chiusura posizione in Mt5Client (nuovo requisito)

Integra nella Phase 16 (sezione `mt5_client.py` / execution):

- Aggiungi in `mt5_client.py` un metodo dedicato alla chiusura di una posizione esistente, senza aprire una posizione opposta:

```python
class Mt5Client:
    ...

    def close_position(self, position_id: int) -> OrderResult:
        """
        Chiude esplicitamente la posizione con id dato, usando l'API MetaTrader5 corretta
        (order_send con campo 'position' valorizzato, non aprendo una posizione opposta).
        Ritorna un OrderResult coerente con models.OrderResult.
        """
        ...
```

- Implementazione (seguendo la doc ufficiale MetaTrader5 Python):
    - usa `mt5.order_send` con:
        - `action = mt5.TRADE_ACTION_DEAL`,
        - `position = position_id`,
        - `type` BUY/SELL opposto alla direzione originale,
        - `volume` uguale alla size residua della posizione,
        - `price` = bid/ask corrente a seconda della direzione.
    - gestisce retry e logging come `send_order`,
    - ritorna `OrderResult(success, order_id, error_message)`.
- Questo metodo deve essere usato da:
    - la logica di gestione posizioni aperte nello scheduler,
    - eventuali altri punti del codice dove serve una chiusura esplicita.

***

### Fix opzionale del server MCP per chiusura posizione

Se il server MCP (`mcp_server.py`) è ancora in uso per l’esecuzione ordini, aggiungi:

1. Un nuovo tool MCP:
    - nome: `close_position`,
    - `inputSchema` JSON con:
        - `position_id: int`,
    - in `@server.call_tool`, questo tool:
        - chiama `mt5.close_position(position_id)`,
        - ritorna un `TextContent` con JSON del `OrderResult`.
2. Deprecare/correggere eventuali tool usati per chiudere posizioni aprendo trade opposti:
    - se esiste un tool che “chiude” in quel modo, rinominalo (es. `reverse_position`) e usa `close_position` per la chiusura reale.
3. Mantieni compatibilità MCP stdio (niente log su stdout, solo stderr/file).

Se invece nel progetto attuale non usi più MCP per l’esecuzione ordini, puoi ignorare questo punto e concentrarti solo sul metodo Python puro in `Mt5Client`.

***

### Ordine delle operazioni nel ciclo di scheduler (aggiornato)

Nella descrizione di `scheduler.py` inserisci il seguente ordine per ogni ciclo:

1. Heart‑beat iniziale:
    - registra in SQLite l’avvio del ciclo (`heartbeat` + `scheduler_state` con stato "RUNNING", timestamp).
2. Lettura `Config` e flag:
    - verifica `PAUSE_TRADING`,
    - verifica orario (giorno della settimana, finestra operativa giornaliera) e eventuale `is_news_window(now_local)`.
3. Lettura `AccountState` + posizioni aperte via `Mt5Client`.
4. **Gestione posizioni aperte**:
    - per ogni posizione su `INTRADAY_SYMBOLS`:
        - valuta il contesto tecnico con strategy,
        - se contesto negativo + profitto ≥ soglia configurata → chiudi posizione con `Mt5Client.close_position`.
5. Dopo aggiornamento posizioni:
    - se `PAUSE_TRADING` o news window o fuori orario intraday → salta la parte di nuovi trade, aggiorna `heartbeat` con outcome `PAUSED`/`NO_TRADE` e passa a sleep.
    - altrimenti:
        - `scanner.scan_universe(cfg.INTRADAY_SYMBOLS)`,
        - `scanner.deep_analyze_top_candidates(..., account_state)` → `StrategyOutcome`.
6. Se `StrategyOutcome.outcome_type == 'TRADE'`:
    - passa la `TradeProposal` a `risk_engine.evaluate_trade_proposal`,
    - se approvata → `execution.run_once(...)` (rispettando EXECUTION_MODE).
7. Aggiorna `heartbeat` + `scheduler_state` con outcome finale (`OK`, `NO_TRADE`, `ERROR`, `PAUSED`) e timestamp fine ciclo.
8. In caso di eccezioni:
    - cattura, logga, marca `ERROR` in SQLite,
    - non ritentare nello stesso slot, passa direttamente alla fase di sleep per il prossimo ciclo.

***

### Modifiche richieste nel codice (riassunto puntuale)

1. `config.py`
    - Aggiungi e gestisci:
        - `INTRADAY_SCAN_INTERVAL_MINUTES: int` (default 15).
        - `PAUSE_TRADING: bool` (default False).
        - `MIN_PROTECT_PROFIT_R_MULTIPLIER: float` (default 1.0–1.5).
        - Parametri per rolling drawdown (se separati da MAX_DAILY_DRAWDOWN_PERCENT).
    - Conferma/integra tutte le variabili intraday già previste in Phase 14.
2. `models.py`
    - Conferma/aggiusta `TechnicalSetup`, `ScanResult`, `DelayedFollowUpRequest`, `StrategyOutcome`.
    - Se utile, puoi aggiungere campi come `max_potential_drawdown_percent` o `drawdown_violation: bool` in `StrategyOutcome`.
3. `indicators.py`
    - Nessun cambiamento concettuale extra oltre Phase 14, ma puoi riusare helper per trend/ATR/spread per la gestione posizioni aperte.
4. `strategy.py` (IntradayStrategy)
    - Integra:
        - controllo news window e finestra oraria,
        - controllo drawdown potenziale prima di proporre un nuovo trade,
        - supporto add‑on/scale‑in,
        - helper per valutare posizioni aperte (`evaluate_open_position` o simili), usato dallo scheduler.
5. `scanner.py` (MultiSymbolScanner)
    - Garantire che `scan_universe` e `deep_analyze_top_candidates`:
        - usino `INTRADAY_SCAN_TOP_N`,
        - ricevano `AccountState` aggiornato,
        - producano `StrategyOutcome` adeguato per logging/heart‑beat.
6. `mt5_client.py`
    - Implementa `close_position(position_id: int) -> OrderResult` usando `mt5.order_send` con il campo `position` corretto, non apertura opposta.
7. `scheduler.py`
    - Implementa loop h24 interno con ordine delle operazioni descritto sopra.
    - Integra `PAUSE_TRADING`, gestione posizioni aperte, rolling drawdown, heart‑beat SQLite, gestione errori.
8. `main.py`
    - Inizializza `Config`, `logger`, `Mt5Client`, `IntradayStrategy`, `MultiSymbolScanner`, `scheduler`.
    - Chiama il loop scheduler (es. `scheduler.run_forever()`).
    - Gestisce lifecycle MT5 (initialize/login/shutdown) come in Phase 6.
9. `mcp_server.py` (opzionale)
    - Aggiungi tool `close_position` se MCP è ancora usato per execution, come descritto.

***

### Test e validazione (inclusi test weekend)

Aggiorna/aggiungi test:

- `tests/test_strategy.py`:
    - `test_drawdown_violation_no_trade`: se nuovo trade eccede drawdown potenziale massimo → NO_TRADE.
    - `test_protect_profit_on_negative_context`: posizione in profitto, contesto tecnico negativo → flag di chiusura (o controllo che la strategia segnali chiusura).
- `tests/test_scanner.py`:
    - `test_deep_analyze_respects_pause_and_news_window`.
- Eventuale `tests/test_scheduler.py`:
    - simula uno o due cicli, controllando l’ordine delle operazioni, la gestione errori e le scritture in `heartbeat`/`scheduler_state`.

Test manuali weekend:

- Prevedi uno script (es. in `scripts/`) o una modalità `DRY_RUN=true` in `.env` che:
    - esegue il ciclo completo senza toccare MT5 live (nessun `send_order`, nessun `close_position` reale),
    - logga solo le azioni che **sarebbero** eseguite.
- Documenta in `phase-16-h24-strategy-update.md`:
    - quali comandi lanciare nel weekend (es. `DRY_RUN=true python main.py` o uno script di test),
    - quali log/output aspettarsi per considerare la logica corretta.

***

### Nuovi file di documentazione

1. `phase-16-h24-strategy-update.md`
    - Descrizione completa delle modifiche a config, strategy, scanner, mt5_client, scheduler, main.
    - Spiegazione della gestione posizioni aperte, chiusura protettiva in profitto, vincoli di drawdown e logica add‑on.
    - Workflow del ciclo h24.
    - Test automatizzati e manuali (weekend/dry‑run).
***

Stile generale:

- Nessun TODO/pseudocodice: implementazione completa.
- No numeri magici: tutto da `.env`/Config.
- Messaggi di log e motivazioni in italiano, come nelle fasi precedenti.
- Non rompere test e contract di risk_engine, execution e mcp_server esistenti.

Usa questo brief come “Phase 16 – H24 Strategy Update” e implementa tutte le modifiche necessarie.
