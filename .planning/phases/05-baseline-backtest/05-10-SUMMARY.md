---
phase: 05-baseline-backtest
plan: 10
title: "Full-history baseline backtest (23.6y) — NEGATIVE FINDING: strategia structurally negative-expectancy"
subsystem: backtest/baseline
tags: [phase-5, baseline-backtest, plan-10, negative-finding, strategy-rebuild-trigger, blocks-phase-7]
requires:
  - 05-09-SUMMARY (Plan 05-09 baseline 1076 trade, ora rivelato come artefatto del KS bug)
  - fix f21abda (KS giornaliero permanente in BacktestBroker)
  - config bc3c0d6 (MAX_DAILY_DRAWDOWN_PERCENT 2% -> 20%)
provides:
  - "Dataset baseline_decisions schema-v2 209k × 59 (PC secondario, NON pushato — 81MB binario)"
  - "Diagnosi root-cause della distribuzione anomala 2002-2021: NIENTE è un bug del runner, è la strategia"
  - "Trigger nuova requirement REQ-STRAT-REBUILD — strategy core senza edge, va rifatta prima di Phase 7"
  - "scripts/diag_decay_05_10.py + scripts/diag_decay_subset.py per repro diagnosi"
affects:
  - "Plan 05-09 dataset (1076 trades) marcato come TAINTED — artefatto KS bug, NON è baseline veritiero"
  - "Phase 7 ML Classifier: BLOCCATA, manca un dataset baseline con edge positivo su almeno un subset"
  - "Roadmap milestone v2-ml-backtest: va inserita nuova phase strategy rebuild PRIMA di Phase 7"
tech-stack:
  unchanged:
    - "strategy/* (4 setup detector ATR-based — risultano structurally negative-expectancy)"
    - "indicators/* (compute_all + compute_all_extended invariati)"
    - "config/strategy.yaml, config/patterns.yaml (invariati)"
key-files:
  created:
    - "scripts/diag_decay_05_10.py (per-year/era/run aggregates + cumulative PnL audit)"
    - "scripts/diag_decay_subset.py (subset edge-hunt across 117 combinations)"
  not_committed:
    - "data/training/baseline_decisions/part-0.parquet (81MB, 209k rows — sostituirebbe il dataset Plan 05-09)"
    - ".planning/research/_smoke_equity_curves/ (27 PNG rigenerate dal nuovo run)"
decisions:
  - "D-10-A1: Plan 05-09 dataset (1076 trades) ARCHIVIATO come tainted-by-KS-bug, NON utilizzabile per Phase 7"
  - "D-10-A2: Plan 05-10 dataset (209k trades) NON committato — è 'vero' ma documenta strategia perdente, non base ML"
  - "D-10-A3: Phase 7 BLOCCATA in attesa di nuovo baseline con edge positivo su almeno un subset"
  - "D-10-A4: REQ-STRAT-REBUILD apre nuova phase 'Strategy Rebuild' prima di Phase 7 nell'order milestone"
  - "D-10-A5: Plan 05-10 chiuso come INTENDED-NEGATIVE-FINDING, non come deliverable utile alla milestone"
metrics:
  parquet_rows: 209052
  parquet_cols: 59
  unique_run_id: 27
  wall_clock_seconds: 269388  # 74h49m sul PC secondario
  date_range_actual: "2002-10-25 → 2021-10-19 (last-trade per run varia 2004→2021)"
  date_range_target: "2002-10 → 2026-05-04 (full CSV coverage)"
  validation_criteria: "VAL-1/2/6 PASS, VAL-3/4/5 FAIL (rows 70× sopra, time coverage 4.5y mancanti, wall-clock 4.7× sopra cap)"
  global_win_rate: 0.243
  global_mean_pnl_usd: -1.27
  positive_expectancy_subsets_4way: 6  # su 81 combinazioni n>=50
  max_subset_expectancy_usd_per_trade: 0.524  # GBPUSD M30 CONSERVATIVE compressed
  date_diagnosis_completed: "2026-05-18"
---

# Phase 5 Plan 10: Full-history baseline backtest — NEGATIVE FINDING Summary

Plan 05-10 doveva produrre il baseline schema-v2 esteso da 10y a 23.6y per arricchire il training set Phase 7. L'esecuzione è completata 27/27 ok sul PC secondario il 2026-05-16 (74h49m wall-clock), ma il dataset prodotto ha rivelato due verità inattese a cascata che invalidano la pianificazione corrente della milestone:

1. **Plan 05-09 lock (1076 trade) era un artefatto del bug `f21abda`** — non un baseline veritiero. Il KS giornaliero in `BacktestBroker` non si resettava, lasciando il broker "inchiodato" dopo il primo -2%.
2. **La strategia base — anche post-fix KS — è strutturalmente negative-expectancy in ogni subset testato.** Non è un problema cross-era né regime-mismatch. Hit rate 24%, 75% chiusure in SL, R < 1 → expectancy negativa aritmeticamente certa.

