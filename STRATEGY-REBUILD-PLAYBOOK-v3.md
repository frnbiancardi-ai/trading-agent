# Strategy Rebuild — Playbook v3 (diagnosi confermata)

> **File**: `STRATEGY-REBUILD-PLAYBOOK-v3.md` (root del repo, versionato).
> Sostituisce `STRATEGY-REBUILD-PLAYBOOK.md` (v1) e `STRATEGY-REBUILD-PLAYBOOK-v2.md`
> (v2) come piano operativo attivo. NON cancellare v1 e v2: restano come audit trail.
>
> Le novità rispetto al v2 derivano dal **Setup B Diagnostic Report 2026-05-19**
> (`.planning/research/diag-setup-b-2026-05-19.log`): la causa dello zero-trade di
> Setup B è stata isolata empiricamente e NON è quella che il v2 ipotizzava. Vedi
> sezione "Diagnosi confermata" sotto.
>
> Razionale generale invariato dal v2: prima di buttare i detector esistenti,
> aggiustare chirurgicamente ciò che li strozza. Rebuild from-books resta
> fallback (STEP 5).

---

## Diagnosi confermata (report 2026-05-19)

Smoke EURUSD H1 2020, single-process, 3 profili, logging gated `DIAG_SETUP_B=1`.
Setup B raggiunge il gate finale 489 volte in un anno ma **non emette mai un
READY**. Distribuzione exit reason:

| Exit reason | Count | % |
|---|---|---|
| `not_at_sr_zone` | 15.579 | 88.5% |
| `at_sr_zone_waiting_pattern` (FORMING) | 1.527 | 8.7% |
| `counter_trend_below_A_grade` | 489 | 2.8% |
| `ready` | **0** | **0.0%** |
| `confluence_below_2_factors` | 0 | 0% |
| `rr_below_profile_min` | 0 | 0% |

**Ipotesi precedenti SMENTITE:**
- ✗ `find_support_resistance` produce livelli inadatti → FALSO. SR popolato 100%,
  coverage at-zone 11.9% (fisiologico, ~0.5×ATR medio 2020).
- ✗ `scan_patterns` ritorna `[]` → FALSO. Pattern presenti 85.6% dei bar.
- ✗ `ENABLE_CANDLESTICK_PATTERNS` disabilitato → FALSO. Default Python True, attivo.

**Causa vera — incompatibilità geometrica fra Setup B e counter-trend gate D-07:**

Setup B è per costruzione un *reversal*: entri a un livello CONTRO la gamba
direzionale precedente. Per definizione è counter-trend rispetto a EMA50.
Il gate D-07 (`b_reversal.py`, blocco "Counter-trend gate") richiede `grade in
{A+, A}` quando `direction != sign(ema50_slope)`. Ma:

1. Il calcolo del grade usa 5 fattori, uno è `trend_alignment` — per un
   counter-trend è strutturalmente False → max 4/5.
2. Nei 489 candidati 2020, grade è **sempre C** (mai B, mai A) → significa che
   oltre a `trend_alignment` cadono altri 2+ fattori.
3. Risultato: Setup B **non può logicamente mai raggiungere grade A**, quindi
   il gate D-07 lo respinge al 100%. Non è tuning, è impossibilità strutturale.

**Effetto secondario (non causa primaria):** i 1.527 FORMING non vengono
persistiti nel parquet/CSV (drafts_rows DEFERRED Plan 05-09). Questo maschera
la diagnosi a chi guarda solo il CSV, ma non è la causa dello zero READY.

**Conclusione:** Setup B non è rotto nel detector, né negli input. È bloccato da
un gate generico semanticamente inappropriato per un setup reversal.

---

## STEP 0 — Preparazione (invariato dal v2)

```powershell
cd C:\trading-agent
git pull
git log --oneline -5     # verifica 11424d5 docs(05-10): NEGATIVE FINDING
Get-ChildItem C:\trading-agent\libri\ -Filter *.pdf   # servono solo per fallback STEP 5
```

### Vincoli architetturali da preservare

