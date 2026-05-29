# Confluence Repair (CRIT-1 + CRIT-2) — Report 2026-05-28

> Branch `fix/confluence-repair-regime-spread`, commit `0839078` (NON merged).
> Due fix in `strategy/adapters/live.py` + `config.py`. Smoke PRE vs POST su
> EURUSD H1, Q1 2020 (3 mesi — ridotto da 12 per budget tempo; include lo shock
> di volatilità COVID, quindi buona varietà di regime).

## 1. Fix applicati

**CRIT-1 — volatility_regime** (`strategy/adapters/live.py`)
- `_build_extended_indicators` continua a produrre `volatility_regime=[None]*N`,
  ma `build_ctx_live` ora calcola la serie reale e la inietta:
  `load_regime_config(symbol, "data/configs/regime.yaml")` + `volatility_regime(regime_bars, regime_cfg)` → `indicators.volatility_regime = regime_result.state`.
- **Re-fetch dedicato**: il classificatore richiede una finestra trailing PIENA di
  ATR validi (`window` valori), ma `INTRADAY_LOOKBACK_BARS (200) == regime_window (200)`
  e l'ATR ha ~14 bar di warm-up None → con 200 bar `state[-1]` resterebbe None.
  Rifetcho `max(INTRADAY_LOOKBACK_BARS, regime_window + 64)` bar **solo** per il
  regime: le altre serie indicatori restano IDENTICHE (nessun reseed EMA/RSI →
  nessun cambiamento collaterale sugli altri 4 fattori). Il detector legge
  `volatility_regime[-1]`, allineato al bar corrente comune alle due finestre.
- Fallback robusti: `load_regime_config` fallita → `regime_cfg=None` (default interni
  del classificatore); `get_ohlc`/`volatility_regime` falliti → si ricade su `bars`/None.
- Anti-leakage preservato: `volatility_regime` usa rolling-rank trailing (Pitfall 4);
  `regime_bars` sono solo storia ≤ bar corrente (il broker non ha futuro).
- Righe: import `Path` aggiunto; blocco regime inserito dopo `_build_extended_indicators`,
  prima del calcolo S/R (≈ live.py:153-196).

**CRIT-2 — spread_session** (`config.py` + `.env.example*`) — **Opzione A**
- Aggiunto `Config.SPREAD_BASELINE_PIPS: float = float(os.getenv("SPREAD_BASELINE_PIPS","1.0"))`.
  `build_ctx_live` legge già `getattr(cfg,"SPREAD_BASELINE_PIPS",None)` → ora 1.0 →
  `ctx.spread_baseline_pips=1.0` → il fallback in `_check_spread_session` calcola
  `spread = 1.0*pip_size` (il BacktestBroker non espone bid/ask). `_check_spread_session`
  NON è stato toccato.
- Scelta A vs B: A (un baseline unico 1.0 pip) sblocca la misura con il minimo invasivo;
  costs.yaml ha 0.5/0.7/0.6 pip per pair, quindi 1.0 è conservativo (più largo → soglia
  spread/atr più facile da superare ma realistica). Per-symbol (B) rimandato.
- `.env.example`, `.env.example.aggressive/conservative/moderate/new` aggiornati con
  `SPREAD_BASELINE_PIPS=1.0`.

**Purity STRAT-08**: **PASS** (`tests/test_strategy_purity.py` verde; `live.py` è già
fuori dal purity gate — è il bridge non-pure — e la lettura YAML config segue il pattern
esistente di `load_cost_model`/`load_regime_config`).

## 2. Test

- **Suite completa** (esclusi 6 moduli con import rotti per `anthropic`/`apscheduler`):
  **443 passed / 2 failed / 13 skipped / 8 xfailed** — **identica al PRE-fix**.
  - Fail 1: `test_backtest_engine.py::test_smoke_12month_under_60s` — perf (244s > 60s).
    Già rosso PRE-fix; il re-fetch regime ~raddoppia il tempo per-bar (era già O(N²)).
  - Fail 2: `test_mcp_legacy_compat.py::test_legacy_entrypoint_imports` — env (`anthropic`).
  - **Nessun nuovo fallimento.**