Plan 05-10 si chiude quindi come **finding negativo documentato**, non come deliverable utile alla milestone. La Phase 7 ML training resta bloccata in attesa di un baseline con edge positivo verificato.

## Risultato

Scope **plan-execute** chiuso 2026-05-16, **diagnosi root-cause completata 2026-05-18**.

Output principale **non è un dataset utile**, è una scoperta scientifica:

| Aspetto | Esito |
|---|---|
| Run tecnico | 27/27 ok, schema-v2 OK, audit trail SQLite OK |
| Dataset dimensione | 209.052 rows × 59 cols |
| Validation criteria 05-10-PLAN | 3 PASS / 3 FAIL (VAL-3 rows 70× target, VAL-4 4.5y recenti mancanti, VAL-5 wall-clock 4.7× sopra cap) |
| Causa "decay 2013→2021" | Strategy structurally negative-expectancy + balance-exhaustion per ogni run |
| Causa "cutoff 2021-10-19" | Time-to-exhaustion variabile per turnover (M15 muore 2004-2007, M30 2009-2013, H1 2015-2021) |
| Phase 7 ML readiness | **BLOCCATA** — dataset non offre segnale separabile (varianza intra-classe troppo bassa) |

## Root Cause Analysis

### Tappa 1: KS giornaliero permanente (fix `f21abda` del 2026-05-13)

`BacktestBroker.get_account_state()` ritornava `starting_balance_of_day = self._initial_balance` hard-coded (mai aggiornato durante il backtest). Conseguenza: `risk_engine.evaluate_trade` (riga 55-63) si attivava appena `balance <= starting_balance_of_day * (1 - MAX_DAILY_DRAWDOWN_PERCENT/100)`. Con la soglia 2% allora vigente, una volta sotto 9800 USD il KS restava attivo per il resto del backtest (in live si resetta ogni giorno).

**Effetto su Plan 05-08/09:** i 1076 trade del parquet baseline_decisions erano concentrati nelle prime ~3 settimane (entry_time 2015-05-14 → 2015-06-03), non distribuiti sul range 10y. Il "low count" non era selezione qualitativa, era il broker simulato bloccato.

**Test di reproducibilità:** 3 mesi EURUSD M15 AGGRESSIVE pre-fix vs post-fix:
- pre-fix:  438 trade su 27 giorni (2015-05-07 → 2015-06-02)
- post-fix: 880 trade su 71 giorni (2015-05-07 → 2015-07-31)

Il fix è corretto. Regression guard aggiunto `tests/test_backtest_broker.py::test_starting_balance_of_day_resets_on_utc_day_rollover`.

### Tappa 2: structural negative-expectancy della strategia (scoperta 2026-05-18)

Con KS riparato + soglia drawdown salita a 20% (`bc3c0d6`), il backtest 23.6y ha potuto correre liberamente. Il risultato (209k trade) ha mostrato un pattern apparentemente strano: 51k trade/anno nel 2003-2004, decay progressivo a quasi-zero post-2013, cutoff 2021-10-19. L'analisi via `scripts/diag_decay_05_10.py` ha chiarito tutto:

**Tutti i 27 run terminano con `final_pnl ≈ -9.840 USD`** (balance partito da ~10.000 → finito a ~160). E `trough_pnl == final_pnl` per ogni run: nessun run è mai "risalito" dopo il crollo. Sono tutti morti per balance-exhaustion, l'ora di morte varia perché M15 brucia capitale più velocemente di H1.

| Sintomo | Valore | Implicazione |
|---|---|---|
| Win rate medio | 24-27% scendendo al 16-21% in ere recenti | edge negativo, non regime mismatch |
| Exit reason | 73-83% SL, 17-24% TP | trade chiudono in SL 3-4× più spesso del TP |
| Setup type | 100% `READY` in tutte le ere | un solo tipo di setup attivo (i detector A/B/C/D producono solo READY) |
| `lot_size` quartiles | Q1=0.24 → Q4=0.01 | sizing % del balance → man mano che perdi, lotti scendono al minimo broker |
| Expectancy stimata | ≈ 0.25·TP − 0.75·SL < 0 anche con TP=2R | il vincolo aritmetico esclude profitto |
| Cumulative PnL peak | nei primi 6-12 mesi quasi sempre | la strategia non ha mai avuto un'era buona, è andata "su" per sample-size piccolo iniziale e poi giù monotono |
| Last-trade clustering | M15 muore 2004-2007, M30 2009-2013, H1 2015-2021 | nessun evento sistemico, è solo time-to-exhaustion per turnover |

