# Strategy Rebuild — Playbook personale

> ⚠️ **DO NOT COMMIT — LOCAL ONLY**
> Questo file è un appunto operativo per te. Non va sotto git. Tienilo come reference durante la prossima sessione di lavoro, poi cancellalo o aggiornalo. Stessa convenzione di `logclaude.txt`.

---

## Da dove veniamo (recap brevissimo)

Plan 05-10 ha mostrato che la strategia attuale (4 setup A/B/C/D ATR-based) **non ha edge in nessun subset testato**: win rate 24-27%, 73-83% chiusure in SL, 27/27 run del backtest muoiono per balance-exhaustion. Plan 05-09 baseline (1076 trades) era artefatto del bug `f21abda` (KS giornaliero permanente) — non un baseline veritiero.

Phase 7 ML è bloccata: un classifier non può imparare a separare buoni-vs-cattivi quando il 75% degli esempi è perdente in qualsiasi sub-popolazione.

Soluzione: aprire una nuova phase **"Strategy Rebuild"** prima di Phase 7. Costruire 2-3 setup nuovi dai libri (Murphy, Probo, StrategieOperative), implementarli, ri-testare sul parquet 209k come benchmark. Gate per sbloccare Phase 7: almeno un detector con expectancy > +2 USD/trade post-costi e median PnL ≥ 0 su subset n ≥ 1000.

Tutto il contesto formale è in:
- `.planning/phases/05-baseline-backtest/05-10-SUMMARY.md` (la diagnosi completa)
- `.planning/REQUIREMENTS.md` → STRAT-REBUILD-01..04
- `.planning/STATE.md` → "Active Work" sezione Plan 05-10 NEGATIVE FINDING
- memoria Claude in `/home/vscode/.claude/projects/-workspaces-trading-agent/memory/`

Scripts di repro:
- `scripts/diag_decay_05_10.py` (8 blocchi diagnostici)
- `scripts/diag_decay_subset.py` (subset edge-hunt 117 combinazioni)

---

## STEP 0 — Preparazione (da fare prima di aprire la nuova sessione Claude)

### 0.1 Verifica libri PDF presenti

