# Task — Fix CRIT-1 + CRIT-2: ripristinare volatility_regime e spread_session nella confluence

> **File**: `.planning/research/task-fix-confluence-repair-2026-05-28.md`
> **Tipo task**: fix chirurgico + misurazione. DUE bug correlati, stesso file (`live.py`).
> **Owner**: Claude Code.
> **Stima**: 2-3 ore (fix + test + smoke + report).
> **Precondizione**: audit `.planning/research/audit-strategy-system-2026-05-28.md`.
> **Output finale**: report markdown strutturato (STEP 6) + branch con il fix.

---

## Contesto (dall'audit 2026-05-28 — NON ri-diagnosticare)

Il baseline 210k è stato prodotto con una confluence **mutilata**: dei 5 fattori,
2 erano sempre False perché i loro input non venivano mai popolati. Risultato:
grade massimo strutturale = B in backtest, A+ irraggiungibile ovunque, e il
sistema ha tradato segnali a 3 fattori effettivi invece dei 5 di design. Questo è
la causa #1-#2 della sintesi audit.

**I due bug da fixare (entrambi in `strategy/adapters/live.py`):**

**CRIT-1 — volatility_regime hard-coded a None** (`live.py:85-86`)
```python
# volatility_regime richiede regime_cfg dict; senza cfg ritorna None per ogni bar.
regime_series = [None] * len(bars)
```
Il classificatore esiste ed è puro e anti-leakage: `volatility_regime(bars, cfg)`
in `indicators/volatility.py:272`, config via `load_regime_config(symbol, path)`
(`indicators/volatility.py:249`, legge `data/configs/regime.yaml`). Non viene
chiamato. Conseguenza: `factors.volatility_regime.*_required` (confluence.py:171-179)
legge una serie tutta None → fattore sempre False.

**CRIT-2 — spread_session non calcolabile in backtest** (`live.py:186` + config)
`_check_spread_session` (confluence.py:190-200) ha DUE vie per lo spread:
1. da `symbol_info.bid/ask` — assenti nel BacktestBroker (broker.py:115)
2. fallback da `ctx.spread_baseline_pips * pip_size` — ma `spread_baseline_pips`
   è None perché `SPREAD_BASELINE_PIPS` NON esiste in `config.py` (live.py:186
   fa `getattr(cfg, "SPREAD_BASELINE_PIPS", None)` → None)
Conseguenza: fattore spread_session sempre False in backtest.

---

## ⚠️ NOTA CRITICA — stai ROMPENDO una "parity" intenzionale

In `backtest/baseline/slice_worker.py:51-53, 355-358` c'è una scelta esplicita:
il `regime_cfg` è **deliberatamente isolato** dal detector "per preservare parity
con Plan 05-08". Questo significa che qualcuno ha INTENZIONALMENTE tenuto il regime
fuori dalla detection.

**Questa parity va rotta di proposito.** Era parity con un baseline che l'audit ha
dimostrato essere strutturalmente mutilato. Mantenerla significa continuare a
misurare la strategia rotta. Il punto di questo task è esattamente ripristinare il
fattore regime nella detection.

Conseguenza pratica: i test di regressione/determinismo che asseriscono "stesso
output di Plan 05-08" **falliranno** dopo questo fix, ed è ATTESO. Vanno
aggiornati (non aggirati) per riflettere il nuovo comportamento corretto. Vedi STEP 3.

---

## STEP 0 — Branch

```bash
cd <repo-root>
git status                 # pulito
git checkout -b fix/confluence-repair-regime-spread
git log --oneline -2
```

---

## STEP 1 — Fix CRIT-1: popolare volatility_regime in build_ctx_live

In `strategy/adapters/live.py`. Il `symbol` è già disponibile come parametro di
`build_ctx_live` (live.py:110). Ma attenzione: `_build_extended_indicators(bars)`
(live.py:40) NON riceve il symbol. Due approcci possibili:

**Approccio consigliato — calcola regime in build_ctx_live e iniettalo:**

1. In `build_ctx_live`, dopo aver costruito gli indicatori e PRIMA di assemblare
   il context, carica la config regime e calcola la serie:
   ```python
   from indicators.volatility import volatility_regime, load_regime_config
   # ... dentro build_ctx_live, dopo bars disponibili ...
   try:
       regime_cfg = load_regime_config(symbol, Path("data/configs/regime.yaml"))
   except (FileNotFoundError, KeyError):
       regime_cfg = None  # fallback: defaults interni di volatility_regime
   regime_result = volatility_regime(bars, regime_cfg)
   # regime_result.state è la list[str|None] da iniettare
   ```
2. Sostituisci nell'oggetto indicators il `volatility_regime=[None]*len(bars)` con
   `volatility_regime=regime_result.state`.

> Decisione di design: il path della config regime è hard-coded in slice_worker
> come `Path("data/configs/regime.yaml")`. Usa lo STESSO path per coerenza. Se
> preferisci, esponilo via `getattr(cfg, "REGIME_CONFIG_PATH", "data/configs/regime.yaml")`
> ma NON è obbligatorio per questo task.