- **Test di parity aggiornati: NESSUNO.** La "parity Plan 05-08" che il task si aspettava
  di rompere **non è enforced da alcun test**: era un invariante a livello di commento in
  `slice_worker.py` (`Count trade atteso == 1076 ± 0`) sul flow del post-hoc snapshot ML,
  non una asserzione di test. `test_baseline_determinism` verifica solo riproducibilità di
  seed/hash (non valori golden). `test_strategy_regression` replaya 10 scenari via
  `analyze_symbol`→`build_ctx_live` e confronta `setup_type/direction/entry/sl/tp` (NON
  grade/confidence): essendo i prezzi indipendenti dai fattori e i 10 scenari stabili sul
  reject-gate, **passa invariato**. Quindi non ho dovuto modificare né aggirare test.
- **Test nuovi anti-regressione** (`tests/test_confluence_repair.py`, 3 test, usano il
  VERO `build_ctx_live` con BacktestBroker sintetico — niente stub che maschera):
  1. `test_build_ctx_live_populates_volatility_regime` — la serie ha valori non-None e
     `[-1] ∈ {compressed,normal,expanded}`.
  2. `test_build_ctx_live_sets_spread_baseline_pips` — `ctx.spread_baseline_pips` non-None
     e == `cfg.SPREAD_BASELINE_PIPS`.
  3. `test_score_factors_can_set_regime_and_spread_true_via_real_adapter` — col context
     reale, sia `volatility_regime` sia `spread_session` possono risultare True.
  Tutti **verdi** (+ purity + regression replay = 19 passed dopo il restore del fix).

## 3. Smoke — distribuzione grade PRE vs POST (la metrica chiave)

EURUSD H1, 2020-01-01 → 2020-04-01 (1560 bar), 3 profili sequenziali (mirror slice_worker,
timeout H1=120). Grade/fattori letti da `decision_context_json` di ogni trade chiuso.

| profilo | metrica | PRE fix | POST fix |
|---|---|---|---|
| **CONSERVATIVE** | A+ / A / B / C | 0 / 0 / 55 / 70 | **26 / 65 / 34 / 0** |
| | % volatility_regime factor True | 0% | **49.6%** |
| | % spread_session True | 0% | **100%** |
| **MODERATE** | A+ / A / B / C | 0 / 0 / 90 / 99 | **40 / 101 / 47 / 0** |
| | % volatility_regime factor True | 0% | **48.9%** |
| | % spread_session True | 0% | **100%** |
| **AGGRESSIVE** | A+ / A / B / C | 0 / 0 / 178 / 176 | **80 / 197 / 94 / 2** |
| | % volatility_regime factor True | 0% | **54.2%** |
| | % spread_session True | 0% | **100%** |