Sul PC primario `C:\trading-agent\libri\`:

```powershell
Get-ChildItem C:\trading-agent\libri\ -Filter *.pdf
```

Devi avere (dalla skill description):
- Murphy — intermarket analysis
- Probo — forex operativo
- StrategieOperative

Se non sono lì, copiali. La skill `forex-strategy-builder` li cita esplicitamente come knowledge base, senza non può estrarre setup specifici.

### 0.2 Allinea il branch sul primario

```powershell
cd C:\trading-agent
git pull
git log --oneline -5    # dovresti vedere 11424d5 docs(05-10): NEGATIVE FINDING
```

### 0.3 Backup mentale dei vincoli architetturali da preservare

Quando entri in discuss-phase, **ricordagli** questi paletti (così il planner non li dimentica):

| Vincolo | Perché |
|---|---|
| Strategy modules side-effect-free (STRAT-08 AST gate) | Test in millisecondi, isolato. Già attivo in `tests/test_strategy_purity.py` |
| Single shared call site `evaluate_proposal_for_bar` (STRAT-09) | Live e backtest devono restare allineati, niente fork |
| Adapters `live` + `backtest` con stesso shape D-05 | I detector nuovi devono usare la stessa firma di input |
| ProposalDraft frozen — extension solo additive | Non rompere i 3 campi ml_* introdotti in Phase 7 PLAN.md |
| EXECUTION_MODE=shadow default | Niente trade live mai, sempre shadow |
| `evaluate_proposal_for_bar` priority D-06: READY > FORMING > NONE + grade tiebreak | I detector nuovi vanno integrati in questa graduatoria |

### 0.4 Decidi (mentalmente, prima di iniziare) la tua preferenza

Devi rispondere a 4 domande chiave in discuss-phase. Vale la pena pensarci ora:

**Q1: rimpiazzo o affiancamento?**
- Opzione A (replace): elimini i 4 setup A/B/C/D, parti da zero con 2-3 nuovi
- Opzione B (augment): tieni i 4 vecchi disabilitati di default + aggiungi 2-3 nuovi attivi
- Opzione C (parallel): mantieni i 4 vecchi + nuovi, gating via feature flag per A/B test

> **Mia raccomandazione:** Opzione B (augment con disable-by-default). Strategy_legacy già archiviato per fallback, ma i 4 setup attuali sono codice testato — disabilitarli via config (`strategy.yaml` enable_setup_a: false) è più sicuro di cancellare. Se i nuovi non funzionano, basta riabilitare.

**Q2: quanti setup nuovi nella prima iterazione?**
- 1 setup ad alta convinzione (es. solo pin bar reversal con tutti i filtri)
- 2-3 setup complementari (uno trend-following, uno mean-reversion, uno breakout)
- Tutti i 5-6 setup che troviamo nei libri

> **Mia raccomandazione:** 2 setup complementari. Uno solo è fragile (binary outcome bias). 5-6 è troppo da costruire/testare in una phase. Due copre regimi diversi (trend + range) e dà ridondanza.

**Q3: quale timeframe primario?**
- M15 (era il primario nel sistema attuale)
- M30 o H1 (più conservativi, meno noise)
- Multi-TF dal day 1 (es. setup su H1 ma confirma su M15)

> **Mia raccomandazione:** H1 primario con confirma M15. I dati del 05-10 mostrano che H1 sopravvive più a lungo (2015-2021 vs M15 2004-2007). H1 ha meno noise da scalping/spread, e i pattern dei libri (Probo) sono pensati per H1+ in genere.

**Q4: criterio di accettazione finale**

Già fissato nel SUMMARY come STRAT-REBUILD-03:
- expectancy > +2 USD/trade post-costi reali
- AND median PnL ≥ 0
- AND subset n ≥ 1000

Non è negoziabile — il classifier ML ha bisogno di un segnale positivo per imparare a separare. Tutto sotto questo gate sarebbe re-iterazione.

---

## STEP 1 — Apertura della phase

### 1.1 Nuova sessione Claude Code (importante: NON proseguire questa, fresh context)

Quando rientri al primario, apri un **nuovo** terminale + nuova sessione Claude Code in `C:\trading-agent`. Devi partire da zero per avere context window pulito (la presente sessione ha già 60k+ token di diagnostica).

### 1.2 Restore del contesto via memory

La prima cosa che farà Claude è caricare `MEMORY.md` automaticamente. Lì trova:
- `plan-05-10-ks-bug-decay.md` (la storia completa)
- `setup-dual-pc.md` (convenzioni primario/secondario/WSL)

Verifica subito che le abbia lette dicendogli: *"Hai accesso alla memoria di Plan 05-10? Riassumi la diagnosi."* Se non risponde con almeno: "strategy structurally negative-expectancy, win rate 24%, Phase 7 bloccata, REQ STRAT-REBUILD aperte" → digli `controlla MEMORY.md` e ricarica.

### 1.3 Comando di apertura

```
/gsd-phase add
```

Quando ti chiede dove inserirla, dì: **"fra Phase 5 e Phase 7"** (sarà Phase 5.5 oppure rinumeri tutto in avanti — lui sceglie il pattern coerente con ROADMAP).

Title proposto: `Strategy Rebuild — replace negative-expectancy READY detector with textbook setups`

Scope proposto in 1-2 frasi:
> Sostituire i 4 setup attuali (A/B/C/D ATR-based, no edge documentato) con 2 setup nuovi estratti da Murphy/Probo/StrategieOperative. Re-test sul parquet 05-10 come benchmark con gate STRAT-REBUILD-03. Solo dopo gate-pass, sblocco Phase 7 ML.

### 1.4 ROADMAP update

Dopo `/gsd-phase add`, controlla che `ROADMAP.md` (se esiste) sia aggiornato con la nuova phase + dipendenze invertite (Phase 7 ora `requires` la nuova phase).

---

## STEP 2 — Discuss-phase (la parte più importante)

```
/gsd-discuss-phase
```

Quando il discusser ti chiede l'obiettivo, **menziona esplicitamente lo skill forex-strategy-builder** così lo carica:

> "Voglio costruire la nuova strategia usando lo skill forex-strategy-builder che ha accesso ai libri Murphy/Probo/StrategieOperative in C:\trading-agent\libri\. Leggi i PDF e estrai 2 setup complementari (uno trend, uno range/reversal) per H1 + confirma M15."

### 2.1 Le 4 aree di discussione attese

Il discusser di solito organizza in 4 aree. Per questa phase, suggerisco di guidarlo verso queste:

**Area A — Setup selection (dai libri)**
- Quali 2 setup specifici dai PDF (es. "Probo cap. X breakout su NR7 confermato volume", "Murphy reversal divergenza con pin bar")
- Per ognuno: condizioni di entry (precise, no soggettività), regole di SL/TP, filtri di mercato (regime, sessione, spread)
- Come si differenziano dai 4 attuali — cosa NON imitare

**Area B — Multi-TF gating**
- H1 come timeframe operativo, M15 come confirmation
- Quali indicatori dell'H1 devono allinearsi con M15
- Regole anti-conflict (es. se H1 dice long ma M15 mostra reversal, salta)

**Area C — Risk management ricalibrato**
- I 4 setup attuali avevano SL a 0.4×ATR cap 1.5×ATR. Era troppo stretto? Troppo largo?
- R:R floor per profilo (oggi 1.8 MODERATE) — va alzato?
- Sizing: percentuale del balance o lotto fisso?
- MAX_DAILY_DRAWDOWN_PERCENT (oggi 20%) — va riportato al 2% ora che il KS è fixato?

**Area D — Benchmark + acceptance**
- Re-test su parquet 05-10 23.6y come benchmark vs 4 setup attuali
- Criterio acceptance verbatim STRAT-REBUILD-03 (expectancy > +2 USD/trade, median ≥ 0, n ≥ 1000)
- Cosa fare se nessun setup passa il gate → loop iterativo o stop?

### 2.2 Decisioni che probabilmente ti chiederà

Tieni queste risposte già pronte (puoi sempre cambiare in corso):

| Domanda probabile | Risposta di partenza |
|---|---|
| Quale skill carico? | forex-strategy-builder (libri C:\trading-agent\libri\) |
| Quanti setup nuovi? | 2 complementari, uno trend uno range |
| Timeframe primario? | H1 + M15 confirma |
| Replace o augment i vecchi? | Augment con disable-by-default via strategy.yaml |
| Quale benchmark? | Parquet 05-10 209k già esistente sul secondario |
| Gate strict o flessibile? | Strict — STRAT-REBUILD-03 verbatim, no negoziazione |
| Failure path? | Se nessun setup passa, capture nuova requirement + raise to user |
| Risk parameters update? | TBD — discutere se MAX_DAILY_DRAWDOWN va riportato al 2% (test con KS fixato) |

---

## STEP 3 — Plan-write

```
/gsd-plan-phase
```

Il planner produrrà 3-5 wave plans. Struttura attesa:

### Wave 0 — Scaffolding
- Nuovi moduli `strategy/setups/e_<nome1>.py`, `f_<nome2>.py` (puri, conformi STRAT-08)
- `strategy.yaml` update con `enable_setup_e: true`, `enable_setup_f: true`, `enable_setup_a..d: false` (default)
- Nuovi test in `tests/test_strategy_setups_new.py` con fixture deterministica
- Update barrel `strategy/__init__.py` per registrare i nuovi detector

### Wave 1 — Setup 1 (es. trend pullback Probo-style)
- TDD: red test edge case → green implementation → refactor
- Pure-function con stesso shape di `detect_a_breakout` etc.
- Filter di regime (es. solo `regime_state=='normal'` o `'expanded'`)
- Levels function `_compute_levels_e(...)` con SL/TP ricalibrati

### Wave 2 — Setup 2 (es. range reversal Murphy-style)
- Stesso pattern Wave 1 ma per il setup complementare
- Filter regime opposto (es. solo `regime_state=='compressed'`)

### Wave 3 — Multi-TF gating
- Helper `multi_tf_align(symbol, h1_bars, m15_bars)` in `strategy/multi_tf.py`
- Wired in `evaluate_proposal_for_bar` come pre-filter prima dei detector
- Test con scenari aligned/conflict/incomplete

### Wave 4 — Re-test su parquet 05-10
- Script `scripts/benchmark_strat_rebuild.py` che:
  - Carica il parquet 05-10 209k
  - Re-esegue strategia *new* su stessi bar (re-run backtest, non re-uso pnl_usd vecchio)
  - Produce confronto: old (con 4 setup vecchi) vs new (con 2 setup nuovi) — expectancy, win rate, median PnL, subset breakdown
  - Output report `.planning/research/strat-rebuild-{date}.md`

### Wave 5 — Gate verification + Phase 7 unblock
- Check STRAT-REBUILD-03 verbatim: expectancy > +2 USD/trade post-costi (vedi `data/configs/costs.yaml`), median ≥ 0, n ≥ 1000
- Se PASS: update STATE.md Phase 7 da BLOCKED → 🟢 plans-written
- Update REQUIREMENTS.md STRAT-REBUILD-01..04 → ✓ Complete
- Se FAIL: capture nuova requirement (es. STRAT-REBUILD-05 per iterazione 2)

---

## STEP 4 — Esecuzione

### 4.1 Sul primario

```
/gsd-execute-phase <numero-nuova-phase>
```

Lascialo girare. Tempo stimato: 4-8h (più dei plan small perché ha lettura PDF + design + 2 detector + multi-TF + benchmark).

### 4.2 Sul secondario — re-run benchmark

Quando Wave 4 ti chiede di girare il benchmark:

```powershell
cd C:\dev\git\trading-agent
git pull
python scripts\benchmark_strat_rebuild.py
```

Tempo stimato: 2-6h sul parquet 209k. **In questo run il KS è già fixato, quindi i numeri saranno realistici fin da subito.**

### 4.3 Risultato gate

Output atteso del benchmark:

```
=== Benchmark Strategy Rebuild ===
Setup E (trend pullback):
  n_trades: 1547
  win_rate: 0.421
  mean_pnl_usd: +3.12
  median_pnl_usd: +0.85
  expectancy_post_costs_usd: +2.34
  GATE STRAT-REBUILD-03: PASS

