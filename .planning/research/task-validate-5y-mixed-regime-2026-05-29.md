# Task — Validazione intermedia: B on/off su 5 anni a regime misto, EURUSD+GBPUSD, H1

> **File**: `.planning/research/task-validate-5y-mixed-regime-2026-05-29.md`
> **Tipo task**: validazione / misurazione (read-only sul codice di produzione).
> **Owner**: Claude Code.
> **Stima**: 2-4 ore (gran parte è tempo macchina del backtest).
> **Precondizione**: branch con confluence-repair + ENABLE_SETUP_* (feat/enable-setup-flags-disable-b).
> **Output finale**: report markdown strutturato (STEP 5).

---

## Obiettivo

Confermare (o smentire) su PIÙ regimi di mercato e DUE pair il risultato finora
visto solo su EURUSD H1 Q1 2020: **disabilitare B_reversal migliora l'expectancy**.

Il criterio di validità NON è la magnitudine del guadagno (numero rumoroso su
campioni piccoli) ma la **consistenza del SEGNO** dell'effetto: togliere B
migliora (o almeno non peggiora) in modo coerente attraverso regimi e pair diversi?

**Scope timeframe: SOLO H1.** Decisione presa: H1 è il timeframe primario di
struttura per ora. M15-trigger e H4-conferma sono lavoro futuro (multi-TF),
fuori da questo task. NON validare M15/M30.

---

## Perché 5 anni a regime misto (non 5 contigui)

Il valore di una validazione breve dipende da quanti regimi copre, non dal numero
di anni. 5 anni scelti per diversità di regime:

| anno | regime di mercato | perché |
|---|---|---|
| 2008 | crisi/volatilità estrema | crash, trend violenti, gap |
| 2014 | trend forte (USD bull) | direzionale pulito |
| 2017 | bassa volatilità / range | compressione, poche spinte |
| 2020 | crash + recovery | già misurato (Q1) — qui anno intero |
| 2023 | recente, post-rialzi tassi | regime corrente |

Se B è zavorra in TUTTI e cinque su ENTRAMBI i pair → robusto, procedi.
Se B è zavorra in 4/5 ma POSITIVO in un regime specifico (es. range 2017) →
finding prezioso: B non va eliminato, va attivato condizionalmente per regime.

> ⚠️ Verifica copertura dati PRIMA di lanciare: lo storico potrebbe non coprire
> il 2008. Controlla `data/historical/{EURUSD,GBPUSD}/H1.csv` min/max date. Se
> il 2008 manca, sostituiscilo con l'anno più vecchio disponibile e DOCUMENTA la
> sostituzione. Se manca anche altro, riporta la copertura reale e adatta il set
> agli anni effettivamente disponibili (mantenendo la diversità di regime).

---

## STEP 0 — Branch e verifica dati

```bash
cd <repo-root>
git status
git checkout feat/enable-setup-flags-disable-b   # parti da qui (B off + meccanismo)
git log --oneline -2

# Verifica copertura storico H1
python -c "
import csv
for sym in ['EURUSD','GBPUSD']:
    p=f'data/historical/{sym}/H1.csv'
    with open(p) as f:
        r=list(csv.reader(f))
    print(sym, 'rows', len(r)-1, 'first', r[1][0][:10], 'last', r[-1][0][:10])
"
```
Riporta la copertura reale nel report. Adatta gli anni se necessario.

---

## STEP 1 — Script di validazione dedicato

Il runner ufficiale (`run_baseline_backtest.py`) NON supporta filtri per-anno,
per-pair o per-TF: gira tutti i symbol × tutti i TF con date globali da
`baseline.yaml`. Quindi serve uno script dedicato che chiami `BacktestEngine`
direttamente (stesso pattern di `slice_worker.run_slice_3profiles`), iterando
sui parametri voluti.

Crea `scripts/_validate_5y_mixed.py` (temporaneo, NON committare il codice; il
REPORT sì). Lo script deve, per ogni combinazione `{anno} × {pair} × {profilo} × {B_on, B_off}`:

1. Caricare i bar H1 del pair, filtrati all'anno (`date_start=YYYY-01-01`,
   `date_end=YYYY-12-31`).
2. Costruire `Config` col profilo (`RISK_MODE`) e settare `ENABLE_SETUP_B`
   secondo il caso (True per il run "B_on", False per "B_off"). Gli altri
   ENABLE_SETUP_A/C/D = True sempre. Forza `INTRADAY_TIMEFRAME="H1"`.
3. Istanziare `BacktestEngine(... timeframe="H1", risk_profile=profilo)` e `run()`.
4. Raccogliere dal ledger: n_trades, n_win, win_rate, mean_pnl_usd,
   median_pnl_usd, total_pnl_usd. E per il run B_on: il subset di trade di
   B_reversal (n e total_pnl).

> Riusa l'infrastruttura esistente: `load_bars`, `BacktestEngine`, e il modo in
> cui `slice_worker` costruisce la Config per profilo. NON reinventare il loop di
> backtest. Guarda `backtest/baseline/slice_worker.py:run_slice_3profiles` e
> `backtest/engine.py:run_backtest` (engine.py:366) come riferimento.