### Tappa 3: subset edge-hunt (script `diag_decay_subset.py`, esecuzione 2026-05-18)

Cercato edge in 117 combinazioni: 1-way su regime/profile/symbol/timeframe (12 gruppi), 2-way (54), 3-way symbol×TF×regime (27), 4-way con profile (81). Risultato:

- **1-way e 2-way: ZERO gruppi positive.** Tutti i regime, tutti i profili, tutti i simboli, tutti i TF: mean_pnl < 0.
- **3-way (n≥100): 2 su 27 positive** ma con expectancy ≤ +0.20 USD/trade.
- **4-way (n≥50): 6 su 81 positive**, top GBPUSD M30 CONSERVATIVE compressed +0.524 USD/trade.

Tre fattori uccidono qualsiasi possibilità di gating ex-post su questi subset:

1. **Median PnL negativo in TUTTI i gruppi positivi** (-1.89 a -6.07). La media positiva è retta solo da pochi outlier-TP. Distribuzione asimmetrica al ribasso, bastano 2-3 trade perdenti in più per cancellare la media.
2. **Win rate 20-28%** anche nei "buoni". Sotto la soglia di 40% richiesta per stabilità statistica.
3. **Expectancy +0.12 / +0.52 USD/trade non copre i costi reali.** Spread + slippage + commissioni in live su questi simboli sono ~0.5-2 USD su un lotto 0.01-0.05 → l'edge teorico evapora sotto i costi.

