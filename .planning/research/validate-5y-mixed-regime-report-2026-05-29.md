# Validazione 5y regime misto — B on/off, EURUSD+GBPUSD H1 — Report 2026-05-29

> Branch `feat/enable-setup-flags-disable-b` @ `207fd59`. Validazione read-only
> (nessuna modifica al codice di produzione). Criterio = consistenza del SEGNO di
> Δtotal_pnl = (B_off) − (B_on) attraverso regimi e pair. SOLO H1.

## 1. Copertura dati e anni effettivi

- EURUSD H1: 21/10/2002 → 04/05/2026 (148.900 righe). GBPUSD H1: 21/10/2002 → 04/05/2026 (148.861).
- **Anni usati: 2008, 2014, 2017, 2020, 2023** — tutti coperti, **nessuna sostituzione**.
- Bar/anno effettivi (n_bars): 2008 ~6560, 2014 ~6470, 2017 ~6200, 2020 ~6280, 2023 ~6210.
- Range per anno: `date_start=YYYY-01-01`, `date_end=(YYYY+1)-01-01` (esclusivo → anno intero).
- Riduzioni di scope: **nessuna**. Tutte le 60 run eseguite (5×2×3×2).

## 2. Setup validazione

- Script: `scripts/_validate_5y_mixed.py` (temporaneo, **rimosso** a fine task; report only).
  Chiama l'infra esistente (`load_bars` + `BacktestEngine`, pattern `slice_worker`),
  ProcessPool su 10 task (anno×pair), ogni task riusa i bar per i 6 engine (3 prof × on/off).
- **Run totali eseguiti: 60 / 60.** Wall ~45 min, 6 worker, 8 CPU.
- **Determinismo: confermato.** `BacktestEngine`/`BacktestBroker` non usano alcuna
  randomness (nessun `random`/`seed`/`slippage` nel codice engine/broker — verificato con
  grep). Lo `slippage_seed` di baseline.yaml è usato solo dal runner/slice_worker, non da
  `BacktestEngine`. Quindi l'**unica differenza** fra le due run di ogni cella è il flag
  `cfg.ENABLE_SETUP_B`; tutto il resto (bar, cost, profilo, timeout) identico.

## 3. Matrice Δtotal_pnl (B_off − B_on)  [+ = B off migliore]

**EURUSD H1**
| anno | CONS | MOD | AGG |
|---|---|---|---|
| 2008 | +221.8 | +270.6 | +576.9 |
| 2014 | +938.7 | +758.3 | +354.6 |
| 2017 | +489.9 | +880.1 | +509.9 |
| **2020** | **−112.9** | **−52.4** | **−188.2** |
| **2023** | **−842.6** | **−764.0** | **−404.5** |

**GBPUSD H1**
| anno | CONS | MOD | AGG |
|---|---|---|---|
| 2008 | +473.1 | +210.6 | +496.6 |
| 2014 | +1087.4 | +599.2 | +358.7 |
| 2017 | +900.7 | +582.9 | +327.5 |
| **2020** | **−1869.6** | **−1642.1** | **−1186.2** |
| 2023 | +423.6 | +246.0 | +129.4 |

**Conteggio celle (30): Δ>0 (B off meglio) = 21 | Δ≈0 = 0 | Δ<0 (B off peggio) = 9.**
- Le 9 celle Δ<0 sono **tutto il 2020 (6/6)** + **2023 EURUSD (3/3)**.
- 2008 / 2014 / 2017: **18/18 celle positive** (B off meglio), entrambi i pair, tutti i profili.

## 4. PnL diretto di B_reversal per anno/pair (run B_on, MODERATE)

| anno | pair | n_B | total_pnl_B | win%_B |
|---|---|---|---|---|
| 2008 | EURUSD | 21 | −271.5 | 9.5 |
| 2008 | GBPUSD | 27 | −440.1 | 7.4 |
| 2014 | EURUSD | 52 | −541.3 | 5.8 |
| 2014 | GBPUSD | 35 | −766.7 | 2.9 |
| 2017 | EURUSD | 40 | −915.7 | 7.5 |
| 2017 | GBPUSD | 39 | −976.5 | 7.7 |
| **2020** | **EURUSD** | 62 | **+387.3** | 9.7 |
| **2020** | **GBPUSD** | 31 | **+1417.5** | 16.1 |
| **2023** | **EURUSD** | 64 | **+1315.9** | 17.2 |
| 2023 | GBPUSD | 38 | −649.9 | 5.3 |

**B NON è zavorra uniforme.** È negativo in 7/10 year-pair (2008, 2014, 2017 entrambi i pair
+ 2023 GBPUSD) ma **positivo in 3/10**: 2020 EURUSD/GBPUSD e 2023 EURUSD — esattamente i
regimi ad **alta volatilità / mean-reversion** (crash+recovery COVID 2020; EURUSD 2023). Dove
B guadagna, il **win% sale a 9.7–17.2%** vs 3–9% nei regimi dove perde. Il numero di trade B
è anche più alto in 2020/2023 (più opportunità di reversal).

