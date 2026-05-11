---
created: 2026-05-11
project: trading-agent
milestone: v2-ml-backtest
branch: feature/update-pythono-pure-strategy
workflow_mode: distributed (PC primario GSD + PC secondario backtest)
constraint: PC primario non regge backtest 23.5y + altri carichi → distribuito su PC secondario
last_commit_before_plan: 434833a
companion_docs:
  - .planning/SETUP-SECONDARY-PC.md
---

# Piano Sessione — Trading Agent v2 ML-Backtest

> **Scopo**: tabella di marcia per portare il milestone v2-ml-backtest fino al termine dei test puliti di Phase 5 (Plan 05-09) e sbloccare Phase 7. Da consultare ad ogni `/gsd-resume-work`. Aggiornare le checkbox man mano che gli step si chiudono.

---

## Strategia in una riga

> **PC primario fa GSD (Phase 6 + discuss/plan), PC secondario esegue il backtest in parallelo.** Il PC primario non regge backtest 23.5y + altre attività; il PC secondario fa solo grunt-work senza Claude Code.

## Workflow distribuito (chi fa cosa)

```
PC PRIMARIO (questo, con Claude Code)          PC SECONDARIO (altro PC, solo Python)
─────────────────────────────────────          ───────────────────────────────────────
STEP 1: Riapri Phase 5 + /gsd-plan-phase 5
        Produce:
          - 05-09-PLAN.md
          - scripts/run_baseline_05_09.py
          - tests/test_baseline_dataset_writer.py
        Plan-checker PASS

STEP 2: git push origin
        feature/update-pythono-pure-strategy  ────►  git clone + checkout branch
                                                     Setup ambiente
                                                     (vedi SETUP-SECONDARY-PC.md)

                                              STEP 3: Pre-flight check
                                                      (pytest + smoke + schema)
                                                      Launch full run notturno
                                                      ~3h18m wall-clock
                                                      (PC primario libero in parallelo)

(PC primario lavora in parallelo:)
STEP 4: /gsd-execute-phase 6
STEP 5: /gsd-discuss-phase 8
STEP 6: /gsd-plan-phase 8
STEP 7: /gsd-discuss-phase 9
STEP 8: /gsd-plan-phase 9
STEP 9: /gsd-discuss-phase 10
STEP 10: /gsd-plan-phase 10
STEP 11: /gsd-discuss-phase 11
STEP 12: /gsd-plan-phase 11
                                                                          git push parquet
        git pull ◄────────────────────────────────────────────────────────  + 05-09-SUMMARY

STEP 13: Verify parquet schema
         /gsd-plan-phase 7 --skip-research
         /gsd-execute-phase 7
```

**Vantaggio di questo ordine:** sblocchi il collo di bottiglia (3h18m di backtest) per primo. Mentre il PC secondario macina di notte, tu di giorno fai tutto il resto: Phase 6 execute + discuss+plan delle 4 fasi rimanenti (8/9/10/11). Quando il parquet arriva, l'unica cosa che resta è Phase 7 plan+execute.

**Race condition gestita:** se sul PC primario finisci STEP 4-12 PRIMA che il backtest sia finito → aspetti. Se il backtest finisce prima → anticipi STEP 13. Tipicamente i 4 cicli discuss+plan + execute Phase 6 richiedono più di 3h18m di lavoro umano, quindi il backtest finisce prima.

---

## Stato di partenza (snapshot 2026-05-11)

| Item | Stato |
|------|-------|
| Phase 1-5 | complete (Phase 5 con D-02 gap deferred — risolto allo STEP 1-3) |
| Phase 6 | 06-01 SUMMARY ✓ — 06-02/03/04 PLAN scritti, mai eseguiti |
| Phase 7 | paused pre-planning (CONTEXT.md ✓, RESEARCH.md ✓; planner mai spawned) |
| Phase 8-11 | pending (nessun CONTEXT.md) |
| Branch | `feature/update-pythono-pure-strategy` — non cambiare |
| Last commit | `434833a wip(phase-7): paused pre-planning — Wave 0 spike pending` |