| Vincolo | Perché |
|---|---|
| Strategy modules side-effect-free (STRAT-08 AST gate) | Test in ms, isolato |
| Single shared call site `evaluate_proposal_for_bar` (STRAT-09) | Live e backtest allineati |
| Adapters live+backtest stesso shape D-05 | Detector usano stessa firma |
| ProposalDraft frozen, extension additive | Non rompere campi ml_* Phase 7 |
| EXECUTION_MODE=shadow default | Niente trade live mai |
| Priority D-06: grade-first poi PRIORITY tiebreak | I detector vanno in graduatoria |

---

## STEP 1 — Apertura phase

Nuova sessione Claude Code fresh context in `C:\trading-agent`. Verifica memoria:
*"Hai accesso alla memoria di Plan 05-10? Riassumi la diagnosi."*

`/gsd-phase add`

**Title**: `Strategy Diagnostic & Surgical Fix — recover edge from existing detectors`

**Insert**: fra Phase 5 e Phase 7.

**Scope**:
> Fix chirurgico dei 4 detector. Setup B: rimuovere counter-trend gate D-07
> (diagnosi 2026-05-19: blocca il 100% dei candidati reversal). Setup A/C/D:
> fix SL geometry + confluence audit. Re-test sul parquet 05-10. Gate
> STRAT-REBUILD-03. Solo se FAIL totale, fallback rebuild from-books.

---

## STEP 2 — Discuss-phase: quattro aree

`/gsd-discuss-phase`

### Area A — Diagnostica residua (ridotta rispetto al v2)

La diagnostica Setup B è già fatta (report 2026-05-19). Resta da fare per A/C/D:

A1. Bars-held per exit_reason × TF × setup_name (conferma "SL precoce mediana 3 bar")
A2. Realized R distribution per setup_name (asimmetria +3.05 vinti / −1.27 persi)
A3. Frequenza attivazione individuale dei 5 fattori confluenza per A/C/D —
    quale fattore strozza il grade A anche per i trend-following?
A4. SL_GAP: distribuzione per giorno settimana, distanza da weekend close

Output: `.planning/research/diag-failure-analysis-{date}.md`

### Area B — Fix chirurgici

**Fix B0 — Setup B counter-trend gate (NUOVO, priorità massima, diagnosi confermata)**
  - Rimuovere il blocco "Counter-trend gate D-07" da `detect_b_reversal`
  - Setup B è reversal per design: il counter-trend è feature, non bug
  - Mantenere come gate downstream: reject (≤1 fattore) + R:R floor
  - Grade B/C → usato per `confidence`, NON per ammissione/rifiuto
  - Atteso post-fix: ~400-500 trade Setup B/anno EURUSD H1 → finalmente misurabili

**Fix B1 — SL geometry (A/C/D)**
  - Buffer attuale 0.3-0.5×ATR cap 1.5×ATR → sweep {1.0, 1.5, 2.0}×ATR
  - Aggiungi `spread_buffer = max(0.5 pip, 0.3 × symbol_spread)`
  - TP geometry invariata (i TP funzionano: realized R +3.05)

**Fix B2 — Confluence checklist (A/C/D)**
  - Audit frequenza attivazione 5 fattori (da A3)
  - Identifica fattore strozzante, trasforma in soft-weight 0.5
  - Re-calibra grade mapping

**Fix B3 — Weekend protection**
  - flat-by-friday rule o SL widening overnight venerdì (da A4)

### Area C — Risk management

- `MAX_DAILY_DRAWDOWN_PERCENT` 2% (KS fixato)
- R:R floor per profilo: confermare 1.8 MODERATE
- Sizing percentuale balance, verifica anti-martingale post-drawdown

### Area D — Benchmark + acceptance

- Re-test parquet 05-10 23.6y come benchmark
- STRAT-REBUILD-03 verbatim: expectancy > +2 USD/trade post-costi, median ≥ 0, n ≥ 1000
- **Gate per-setup, non solo aggregato**: anche 1 solo setup che passa è
  materiale valido per Phase 7

---

## STEP 3 — Plan-write

`/gsd-plan-phase` → wave attesi:

