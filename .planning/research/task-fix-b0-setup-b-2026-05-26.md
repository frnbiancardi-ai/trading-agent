# Task — Fix B0: rimuovere counter-trend gate D-07 da Setup B + misurare l'edge

> **File**: `.planning/research/task-fix-b0-setup-b-2026-05-26.md`
> **Tipo task**: fix chirurgico + misurazione. UN solo intervento, ben isolato.
> **Owner**: Claude Code.
> **Stima**: 1-2 ore (fix + test + smoke + report).
> **Precondizione**: diagnosi confermata dal report
> `.planning/research/diag-setup-b-2026-05-19.log`.
> **Output finale**: report markdown strutturato (STEP 5) + branch con il fix
> committato seguendo le convenzioni del repo (`COMMIT_CONVENTIONS.md`).

---

## Contesto (cosa sappiamo già — NON ri-diagnosticare)

Il Setup B (`B_reversal`) non emette **mai** un READY in 210k trade baseline.
Diagnosi confermata empiricamente (smoke EURUSD H1 2020, report 2026-05-19):

- Setup B raggiunge il gate finale 489 volte/anno ma esce sempre su
  `counter_trend_below_A_grade` con `grade=C` (mai A).
- Causa: il **counter-trend gate D-07** dentro `detect_b_reversal` richiede
  `grade in {A+, A}` quando la direzione oppone `sign(ema50_slope)`. Ma Setup B
  è un *reversal*, quindi è counter-trend per costruzione, e il fattore
  `trend_alignment` è strutturalmente False → grade max strutturale è B, in
  pratica sempre C. **Impossibilità logica di raggiungere A.**
- `find_support_resistance` e `scan_patterns` funzionano correttamente (SR 100%,
  patterns 85.6%). NON sono il problema. NON toccarli.

Il fix è: **rimuovere il counter-trend gate da Setup B**, perché è semanticamente
inappropriato per un setup reversal. I gate downstream (reject su ≤1 fattore,
R:R floor) restano a proteggere la qualità.

---

## STEP 0 — Setup branch

```powershell
cd C:\trading-agent
git status                          # deve essere pulito
git checkout -b fix/setup-b-remove-counter-trend-gate
git log --oneline -2                # conferma HEAD
```

Se c'è lo stash diagnostico `stash@{0}` del task precedente, NON applicarlo —
quel logging era temporaneo. Lavoriamo su codice pulito.

---

## STEP 1 — Il fix nel detector

Apri `strategy/setups/b_reversal.py`. Individua il blocco "Counter-trend gate
D-07" dentro `detect_b_reversal` (è dopo il calcolo di `factors` e `grade`,
prima del check `grade == "reject"`). Ha questa forma:

```python
    # --- Counter-trend gate D-07: PRIMA del check reject (più informativo per debug) ---
    slope = _last(getattr(indicators, "ema50_slope", None)) or 0.0
    trend_dir: str | None = None
    if slope > 0:
        trend_dir = "BUY"
    elif slope < 0:
        trend_dir = "SELL"

    is_counter_trend = trend_dir is not None and direction != trend_dir
    if is_counter_trend and grade not in ("A+", "A"):
        return ProposalDraft(
            setup_type="NONE",
            setup_name="B_reversal",
            direction=direction,
            factors=factors,
            grade=grade,
            reason="counter_trend_below_A_grade",
            setup_specific={...},
        )
```

### 1.1 Cosa fare

**Rimuovi il `return` di blocco** ma **mantieni il calcolo di `slope` e
`is_counter_trend`** — servono ancora per il `setup_specific` finale e per la
confidence. La versione corretta:

```python
    # --- Trend context (D-07 gate RIMOSSO — Setup B è reversal per design) ---
    # NOTA: il counter-trend gate è stato rimosso il 2026-05-19. Diagnosi:
    # bloccava il 100% dei candidati reversal perché grade strutturalmente ≤ C
    # (trend_alignment sempre False per un reversal). Il counter-trend è feature
    # del setup, non un rischio da gateare qui. Protezione qualità delegata a:
    # reject (≤1 fattore True) + R:R floor downstream.
    slope = _last(getattr(indicators, "ema50_slope", None)) or 0.0
    trend_dir: str | None = None
    if slope > 0:
        trend_dir = "BUY"
    elif slope < 0:
        trend_dir = "SELL"
    is_counter_trend = trend_dir is not None and direction != trend_dir
    # is_counter_trend resta tracciato in setup_specific per analisi ex-post.
```

Il flusso prosegue al check `grade == "reject"` esistente, che resta invariato.

### 1.2 Vincoli da rispettare

- **NON toccare** `find_support_resistance`, `scan_patterns`, `score_factors`,
  `grade_for`. Sono fuori scope e funzionano.
- **NON modificare** la geometria SL/TP (`_compute_levels_b`). Quello è Fix B1,
  un task separato.