**Vincoli:**
- Mantieni il modulo conforme a STRAT-08 (pure: niente datetime.now, niente I/O
  oltre la lettura della config che già avviene altrove con lo stesso pattern).
  La lettura YAML di config è accettata (lo fa già `load_cost_model`, `load_regime_config`).
- NON toccare `volatility_regime` né `load_regime_config` — funzionano, sono testati.
- Verifica anti-leakage: `volatility_regime` calcola il rank DENTRO la window
  trailing (docstring Pitfall 4). Non introdurre tu leakage nell'iniezione: la
  serie regime per il bar i deve usare solo bars[:i+1]. Poiché passi `bars`
  completi alla funzione che già rispetta la window trailing, è ok — ma il
  detector consuma `volatility_regime[-1]`, quindi assicurati che l'allineamento
  indici sia 1:1 con la serie bars (stessa lunghezza).

---

## STEP 2 — Fix CRIT-2: rendere lo spread disponibile in backtest

Due opzioni; scegli la più pulita per il codebase (probabilmente A).

**Opzione A — aggiungi SPREAD_BASELINE_PIPS a config.py (consigliata)**
Lo spread per simbolo esiste già in `data/configs/costs.yaml`
(`spread_pips` per EURUSD/GBPUSD/USDJPY). Il fallback in `_check_spread_session`
(confluence.py:195) usa `ctx.spread_baseline_pips`. Quindi:

1. In `config.py`, aggiungi un default sensato:
   ```python
   SPREAD_BASELINE_PIPS: float = _get_float("SPREAD_BASELINE_PIPS", 1.0)
   ```
   (usa l'helper esistente per i float se c'è; altrimenti `float(os.getenv(...))`
   col pattern degli altri campi. 1.0 pip è un baseline ragionevole multi-pair.)
2. Aggiorna `.env.example*` con `SPREAD_BASELINE_PIPS=1.0`.

> Limite di Opzione A: usa UN solo baseline per tutti i simboli. Accettabile per
> sbloccare la misura. Un fix per-symbol (leggere costs.yaml spread_pips nel
> context) è più preciso ma più invasivo → rimandato.

**Opzione B — per-symbol da costs.yaml (più preciso, più lavoro)**
In `build_ctx_live`, carica `load_cost_model(symbol)` e usa il suo `spread_pips`
come `spread_baseline_pips`. Più corretto ma tocca più codice. Scegli A salvo
forte motivo per B; documenta la scelta nel report.

**Vincolo:** NON modificare `_check_spread_session` in confluence.py — il fallback
c'è già e funziona. Devi solo far arrivare un valore non-None a
`ctx.spread_baseline_pips`.

---

## STEP 3 — Aggiornare i test (la parity rotta è ATTESA)

1. Gira la suite e identifica cosa si rompe:
   ```bash
   python -m pytest tests/ -q --tb=line 2>&1 | tail -40
   ```
2. I fallimenti attesi sono nei test che asseriscono parity/determinismo con
   Plan 05-08 (es. `test_baseline_determinism`, eventuali regression fixture).
   Questi vanno **aggiornati** per riflettere il nuovo comportamento corretto
   (regime+spread attivi), NON aggirati con skip o xfail.