**Decisioni già fissate (non rinegoziare):**
- Latency target Phase 7: **p95 < 10ms** (NON p99) — locked.
- Re-run dataset = **Plan 05-09 di Phase 5** (NON Wave 0 di Phase 7). Phase 7 consuma il parquet, non lo produce.
- Workflow sequenziale per vincolo hardware (no parallelizzazione tra Phase 6 execute, discuss-phase, e backtest 23.5y).

---

## Roadmap step-by-step

> **Nuovo ordine (rev 4):** prima sblocchi il collo di bottiglia (Plan 05-09 → push → backtest sul PC secondario), poi lavori in parallelo sul PC primario su tutto il resto. STEP 1-3 sono il "fast-track" verso il PC secondario. STEP 4-12 girano sul PC primario mentre il backtest macina di notte. STEP 13 chiude il cerchio.

### STEP 1 — Riapri Phase 5 e pianifica Plan 05-09 (SCRIPT-FIRST)

**Cosa fa:** riapri Phase 5 in ROADMAP/STATE, poi pianifica un plan 05-09 che (a) estende il dataset_writer con le 24+ colonne mancanti + 4 metadati, e (b) produce uno **script Python wrapper eseguibile stand-alone** (`scripts/run_baseline_05_09.py`) che il PC secondario possa lanciare senza Claude Code.

**Comandi (in ordine):**

1. **Riapri Phase 5** (verifica prima se è necessario):
```
# Controlla se Phase 5 è marcata "complete" in ROADMAP — se sì, edit:
/gsd-phase --edit 5 --status pending
# Se /gsd-phase --edit non supporta riapertura, modifica manualmente:
#  - .planning/ROADMAP.md: aggiungi plan 05-09 alla lista Phase 5
#  - .planning/STATE.md: Phase 5 status → 8/9 + nuovo plan 05-09 pending
```

2. **Pianifica Plan 05-09:**
```
/gsd-plan-phase 5
```

Il planner deve produrre `05-09-PLAN.md` con scope:

**Deliverable di codice:**
- Estendi `backtest/baseline/dataset_writer.py` per scrivere 30+ feature da `compute_all_extended()` al bar di entrata
- Aggiungi colonne meta: `profile`, `regime`, `run_id`, `decision_ts_utc` (UTC ISO8601)
- Opzionale (decidere in discuss/planning): catturare anche FORMING/NONE drafts (chiude il gap `drafts_rows = []` deferred per Phase 9 failure analysis)
- Modifica `data/configs/baseline.yaml`: `force_rerun: true` per invalidare hash e forzare re-run

**Deliverable per PC secondario (CRITICO):**
- **`scripts/run_baseline_05_09.py`** — wrapper Python eseguibile stand-alone:
  - `python scripts/run_baseline_05_09.py` → full run 27/27
  - `python scripts/run_baseline_05_09.py --smoke` → smoke run mini-range (1 mese × 1 pair × 1 TF × 1 profile, ~30-60 sec) per validare writer prima del full run
  - Stampa tqdm progress, scrive log strutturato, exit code 0 se 27/27, !=0 se anomalie
  - Auto-detect path (`load_baseline_config()` standard)
  - Nessuna dipendenza da Claude Code o GSD
- **`tests/test_baseline_dataset_writer.py`** (extended) — unit test del writer su dataframe in-memory, verifica schema 30+ cols + 4 meta
- **`tests/test_baseline_runner.py`** — smoke test del runner che gira `--smoke` in CI

**Deliverable di verifica:**
- Schema-validation post-run (parquet ha tutte le colonne attese, asserzioni esplicite)
- Verifica no-leakage: indicatori calcolati su `bar[entry_time-1]`, mai su `bar[entry_time]` o futuri
- Documentazione recovery: come re-lanciare run parziali se il PC secondario crasha a metà

**Pre-check:**
- [ ] Working tree pulito (`git status`)
- [ ] Branch `feature/update-pythono-pure-strategy` attivo
- [ ] `data/training/baseline_decisions/part-0.parquet` corrente preservato (backup): `cp -r data/training/baseline_decisions data/training/baseline_decisions.pre-05-09`

