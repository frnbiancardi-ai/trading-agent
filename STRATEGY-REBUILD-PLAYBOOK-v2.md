# Strategy Rebuild — Playbook v2 (revisionato)

> ⚠️ **DO NOT COMMIT — LOCAL ONLY**
> Sostituisce il playbook v1 ("Strategy Rebuild — Playbook personale").
> Il v1 era corretto sui vincoli architetturali e sul gate STRAT-REBUILD-03,
> ma saltava la failure analysis empirica e andava dritto a "costruisci 2
> setup nuovi dai libri". Questa v2 inserisce **prima** una fase diagnostica
> e di **fix chirurgico** dei detector esistenti, e tiene il rebuild
> from-books come fallback **solo se** i fix non passano il gate.
>
> Razionale: la diagnostica sui 210k trade del parquet 05-10 mostra che il
> problema dominante non è "i setup sono sbagliati come concept" ma
> "geometria SL troppo stretta + Setup B detector rotto + confluence
> checklist strozzata". Se i fix bastano, salti 2-3 settimane di rebuild.

---

## Da dove veniamo (recap aggiornato con i numeri)

Plan 05-10 ha mostrato: 210.128 trade, win rate 24.3%, expectancy −0.22R
(−1.30 USD/trade), P&L cumulato −274k USD. 27/27 run muoiono per
balance-exhaustion. Phase 7 ML bloccata.

**Nuove evidenze emerse dalla failure analysis preliminare** (da
formalizzare in STEP 1 sotto):

| Evidenza | Numero | Implicazione |
|---|---|---|
| Setup B firma zero trade | 0/210k | Detector rotto, mai testato veramente |
| Setup distribution | D 64% / A 20% / C 17% / B 0% | Portafoglio sbilanciato su D |
| Grade A frequency | 0/210k | Confluence checklist strozzata (mai 4-5 fattori contemporaneamente) |
| SL bars-held mediana H1 | 3 barre | SL dentro il rumore intra-bar |
| SL bars-held p10 | 1 barra | 10% dei trade muore al primo wick (spread+slippage) |
| TP bars-held mediana | 9 barre | TP a tempo "normale", i TP funzionano |
| Realized R vinti | +3.05 (vs +2.82 planned) | Quando vinci, vinci meglio del piano |
| Realized R persi | −1.27 (vs −1.00 atteso) | Slippage allo SL costa 27% extra |
| SL_GAP | 4.4k trade, mean −3.04R | Mancanza di flat-by-friday rule |

**Diagnosi sintetica**: la strategia ha edge embrionale (TP che superano il
piano), distrutto da tre patologie composte:

1. SL geometry troppo stretta vs noise dei pair → 10-15% kill nelle prime
   2 barre
2. Setup B mancante → portafoglio incompleto, niente reversal at level
3. Confluence checklist mai grade A → operi sempre in zona subottimale

**Conseguenza per il piano**: prima di buttare i setup esistenti, vanno
*aggiustati chirurgicamente*. Se anche dopo il fix non c'è edge, allora
si fa rebuild from-books come da v1.

Contesto formale ancora valido in:
- `.planning/phases/05-baseline-backtest/05-10-SUMMARY.md`
- `.planning/REQUIREMENTS.md` → STRAT-REBUILD-01..04 (gate invariato)
- `.planning/STATE.md` → "Active Work" sezione Plan 05-10
- scripts/diag_decay_05_10.py, scripts/diag_decay_subset.py

---

## STEP 0 — Preparazione

### 0.1 Verifica libri PDF presenti (preventivo, serve dopo)