Setup F (range reversal):
  n_trades: 892
  win_rate: 0.388
  mean_pnl_usd: +1.91
  median_pnl_usd: -0.12
  expectancy_post_costs_usd: +0.78
  GATE STRAT-REBUILD-03: FAIL (median < 0, n < 1000)

Decision: Setup E PASS gate → Phase 7 può procedere con Setup E come unico baseline
          Setup F va in iterazione 2 (eventualmente STRAT-REBUILD-05)
```

Se almeno **uno** dei due passa il gate, sei a posto per Phase 7. Se nessuno passa, l'iterazione 2 entra in scope (vedi STEP 6 sotto).

---

## STEP 5 — Sblocco Phase 7

### 5.1 Update STATE.md manualmente o via /gsd-progress

```
/gsd-progress
```

Lui dovrebbe rilevare:
- Nuova phase Strategy Rebuild completata
- STRAT-REBUILD-03 gate-pass
- Phase 7 da BLOCKED → plans-written

Se non aggiorna correttamente, fagli notare il gate-pass e digli di aggiornare STATE.md manualmente.

### 5.2 Phase 7 originale procede

I 6 PLAN.md di Phase 7 esistenti sono validi architetturalmente. Però attenzione: **vanno revisionati** alla luce del fatto che ora il baseline ha 1 solo setup (non 4) e numeri completamente diversi. Probabilmente:
- Plan 07-01 feature_extraction: derive 8 fields D-09-G — invariato
- Plan 07-02 walk_forward: invariato
- Plan 07-03 train LightGBM: scale_pos_weight per fold — ora i pos/neg ratio sono diversi, va ricalcolato a runtime (era già così)
- Plan 07-04 threshold sweep: invariato
- Plan 07-05 inference singleton: invariato
- Plan 07-06 risk_engine ML gate: invariato

Prima di `/gsd-execute-phase 7` farei un **plan-check rapido** giusto per sicurezza:

```
/gsd-plan-phase 7
```

E vedere se rileva drift coi nuovi setup. Se OK, procedi all'execute.

---

## STEP 6 — Failure paths (se nessun setup passa il gate)

Possibili scenari di fallimento e cosa fare:

### Scenario A — Tutti i setup mostrano expectancy positiva ma sotto i costi
*Es. Setup E expectancy +1.20/trade, costs reali 1.5/trade*
- Soluzione 1: rivedere costs.yaml (forse troppo conservativo)
- Soluzione 2: filtrare ulteriormente (es. solo certe sessioni, certi giorni)
- Soluzione 3: aumentare R (TP più ambizioso)
- Capture STRAT-REBUILD-05 "tighten cost-aware filtering"

### Scenario B — Median PnL negativo nonostante expectancy positiva
*Asimmetria distribuzione: pochi big winner trascinano media*
- Soluzione: aggiungere filtro post-entry (es. partial close al 50% RR)
- Soluzione: capping del max profit/trade per ridurre asimmetria
- Capture STRAT-REBUILD-06 "median-PnL stabilization"

### Scenario C — n_trades < 1000 (campione troppo piccolo)
*Es. filtri troppo stretti, il setup scatta raramente*
- Soluzione: allargare uno dei filtri (es. accettare 2 regimi invece di 1)
- Soluzione: aggiungere un terzo setup per ampliare la copertura

### Scenario D — Setup completamente perdenti
*Cioè i nuovi setup hanno expectancy ancora più negativa dei vecchi*
- Stop. Ri-leggi i libri con più attenzione.
- Possibile causa: il setup nel libro funziona su asset diversi (azioni, indici) non FX.
- Capture STRAT-REBUILD-07 "library setup rejection — reconsider source material"

### Scenario E — Nessun setup completa la build
*Cioè problemi tecnici nell'implementazione*
- Debug normale. `/gsd-debug` se serve.

---

## STEP 7 — Aspetti operativi minori

### 7.1 Cosa fare del parquet 05-10 sul secondario

Tienilo. Anche se il dataset documenta strategia perdente, serve come **benchmark di confronto**. Quando il benchmark Wave 4 confronta old vs new, ha bisogno di ri-girare la simulazione sui bar grezzi (CSV) usando i nuovi detector. Il parquet 05-10 vecchio resta come reference: "vedi cosa succedeva con i 4 setup vecchi su questi stessi bar".

Path attesi sul secondario:
- `C:\dev\git\trading-agent\data\training\baseline_decisions\part-0.parquet` (vecchio = output 4 setup)
- `C:\dev\git\trading-agent\data\training\strat_rebuild_decisions\part-0.parquet` (nuovo = output Setup E+F)

### 7.2 Cosa fare del 05-09 parquet ora "tainted"

Il file `data/training/baseline_decisions/part-0.parquet` committato è ancora il vecchio 1076 rows. Tecnicamente è già etichettato in STATE.md come "TAINTED-BY-KS-BUG". Due opzioni:

- **Lasciarlo dov'è** (preferito): è un audit trail. Quando lo leggi sai che era artefatto del bug. Non cancellarlo per non perdere reproducibility storica.
- Archiviarlo in `.planning/archive/data/baseline_decisions.tainted-ks-bug/`: più pulito ma rompe l'audit storico. Skip.

### 7.3 Quando re-iterare?

Probabilmente serviranno 2-3 cicli di Strategy Rebuild prima di trovare combinazione vincente. Pianifica mentalmente:

- Ciclo 1: setup base dai libri, semplici — può fallire, ti dà signal su cosa manca
- Ciclo 2: filtri aggiunti (sessione, regime, multi-TF strict)
- Ciclo 3: risk management ricalibrato (R:R, sizing, daily DD)

Ogni ciclo è una phase separata o sub-phase. Non incaponirti sulla prima iterazione.

### 7.4 Quando coinvolgermi/Claude

Da fare con Claude:
- Lettura libri + estrazione setup (richiede skill forex-strategy-builder)
- Plan-write (richiede gsd-plan-phase)
- Implementazione TDD
- Benchmark + verifica gate
- Update STATE/REQUIREMENTS

Da fare senza Claude (decisioni umane):
- Quale setup scegliere fra i 5-6 estratti dai libri
- Quando dichiarare "abbastanza iterazioni, basta"
- Decidere se accettare un'expectancy borderline
- Approvare deviation di scope

---

## STEP 8 — Reference rapida

### Comandi GSD che userai

```
/gsd-phase add               # nuova phase nel roadmap
/gsd-discuss-phase           # discuss context + decisioni 4 aree
/gsd-plan-phase              # 3-5 wave plans
/gsd-execute-phase <N>       # esegue tutto
/gsd-progress                # status check + advance state
/gsd-validate-phase <N>      # se servono test mancanti retroattivi
```

### File chiave da consultare

| File | Cosa contiene |
|---|---|
| `.planning/phases/05-baseline-backtest/05-10-SUMMARY.md` | Diagnosi completa Plan 05-10, root cause, subset analysis |
| `.planning/REQUIREMENTS.md` (STRAT-REBUILD-01..04) | Requirements formali |
| `.planning/STATE.md` (Active Work) | Status corrente milestone |
| `scripts/diag_decay_05_10.py` | Diagnostica generale parquet |
| `scripts/diag_decay_subset.py` | Subset edge-hunt |
| `strategy/__init__.py` | Barrel + evaluate_proposal_for_bar |
| `strategy/setups/{a..d}_*.py` | Detector attuali (riferimento per i nuovi) |
| `data/configs/strategy.yaml` | Config enable/disable setup |
| `data/configs/baseline.yaml` | Config backtest baseline |
| `data/configs/costs.yaml` | Costs per symbol (spread/slippage/commissione) |
| `tests/test_strategy_purity.py` | AST gate purity da rispettare |
| `tests/capture_regression_baseline.py` | Regression fixture (da aggiornare con nuovi setup) |

### Commit message convention (per riferimento)

Vedi `COMMIT_CONVENTIONS.md`. Pattern atteso:
- `docs(phase-N): ...`
- `feat(N-XX): ...`
- `test(N-XX): ...`
- `fix(N-XX): ...`
- `chore(N-XX): ...`

Co-Authored-By line per i commit di Claude. Mai amendare commits passati.

---

## Domande aperte da chiarire con Claude nella prossima sessione

Queste sono cose che potrebbero emergere durante discuss-phase. Tienile in mente:

1. **MAX_DAILY_DRAWDOWN_PERCENT 2% vs 20%**: il KS è ora fix-ato, quindi 2% non causa più il problema "stuck for all backtest". Vale la pena testare a 2% (più realistico per live)? Oppure 5% come compromesso?

2. **Profile sizing**: i 3 profili (CONS/MOD/AGGR) avevano R:R floor diversi (1.8/2.5/3.0?). Ricalibrare alla luce dei costi reali?

3. **Outlier handling nei nuovi setup**: pre-emptive partial close al 50% di RR per stabilizzare median PnL?

4. **Sessione FX**: solo Londra+NY overlap (alta liquidità) o anche Tokyo? Il parquet 05-10 mostra trade in tutte le sessioni — vedere se filtrare riduce churn senza perdere edge.

5. **Holding time**: i trade attuali hanno timeout 120 min. Per setup H1 può servire estensione (es. 6h)?

6. **Cross-pair correlation**: se i 2 setup nuovi triggerano contemporaneamente su EURUSD e GBPUSD (correlati), aprire entrambi o gating?

---

## Quando hai finito di leggere

Quando ti senti pronto per la sessione, esegui:

```powershell
cd C:\trading-agent
git log --oneline -3
# verifica 11424d5 docs(05-10): NEGATIVE FINDING è presente
```

Poi avvia Claude Code in quella directory e comincia con:

> "Ho letto il playbook locale. Procediamo: /gsd-phase add per aprire la nuova phase Strategy Rebuild fra Phase 5 e Phase 7."

Da lì Claude prende in mano. Tu rispondi alle 4 aree di discuss-phase, lasci girare il plan-write, poi monitori l'execute.

---

## Cosa farò io (Claude) automaticamente

In quella nuova sessione, grazie alla memoria persistente:
- Carico `MEMORY.md` → leggo `plan-05-10-ks-bug-decay.md` + `setup-dual-pc.md`
- Già so che la strategia è broken e perché
- Già so del workflow dual-PC (Windows primario/secondario + WSL)
- Già so della convenzione PowerShell (niente python -c con virgolette nidificate)

Quello che NON saprò automaticamente:
- Le tue preferenze di STEP 0.4 — me le dici tu
- Il contenuto dei libri PDF — la skill forex-strategy-builder li legge per la prima volta in discuss-phase
- Se hai già fatto i pull sui 2 PC — me lo dici

---

## TL;DR (per quando rileggerai fra una settimana)

1. **Verifica libri PDF** in `C:\trading-agent\libri\`
2. **Git pull** sui due Windows
3. **Nuova sessione Claude** in `C:\trading-agent`
4. **`/gsd-phase add`** — title "Strategy Rebuild", insert fra 5 e 7
5. **`/gsd-discuss-phase`** — menziona skill forex-strategy-builder, decidi le 4 aree (Q1=B augment, Q2=2 setup, Q3=H1+M15, Q4=gate strict)
6. **`/gsd-plan-phase`** — 5 wave atteso (scaffold, setup1, setup2, multi-TF, benchmark+gate)
7. **`/gsd-execute-phase`** — primario fa il code, secondario fa il benchmark
8. **Verifica gate** STRAT-REBUILD-03 → almeno 1 setup pass
9. **Update STATE** Phase 7 BLOCKED → plans-written
10. **`/gsd-execute-phase 7`** procede con il vero ML training su dataset con edge

Buona caccia.
