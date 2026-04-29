# Fase 13 — Scheduled Orchestrator

## Obiettivo
Evolvere l'applicazione per eseguire il ciclo da `main.py` in modo continuo e controllato durante la finestra operativa, integrando in un unico flusso:
- market scanner multi-symbol;
- possibilità per l'agente di chiedere un solo rinvio temporaneo su un simbolo promettente;
- riesecuzione mirata dopo il ritardo richiesto;
- prevenzione delle sovrapposizioni tra job pianificati;
- target giornaliero: somma di trade finali e no-trade finali pari a 5 entro fine giornata operativa.

La finestra operativa deve essere:
- lunedì–venerdì
- dalle 08:00 alle 22:00 (timezone configurata in `.env`).

Il ciclo ordinario deve partire ogni 3 ore nella finestra operativa, in modo da lasciare spazio ai follow-up fino a 2 ore senza sovrapposizioni.
Slot ordinari consigliati: **08:00, 11:00, 14:00, 17:00, 20:00**.

Vincoli generali:
- nessun bypass del risk engine;
- `EXECUTION_MODE=shadow` di default durante sviluppo/test;
- un candidato può essere ritardato al massimo una volta;
- il ritardo massimo consentito è 120 minuti;
- nessuna sovrapposizione di più richieste concorrenti sullo stesso orchestratore;
- niente output su stdout nei componenti MCP;
- nessun TODO, pseudocodice o placeholder incompleto nei file creati.

---

## File da creare o modificare

Questa fase tocca i seguenti file del progetto:

1. `config.py`
2. `models.py`
3. `prompts/system_prompt_scanner.txt`
4. `prompts/context_template_scanner.txt`
5. `claude_agent.py`
6. `scheduler.py`
7. `main.py`
8. `execution.py` (solo se servono piccoli adattamenti di log/metadata)
9. `tests/test_scheduler.py`
10. `tests/test_daily_orchestrator.py`
11. `STATE.md` (solo per tracking stato, mai per specifiche tecniche)

L'orchestrator deve procedere **micro-step per micro-step**, aggiornando `STATE.md` dopo ogni file completato come da prompt root.

---

## Parametri `.env` richiesti

Questa fase introduce/usa i seguenti parametri, che devono essere letti da `.env` via `Config`, senza magic numbers nel codice.

### Nuove variabili

```env
EXECUTION_MODE=shadow
OPERATING_TIMEZONE=Europe/Rome
OPERATING_START_HOUR=8
OPERATING_END_HOUR=22
OPERATING_WEEKDAYS=0,1,2,3,4
MAIN_CYCLE_HOURS=3
DAILY_TARGET_DECISIONS=5
MAX_DELAY_MINUTES=120
MAX_SYMBOLS_TO_DEEPEN=3
FOLLOWUP_ENABLED=true
SCHEDULER_POLL_SECONDS=5
```

Significato atteso:
- `EXECUTION_MODE`: deve restare `shadow` di default durante sviluppo e test.
- `OPERATING_TIMEZONE`: timezone usata per finestra operativa e scheduler.
- `OPERATING_START_HOUR`: ora di inizio finestra, inclusiva.
- `OPERATING_END_HOUR`: ora di fine finestra; gli slot ordinari devono restare coerenti con 08, 11, 14, 17, 20.
- `OPERATING_WEEKDAYS`: giorni consentiti, con convenzione Python `0=Monday ... 4=Friday`.
- `MAIN_CYCLE_HOURS`: intervallo dei cicli ordinari, fissato a 3 ore.
- `DAILY_TARGET_DECISIONS`: numero target di decisioni finali in una giornata.
- `MAX_DELAY_MINUTES`: attesa massima che l'agente può richiedere per un follow-up (minimo > 0, massimo 120).
- `MAX_SYMBOLS_TO_DEEPEN`: numero massimo di simboli da approfondire dopo lo scan preliminare.
- `FOLLOWUP_ENABLED`: abilita/disabilita la logica di follow-up ritardato.
- `SCHEDULER_POLL_SECONDS`: frequenza del loop di servizio, solo tecnica, non sostitutiva dello scheduler principale.

Se alcune variabili esistono già in `config.py`, riusarle ed evitare duplicazioni.

---

## Requisiti per `config.py`

Estendere `Config` per esporre i nuovi parametri sopra, tutti letti da `.env`.

Requisiti:
- valori con default coerenti con questa fase (shadow, 08–22, 3 ore, 5 decisioni, 120 minuti);
- nessun valore hardcodato sparso in altre parti del codice;
- validazione minima: clamp o errore chiaro se `MAX_DELAY_MINUTES` > 120 o `MAIN_CYCLE_HOURS` non è positivo.