Sul primario `C:\trading-agent\libri\` — sempre necessario perché se i fix
falliscono ricaschi nel rebuild from-books.

```powershell
Get-ChildItem C:\trading-agent\libri\ -Filter *.pdf
```

Devi avere: Murphy (intermarket), Probo (forex operativo),
StrategieOperative.

### 0.2 Allinea i branch

```powershell
cd C:\trading-agent
git pull
git log --oneline -5    # verifica 11424d5 docs(05-10): NEGATIVE FINDING
```

### 0.3 Vincoli architetturali da preservare (invariati dal v1)

| Vincolo | Perché |
|---|---|
| Strategy modules side-effect-free (STRAT-08 AST gate) | Test in ms, isolato |
| Single shared call site `evaluate_proposal_for_bar` (STRAT-09) | Live e backtest allineati |
| Adapters `live` + `backtest` con stesso shape D-05 | Detector usano stessa firma |
| ProposalDraft frozen — extension solo additive | Non rompere campi ml_* di Phase 7 |
| EXECUTION_MODE=shadow default | Niente trade live mai |
| `evaluate_proposal_for_bar` priority D-06 | I detector vanno integrati in graduatoria |

### 0.4 Decisioni preliminari (cambiate dal v1)

| Domanda | Risposta v2 |
|---|---|
| Replace vs augment vs parallel? | **Fix chirurgico prima**, augment dopo solo se i fix falliscono |
| Quanti setup nuovi nella prima iterazione? | **Zero. Aggiusta i 3 esistenti + sblocca B = 4 setup risanati** |
| Quale TF primario? | **Diagnostica per-TF prima**, decisione data-driven (probabilmente H1) |
| Gate strict? | **Verbatim STRAT-REBUILD-03 invariato**: expectancy > +2 USD post-costi, median ≥ 0, n ≥ 1000 |

---

## STEP 1 — Failure analysis formalizzata (NEW — non c'era in v1)

**Obiettivo**: trasformare le evidenze preliminari (vedi tabella sopra) in
risultati riproducibili dentro `.planning/research/` con script committati.

Apri nuova sessione Claude Code in `C:\trading-agent`, fresh context.
Verifica memoria persistente con: *"Hai accesso alla memoria di Plan
05-10? Riassumi la diagnosi."*

### 1.1 `/gsd-phase add` — nuova phase

**Title**: `Strategy Diagnostic & Surgical Fix — recover edge from existing detectors before rebuild`

**Insert position**: fra Phase 5 e Phase 7 (sarà Phase 5.5 o rinumerazione)

**Scope (1-2 frasi)**:
> Fase diagnostica + fix chirurgico dei 3 detector esistenti (A/C/D) +
> sblocco Setup B (zero trade nel parquet 05-10 = detector rotto). Re-test
> sul parquet 05-10 come benchmark. Solo se non passa gate
> STRAT-REBUILD-03, fallback al rebuild from-books del playbook v1.

### 1.2 `/gsd-discuss-phase` — quattro aree

**Area A — Diagnostica formale (NEW)**

Lavori da eseguire (saranno wave plans):

A1. Distribuzione setup_name × symbol × TF × profile. Conferma B=0
    ovunque e ricerca per quale fold/era B firma o non firma.
A2. Bars-held per exit_reason × TF × setup_name. Quantifica il problema
    "SL precoce" per setup individuale (è solo D? Tutti?).
A3. Realized R distribution per setup_name. Quale setup ha la migliore
    asimmetria? Quale ha la peggiore?
A4. Frequenza di attivazione individuale dei 5 fattori di confluenza
    (`trend_alignment`, `setup_pattern`, `momentum`, `volatility_regime`,
    `spread_session`). Quale è il bottleneck che impedisce grade A?
A5. Analisi temporale: quale era (2002-2010 vs 2011-2020 vs 2021-2026) ha
    edge? Il sistema è era-specific?
A6. SL_GAP analysis: distribuzione per giorno della settimana, ora, e
    distanza dal weekend close.

Output atteso: `.planning/research/diag-failure-analysis-{date}.md` con
tabelle. Non serve azione, serve evidenza.

**Area B — Fix chirurgici (NEW, sostituisce "estrai dai libri" del v1)**

Fix B1 — **SL geometry**:
  - Buffer attuale: `0.3-0.5 × ATR`, cap `1.5 × ATR`
  - Test: `1.0 × ATR`, `1.5 × ATR`, `2.0 × ATR` (parametrizzato)
  - Aggiungi `spread_buffer = max(0.5 pip, 0.3 × symbol_spread)` come
    aggiuntivo
  - Mantieni TP geometry invariata (i TP funzionano, R realized = +3.05)

Fix B2 — **Setup B detector**:
  - Reverse-engineer del codice esistente (se esiste); altrimenti
    implementazione ex-novo seguendo `forex-trader-pro` playbook
  - Tre condizioni primarie (livello + prior leg + reversal candle) come
    AND
  - Reversal pattern come `OR` di 4 pattern (pinbar / engulfing / inside
    break / morning-evening star) — **non AND**
  - Soglie rilassate: RSI 45/55 invece di 35/65; closing_score ≥ 55
    invece di ≥ 65
  - Hit rate target: 0.3-1% delle barre (sanity check su 2002-2010 OOS)

Fix B3 — **Confluence checklist**:
  - Audit della frequenza di attivazione dei 5 fattori (vedi A4)
  - Identifica il fattore strozzante (atteso: `setup_pattern` o
    `volatility_regime`)
  - Trasforma il fattore strozzante da hard-gate a soft-weight 0.5 (cioè
    rende grade A raggiungibile con 3 hard + 2 soft)
  - Re-calibra mapping: grade A = score ≥ 4.0, grade B = 3.0-3.9, etc.

Fix B4 — **SL_GAP / weekend protection**:
  - Aggiungi flat-by-friday rule: chiudi posizioni con `bars_remaining_to_weekend < N`
  - Oppure: aumenta SL buffer per posizioni overnight venerdì
  - Decisione data-driven da A6

**Area C — Risk management ricalibrato (invariato dal v1)**

- `MAX_DAILY_DRAWDOWN_PERCENT`: 2% (KS bug fixato, si può riportare al
  valore production-realistico)
- R:R floor per profilo: confermare 1.8 MODERATE
- Sizing: percentuale balance (verifica anti-martingale dopo drawdown)

**Area D — Benchmark + acceptance (invariato dal v1)**

- Re-test su parquet 05-10 23.6y come benchmark
- STRAT-REBUILD-03 verbatim: expectancy > +2 USD/trade post-costi,
  median ≥ 0, n ≥ 1000
- **NEW**: gate per-setup, non solo aggregato. Anche se passa solo un
  setup (es. solo D_pullback con SL fixato), è materiale per Phase 7.

### 1.3 Decisioni pre-cotte per discuss-phase

| Domanda probabile | Risposta v2 |
|---|---|
| Quale skill carico? | **Nessuno per ora**. Skill `forex-strategy-builder` solo se fallback al rebuild. Per i fix non servono libri. |
| Quanti setup tocchiamo? | I 3 esistenti + sblocco B = 4 detector |
| Cosa modifichiamo dei detector esistenti? | Solo geometry SL e checklist. Logica entry invariata. |
| Replace o augment? | **Modifica in-place dei detector A/C/D + implementazione B mancante**. No augment. |
| Benchmark? | Parquet 05-10 esistente sul secondario |
| Gate strict? | STRAT-REBUILD-03 verbatim, no negoziazione |
| Failure path se fix non passano gate? | Trigger fallback `/gsd-phase add` rebuild from-books (playbook v1 entra in scope) |
| Risk parameters update? | MAX_DAILY_DRAWDOWN al 2%, R:R floor invariato |

---

## STEP 2 — Plan-write

`/gsd-plan-phase` → wave plans attesi:

### Wave 0 — Scaffolding diagnostico
- Script `scripts/diag_failure_analysis.py` che produce le 6 tabelle A1-A6
- Output a `.planning/research/diag-failure-analysis-{date}.md`
- Test fixture per validare gli script su un mini-parquet (10k rows)

### Wave 1 — Fix B1 — SL geometry
- Parametrizza `sl_atr_multiplier` in `strategy.yaml` per ogni setup
- Modifica `_compute_levels_*` per accettare il parametro
- Aggiungi `spread_buffer` come componente additiva
- Unit test: dato un bar fixture e ATR noto, SL atteso a posizione X
- Backtest sweep su {1.0, 1.5, 2.0} × ATR, output a
  `.planning/research/sl-geometry-sweep-{date}.md`

### Wave 2 — Fix B2 — Setup B detector
- Implementa `strategy/setups/b_test_sr.py` puro (rispetta STRAT-08)
- Detector di livelli S/R (lookback parametrico, default 50 barre)
- Detector dei 4 pattern di reversal come OR
- Validazione hit rate su 2002-2010 OOS (target 0.3-1%)
- Spot check visuale: 20 trade firmati a caso, plottati per review umana
- Unit test su scenari sintetici (pinbar su livello, engulfing, ecc.)

### Wave 3 — Fix B3 — Confluence checklist
- Script `scripts/audit_confluence_factors.py` (per A4)
- Identifica fattore strozzante
- Trasforma in soft-weight nel codice
- Re-calibra grade mapping
- Test che grade A sia raggiungibile su scenari sintetici dove prima era
  impossibile

### Wave 4 — Fix B4 — Weekend / gap protection
- Helper `is_near_weekend_close(bar_ts)` in `strategy/sessions.py`
- Wired in `evaluate_proposal_for_bar` come gate
- Test su SL_GAP candidates del parquet 05-10

### Wave 5 — Benchmark fix-vs-baseline
- Script `scripts/benchmark_surgical_fix.py`
- Re-esegue strategia *fixed* sui bar grezzi 05-10
- Confronto: original (4 setup vecchi) vs fixed (4 setup risanati) — per
  setup, per symbol, per TF, per profile
- Output: `.planning/research/surgical-fix-{date}.md`

### Wave 6 — Gate verification + decisione
- Check STRAT-REBUILD-03 verbatim
- **Se PASS**: update STATE Phase 7 BLOCKED → plans-written
- **Se PARTIAL** (1-2 setup passano gate, altri no): Phase 7 procede solo
  con setup che passano. Disabilita gli altri via strategy.yaml.
- **Se FAIL totale**: trigger fallback. Apri Phase "Strategy Rebuild
  from Books" come da playbook v1. Le evidenze raccolte in Wave 0-5
  guidano la scelta dei setup nuovi (sai cosa NON ha funzionato).

---

## STEP 3 — Esecuzione

`/gsd-execute-phase <N>` sul primario.

Tempo stimato: **3-5 giorni** (vs 4-8h del rebuild v1 perché c'è più
diagnostica, ma evita la spesa di leggere PDF + design from scratch).

Benchmark Wave 5 sul secondario:
```powershell
cd C:\dev\git\trading-agent
git pull
python scripts\benchmark_surgical_fix.py
```

Tempo benchmark: 2-6h sul parquet 209k.

### 3.1 Output atteso del gate

```
=== Benchmark Surgical Fix ===