### Wave 0 — Scaffolding diagnostico
- `scripts/diag_failure_analysis.py` per tabelle A1-A4
- Test fixture su mini-parquet 10k rows

### Wave 1 — Fix B0: Setup B counter-trend gate (PRIMA, è il più isolato)
- Rimuovi blocco counter-trend da `strategy/setups/b_reversal.py`
- I test esistenti `test_detect_b_reversal_counter_trend_gate` vanno AGGIORNATI
  (cambiano semantica: counter-trend ora ammesso). NON cancellarli, riscrivili
  per asserire il nuovo comportamento (counter-trend grade C → READY se R:R ok)
- Smoke EURUSD H1 2020 → verifica ~400-500 Setup B READY emessi
- Re-run baseline parziale (EURUSD H1) → misura expectancy Setup B isolato

### Wave 2 — Fix B1: SL geometry (A/C/D)
- Parametrizza `sl_atr_multiplier` per setup in `strategy.yaml`
- Modifica `_compute_levels_*` per accettare il parametro + `spread_buffer`
- Unit test geometry
- Backtest sweep {1.0, 1.5, 2.0}×ATR → `.planning/research/sl-geometry-sweep-{date}.md`

### Wave 3 — Fix B2: confluence checklist (A/C/D)
- `scripts/audit_confluence_factors.py`
- Soft-weight del fattore strozzante
- Re-calibra grade mapping + test grade A raggiungibile

### Wave 4 — Fix B3: weekend protection
- `is_near_weekend_close(bar_ts)` in `strategy/sessions.py`
- Wired in `evaluate_proposal_for_bar` come gate

### Wave 5 — Benchmark fix-vs-baseline
- `scripts/benchmark_surgical_fix.py`
- Re-esegue strategia fixed sui bar grezzi 05-10
- Confronto original vs fixed per setup/symbol/TF/profile
- Output `.planning/research/surgical-fix-{date}.md`

### Wave 6 — Gate verification + decisione
- STRAT-REBUILD-03 verbatim
- PASS → Phase 7 BLOCKED → plans-written
- PARTIAL (1-2 setup passano) → Phase 7 con setup ammessi, disabilita altri
- FAIL totale → fallback rebuild from-books (STEP 5)

---

## STEP 4 — Esecuzione

`/gsd-execute-phase <N>` sul primario. Stima 3-5 giorni.

Benchmark Wave 5 sul secondario:
```powershell
cd C:\dev\git\trading-agent
git pull
python scripts\benchmark_surgical_fix.py
```

### Output gate atteso (ipotetico, plausibile)

```
=== Benchmark Surgical Fix ===

B_reversal (gate D-07 removed):
  n: 0 → ~9.5k         ← finalmente firma
  win_rate: N/A → ?    ← DA MISURARE, ignoto finora
  expectancy_post_costs: N/A → ?
  GATE: ?              ← prima misurazione reale di Setup B

A_breakout (SL fixed):
  win_rate: 25.4% → ~40%
  expectancy: -2.35 → ?

C_compression (SL fixed):
  win_rate: 19.6% → ~38%
  expectancy: -0.77 → ?

D_pullback (SL fixed):
  win_rate: 25.2% → ~44%
  expectancy: -1.12 → ?  ← candidato più promettente per PASS

Decision: [setup che passano gate] → Phase 7 baseline
```

---

## STEP 5 — Fallback rebuild from-books

Trigger: tutti i 4 setup falliscono il gate anche dopo i fix.

Azione: apri NUOVA phase "Strategy Rebuild from Books", carica skill
`forex-strategy-builder`, leggi Murphy/Probo/StrategieOperative. Le tabelle
diagnostiche di Wave 0-5 + il report Setup B 2026-05-19 guidano la scelta di
setup *davvero diversi* (vincoli ex-ante: niente reversal con gate trend-following,
niente SL stretti ATR-based).

---

## STEP 6 — Failure paths intermedi

### Scenario A — Solo 1 setup passa (es. D_pullback)
Phase 7 con quel solo setup. Aggiorna i 6 PLAN.md Phase 7 (scale_pos_weight
ricalcolato, feature extraction D-only). Disabilita gli altri via strategy.yaml,
tieni il codice.