3. **Aggiungi test nuovi** che prevengano la regressione del bug:
   - Un test che verifica che `build_ctx_live` produca `volatility_regime` con
     almeno alcuni valori non-None su un dataset di lunghezza > window (200).
   - Un test che verifica che `ctx.spread_baseline_pips` sia non-None dopo il fix.
   - Se esiste un test confluence con stub che popola regime/bid-ask
     artificialmente (l'audit cita setups.py stub righe 156-171, 200-215, 229-242),
     valuta un test che usi il VERO `build_ctx_live` per confermare il grade
     ceiling reale (ora dovrebbe poter raggiungere A in live, B+ in BT con spread).
4. Purity gate STRAT-08 deve restare PASS. Se il fix introduce un side-effect che
   la rompe, ripensa l'approccio (la lettura config YAML è ok, altri side-effect no).

> Regola: ogni test che cambi, documenta nel report PERCHÉ cambia (vecchia
> asserzione = comportamento rotto; nuova = comportamento corretto). Non
> cancellare test per "farli passare".

---

## STEP 4 — Smoke di misurazione: il primo baseline "vero"

Per la prima volta la confluence gira a (quasi) pieno. Misura cosa cambia.

### 4.1 Smoke EURUSD H1 2020, 3 profili
Stesso range del report Fix B0, per confrontabilità.
```bash
python scripts/run_baseline_backtest.py --symbols EURUSD --timeframes H1 --date-start 2020-01-01 --date-end 2020-12-31
```
(adatta i flag al runner reale; se non separa per profilo, gira tutto e filtra.)

### 4.2 Metriche da estrarre (confronto PRE vs POST fix)

Dal ledger, aggregato e per setup:
```
n_trades totali
win_rate
mean_pnl_usd / median_pnl_usd
mean_pnl_R
expectancy_post_costs
distribuzione grade: A+ / A / B / C   ← QUESTA è la metrica chiave
% trade con volatility_regime non-None all'entry
% trade con spread_session=True all'entry
```

La distribuzione grade è il punto: PRIMA del fix era 100% C (per Setup B) /
ceiling B. DOPO il fix, se regime e spread funzionano, dovresti vedere comparire
grade B e — in live — A. In backtest il ceiling resta B finché lo spread non è
calcolabile; con Opzione A lo spread c'è, quindi potrebbe salire.

### 4.3 Sanity
- Se la distribuzione grade è ANCORA 100% C, il fix non ha avuto effetto →
  verifica che `volatility_regime` non sia ancora None (logga la serie per 1 bar).
- Se il numero di trade crolla a zero, qualche gate è diventato troppo
  restrittivo → indaga prima di concludere.

---

## STEP 5 — Commit

Solo se test verdi (con quelli di parity aggiornati) e smoke plausibile:
```bash
git add strategy/adapters/live.py config.py .env.example* tests/<file modificati>
git commit -m "fix(strat): wire volatility_regime + spread_session into confluence

Audit 2026-05-28: baseline 210k computed with mutilated 5-factor confluence —
volatility_regime hard-coded None (live.py:85) and spread_session uncomputable
in backtest (missing SPREAD_BASELINE_PIPS). Both factors always False -> grade
ceiling B, A+ unreachable. This restores the designed confluence.

Intentionally breaks Plan 05-08 parity (was parity with a broken baseline).
Regression/determinism tests updated to reflect corrected behavior.

Co-Authored-By: Claude <noreply@anthropic.com>"
```
NON fare merge. Lascia il branch per review.

---

## STEP 6 — Report finale (formato richiesto)

````markdown
# Confluence Repair (CRIT-1 + CRIT-2) — Report [data]

## 1. Fix applicati
- CRIT-1 volatility_regime: [come iniettato, righe modificate live.py]
- CRIT-2 spread: [Opzione A o B scelta + perché; righe config.py + .env]
- Purity STRAT-08: [PASS/FAIL]

## 2. Test
- Suite: [N passed / N failed / N skipped]
- Test di parity aggiornati: [lista + perché ognuno]
- Test nuovi anti-regressione: [lista]
- [se FAIL inattesi: dettaglio]

## 3. Smoke — distribuzione grade PRE vs POST (la metrica chiave)
| metrica | PRE fix (da report B0/baseline) | POST fix |
|---|---|---|
| grade A+ | 0 | ? |
| grade A  | 0 | ? |
| grade B  | 0 | ? |
| grade C  | 100% | ? |
| % regime non-None | 0% | ? |
| % spread_session True | 0% | ? |

## 4. Smoke — performance PRE vs POST
- n_trades, win_rate, mean/median pnl, expectancy (aggregato + per setup)

## 5. Interpretazione (solo dati)
- Il ceiling grade è salito? Di quanto?
- I trade ora si distribuiscono su più grade o sono ancora tutti C?
- L'expectancy è cambiata? In che direzione?

## 6. Anomalie

## 7. Git status
- Branch / commit / files changed
````

---

## Vincoli rigorosi

1. **DUE fix soltanto**: regime (CRIT-1) e spread (CRIT-2). NIENTE altro —
   non min_grade, non SL geometry, non grade_map. Quelli sono task successivi.
2. **NON toccare** `volatility_regime`, `load_regime_config`,
   `_check_spread_session`, i detector, gli altri fattori. Sono corretti; il bug
   è solo che i loro input non arrivano.
3. **Rompere la parity Plan 05-08 è ATTESO e voluto.** Aggiorna i test di
   parity, non aggirarli. Documenta ogni test cambiato.
4. **Verifica anti-leakage** dell'iniezione regime (serie allineata 1:1 ai bar,
   nessun valore futuro). I test `test_baseline_no_future_leakage` devono restare
   verdi; se si rompono, è un campanello — indaga.
5. **Se la distribuzione grade resta 100% C dopo il fix**, fermati e riporta: il
   fix non ha avuto l'effetto atteso, serve capire perché prima di proseguire.
6. **NON proporre il fix successivo.** Consegna il report. La decisione (attivare
   min_grade? procedere a SL geometry? rebuild?) viene presa esternamente sui dati.
7. **Tempo massimo**: 3 ore. Se sfori sullo smoke, riduci a 3 mesi.

---

## Quando hai finito

Consegna il report markdown delle 7 sezioni come singolo messaggio. Niente
preamboli. L'analisi esterna deciderà il prossimo passo sulla distribuzione grade
PRE vs POST: è la prova se la strategia, finalmente completa, mostra segni di vita.