---

## Requisiti per `models.py`

Aggiungere modelli semplici e serializzabili, ad esempio:

- `DelayedFollowUpRequest`
- `AgentCycleOutcome`
- `DailyRunState`

### `DelayedFollowUpRequest`

Campi minimi richiesti:
- `symbol: str`
- `timeframe: str`
- `delay_minutes: int`
- `reason: str`
- `focus_prompt: str`
- `created_at: datetime`
- `expires_at: datetime`
- `already_delayed: bool`

### `AgentCycleOutcome`

Deve rappresentare tre esiti:
- trade proposal
- no trade
- wait/follow-up requested

Struttura suggerita:
- `outcome_type: Literal["TRADE", "NO_TRADE", "WAIT_FOLLOW_UP"]`
- `proposal: TradeProposal | None`
- `follow_up: DelayedFollowUpRequest | None`
- metadati utili (timestamp, note sintetiche).

### `DailyRunState`

Responsabilità:
- tracciare il numero di decisioni finali della giornata;
- distinguere opportunità con follow-up da quelle concluse direttamente.

Campi minimi:
- `date: date`
- `decisions_count: int`
- eventuali contatori distinti per `TRADE` vs `NO_TRADE`.

---

## Requisiti per i prompt scanner

### `prompts/system_prompt_scanner.txt`

Aggiornare il prompt scanner per riflettere la nuova fase.

Deve imporre che a ogni ciclo l'agente:
1. controlli sempre account state, free margin e posizioni aperte;
2. tenga conto delle posizioni aperte già presenti prima di cercare nuove opportunità;
3. possa decidere tre esiti:
   - proporre un trade,
   - chiudere con `NO_TRADE`,
   - richiedere un follow-up ritardato una sola volta;
4. se richiede attesa, specifichi ritardo in minuti e scenario da ricontrollare;
5. non richieda attese oltre 120 minuti;
6. al follow-up si concentri prioritariamente sul simbolo e sullo scenario salvati;
7. non proponga mai più di un trade per ciclo.

Il prompt deve continuare a vietare:
- più di un trade per ciclo;
- più di un delay per opportunità;
- operatività in condizioni di mercato ambigue.

### `prompts/context_template_scanner.txt`

Aggiornare il context template per includere placeholder espliciti almeno per:

- `{candidate_symbols}`
- `{timeframe}`
- `{now_local}`
- `{execution_mode}`
- `{min_sl_pips}`
- `{max_sl_pips}`
- `{max_symbols_to_deepen}`
- `{balance}`
- `{equity}`
- `{free_margin}`
- `{open_positions_count}`
- `{open_positions_summary}`
- `{followup_mode}` (true/false)
- `{followup_symbol}`
- `{followup_delay_minutes}`
- `{followup_focus_prompt}`

Comportamento richiesto:
- se `followup_mode` è false, il ciclo è ordinario e deve fare market scan completo;
- se `followup_mode` è true, il ciclo deve dare priorità al simbolo e allo scenario richiesti nel follow-up.

---

## Requisiti per `claude_agent.py`

Estendere il workflow scanner per consentire anche una decisione di attesa strutturata.

Nuovo comportamento richiesto:

1. L'agente esegue market scan multi-symbol.
2. L'agente valuta tre possibili esiti:
   - `TRADE`: ritorna una `TradeProposal`;
   - `NO_TRADE`: nessuna proposta;
   - `WAIT_FOLLOW_UP`: ritorna un `DelayedFollowUpRequest`.
3. Se l'agente chiede attesa, deve restituire dati strutturati con almeno:
   - simbolo,
   - delay in minuti,
   - motivazione sintetica,
   - focus prompt / scenario key da ricontrollare.

Vincoli specifici:
- ritardo minimo sensato > 0;
- ritardo massimo 120 minuti;
- un simbolo non può essere ritardato più di una volta nella stessa opportunità;
- al follow-up si analizza prioritariamente il simbolo richiesto e lo scenario memorizzato;
- se al follow-up non c'è edge, l'esito finale è `NO_TRADE`.

A ogni avvio di ciclo l'agente deve:
- leggere sempre lo stato account aggiornato;
- verificare sempre le posizioni aperte;
- tenerne conto nella decisione finale.

Non introdurre loop infiniti: il controllo dei cicli multipli è responsabilità dello scheduler.

---

## Requisiti per `scheduler.py`

Creare un modulo di orchestrazione con responsabilità chiare.

