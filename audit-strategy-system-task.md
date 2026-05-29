# Task — Audit completo del sistema strategia (config wiring, dead code, flow, test, bug hunt)

> **File**: `.planning/research/audit-strategy-system-2026-05-28.md`
> **Tipo task**: audit diagnostico read-only + report. NESSUN fix, NESSUN commit di codice.
> **Owner**: Claude Code (hai accesso all'INTERO repo, inclusi git history, file
> non condivisi esternamente, e la possibilità di FAR GIRARE i test).
> **Stima**: 1-2 ore.
> **Output finale**: report markdown strutturato (STEP 8). Solo fatti, niente fix.

---

## Perché questo task

Sono stati trovati finora due bug nel sistema strategia:
1. Counter-trend gate D-07 bloccava Setup B (GIÀ FIXATO, commit precedente).
2. `profile_filters.min_grade` e `min_confidence` sembrano definiti in
   `config/strategy.yaml` ma MAI applicati nel codice (solo `min_rr` è collegato).

Il sospetto è che ci sia **altra config morta** (definita ma non wired) e altri
gap fra ciò che il sistema dichiara di fare e ciò che fa davvero. Tu hai accesso
a tutto il repo — anche a file, test e history che un'analisi esterna su uno zip
parziale non vede. Questo audit serve a mappare lo stato reale del sistema PRIMA
di pianificare i fix del playbook v3, così non si costruisce su assunzioni
sbagliate (com'era già successo assumendo che `strategy.yaml` non esistesse).

**Regola d'oro di questo task: non fidarti dei commenti, docstring o nomi. Verifica
sul codice eseguito.** Un campo in un dataclass non significa che venga usato. Un
return "READY" non significa che il trade venga aperto. Una docstring che dice
"applica X" non significa che X sia applicato.

---

## STEP 0 — Setup

```bash
cd <repo-root>
git status              # deve essere pulito; se no, NON committare nulla, lavora read-only
git log --oneline -10   # contesto recenti commit
git branch --show-current
```

Lavora SENZA modificare codice. Se crei script di audit temporanei, mettili in
`scripts/_audit_*` e rimuovili a fine task (o tienili in `.gitignore`).
Documenta ogni script creato nel report.

---

## STEP 1 — Mappa del config wiring (il cuore dell'audit)

Per OGNI file di config in `config/` e `data/configs/` (`strategy.yaml`,
`patterns.yaml`, `costs.yaml`, `regime.yaml`, `baseline.yaml`, e qualunque altro):

1. Elenca TUTTE le chiavi (anche annidate) definite nel file.
2. Per ogni chiave, cerca nel codice Python (`grep -rn`) se viene **letta** e
   soprattutto se il valore letto viene **usato in una decisione** (gate, branch,
   calcolo) o solo letto-e-scartato.
3. Classifica ogni chiave in:
   - **WIRED**: letta e usata in logica effettiva. Indica dove (`file:linea`).
   - **READ-ONLY**: letta in un dataclass/dict ma il valore non influenza mai
     una decisione (dead-ish).
   - **DEAD**: mai letta da nessuna parte nel codice non-test.

Casi noti da confermare esplicitamente (parti da questi ma non fermarti qui):
- `profile_filters.min_grade` → WIRED o DEAD?
- `profile_filters.min_confidence` → WIRED o DEAD?
- `profile_filters.min_rr` → atteso WIRED (`strategy/proposal.py`), conferma.
- `factors.*` (trend_alignment, setup_pattern, momentum, volatility_regime,
  spread_session) → ognuno è realmente usato in `score_factors`?
- `adjusters.*` (i 6 adjuster di confidence) → ognuno applicato in
  `compute_confidence`? Quali sì, quali no?
- `grade_map`, `base_confidence`, `bounds` → wired?
- `counter_trend_allowed_grades` in `factors.trend_alignment` → ancora usato da
  qualcuno dopo la rimozione del gate D-07 da Setup B? (Potrebbe essere config
  orfana ora.)

**Output**: una tabella `chiave | stato | dove usata (file:linea) | note`.

---

## STEP 2 — Flow di valutazione: dal bar al trade

Traccia il percorso completo che un bar segue fino a diventare (o non diventare)
un trade. Documenta la catena reale di chiamate, file per file:

1. **Entrypoint backtest**: da `scripts/run_baseline_backtest.py` →
   `backtest/baseline/runner.py` → `slice_worker.py` → `backtest/engine.py`.
   Chi istanzia cosa, con quali parametri.
2. **Costruzione context**: come viene costruito lo `StrategyContext` nel
   backtest. Quali campi vengono popolati e quali restano default/vuoti.
   In particolare conferma: `sr`, `patterns` vengono popolati nel path di
   backtest? (Storicamente erano vuoti — è ancora così o è cambiato?)
3. **Orchestrator**: `evaluate_proposal_for_bar` in `strategy/__init__.py`.
   Come seleziona il winner fra i 4 detector (priorità D-06). Quali gate
   applica DOPO il detector (se ne applica).
4. **Da READY a posizione**: cosa succede a un ProposalDraft READY. Chi decide
   se aprire la posizione? Risk engine? Crowding (posizioni già aperte)?
   Sizing? Dove un READY può essere scartato silenziosamente.
5. **Punto chiave**: i `profile_filters` (min_grade/min_confidence/min_rr)
   dovrebbero essere applicati in questo flow. DOVE esattamente vengono (o non
   vengono) applicati? Se min_grade non è applicato da nessuna parte nella
   catena, confermalo tracciando il flow, non solo con grep.

**Output**: diagramma testuale della catena + lista dei punti dove un segnale
può essere scartato (con file:linea).

---

## STEP 3 — Discrepanza live vs backtest

Esistono due adapter: `strategy/adapters/live.py` e
`strategy/adapters/backtest.py`. Devono produrre lo stesso `StrategyContext`
(stesso shape, stessa semantica) altrimenti backtest e live divergono.

1. Confronta i due adapter campo per campo: cosa popola live, cosa popola backtest.
2. Evidenzia OGNI differenza: campi popolati in uno e non nell'altro, funzioni
   chiamate in uno e non nell'altro (es. `find_support_resistance`,
   `scan_patterns`, indicatori).