**Criteri di completamento:**
- [ ] Phase 5 status → reopened in STATE/ROADMAP
- [ ] `05-09-PLAN.md` esiste e passa plan-checker
- [ ] Plan 05-09 esplicita: writer extension + script wrapper + schema target + re-run modalità + verifica
- [ ] **`scripts/run_baseline_05_09.py`** committato e funziona con `--smoke` (test locale veloce per validare wrapper)
- [ ] **`tests/test_baseline_dataset_writer.py`** verde
- [ ] **`tests/test_baseline_runner.py`** verde (con `--smoke`)
- [ ] Commit per ogni deliverable (writer, script, test, plan)

**Stima durata:** ~1-3 ore (planning conversazionale + creazione script wrapper + scrittura test).

**Status:** [ ] not started · [ ] in progress · [x] complete (2026-05-11, commit `ea89763` — plan 2143 righe, 7 decisions D-09-A..G, 12 truths, 10 threats STRIDE, 6 task seriali, 12 test nuovi totali; plan-checker workflow 3 iter convergente → APPROVED)

---

### STEP 1.5 — Execute Plan 05-09 Task 1-6 (sul PC PRIMARIO, sessione Claude)

**Cosa fa:** esegue i 6 task del Plan 05-09 sul PC primario per produrre tutti i deliverable di codice (dataset_writer extended + slice_worker integration + baseline.yaml bump + script wrapper + test). Sessione Claude Code single-thread, ~3-5h wall-clock con orchestration GSD (atomic commits, deviation handling, plan-checker integration).

**Comando:**
```
/gsd-execute-plan 5 9
```
(oppure `/gsd-execute-phase 5` — orchestrator riconosce che solo plan 05-09 è pending)

**Pre-check:**
- [ ] STEP 1 completato (Plan 05-09 APPROVED)
- [ ] Working tree pulito (`git status`)
- [ ] Backup parquet pre-esistente: `cp -r data/training/baseline_decisions data/training/baseline_decisions.pre-05-09`
- [ ] Suite pytest baseline corrente verde (controlla regressioni di partenza)

**Task del plan da eseguire (ordine seriale):**
1. Task 1: estende `dataset_writer.py` (schema v2 con `_SCHEMA_V2_REQUIRED_KEYS` extraction programmatica) + 5 test
2. Task 2: integra `slice_worker.py` con regime_cfg per-symbol + 3 timestamp distinti + enrichment post-engine (NON tocca top-level compute_all_extended, FIX D iter 3 invariante)
3. Task 3: modifica `data/configs/baseline.yaml` (bump `dataset_schema_version: 2`, hash invalidation force re-run)
4. Task 4: crea `scripts/run_baseline_05_09.py` (--smoke 3 mesi | default full 27/27 | --only-runs via `_force_clear_run` reuse | --force | path absolute via ROOT)
5. Task 5: 4 test no-leakage invariant (`tests/test_baseline_no_leakage_extended.py`) + 3 test runner (smoke + only-runs + regime per-symbol)
6. Task 6: recovery docs + suite verde finale (NO execution del full 27/27 — quello è STEP 3 sul PC secondario)

**Criteri di completamento:**
- [ ] 6 task atomici committati (uno per ogni task del plan)
- [ ] 12 test nuovi tutti verdi
- [ ] Suite pytest baseline esistente (~30 test Phase 5) tutti verdi (backward-compat preservato)
- [ ] `scripts/run_baseline_05_09.py --smoke` testato localmente (~120-180s wall-clock) — produce parquet smoke con schema v2 valido
- [ ] `05-09-SUMMARY.md` parziale scritto (sezione "Plan-write tasks completed"; full SUMMARY post-backtest sul PC secondario)
- [ ] STATE.md aggiornato (STEP 1.5 → complete)

**Stima durata:** ~3-5h sessione Claude Code attiva (no backtest reale; solo plan-write code).

**Failure recovery:** se un task fallisce, GSD si ferma con `.continue-here.md`. Riprendi con `/gsd-resume-work`.