## 5. Effetto equity-path

Nelle celle a crowding basso, Δtotal_pnl dovrebbe ≈ −PnL_B (pura rimozione). Verifica
(MODERATE, eccesso = Δ − (−PnL_B)):

| anno pair | Δtot | −PnL_B | eccesso | crowding_new |
|---|---|---|---|---|
| 2008 EURUSD | +270.6 | +271.5 | −0.9 | 2 |
| 2017 GBPUSD | +582.9 | +976.5 | −393.6 | 1 |
| 2020 EURUSD | −52.4 | −387.3 | +334.9 | 2 |
| 2023 EURUSD | −764.0 | −1315.9 | +551.8 | 6 |
| 2014 GBPUSD | +599.2 | +766.7 | −167.5 | 7 |

A differenza di Q1 2020 (crowding 0, equity-path netto isolabile), qui il **crowding è
non-trascurabile** (0–7 trade nuovi da A/C/D) e l'eccesso oscilla di segno. Quindi su anno
intero l'effetto equity-path **non è isolabile in modo pulito**: Δtotal_pnl ≠ −PnL_B in
modo consistente perché (a) altri setup raccolgono bar lasciati liberi da B e (b) il
sizing balance-dipendente interagisce. Conclusione onesta: l'effetto equity-path c'è
(visibile dove l'eccesso è positivo, es. 2020/2023 EURUSD) ma è confuso dal crowding e non
quantificabile pulito su finestra annuale.

## 6. Verdetto (solo dati)

- **Il segno NON è consistente attraverso i regimi.** B off migliora in modo netto e
  uniforme in **2008/2014/2017** (18/18 celle, entrambi i pair, tutti i profili), ma
  **peggiora in 2020** (6/6 celle) e in **2023 EURUSD** (3/3).
- **B_reversal è un setup CONDIZIONALE al regime, non zavorra uniforme.** È un drag in
  regimi di trend (2014) e range/bassa-vol (2017) e nell'avvio-crisi 2008, ma è
  **profittevole nei regimi ad alta volatilità / mean-reversion** (2020 crash+recovery su
  entrambi i pair; 2023 EURUSD) — coerente con la natura di un reversal.
- **Reconciliation critica col task precedente**: la conclusione "B è zavorra (−52/trade)"
  era basata su **Q1 2020** soltanto (la sola gamba di crash). Sull'**anno intero 2020** B
  è **positivo** (+387 EURUSD, +1417 GBPUSD): Q1 era un sotto-campione di regime non
  rappresentativo. Questo ribalta il segno per il 2020.
- **Aggregato 5y×2pair per profilo** (Δ = B_off − B_on): CONS **+1710**, MOD **+1089**, AGG
  **+975** — netto leggermente a favore di B-off, ma trainato interamente da 2008/2014/2017
  e quasi annullato da 2020/2023. Magnitudine piccola rispetto alla varianza (entrambe le
  configurazioni perdono decine di migliaia di USD su 5y — la strategia nel complesso è
  negativa su H1, contesto a parte rispetto alla domanda B on/off).
- **Verdetto: CONDITIONAL (NON GO per disabilitazione permanente, NON NO-GO).** I dati
  supportano un'**attivazione condizionale per regime** di B_reversal: disabilitato in
  trend/range, abilitato in alta-volatilità/reversion. La disabilitazione globale di
  default attuale resta difendibile come scelta conservativa (netto 5y positivo e segno
  positivo in 3/5 regimi su entrambi i pair), MA scarta un edge reale nei regimi
  reversal-friendly. Decisione finale all'analisi esterna.

## 7. Anomalie

- **Q1 2020 vs anno intero 2020 si contraddicono** sul segno di B (vedi §6). Il campione
  trimestrale era fuorviante. È il rischio esatto che questa validazione 5y mirava a coprire.
- **2020 GBPUSD** ha il Δ più negativo in assoluto (−1642 MOD): B lì rende molto (+1417) →
  toglierlo costa caro. Outlier che pesa sull'aggregato.
- **Strategia complessivamente negativa su 5y H1** in entrambe le configurazioni (B_on/off):
  total_pnl aggregati −29k…−55k. Fuori scope (la domanda era B on/off), ma rilevante come
  contesto: l'edge di B in 2020/2023 non basta a rendere la strategia positiva, né la sua
  rimozione la salva.
- **Crowding non-trascurabile** (0–7 trade/cella) → effetto equity-path non isolabile pulito
  su finestra annuale (a differenza di Q1 2020 a crowding 0). Vedi §5.
- B_reversal resta sempre grade max **A** (mai A+) anche nelle run B_on (counter-trend →
  trend_alignment quasi sempre False), coerente coi report precedenti.

## 8. Git status

- Branch `feat/enable-setup-flags-disable-b` @ `207fd59` — **invariato** (validazione
  read-only, nessun commit, nessuna modifica al codice di produzione).
- Script temporaneo `scripts/_validate_5y_mixed.py` **rimosso** (non committato).
  Dati grezzi in `/tmp/validate_5y.json` (60 run). Report in `.planning/research/`.