3. Per ogni differenza, valuta l'impatto: un detector che dipende da un campo
   popolato solo in live darà risultati diversi in backtest.

**Output**: tabella `campo/funzione | live | backtest | impatto potenziale`.

---

## STEP 4 — Audit dei 4 detector

Per ognuno di `a_breakout`, `b_reversal`, `c_compression`, `d_pullback`:

1. Quali campi del context e quali indicatori consuma.
2. Quali gate applica e in quale ordine (READY/FORMING/NONE + reason).
3. Dipende da campi che potrebbero essere vuoti nel backtest (vedi STEP 3)?
4. Il grade calcolato può realisticamente raggiungere A/A+, o c'è un limite
   strutturale (come era per Setup B col gate D-07)?

Poi un controllo trasversale:
- Quanti grade A/A+ sono teoricamente raggiungibili da ciascun detector?
  Se un detector non può MAI raggiungere grade A per costruzione, e da qualche
  parte c'è un filtro min_grade=A, quel detector è silenziosamente escluso.
- `ALL_DETECTORS` (`strategy/setups/__init__.py`): conferma che è hard-coded e
  che NON esiste meccanismo enable/disable. Cerca `ENABLE_SETUP`, `enable_setup`,
  feature flag, o qualunque filtro della lista detector. Riporta cosa trovi.

**Output**: per detector, un mini-profilo + flag di rischio strutturale.

---

## STEP 5 — Audit dei test: cosa è coperto e cosa NO

L'obiettivo è capire di quali parti del sistema ci si può fidare e quali sono
non testate (quindi a rischio bug silenti).

1. Elenca i file di test rilevanti per la strategia (`test_strategy*`,
   `test_backtest*`, `test_baseline*`).
2. Per ogni bug noto/sospetto, verifica se esiste un test che lo avrebbe colto:
   - Esiste un test che verifica che `min_grade` filtri davvero i trade per
     profilo? (Se NO, ecco perché il bug è passato.)
   - Esiste un test che verifica che min_confidence sia applicato?
   - Esistono test che verificano il flow END-TO-END (bar → trade) o solo unit
     isolati dei detector?
3. Identifica le aree senza copertura: config wiring, profile_filters
     application, adapter parity live/backtest, crowding/sizing.
4. Gira la suite e riporta il risultato reale:
   ```bash
   python -m pytest tests/ -q --tb=no 2>&1 | tail -30
   ```
   Quanti pass/fail/skip. Se ci sono test skipped o xfail rilevanti per la
   strategia, elencali (uno skip può nascondere una feature non implementata).

**Output**: tabella `area | coperta da test? | quale test | gap`.

---

## STEP 6 — Caccia ai bug (oltre i due noti)

Con tutto il contesto raccolto, cerca attivamente altri problemi. Categorie da
controllare (non esaustivo — usa giudizio):

1. **Config morta** oltre min_grade/min_confidence (dal STEP 1).
2. **Look-ahead / future leakage**: un detector o un indicatore che usa
   `bars[-1]` quando dovrebbe usare `bars[-2]`, o che accede a dati futuri.
   (Ci sono test `test_baseline_no_future_leakage` — girano verdi? coprono
   davvero i detector?)
3. **Off-by-one nei bar**: warmup, slicing `bars[:i]` vs `bars[:i+1]`.
4. **Timezone / timestamp**: confronti tz-naive vs tz-aware, conversioni UTC.
5. **Sizing / risk math**: il sizing è coerente fra i profili? C'è rischio di
   martingale (size cresce dopo loss)?