Anche il sanity check 2002-2003 (dove l'analisi precedente suggeriva un possibile "early edge") conferma: solo EURUSD H1 +1.25 USD/trade (n=3812), il resto -2 → -4. Non è un'era con edge, è una singola coppia/TF con qualche TP fortunato all'inizio.

**Direction bias:** BUY -1.38, SELL -1.16. Né l'uno né l'altro lato lavora.

## Validation criteria 05-10-PLAN — risultati

| Criterio | Atteso | Reale | Verdetto |
|---|---|---|---|
| VAL-1 — 27/27 ok | 27/27 ok | 27/27 ok | ✅ |
| VAL-2 — schema-v2 | ≥55 cols + chiavi canoniche | 59 cols, chiavi OK | ✅ |
| VAL-3 — row count | 2.000–3.000 (atteso ~2.500) | 209.052 | ❌ 70× sopra |
| VAL-4 — time coverage | min ≤ 2003-12-31 AND max ≥ 2025-12-31 | min 2002-10-25 OK / max 2021-10-19 | ❌ 4,5y mancanti |
| VAL-5 — wall-clock | <16h | 74,8h | ❌ 4,7× sopra cap soft |
| VAL-6 — profili ordine | AGGR > MOD > CONS | 81.7k > 67.5k > 59.8k | ✅ ma ratio collassato (1.37× vs 6.1× Plan 05-09) |

VAL-3/4/5 sono failure **legittimi** (non bug): il dataset *poteva* essere più piccolo e regimi più moderni — sarebbe stato se la strategia avesse smesso di tradare quando logicamente doveva. Invece ha continuato finché ha esaurito il capitale.

## Cross-phase impact

**Plan 05-09 (1076 trade) — RICLASSIFICATO**

Status precedente: "Phase 5 ✓ COMPLETE 9/9 (parquet schema-v2 1076 × 59 cols PASS)" come baseline-of-record per Phase 7.

Status nuovo: **tainted-by-KS-bug**, non è un baseline veritiero. Resta committato per audit trail e regression replay, ma non è utilizzabile come training set ML.

**Phase 7 ML Classifier — BLOCCATA**

Phase 7 era "plans-written, ready for /gsd-execute-phase 7". Continua a essere in stato plan-written (i 6 PLAN.md non sono invalidati architetturalmente), ma l'esecuzione viene **sospesa** fino a quando un nuovo baseline non offra edge positivo verificato su almeno un subset (regime/setup/TF/coppia) con expectancy ≥ +2 USD/trade post-costi e median PnL ≥ 0 su n ≥ 1000.

Motivo tecnico: un classifier binario "trade was profitable y/n" addestrato su un dataset dove **il 75% degli esempi è perdente in qualsiasi sub-popolazione testata** non ha varianza intra-classe sufficiente per separare buoni da cattivi. Il modello imparerebbe a predire "trade perde" come prior, non a discriminare features.

**Phase 8 MCP ML (Wave 1-5) — Cascade BLOCCATA**

Wave 1-5 hard-dipendono da Phase 7 complete (vedi STATE.md). Wave 0 (Plan 08-01 scaffolding) resta valido perché è solo plumbing API. La feature `run_ml_on backtest` (Plan 08-06) richiede un bundle.pkl prodotto da Phase 7 che oggi non esiste.

**Roadmap milestone v2-ml-backtest — VA RIVISTA**

Inserire nuova phase **"Strategy Rebuild"** fra Phase 5 e Phase 7 nella roadmap. La phase nuova:
- Usa skill `forex-strategy-builder` (path libri `C:\trading-agent\libri\` — Murphy intermarket, Probo forex operativo, StrategieOperative)
- Seleziona 2-3 setup specifici dai testi (es. breakout su compression confermato da volume, reversal su S/R con pin bar + closing score, trend pullback su EMA-200 con confluenza Fibo)
- Implementa i nuovi detector dedicati (eventualmente rimpiazzando o affiancando i 4 attuali)
- Ri-testa su Plan 05-10 dataset come benchmark
- **Gate per procedere a Phase 7**: almeno un detector con expectancy > +2 USD/trade post-costi e median PnL ≥ 0 su un subset n ≥ 1000

## Diagnostic scripts predisposti

`scripts/diag_decay_05_10.py` (8 blocchi):

1. Per-year overview (rows, win_rate, mean_pnl, mean_lot, mean_risk, mean_atr)
2. Era aggregates (early 2002-2010 / mid 2011-2015 / modern 2016-2026)
3. exit_reason distribution per era
4. setup_type distribution per era
5. regime_state distribution per era
6. Cumulative PnL per run_id (peak/trough/final)
7. Last-trade timestamp per run_id (cliff diagnosis)
8. lot_size per quartile temporale (H1 balance-exhaustion confirm)

`scripts/diag_decay_subset.py`:

- 1-way breakdowns per regime/profile/symbol/timeframe
- 2-way breakdowns (6 pair combinations)
- 3-way symbol×TF×regime
- 4-way symbol×TF×profile×regime
- BUY vs SELL direction bias
- Early-years 2002-2003 sanity check

Entrambi gli script lavorano su qualsiasi parquet schema-v2 (default `data/training/baseline_decisions/part-0.parquet`, override con argv[1]).

## Artefatti versionati

**Pushare:**
- Questo SUMMARY (`.planning/phases/05-baseline-backtest/05-10-SUMMARY.md`)
- `scripts/diag_decay_05_10.py`
- `scripts/diag_decay_subset.py`
- Update `.planning/REQUIREMENTS.md` con REQ-STRAT-REBUILD
- Update `.planning/STATE.md` con nuova Active Work

**NON pushare (sul PC secondario):**
- `data/training/baseline_decisions/part-0.parquet` 81MB (il vecchio 1076-row parquet resta come archive di audit; il nuovo 209k sostituirebbe ma è meno informativo del SUMMARY)
- `.planning/research/_smoke_equity_curves/*.png` 27 PNG rigenerate (riflettono dataset compromesso)
- `.planning/research/baseline-2026-05-13.md` (report ufficiale auto-generato dal runner, deprecato dalle conclusioni di questo SUMMARY)

## Deviation log

| # | Tipo | Dettaglio |
|---|---|---|
| 1 | Rule 4 (scope) | Plan 05-10 doveva produrre dataset usabile per Phase 7. Esito: dataset non usabile, ma scoperta sostanziale (strategia broken). User-accepted come trade-off scientifico. |
| 2 | Rule 4 (wall-clock) | 74h vs cap 16h. Era già accepted come deviation Plan 05-08 a livello milestone. |
| 3 | Rule 4 (push) | Parquet 81MB + 27 PNG rigenerate NON committati, contro abituale workflow Plan 05-09. Motivo: dataset documenta strategia perdente, l'evidenza utile è questo SUMMARY + gli script di diagnosi. |

## Recommended next step

Aprire nuova phase **"Strategy Rebuild"** (proposed: Phase 4.5 o riapertura Phase 4) prima di sbloccare Phase 7.

Procedura suggerita:

1. `/gsd-phase add` con title "Strategy Rebuild — replace negative-expectancy READY detector with 2-3 textbook setups"
2. `/gsd-discuss-phase` con skill `forex-strategy-builder` per estrarre setup specifici da Probo/Murphy/StrategieOperative (libri PDF in `C:\trading-agent\libri\`)
3. Plan-write con 3-5 wave: nuovi detector pure-fn, gating per regime/sessione, ri-testing su parquet 05-10 come benchmark, criterio di accettazione hard `expectancy > +2 USD/trade post-costi su n≥1000`
4. Solo dopo gate-pass: `/gsd-execute-phase 7` originale rimane valido (i 6 PLAN.md sono technicalmente OK, è il segnale che mancava)

---

*Plan 05-10 chiuso 2026-05-18 come negative-finding. Phase 5 status invariato (9/9 plans complete tecnicamente), ma il deliverable utile della milestone — un dataset baseline con edge identificabile — non esiste ancora.*