### Scenario B — Setup B post-fix è negativo
Era l'ipotesi peggiore ma ora misurabile. Se Setup B firma ma perde
sistematicamente, disabilita via strategy.yaml e documenta: "reversal puro non
ha edge su questi major/TF". Capture STRAT-REBUILD-08.

### Scenario C — Nessuno passa ma 1+ è breakeven [0, +2)
Phase 7 procede come "marginal baseline" — il ML ha un mix non degenerato da
cui imparare. Documenta come baseline marginale.

### Scenario D — Tutti i fix peggiorano
Rollback, trigger fallback STEP 5.

---

## STEP 7 — Aspetti operativi

### Parquet 05-10
Tienilo come benchmark. Wave 5 ri-esegue sui bar grezzi, non riusa pnl vecchio.
- `data/training/baseline_decisions/part-0.parquet` (vecchio, 4 setup, audit trail)
- `data/training/surgical_fix_decisions/part-0.parquet` (nuovo)

### FORMING persistence (sub-task opportuno)
Il report 2026-05-19 ha confermato che i FORMING non sono persistiti
(drafts_rows DEFERRED Plan 05-09). Per Phase 7 ML failure analysis serve un
dataset completo. Considera di chiudere questo DEFERRED come sub-task di Wave 0:
hook in `engine.run()` per persistere ogni proposta (READY+FORMING+NONE con reason)
nello shard `baseline_drafts`. Non bloccante, ma utile per il ML.

### Re-iterazione
Max 2 cicli di fix chirurgico prima del rebuild from-books.

### Decisioni umane (senza Claude)
- Quale ATR multiplier per SL fra {1.0, 1.5, 2.0}
- Quale fattore confluenza → soft-weight
- Accettare expectancy borderline
- Trigger fallback STEP 5

---

## STEP 8 — Reference rapida

### Comandi GSD
```
/gsd-phase add
/gsd-discuss-phase
/gsd-plan-phase
/gsd-execute-phase <N>
/gsd-progress
/gsd-validate-phase <N>
```

### File chiave
| File | Cosa |
|---|---|
| `.planning/research/diag-setup-b-2026-05-19.log` | Report diagnostico Setup B (archiviato) |
| `.planning/phases/05-baseline-backtest/05-10-SUMMARY.md` | Diagnosi 05-10 |
| `.planning/REQUIREMENTS.md` STRAT-REBUILD-01..04 | Requirements |
| `strategy/setups/b_reversal.py` | Detector B — rimuovere gate D-07 |
| `strategy/setups/{a,c,d}_*.py` | Detector da fixare SL geometry |
| `strategy/confluence.py` | score_factors, grade_for — audit |
| `strategy/__init__.py` | evaluate_proposal_for_bar (priority D-06) |
| `strategy/adapters/{live,backtest}.py` | build_ctx_* |
| `data/configs/strategy.yaml` | enable/disable setup + sl_atr_multiplier |
| `data/configs/costs.yaml` | costs per symbol |
| `tests/test_strategy_setups.py` | test detector (B counter-trend test da aggiornare) |

---

## TL;DR

1. Git pull, nuova sessione Claude Code fresh context
2. `/gsd-phase add` — "Strategy Diagnostic & Surgical Fix", fra 5 e 7
3. `/gsd-discuss-phase` — 4 aree: A diag residua A/C/D, B fix (B0 gate Setup B
   PRIMA, poi SL geometry + confluence + weekend), C risk, D benchmark+gate
4. `/gsd-plan-phase` — 7 wave (Wave 1 = rimozione gate D-07 Setup B)
5. `/gsd-execute-phase` — primario code, secondario benchmark
6. Verifica gate STRAT-REBUILD-03 → almeno 1 setup PASS sblocca Phase 7
7. Se FAIL totale → fallback rebuild from-books (STEP 5)
8. `/gsd-execute-phase 7` ML su dataset con edge

Nota chiave: per la PRIMA volta Setup B sarà misurabile (rimozione gate D-07).
Non sappiamo ancora se ha edge — ma almeno smetteremo di essere ciechi su di lui.