**Status:** [ ] not started · [ ] in progress · [x] complete (2026-05-11, 6 commit atomici `5630bcc → 9e477cc` — +1138 LOC totali, 12 nuovi test verdi, suite globale 400 passed + 11 skip + 55 xfail; invariante FIX D iter 3 verificato; 1 deviation Rule 1 documentata; SUMMARY parziale plan-write committed, sezione backtest-execution lasciata pending PC secondario)

---

### STEP 2 — Commit + Push: pubblica Plan 05-09 sul remoto

**Cosa fa:** push del branch `feature/update-pythono-pure-strategy` al remoto GitHub, così il PC secondario può `git pull` e iniziare il setup.

**Comandi:**
```bash
# Verifica stato
git status
git log --oneline -10    # conferma commit Plan 05-09 presenti

# Push (no force, nessuna sorpresa)
git push origin feature/update-pythono-pure-strategy
```

**Pre-check:**
- [ ] STEP 1 completato
- [ ] Tutti i commit relativi al Plan 05-09 presenti localmente
- [ ] Nessun file `.env` o secret accidentalmente committato
- [ ] `scripts/run_baseline_05_09.py` esiste nel working tree

**Criteri di completamento:**
- [ ] Push completato senza errori
- [ ] Verifica su GitHub web: l'ultimo commit del branch corrisponde all'HEAD locale
- [ ] PC secondario può ora `git pull`

**Stima durata:** ~1-5 minuti.

**Status:** [ ] not started · [ ] in progress · [x] complete (2026-05-11, push 22 commit `a4fb6a9..9547797` su origin; remote tip == `9547797`; lavoro distribuito sbloccato per PC secondario)

---

### STEP 3 — PC SECONDARIO: setup + pre-flight + lancio backtest notturno

> **Esecuzione delegata.** Guida completa: **`.planning/SETUP-SECONDARY-PC.md`** (setup ambiente cross-platform, pre-flight, lancio, troubleshooting, consegna risultati via git).
>
> **Sul PC primario (questo) NON fai nulla per STEP 3.** Vai direttamente a STEP 4 in parallelo.

**Cosa fa (sul PC secondario):** clone repo + setup deps + pre-flight check + lancio full run notturno 27 backtest (3 pairs × 3 TF × 3 profile) sul range 10y. Output: parquet completo con 30+ feature + 4 meta, pushato indietro al remoto per il pull sul PC primario.