PRE: **A+=0, A=0 ovunque** (ceiling B confermato dall'audit). POST: A+ e A compaiono per
la prima volta; C quasi azzerato. Sanity STEP 4.3 superata (NON 100% C, trade > 0).

## 4. Smoke — performance PRE vs POST

| profilo | n_trades PRE→POST | win% PRE→POST | mean_pnl_usd PRE→POST | total_pnl_usd PRE→POST |
|---|---|---|---|---|
| CONSERVATIVE | 125 → 125 | 21.6 → 21.6 | −1.36 → −1.36 | −169.63 → −169.63 |
| MODERATE | 189 → 188 | 25.4 → 25.0 | −0.57 → −1.18 | −107.12 → −221.72 |
| AGGRESSIVE | 354 → 373 | 35.6 → 35.7 | +7.49 → +6.58 | +2650.42 → +2454.99 |

**Per-setup (POST, mean_pnl_usd) — pattern diagnostico costante sui 3 profili:**
- `B_reversal`: **−52 … −55** (sempre il peggiore; grade max A, mai A+ — counter-trend →
  trend_alignment quasi sempre False).
- `A_breakout`: **+9.8 … +16.3** (positivo).
- `C_compression`: **+0.1 … +28** (variabile, spesso positivo).
- `D_pullback`: **+0.2 … +12.2** (da flat a positivo; volume di trade più alto).

## 5. Interpretazione (solo dati)

- **Il ceiling grade è salito da B a A+.** A+ ora raggiungibile per A_breakout /
  C_compression / D_pullback (5 fattori). `B_reversal` resta strutturalmente max **A**
  (0 A+ in tutti i profili): è counter-trend, quindi `trend_alignment` è quasi sempre
  False → max 4 fattori. Coerente con l'audit §4.
- **I trade ora si distribuiscono su A+/A/B**; il grade C, che PRE era ~50% dei trade
  (es. MODERATE 99/189), POST è ≈0. Causa: `spread_session` ora True al 100% (baseline
  1.0 pip supera sempre `spread/atr ≤ 0.20` con l'ATR H1 tipico) → +1 fattore garantito a
  ogni trade; `volatility_regime` aggiunge un altro fattore ~50% delle volte → le grade
  scivolano verso l'alto.
- **L'expectancy è sostanzialmente INVARIATA, non migliorata dal fix in sé.**
  CONSERVATIVE è **identico bit-per-bit** (stessi 125 trade, stesso pnl): cambiano solo le
  ETICHETTE grade (B/C → A/A+), non quali trade vengono presi né i loro prezzi. Motivo:
  `min_grade` e `min_confidence` restano **DEAD** (task successivo) e `risk_engine` ignora
  grade/confidence → la qualità del segnale ora è MISURATA correttamente ma non ancora
  USATA come gate. MODERATE/AGGRESSIVE cambiano di poco il numero di trade (−1 / +19) solo
  al margine del reject-gate (il +1 fattore di spread porta qualche setup da ≤1 fattore
  reject a ≥2 READY), con expectancy che resta negativa (CONS/MOD) o positiva (AGG).
- **Segni di vita**: la confluence ora discrimina. Il segnale per-setup è netto e stabile
  (B_reversal nettamente negativo; A_breakout/D_pullback positivi). Questo è ciò che un
  eventuale `min_grade`/filtro per-setup potrebbe sfruttare — ma quella decisione è esterna.

## 6. Anomalie

- **CONSERVATIVE PRE==POST identico**: non un bug — conferma che il fix tocca solo
  grade/confidence (cosmetici finché min_grade è dead), non la selezione dei trade quando
  il gate vincolante è `min_rr` (CONS min_rr=2.5, alto, assorbe i setup marginali extra).
- **`spread_session` = 100% True POST**: con baseline 1.0 pip il fattore non discrimina
  quasi mai in backtest (sempre soddisfatto). È un fattore "gratis" → spinge i grade verso
  l'alto in modo poco informativo. Un baseline per-symbol (Opzione B) o l'uso di bid/ask
  reali lo renderebbe discriminante. Segnalato per decisione esterna; fuori scope.
- **`volatility_regime` factor ~50% True**: plausibile (il fattore richiede regime nel set
  allowed PER setup, es. breakout vuole expanded/normal). Coerente con Q1 2020 (regime
  misto pre/post shock COVID).
- **Perf**: il re-fetch regime per-bar aggrava l'O(N²) di `build_ctx_live` (il 12-mesi
  smoke passa da rosso a più rosso, 244s). Non è regressione funzionale ma il baseline
  full-history sarà più lento; ottimizzazione (cache regime per-slice) è un task a parte.
- **`indicators_full` resta inutilizzato** dall'engine (audit HIGH): questo fix non lo
  tocca; la detection continua a ricalcolare per-bar via `build_ctx_live`.

## 7. Git status

- Branch: `fix/confluence-repair-regime-spread` (NON merged, NON pushed).
- Commit: `0839078` "fix(strat): wire volatility_regime + spread_session into confluence".
- Files changed (committati): `strategy/adapters/live.py`, `config.py`,
  `.env.example`, `.env.example.aggressive`, `.env.example.conservative`,
  `.env.example.moderate`, `.env.example.new`, `tests/test_confluence_repair.py`.
- Script smoke temporaneo (`scripts/_audit_smoke_grade.py`) **rimosso** a fine task
  (non committato). Riproducibilità: caricava EURUSD H1 da `data/historical/EURUSD/H1.csv`,
  girava 3 profili via `BacktestEngine` (timeout 120), aggregava grade/factors da
  `trade.decision_context_json`. PRE/POST ottenuti con `git stash` del fix sullo stesso range.
- Report e audit in `.planning/research/` (untracked, non committati in questo commit).