A_breakout (fixed):
  n: 41k → 35k (SL più largo riduce false breakout)
  win_rate: 25.4% → 42.1%
  mean_pnl_R: -0.19 → +0.18
  expectancy_post_costs: -2.35 → +0.95 USD/trade
  GATE STRAT-REBUILD-03: FAIL (expectancy < +2)

C_compression (fixed):
  n: 35k → 28k
  win_rate: 19.6% → 38.4%
  mean_pnl_R: -0.75 → +0.04
  expectancy_post_costs: -0.77 → -0.21 USD/trade
  GATE STRAT-REBUILD-03: FAIL

D_pullback (fixed):
  n: 134k → 110k
  win_rate: 25.2% → 44.7%
  mean_pnl_R: -0.10 → +0.31
  expectancy_post_costs: -1.12 → +2.18 USD/trade
  GATE STRAT-REBUILD-03: PASS

B_test_sr (NEW):
  n: 0 → 8.5k
  win_rate: N/A → 39.1%
  mean_pnl_R: N/A → +0.12
  expectancy_post_costs: N/A → +1.45 USD/trade
  GATE STRAT-REBUILD-03: FAIL (expectancy < +2)

Decision: D_pullback PASS → Phase 7 baseline = D_pullback only
          A/C/B sotto gate, disable via strategy.yaml ma keep code per
          iterazione futura