- **NON rimuovere** il check `grade == "reject"` né il gate R:R floor. Restano.
- Mantieni il modulo **pure** (STRAT-08): niente logging, niente datetime, niente I/O.
- `is_counter_trend` deve restare nel `setup_specific` del ProposalDraft READY
  finale (serve per l'analisi ex-post: vogliamo sapere quanti READY sono
  counter-trend).

---

## STEP 2 — Aggiornare i test esistenti

Il test `test_detect_b_reversal_counter_trend_gate` in
`tests/test_strategy_setups.py` (o file equivalente) **codifica il vecchio
comportamento** e ora fallirà. Va **riscritto**, non cancellato.

### 2.1 Vecchia semantica (da rimuovere)
> "counter-trend + grade B/C → NONE/counter_trend_below_A_grade"

### 2.2 Nuova semantica (da asserire)
> "counter-trend + grade B/C + R:R sufficiente → READY (il gate non blocca più)"
> "counter-trend + grade reject (≤1 fattore) → NONE/confluence_below_2_factors"
> "counter-trend + R:R sotto floor → NONE/rr_below_profile_min_X.XX"

Riscrivi il test per coprire questi tre casi. Esempio scheletro (adatta a
fixtures esistenti `_make_bars`, `_make_pattern_hit`, `_stub_indicators_b`,
`_stub_ctx`):

```python
def test_detect_b_reversal_counter_trend_now_allowed():
    """Post-fix 2026-05-19: counter-trend NON è più bloccato.
    SELL a resistance con slope+ (counter-trend) + grade C + R:R ok → READY."""
    bars = _make_bars([1.10498] * 200)
    pattern = _make_pattern_hit("shooting_star", "bearish", bar_index=-1,
                                extreme_price=1.10520)
    ind = _stub_indicators_b(close_ref=1.10498, slope=0.0001,  # slope+ → counter-trend per SELL
                             regime="normal", rsi=80.0)
    ctx = _stub_ctx(profile="MODERATE", resistance=1.10500, support=1.09000,
                    close_ref=1.10498)  # support lontano → R:R ampio per SELL
    ctx = replace(ctx, patterns=[pattern])
    d = detect_b_reversal(bars, ind, ctx)
    # Il gate counter-trend non esiste più: ci aspettiamo READY (se R:R ok) o
    # al più NONE per reject/R:R, MAI counter_trend_below_A_grade
    assert d.reason != "counter_trend_below_A_grade"
    if d.setup_type == "READY":
        assert d.setup_specific.get("is_counter_trend") is True
        assert d.direction == "SELL"


def test_detect_b_reversal_reject_still_blocks():
    """Reject (≤1 fattore True) deve ancora bloccare, indipendentemente dal trend."""
    # ... costruisci scenario con 0-1 fattori True ...
    # assert d.setup_type == "NONE" and d.reason == "confluence_below_2_factors"


def test_detect_b_reversal_rr_floor_still_blocks():
    """R:R sotto floor deve ancora bloccare."""
    # ... costruisci scenario con TP troppo vicino → R:R < profile floor ...
    # assert d.setup_type == "NONE" and d.reason.startswith("rr_below_profile_min")
```

### 2.3 Esegui i test

```powershell
python -m pytest tests/test_strategy_setups.py -k "b_reversal" -v --tb=short
```

Tutti devono passare. Se un test pre-esistente diverso da quello counter-trend
fallisce, **fermati**: significa che il fix ha avuto un effetto collaterale
inatteso. Documenta nel report e NON forzare.

### 2.4 Regression sugli altri detector

```powershell
python -m pytest tests/test_strategy_setups.py tests/test_strategy_purity.py -v --tb=short
```

A/C/D non devono cambiare comportamento. La purity gate STRAT-08 deve passare
(il fix non introduce side-effect).

---

## STEP 3 — Smoke di misurazione (il punto del task)

Per la **prima volta** Setup B emetterà READY. Misuriamo quanti e con che
qualità. Riusa l'infrastruttura del task diagnostico precedente, ma stavolta
**senza** il logging gated (i trade ora finiscono nel ledger come READY reali).

### 3.1 Smoke EURUSD H1 2020

Stesso range del report diagnostico per confrontabilità diretta:

```powershell
# Adatta al runner reale; se serve isola EURUSD H1 spostando gli altri CSV
python scripts\run_baseline_backtest.py `
    --symbols EURUSD --timeframes H1 --profiles MODERATE `
    --date-start 2020-01-01 --date-end 2020-12-31
```

Se il runner non separa per profilo, lancia i 3 profili e filtra Setup B nel
report (è profile-agnostic per la logica di detection).

### 3.2 Estrai le metriche Setup B dal ledger

Dal parquet/DB di output, filtra `setup_name == "B_reversal"` e calcola:

```
n_trades
win_rate            = (pnl_usd > 0).mean()
mean_pnl_usd
median_pnl_usd
mean_pnl_R          = (pnl_usd / risk_usd).mean()
expectancy_post_costs   (mean_pnl_usd, già al netto costi se il backtest li applica)
n_counter_trend     = (setup_specific.is_counter_trend == True).sum()
% counter_trend
breakdown per direction (BUY/SELL)
breakdown per grade (B/C — non ci sarà A)
```

### 3.3 Sanity check

- Atteso ~400-500 READY/anno (dai 489 candidati counter-trend del report, meno
  quelli che cadono su reject o R:R floor). Se vedi **0**, il fix non è attivo
  → verifica di aver salvato il file e che il runner usi il codice nuovo.
- Se vedi **>2000**, qualcosa è troppo permissivo → controlla che reject e R:R
  floor siano ancora in funzione.

---

## STEP 4 — Commit

Solo se STEP 2 (tutti i test verdi) e STEP 3 (Setup B emette READY plausibili)
sono OK:

```powershell
git add strategy/setups/b_reversal.py tests/test_strategy_setups.py
git commit -m "fix(strat): remove counter-trend gate D-07 from Setup B

Setup B (reversal) was structurally blocked: counter-trend gate required
grade A but reversal trades are counter-trend by design (trend_alignment
always False -> max grade B, in practice always C). 0 READY in 210k trades.

Diagnosis: .planning/research/diag-setup-b-2026-05-19.log
Quality now protected by downstream gates: reject (<2 factors) + R:R floor.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Segui la convention reale del repo (`COMMIT_CONVENTIONS.md`) se diverge da questa.

NON fare merge su main/feature branch principale. Lascia il branch
`fix/setup-b-remove-counter-trend-gate` per review umana.

---

## STEP 5 — Report finale

Singolo blocco markdown, sezioni numerate, solo dati:

````markdown
# Setup B Fix B0 — Report [data]

## 1. Fix applicato
- File: strategy/setups/b_reversal.py
- Blocco rimosso: counter-trend gate D-07
- Righe modificate: [N]
- slope / is_counter_trend mantenuti per setup_specific: [SI/NO]

## 2. Test
- test_strategy_setups (b_reversal): [N passed / N failed]
- test counter-trend riscritto: [nome nuovo test]
- regression A/C/D: [PASS/FAIL]
- purity gate STRAT-08: [PASS/FAIL]
- [se FAIL: dettaglio]

## 3. Smoke misurazione — Setup B (EURUSD H1 2020)
- n_trades READY: [N]
- win_rate: [%]
- mean_pnl_usd: [valore]
- median_pnl_usd: [valore]
- mean_pnl_R: [valore]
- expectancy_post_costs: [valore]
- % counter-trend fra i READY: [%]
- breakdown direction: BUY [N] / SELL [N]
- breakdown grade: B [N] / C [N]

## 4. Confronto con diagnosi precedente
- Candidati counter-trend nel report 2026-05-19: 489 (su 3 profili, ~163/profilo)
- READY emessi ora: [N] → [coerente / discrepanza + spiegazione]
- Dove sono finiti i candidati non-READY: reject [N], R:R floor [N]

## 5. Verdetto preliminare (solo dati, no raccomandazione)
- Setup B ha expectancy [positiva / negativa / breakeven] su EURUSD H1 2020
- Gate STRAT-REBUILD-03 (expectancy > +2 USD, median ≥ 0, n ≥ 1000) su questo
  solo subset: [PASS / FAIL / n insufficiente — serve full 24y]

## 6. Anomalie
[fatti fuori dall'atteso, niente conclusioni di fix]

## 7. Git status
- Branch: fix/setup-b-remove-counter-trend-gate
- Commit: [hash]
- Files changed: [lista]
````

---

## Vincoli rigorosi

1. **UN solo fix**: rimozione gate D-07 da Setup B. Niente SL geometry, niente
   confluence audit, niente weekend rule. Quelli sono task separati.
2. **NON toccare** find_support_resistance, scan_patterns, confluence.py,
   gli altri detector.
3. **NON estendere lo smoke** oltre EURUSD H1 2020. Il full 24y è un task
   successivo (benchmark Wave 5).
4. **Se i test non passano o Setup B non emette READY**, fermati e riporta.
   Non forzare, non aggiungere permissività per "far uscire trade".
5. **Tempo massimo**: 2 ore. Se sfori sullo smoke, riduci a 3 mesi.
6. **NON proporre il fix successivo**. Consegna il report e basta. La decisione
   se Setup B resta nel portafoglio (in base all'expectancy misurata) viene
   presa esternamente.

---

## Quando hai finito

Consegna il report markdown delle 7 sezioni come singolo messaggio. Niente
preamboli. L'utente lo passerà all'analisi esterna per decidere il prossimo passo
(includere Setup B nel baseline, oppure procedere ai Fix B1-B3 sugli altri setup).