Responsabilità principali:
- orchestratore principale della giornata;
- registrazione job ricorrente nella finestra operativa;
- registrazione job one-shot per follow-up posticipati;
- prevenzione sovrapposizioni;
- tracking delle decisioni giornaliere.

Comportamento richiesto:

- eseguire cicli solo lun–ven dalle 08:00 alle 22:00;
- pianificare i cicli ordinari ogni 3 ore (slot 08, 11, 14, 17, 20);
- non avviare un nuovo ciclo se uno è già in corso;
- non avviare un ciclo ordinario se esiste un follow-up che cadrebbe in conflitto temporale;
- consentire un solo follow-up per opportunità;
- contare come decisione giornaliera sia `TRADE` sia `NO_TRADE` finale;
- non contare come decisione finale il solo stato di attesa;
- a fine giornata la somma di trade e no-trade finali deve essere 5;
- se il target 5 è già raggiunto, non aprire nuovi cicli ordinari quel giorno, salvo cleanup tecnico.

I follow-up devono usare trigger one-shot (es. `date` di APScheduler) e i cicli principali trigger ricorrenti (`cron` o equivalente robusto).

---

## Requisiti per `main.py`

`main.py` deve diventare il punto di ingresso dell'orchestratore continuo.

Comportamento atteso:
- inizializza config, logger, MT5 client, agent e scheduler;
- avvia il servizio di scheduling;
- gestisce shutdown pulito;
- non esegue ordini reali di default;
- evita doppie inizializzazioni di risorse.

Deve essere possibile lanciare il progetto in modalità continua con:

```powershell
python main.py
```

---

## Policy giornaliera richiesta

Definire chiaramente nel codice la nozione di "decisione giornaliera":

- conta 1 se il ciclo termina con trade approvato o rifiutato dal risk engine ma formalmente proposto;
- conta 1 se il ciclo termina con `NO_TRADE` finale;
- non conta 1 quando l'agente chiede solo di aspettare: il follow-up eredita e chiude quella opportunità;
- una stessa opportunità con attesa e follow-up successivo conta al massimo 1 decisione finale.

L'obiettivo operativo di giornata è arrivare a 5 decisioni finali entro la fine della finestra operativa.

---

## Test richiesti

### `tests/test_scheduler.py`

Casi minimi:
- il job ricorrente viene pianificato solo nei giorni/orari consentiti;
- il job ricorrente rispetta i 5 slot giornalieri 08, 11, 14, 17, 20;
- il follow-up one-shot viene creato correttamente;
- `delay_minutes` > 120 viene rifiutato o clampato secondo il design scelto e documentato;
- nessuna sovrapposizione se un job è già in corso;
- un'opportunità non può essere ritardata due volte.

### `tests/test_daily_orchestrator.py`

Casi minimi:
- trade + no-trade finali arrivano a 5 entro la giornata simulata;
- una decisione con wait seguita da follow-up conta 1 sola volta;
- se il target 5 è già raggiunto, i job ordinari successivi non partono;
- il follow-up su simbolo specifico richiama un'analisi focalizzata sul simbolo e sul focus prompt salvato;
- se il follow-up non produce edge, l'esito finale è `NO_TRADE`;
- ogni ciclo verifica sempre le posizioni aperte prima della decisione.

Checkpoint di fase:

```powershell
pytest tests/test_scheduler.py -v
pytest tests/test_daily_orchestrator.py -v
```

Entrambi i comandi devono passare prima di marcare la fase come VALIDATED e procedere.

---

## Errori comuni da evitare

- Usare `sleep()` come scheduler principale invece di un vero scheduler.
- Non aggiornare i prompt scanner dopo l'introduzione del follow-up.
- Contare il `WAIT_FOLLOW_UP` come decisione finale giornaliera.
- Permettere più di un delay sulla stessa opportunità.
- Avviare nuovi scan mentre un follow-up prioritario è pendente o mentre un job è già in esecuzione.
- Non fermare i cicli dopo il raggiungimento del target giornaliero.
- Dimenticare timezone e finestra lun–ven 08:00–22:00.
- Non verificare le posizioni aperte a ogni ciclo.
- Rendere il follow-up troppo generico invece che focalizzato sul simbolo/scenario salvato.

---

## Commit attesi

Alla fine della fase, a test verdi, sono attesi commit del tipo:

- `feat(config): add scheduler and daily orchestration settings`
- `docs(prompts): update scanner prompts for follow-up scheduling`
- `feat(agent): add delayed follow-up outcome support`
- `feat(runtime): add scheduler-based main orchestrator`
- `test(runtime): add scheduler and daily orchestration tests`
- `feat(phase-13): complete and validated`