**Combinatoria**: 5 anni × 2 pair × 3 profili × 2 (B on/off) = 60 run.
Su H1 un anno è ~6000 bar → gestibile. Attenzione all'O(N²) di build_ctx_live
(noto): 60 run da ~6000 bar possono richiedere tempo. Se sfori il budget:
- riduci prima i profili (fai solo MODERATE per il grosso, aggiungi CONS/AGG
  solo sugli anni dove il segno è ambiguo), oppure
- riduci i pair (EURUSD completo, GBPUSD solo come conferma su 2-3 anni).
Documenta ogni riduzione di scope.

---

## STEP 2 — Determinismo

Per ogni coppia (B_on, B_off) sullo STESSO anno/pair/profilo, l'unica differenza
deve essere il flag B. Stesso seed, stessa config altrove. Così la differenza
osservata è attribuibile a B (e all'effetto equity-path che ne consegue), non a
rumore di esecuzione. Verifica che lo slippage_seed sia fisso (da baseline.yaml).

---

## STEP 3 — Aggregazione: tabella del SEGNO

La metrica decisionale è il **segno di Δtotal_pnl = (B_off) − (B_on)** per ogni
cella anno×pair×profilo. Costruisci una matrice:

```
Δtotal_pnl (B_off − B_on), EURUSD H1
            CONS    MOD     AGG
2008        +/−     +/−     +/−
2014        ...
2017        ...
2020        ...
2023        ...
```
e identica per GBPUSD.

Conta: su 30 celle (5×3×2pair), in quante Δ > 0 (B off meglio), Δ ≈ 0, Δ < 0.

---

## STEP 4 — Analisi per regime

Per ogni anno, oltre al Δ, riporta il PnL DIRETTO dei soli trade B_reversal
(dal run B_on): in quali anni/pair B perde di più, in quali (se esistono) B è
positivo. Questo separa due ipotesi:
- B è zavorra UNIFORME → disabilitazione globale confermata
- B è zavorra TRANNE in regime X → candidato per attivazione condizionale

Nota anche, dove il dato è pulito (crowding ~0), l'**effetto equity-path**: il
Δtotal_pnl eccede il |PnL di B|? (come visto in Q1 2020). Se sì, conferma che le
perdite di B avvelenano il sizing dei trade successivi.

---

## STEP 5 — Report finale

````markdown
# Validazione 5y regime misto — B on/off, EURUSD+GBPUSD H1 — Report [data]

## 1. Copertura dati e anni effettivi
- EURUSD H1: [first]–[last]; GBPUSD H1: [first]–[last]
- Anni usati: [lista; eventuali sostituzioni e perché]
- Riduzioni di scope (se presenti): [quali e perché]

## 2. Setup validazione
- Script: scripts/_validate_5y_mixed.py
- Run totali eseguiti: [N] di 60 previsti
- Determinismo: [seed fisso confermato? differenza solo flag B?]

## 3. Matrice Δtotal_pnl (B_off − B_on)
[tabella EURUSD: anni × profili]
[tabella GBPUSD: anni × profili]
- Celle Δ>0: [N] / Δ≈0: [N] / Δ<0: [N]

## 4. PnL diretto di B_reversal per anno/pair (dal run B_on)
[tabella: anno × pair → n_trade_B, total_pnl_B, win%_B]
- B è negativo ovunque? o positivo in qualche regime?

## 5. Effetto equity-path
- Nelle celle a crowding ~0, Δtotal_pnl eccede |PnL_B|? [SI/NO + esempi]

## 6. Verdetto (solo dati)
- Il segno dell'effetto "B off migliora" è consistente attraverso regimi e pair?
- B è zavorra uniforme o condizionale a un regime?
- GO / NO-GO / CONDITIONAL per la disabilitazione permanente di B

## 7. Anomalie

## 8. Git status
````

---

## Vincoli rigorosi

1. **Scope**: solo validazione B on/off. SOLO H1. NIENTE M15/M30, niente
   min_grade, niente altri fix. Nessuna modifica al codice di produzione (solo
   lo script di validazione temporaneo + lettura).
2. **Read-only sul codice**: lo script chiama l'infra esistente, non la modifica.
3. **Determinismo**: stessa config tranne il flag B fra le due run di ogni cella.
4. **Criterio = consistenza del SEGNO**, non magnitudine. Campioni piccoli →
   guarda la direzione coerente su molte celle, non il numero su una cella.
5. **Se manca lo storico per un anno**, sostituisci documentando; non inventare
   dati né estrapolare.
6. **Se B risulta positivo in qualche regime**, NON è un fallimento — è un
   finding (attivazione condizionale). Riportalo, non nasconderlo.
7. **NON proporre il fix successivo.** Consegna il report.
8. **Tempo massimo**: 4 ore. Riduci scope (profili/pair) prima dei tempi, mai la
   diversità di regime degli anni.

---

## Quando hai finito

Consegna il report markdown delle 8 sezioni. L'analisi esterna deciderà sul
verdetto (sezione 6) se la disabilitazione di B è confermata e si procede ai fix
rimanenti (min_grade), tenendo il 24y come conferma finale.