**Sintesi flow PC secondario** (dettagli in SETUP-SECONDARY-PC.md):
1. `git clone` + `git checkout feature/update-pythono-pure-strategy`
2. Setup ambiente Python 3.12 + venv (Path A Linux/macOS, B Windows, C Docker — l'utente sceglie)
3. Install deps con workaround MetaTrader5 (skip su Linux/Mac) + tqdm
4. Pre-flight: pytest writer + smoke run mini-range + schema validation
5. Solo se pre-flight OK → lancio full run con tmux/Start-Process (`python scripts/run_baseline_05_09.py`)
6. Run notturno ~3h18m
7. Verifica criteri: 27/27 ok, parquet 30+ cols, rows ≥ 1076
8. `git add data/training/baseline_decisions/` + `git commit` + `git push`

**Pre-check:**
- [ ] STEP 2 completato (push effettuato)
- [ ] PC secondario fisicamente accessibile
- [ ] PC secondario con corrente attaccata, sleep disabilitato per la notte
- [ ] (Sul PC primario) `.env` minimo trasferito al PC secondario via canale sicuro (USB / password manager / cloud privato) — NON via git

**Criteri di completamento (verifica AL RISVEGLIO):**
- [ ] PC secondario log finale: "27/27 ok"
- [ ] PC secondario ha pushato il parquet aggiornato
- [ ] PC primario può fare `git pull` e trovare il nuovo parquet
- [ ] Schema validation passa anche sul PC primario post-pull

**Stima durata:** setup ~20-30 min (manuale, una tantum) + pre-flight ~1-2 min + full run ~3h18m wall-clock = ~4h totali sul PC secondario.

**Status:** [ ] not started · [ ] in progress · [ ] complete

---

### STEP 4 — Phase 6 execute (sul PC PRIMARIO, in parallelo a STEP 3)

**Cosa fa:** completa MCP Tools part 1 (Wave 1 server/schemas, Wave 2 job_queue+backtest handlers, Wave 3 trail_daemon+position handlers).

**Comando:**
```
/gsd-execute-phase 6
```

**Pre-check:**
- [ ] STEP 2 completato (push fatto — non strettamente necessario per Phase 6 ma evita conflict)
- [ ] 06-01-SUMMARY esiste (confermato `8a90b94`)
- [ ] Working tree pulito (`git status`)
- [ ] PC secondario sta già lavorando o sta per iniziare (no contesa CPU se sul PC primario; sì se backtest gira sullo stesso PC — non è il tuo caso)

**Criteri di completamento:**
- [ ] 06-02-SUMMARY.md scritto
- [ ] 06-03-SUMMARY.md scritto
- [ ] 06-04-SUMMARY.md scritto
- [ ] Suite pytest verde
- [ ] STATE.md aggiornato: Phase 6 → complete (4/4 plans, 100%)
- [ ] ROADMAP checkbox Phase 6 → [x]

**Stima durata:** ~2-4 ore wall-clock.

**Failure recovery:** se un plan fallisce, GSD si ferma con un `.continue-here.md`. Riprendi con `/gsd-resume-work` o `/gsd-execute-plan 6 <num>`.

**Status:** [ ] not started · [ ] in progress · [ ] complete

---

### STEP 5 — Phase 8: discuss-phase

**Cosa fa:** raccoglie CONTEXT.md per Phase 8 (MCP Tools part 2 — ML training/inference/calibration tools, ML-aware risk evaluation).

**Comando:**
```
/gsd-discuss-phase 8
```

**Pre-check:**
- [ ] STEP 4 completato (Phase 6 chiusa)

**Note operative:**
- Alcune domande dipenderanno da Phase 7 (threshold, calibration shape). Rispondi `TBD pending Phase 7` quando serve — il discuss-phase accetta TBD.
- Riferimento incrociato: 07-CONTEXT.md (D-decisions Phase 7) e 07-RESEARCH.md (sklearn 1.8 pattern).

**Criteri di completamento:**
- [ ] `.planning/phases/08-mcp-tools-part-2/08-CONTEXT.md` creato
- [ ] `08-DISCUSSION-LOG.md` archiviato
- [ ] Commit `docs(phase-8): CONTEXT.md gathered`

**Stima durata:** ~30-60 min conversazionali.

**Status:** [ ] not started · [ ] in progress · [ ] complete

---

### STEP 6 — Phase 8: plan-phase

**Cosa fa:** produce i PLAN.md per Phase 8 (ML training/inference tools, ML-aware risk).

**Comando:**
```
/gsd-plan-phase 8
```

**Pre-check:**
- [ ] STEP 5 completato (08-CONTEXT.md esiste)
- [ ] (Opzionale) `/gsd-plan-phase 8 --research-phase` se servono ricerche tecniche su LightGBM inference packaging

**Criteri di completamento:**
- [ ] Plans 08-NN-PLAN.md scritti
- [ ] Plan-checker PASS
- [ ] Commit per ogni plan + commit indice

**Stima durata:** ~1-2 ore.

**Status:** [ ] not started · [ ] in progress · [ ] complete

---

### STEP 7 — Phase 9: discuss-phase

**Cosa fa:** CONTEXT.md per Phase 9 (Failure Analysis + Drift — clustering, drift monitor, retrain trigger, suggest_position_action).

**Comando:**
```
/gsd-discuss-phase 9
```

**Pre-check:**
- [ ] STEP 6 completato

**Note operative:**
- Forte coupling con Phase 7 (drift monitora il classifier) e con il dataset Phase 5 (`drafts_rows = []` deferred — Phase 9 potrebbe richiedere FORMING/NONE drafts; annotare se serve estendere ulteriormente il dataset).

**Criteri di completamento:**
- [ ] `.planning/phases/09-failure-analysis-drift/09-CONTEXT.md` creato
- [ ] Commit `docs(phase-9): CONTEXT.md gathered`

**Stima durata:** ~30-60 min.

**Status:** [ ] not started · [ ] in progress · [ ] complete

---

### STEP 8 — Phase 9: plan-phase

**Comando:**
```
/gsd-plan-phase 9
```

**Pre-check:**
- [ ] STEP 7 completato

**Criteri di completamento:**
- [ ] Plans 09-NN-PLAN.md scritti
- [ ] Plan-checker PASS

**Stima durata:** ~1-2 ore.

**Status:** [ ] not started · [ ] in progress · [ ] complete

---

### STEP 9 — Phase 10: discuss-phase

**Cosa fa:** CONTEXT.md per Phase 10 (Intermarket + News — DXY/yields/commodities context + economic calendar blackout).

**Comando:**
```
/gsd-discuss-phase 10
```

**Pre-check:**
- [ ] STEP 8 completato

**Note operative:**
- Bassa dipendenza da Phase 7. CONTEXT.md sarà più "pulito".

**Criteri di completamento:**
- [ ] `.planning/phases/10-intermarket-news/10-CONTEXT.md` creato
- [ ] Commit `docs(phase-10): CONTEXT.md gathered`

**Stima durata:** ~30-45 min.

**Status:** [ ] not started · [ ] in progress · [ ] complete

---

### STEP 10 — Phase 10: plan-phase

**Comando:**
```
/gsd-plan-phase 10
```

**Pre-check:**
- [ ] STEP 9 completato

**Criteri di completamento:**
- [ ] Plans 10-NN-PLAN.md scritti
- [ ] Plan-checker PASS

**Stima durata:** ~1-2 ore.

**Status:** [ ] not started · [ ] in progress · [ ] complete

---

### STEP 11 — Phase 11: discuss-phase

**Cosa fa:** CONTEXT.md per Phase 11 (Paper Deploy Gate — 30-day demo MT5 run, metric tolerance gate, promozione live).

**Comando:**
```
/gsd-discuss-phase 11
```

**Pre-check:**
- [ ] STEP 10 completato

**Note operative:**
- Phase 11 dipende da TUTTE le fasi a monte. Molte domande chiederanno "quale soglia metrica per promozione live?" — possono restare TBD finché Phase 7-9 non sono concrete, ma il discuss-phase scopre già le ambiguità.

**Criteri di completamento:**
- [ ] `.planning/phases/11-paper-deploy-gate/11-CONTEXT.md` creato
- [ ] Commit `docs(phase-11): CONTEXT.md gathered`

**Stima durata:** ~30-60 min.

**Status:** [ ] not started · [ ] in progress · [ ] complete

---

### STEP 12 — Phase 11: plan-phase

**Comando:**
```
/gsd-plan-phase 11
```

**Pre-check:**
- [ ] STEP 11 completato

**Criteri di completamento:**
- [ ] Plans 11-NN-PLAN.md scritti
- [ ] Plan-checker PASS

**Stima durata:** ~1-2 ore.

**Status:** [ ] not started · [ ] in progress · [ ] complete

---

### [Fallback opzionale] Eseguire il backtest sul PC PRIMARIO invece che secondario

> Solo se il PC secondario non è disponibile. In tal caso, **non procedere a STEP 4-12 in parallelo** — devi sospendere il lavoro GSD sul PC primario mentre il backtest gira (vincolo hardware dichiarato).
>
> **Pre-flight check da fare comunque** (riassunto, dettagli in SETUP-SECONDARY-PC.md §2):
> 1. `pytest tests/test_baseline_dataset_writer.py tests/test_baseline_runner.py -v`
> 2. Smoke run mini-range: `python scripts/run_baseline_05_09.py --smoke` (output in `data/training/_smoke_05_09/`)
> 3. Schema validation post-smoke (verifica 30+ cols + 4 meta presenti)
> 4. `rm -rf data/training/_smoke_05_09/`
>
> **Devcontainer persistence** (se usi VS Code Dev Containers):
> - Aggiungi `"shutdownAction": "none"` in `.devcontainer/devcontainer.json` per evitare che il container si fermi chiudendo VS Code
> - Installa tmux: `apt-get install -y tmux`
> - PC con corrente, sleep/hibernation disabilitati
>
> **Lancio del full run** (due opzioni):
> - **Opzione A**: in Claude Code → `/gsd-execute-plan 5 9` (VS Code resta aperto, orchestration GSD completa)
> - **Opzione B**: tmux + `python scripts/run_baseline_05_09.py 2>&1 | tee 05-09-RUN.log` (indipendente da Claude Code, commit + SUMMARY a mano dopo)

---

### STEP 13 — Sync risultati + Phase 7 planning + execution

**Cosa fa:** sincronizza il parquet pushato dal PC secondario, verifica schema, sblocca Phase 7. Pianifica i plan ML e poi eseguili.

**Comandi (in ordine):**

1. **Pull risultati dal PC secondario:**
```bash
git pull origin feature/update-pythono-pure-strategy
# Verifica parquet aggiornato
ls -la data/training/baseline_decisions/
```

2. **Schema validation post-pull:**
```bash
python -c "
import pyarrow.parquet as pq
t = pq.read_table('data/training/baseline_decisions/part-0.parquet')
required = {'rsi_14','atr_14','profile','regime','run_id','decision_ts_utc'}
missing = required - set(t.column_names)
assert not missing, f'MISSING: {missing}'
print(f'Rows: {t.num_rows}, Cols: {t.num_columns}, SCHEMA OK')
"
```

3. **Aggiorna stato pause Phase 7:**
```bash
# Aggiorna HANDOFF.json: blocker dataset_gap → resolved (link a 05-09-SUMMARY.md)
# Aggiorna .planning/phases/07-ml-classifier/.continue-here.md: spike Wave 0 NON più necessario
```

4. **Pianifica Phase 7:**
```
/gsd-plan-phase 7 --skip-research
```
(RESEARCH.md è già committato e current — `2938374`.)

Il planner deve produrre plans 07-01..N coprendo:
- Wave 0: feature engineering pipeline (load parquet, build X/y, encode categorical)
- Wave 1: walk-forward harness (expanding, 10 fold, embargo timeout_bars[tf], train/val 80/20 temporal)
- Wave 2: LightGBM training + manual Platt/Isotonic calibration (sklearn 1.8 pattern da 07-RESEARCH.md §Pattern 2 — NON usare CalibratedClassifierCV cv='prefit')
- Wave 3: threshold optimization profit-curve per profile, mediana 10 fold
- Wave 4: artifact persistence (joblib + sidecar metadata.json), inference hook (latency benchmark p95 < 10ms)

5. **Esegui Phase 7:**
```
/gsd-execute-phase 7
```

**Pre-check:**
- [ ] STEP 3 completato sul PC secondario (parquet pushato)
- [ ] STEP 4-12 completati sul PC primario (Phase 6 chiusa, fasi 8-11 con CONTEXT+PLAN)
- [ ] `git pull` eseguito senza conflitti
- [ ] Schema validation post-pull PASS
- [ ] HANDOFF.json / .continue-here.md aggiornati

**Criteri di completamento:**
- [ ] PLAN files Phase 7 esistono e passano plan-checker
- [ ] Classifier addestrato 10 fold, no `shuffle=True` mai usato
- [ ] Calibrazione: Brier-winner picking documentato per ogni fold (con fallback Platt per val<50 se applicabile)
- [ ] Threshold per profile salvato in metadata.json
- [ ] Latency benchmark p95 < 10ms registrato (su 1000 inferenze)
- [ ] `07-N-SUMMARY.md` per ogni plan + `07-VERIFICATION.md`
- [ ] STATE.md aggiornato: Phase 7 → complete

**Stima durata:** planning ~2-3 ore conversazionali; execution ~4-8 ore (dipende dai plan).

**Status:** [ ] not started · [ ] in progress · [ ] complete

---

## Stati post-completamento

Dopo STEP 13 i blocker noti del milestone v2-ml-backtest sono tutti chiusi:
- Phase 5 ✓ complete (9/9 plans, D-02 gap CHIUSO)
- Phase 6 ✓ complete (MCP tools part 1)
- Phase 7 ✓ complete (classifier ML)
- Phase 8-11 con CONTEXT.md + PLAN.md (pronti per `/gsd-execute-phase`)
- Dataset baseline completo e canonico

Prossimi step (FUORI scope di questo file, da decidere a STEP 13 chiuso):
- Execute Phase 8 → Execute Phase 9 → Execute Phase 10 → Execute Phase 11
- `/gsd-complete-milestone v2-ml-backtest` quando 11/11 fasi chiuse

---

## Come riprendere la sessione

Quando torni:
1. `/gsd-resume-work` → leggi `STATE.md` e poi questo file.
2. Identifica lo step in corso (cerca "in progress" o l'ultimo "complete").
3. Esegui il comando dello step successivo.
4. Aggiorna le checkbox di questo file a fine step (commit `docs: resume-plan checkbox update`).

**Se sei nel mezzo di uno step:**
- Cerca `.continue-here.md` nella phase corrente o `HANDOFF.json` aggiornato.
- Riprendi con `/gsd-execute-plan` o `/gsd-resume-work` come indicato dal sotto-step.

**Caso speciale STEP 3 (backtest sul PC secondario):**
- Mentre il PC secondario lavora di notte, sul PC primario procedi con STEP 4-12.
- Al risveglio: `git pull` per scaricare il parquet pushato dal secondario, poi STEP 13.

---

## Note di sicurezza

- **Non cambiare branch** — tutto su `feature/update-pythono-pure-strategy`.
- **Non eseguire il backtest sul PC primario mentre lavori in Claude Code** — vincolo hardware. Se non hai PC secondario, fermati per le ~3h18m di run.
- **Non rinegoziare decisioni locked** (latency p95<10ms, Plan 05-09 = Phase 5 reopen).
- **Backup parquet pre-re-run obbligatorio** prima di STEP 3 (sul PC primario, prima del push).
- **Pre-flight obbligatorio prima del full run notturno** — pytest + smoke + schema validation. Dettagli in `SETUP-SECONDARY-PC.md` §2. Non saltare: un fallimento a 2h30m è uno spreco di notte.
- **`/gsd-execute-plan` è uno slash command Claude Code, NON un comando shell.** Sul PC secondario il backtest si lancia con `python scripts/run_baseline_05_09.py`, NON con `nohup /gsd-execute-plan`.
- **`.env` NON va via git** (è in `.gitignore`). Trasferisci al PC secondario via USB/password manager/cloud privato.
- **Verifica il push prima di passare al PC secondario** (STEP 2): se il PC secondario fa `git pull` su un branch obsoleto, esegue un Plan 05-09 vecchio o assente.

---

## Changelog di questo file

- 2026-05-11 (rev 4) — riordino: STEP 1 = Plan 05-09 (era STEP 6), STEP 2 = push, STEP 3 = PC secondario backtest (era STEP 7), STEP 4-12 = Phase 6 execute + discuss/plan fasi 8-11 in parallelo, STEP 13 = sync + Phase 7. Vecchio STEP 7 dettagliato archiviato come "Fallback opzionale" compatto. Logica: sblocca prima il collo di bottiglia (3h18m), poi lavora in parallelo.
- 2026-05-11 (rev 3) — workflow distribuito: STEP 7 delegato a PC secondario (nuovo file `.planning/SETUP-SECONDARY-PC.md`). STEP 6 esteso "script-first" (Plan 05-09 deve produrre `scripts/run_baseline_05_09.py` eseguibile stand-alone). Aggiunto diagramma workflow distribuito in testa.
- 2026-05-11 (rev 2) — corretto STEP 7: aggiunto pre-flight 7.A (pytest + smoke + schema validation + no-leakage spot check), aggiunto 7.B persistence devcontainer (shutdownAction, tmux, PC no-sleep), chiarito 7.C due modalità di lancio (slash command Claude vs script Python in tmux). Rimosso comando errato `nohup /gsd-execute-plan ...` che mischiava slash command e shell.
- 2026-05-11 — creato dopo `/gsd-resume-work` + decisione utente workflow sequenziale.