6. **Gate applicati nell'ordine sbagliato**: es. un gate costoso prima di uno
   economico, o un gate che rende un altro irraggiungibile.
7. **Default silenziosi**: `getattr(x, "y", default)` o `.get("y", default)`
   dove il default maschera un campo mancante invece di far fallire.

Per ogni bug sospetto: file:linea, cosa fa, cosa dovrebbe fare, impatto stimato,
e — importante — **se esiste un test che lo copre**.

**Output**: lista bug con severità (CRITICAL/HIGH/MEDIUM/LOW) e impatto.

---

## STEP 7 — Git history check (contesto che lo zip non ha)

Tu hai la history, l'analisi esterna no. Controlla:
1. `git log --oneline -- config/strategy.yaml` — quando è stato introdotto
   `profile_filters`? È stato wired e poi scollegato, o mai wired?
2. `git log --oneline -- strategy/setups/b_reversal.py` — conferma il fix B0.
3. Cerca commit con "DEFERRED", "TODO", "FIXME", "HACK", "XXX" recenti nel
   codice strategia/backtest:
   ```bash
   grep -rn "DEFERRED\|TODO\|FIXME\|HACK\|XXX" strategy/ backtest/ --include="*.py" | head -40
   ```
   Ogni DEFERRED è una feature dichiarata ma non finita — potenziale gap.

**Output**: lista di feature deferred/incomplete trovate + contesto da git.

---

## STEP 8 — Report finale (formato richiesto)

Un singolo blocco markdown, sezioni numerate. Solo fatti, niente raccomandazioni
di fix (quelle le decide l'analisi esterna).

````markdown
# Audit Strategy System — Report 2026-05-28

## 1. Config wiring map
[tabella: chiave | WIRED/READ-ONLY/DEAD | dove usata | note]
[per ogni file config]

## 2. Evaluation flow (bar → trade)
[catena di chiamate file:linea]
[lista punti di scarto silenzioso]
[dove min_grade/min_confidence DOVREBBERO essere applicati e dove sono (o non sono)]

## 3. Live vs backtest adapter parity
[tabella differenze + impatto]

## 4. Detector audit
[per detector: campi consumati, gate, grade raggiungibile, rischi strutturali]
[conferma ALL_DETECTORS hard-coded, nessun enable/disable]

## 5. Test coverage
[tabella area | coperta? | test | gap]
[risultato pytest reale: N passed / N failed / N skipped]
[skip/xfail rilevanti]

## 6. Bug trovati
[lista: severità | file:linea | cosa fa | cosa dovrebbe | impatto | test esistente?]
[includi i 2 noti + tutti i nuovi]

## 7. Feature deferred/incomplete
[lista DEFERRED/TODO/FIXME + contesto git]

## 8. Sintesi: top 5 problemi per impatto
[i 5 problemi che più probabilmente spiegano il baseline negativo, ordinati per
impatto stimato, ognuno con 1-2 frasi di razionale — SOLO diagnosi, no fix]

## 9. Anomalie / cose che non tornano
[qualunque cosa strana incontrata durante l'audit]

## 10. Script di audit creati e cleanup
[lista script temporanei + stato rimozione]
````

---

## Vincoli rigorosi

1. **READ-ONLY sul codice di produzione.** NESSUN fix, NESSUNA modifica a
   detector/config/adapter. Solo lettura, grep, e script di audit temporanei.
2. **NON committare codice.** Se vuoi salvare il report, va in
   `.planning/research/audit-strategy-system-2026-05-28.md` — quello sì può
   essere committato come documentazione, ma niente fix.
3. **Verifica, non fidarti.** Non dichiarare una chiave WIRED perché c'è una
   docstring che lo dice. Trova la linea di codice che la usa in una decisione.
4. **Distingui "letto" da "usato".** Un campo caricato in un dataclass ma mai
   consultato in un branch/gate/calcolo è DEAD anche se "letto".
5. **Quando trovi un bug, cerca SEMPRE se c'è un test che lo copre.** L'assenza
   di test è essa stessa un finding.
6. **NON proporre fix né priorità di intervento** oltre la sintesi per impatto
   (STEP 8.8 è diagnosi di impatto, non piano di fix).
7. **Tempo massimo**: 2 ore. Se sfori, consegna report parziale onesto indicando
   quali STEP non hai completato.
8. **Se la suite test non gira** (dipendenze, env), documentalo e prosegui con
   l'audit statico; non bloccarti.

---

## Quando hai finito

Consegna il report markdown delle 10 sezioni come singolo messaggio. Niente
preamboli. L'analisi esterna userà questo report per decidere l'ordine dei fix
nel playbook v3, sostituendo le assunzioni con lo stato reale del codice.