```

I numeri sono ipotetici ma plausibili dato il pattern dei TP che già
funzionavano (+3.05 realized R). Aspettativa: **almeno 1 setup passa** il
gate dopo SL fix.

---

## STEP 4 — Sblocco Phase 7

Identico al v1 STEP 5:

```
/gsd-progress
```

Verifica advance Phase 7 BLOCKED → plans-written. I 6 PLAN.md di Phase 7
sono validi architetturalmente, ma vanno revisionati alla luce del nuovo
baseline. Se solo D_pullback è ammesso, ricalcola scale_pos_weight a
runtime in Plan 07-03.

`/gsd-plan-phase 7` per plan-check rapido, poi `/gsd-execute-phase 7`.

---

## STEP 5 — Fallback al rebuild from-books (v1)

Trigger: tutti e 4 i setup falliscono il gate STRAT-REBUILD-03 anche dopo
i fix.

Azione: apri NUOVA phase "Strategy Rebuild from Books" come descritto nel
playbook v1. Il playbook v1 da STEP 1 in poi resta valido — sai già che i
fix chirurgici non bastano, quindi serve materiale concettualmente
diverso dai libri.

Vantaggio rispetto al v1 direct: hai 6 tabelle diagnostiche
(.planning/research/diag-failure-analysis-{date}.md) che dicono *cosa è
fallito e perché*. La skill `forex-strategy-builder` può usarle come
vincoli ex-ante per estrarre setup *davvero diversi* (es. "non un altro
pullback ATR-based, voglio un setup con SL strutturale e R:R variabile").

---

## STEP 6 — Failure paths intermedi

### Scenario A — Solo 1 setup passa il gate (es. D_pullback)

Procedi a Phase 7 con quel solo setup. Phase 7 PLAN.md va aggiornato:
- Plan 07-01: feature extraction solo da D_pullback
- Plan 07-03: scale_pos_weight ricalcolato
- Plan 07-04: threshold sweep su distribuzione D-only
- Plan 07-06: risk_engine ML gate invariato

Disabilita A/C/B via `strategy.yaml`, ma tieni il codice. Iterazione 2
(post-Phase 7) può tentare di recuperarli con detector revisions
ulteriori.

### Scenario B — 2+ setup passano

Procedi a Phase 7 normalmente. Dataset più ricco, ML potrà imparare a
gradare fra i setup.

### Scenario C — Nessun setup passa, ma 1+ è breakeven (expectancy [0, +2))

Phase 7 può comunque proseguire come "marginal baseline": il ML
classifier ha materiale (mix di winner e loser non degenerato) per
imparare a filtrare. Documenta come baseline marginale.

### Scenario D — Tutti i fix peggiorano le cose

Improbabile ma possibile (es. SL più largo riduce win rate troppo).
Rollback completo, trigger fallback v1.

### Scenario E — Setup B non firma nemmeno con detector nuovo

Significa che le condizioni "livello + prior leg + reversal" non
coesistono mai sui pair tested. Nota empirica importante: i 3 major non
fanno reversal at level in modo riconoscibile, almeno non sui TF testati.
Capture come STRAT-REBUILD-08 per future iterazioni.

---

## STEP 7 — Aspetti operativi

### 7.1 Parquet 05-10

Tienilo come benchmark. Wave 5 ri-esegue strategia fixed sui bar grezzi
(via CSV), non riusa pnl_usd vecchio.

Path attesi sul secondario:
- `data/training/baseline_decisions/part-0.parquet` (vecchio = 4 setup
  broken, TAINTED audit trail)
- `data/training/surgical_fix_decisions/part-0.parquet` (nuovo = 4 setup
  risanati)

### 7.2 Re-iterazione

Massimo 2 cicli di fix chirurgico prima di passare al rebuild from-books:

- **Ciclo 1** (questo playbook): fix geometry + checklist + Setup B +
  weekend
- **Ciclo 2** (se ciclo 1 partial): tightening filtri (session, regime,
  multi-TF entry confirma)
- **Ciclo 3 (= fallback v1)**: rebuild from books

### 7.3 Quando coinvolgere Claude

Con Claude:
- Failure analysis (Wave 0)
- Implementazione TDD dei fix
- Setup B detector ex-novo
- Benchmark + verifica gate
- Update STATE/REQUIREMENTS

Senza Claude (decisioni umane):
- Quale fattore di confluenza trasformare in soft-weight
- Quale ATR multiplier per SL fra {1.0, 1.5, 2.0}
- Spot check visuale dei trade Setup B (20 plot review)
- Accettare expectancy borderline
- Trigger fallback v1

---

## STEP 8 — Reference rapida

### Comandi GSD

```
/gsd-phase add               # nuova phase Strategy Diagnostic & Surgical Fix
/gsd-discuss-phase           # 4 aree (A diag, B fix, C risk, D bench)
/gsd-plan-phase              # 7 wave plans attesi
/gsd-execute-phase <N>       # esegue tutto
/gsd-progress                # status check
/gsd-validate-phase <N>      # se servono test mancanti
```

### File chiave

| File | Cosa contiene |
|---|---|
| `.planning/phases/05-baseline-backtest/05-10-SUMMARY.md` | Diagnosi 05-10 |
| `.planning/REQUIREMENTS.md` (STRAT-REBUILD-01..04) | Requirements formali |
| `.planning/STATE.md` (Active Work) | Status milestone |
| `scripts/diag_decay_05_10.py` | Diagnostica esistente |
| `scripts/diag_decay_subset.py` | Subset edge-hunt |
| `scripts/diag_failure_analysis.py` (NEW) | Failure analysis formale |
| `scripts/audit_confluence_factors.py` (NEW) | Frequenza fattori |
| `scripts/benchmark_surgical_fix.py` (NEW) | Re-bench post-fix |
| `strategy/__init__.py` | Barrel + evaluate_proposal_for_bar |
| `strategy/setups/{a,c,d}_*.py` | Detector da modificare |
| `strategy/setups/b_test_sr.py` (NEW or FIXED) | Detector Setup B |
| `data/configs/strategy.yaml` | Config setup + nuovi sl_atr_multiplier |
| `data/configs/costs.yaml` | Costs per symbol |
| `tests/test_strategy_purity.py` | AST gate purity |

### Commit message convention (invariato)

Pattern: `feat(N-XX): ...`, `fix(N-XX): ...`, `test(N-XX): ...`,
`docs(N-XX): ...`. Co-Authored-By per i commit di Claude.

---

## Domande aperte da chiarire in discuss-phase

1. **SL multiplier sweep**: testiamo {1.0, 1.5, 2.0} oppure aggiungiamo
   anche 0.75 e 2.5 per avere curva completa?
2. **Setup B implementation strategy**: reverse-engineer del codice
   esistente (se c'è) o implementazione ex-novo? Dipende dallo stato del
   detector attuale.
3. **Confluence soft-weight**: 0.5 per il fattore strozzante o granularità
   maggiore (es. 0.0/0.25/0.5/0.75/1.0)?
4. **Weekend rule**: flat-by-friday hard cutoff (es. venerdì 20:00 UTC) o
   SL widening progressivo nelle ultime N ore?
5. **MAX_DAILY_DRAWDOWN_PERCENT**: 2% diretto o sweep {2%, 5%, 10%} per
   verificare sensitivity post-KS-fix?
6. **Gate per-setup vs aggregato**: se aggregato è negativo ma uno singolo
   è positivo, procediamo con quello solo? (Mia raccomandazione: sì.)

---

## TL;DR

1. **Verifica libri PDF** (servono solo per fallback) e git pull
2. **Nuova sessione Claude Code** in `C:\trading-agent`, fresh context
3. **`/gsd-phase add`** — title "Strategy Diagnostic & Surgical Fix",
   insert fra 5 e 7
4. **`/gsd-discuss-phase`** — 4 aree: A diagnostica, B fix chirurgici, C
   risk, D benchmark+gate
5. **`/gsd-plan-phase`** — 7 wave (scaffold diag, 4 fix wave, benchmark,
   gate)
6. **`/gsd-execute-phase`** — primario implementa, secondario benchmarka
7. **Verifica gate** STRAT-REBUILD-03 → se almeno 1 setup PASS, Phase 7
   sblocca
8. **Update STATE** Phase 7 BLOCKED → plans-written
9. **Se TOTAL FAIL** dei fix → fallback: apri NUOVA phase "Strategy
   Rebuild from Books" come da playbook v1 STEP 1+
10. **`/gsd-execute-phase 7`** ML training su dataset con edge

Razionale finale: i tuoi dati hanno *edge embrionale* (TP che superano il
piano). Prima di buttare via i detector, prova ad aggiustare la geometria
che li sta soffocando. Se basta, hai risparmiato 3 settimane di rebuild
from-books. Se non basta, il rebuild v1 entra in scope con evidenze
diagnostiche solide per guidarlo.