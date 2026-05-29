# Task — Meccanismo ENABLE_SETUP_* + disabilitare B_reversal + misurare l'impatto

> **File**: `.planning/research/task-disable-setup-b-2026-05-29.md`
> **Tipo task**: feature (meccanismo config) + decisione di scope + misurazione.
> **Owner**: Claude Code.
> **Stima**: 2-3 ore.
> **Precondizione**: confluence repair mergiata o sul branch corrente (i grade
>   ora sono corretti). Report `task-fix-confluence-repair-2026-05-28`.
> **Output finale**: report markdown strutturato (STEP 6) + branch con il fix.

---

## Contesto (dai report precedenti — NON ri-diagnosticare)

Con la confluence riparata (regime+spread wired), i dati per-setup su EURUSD H1
2020 sono netti e stabili sui 3 profili:

| setup | mean_pnl_usd | verdetto |
|---|---|---|
| A_breakout | +9.8 … +16.3 | positivo |
| C_compression | +0.1 … +28 | positivo |
| D_pullback | +0.2 … +12.2 | positivo |
| **B_reversal** | **−52 … −55** | **zavorra netta** |

**3 setup su 4 sono positivi; B_reversal è negativo in modo costante e marcato.**
Ipotesi da testare: disabilitando B_reversal, l'expectancy aggregata migliora
sensibilmente, soprattutto sui profili dove B pesa di più.

**Problema**: NON esiste alcun meccanismo per disabilitare un setup. `ALL_DETECTORS`
(`strategy/setups/__init__.py`) è hard-coded e `evaluate_proposal_for_bar`
(`strategy/__init__.py:75`) li esegue tutti. Quindi questo task fa DUE cose:
1. Costruisce il meccanismo `ENABLE_SETUP_*` (era la Wave 1b del playbook v3).
2. Lo usa per disabilitare B_reversal di default, e misura l'impatto.

---

## Architettura del fix (verificata sul codice 2026-05-29)

Il flusso reale è:
```
_shim.analyze_symbol → build_ctx_live(symbol, mt5_client, profile, cfg, ...)
  → ctx  (ha accesso a cfg dentro build_ctx_live)
→ evaluate_proposal_for_bar(bars, indicators, ctx)
  → drafts = [detect(...) for detect in ALL_DETECTORS]   # ← qui si filtra
```

`evaluate_proposal_for_bar` riceve `ctx` ma NON `cfg`. Per mantenere il detector e
l'orchestrator **puri** (STRAT-08, niente `os.environ` letto dentro), il pattern
pulito è: i flag enable/disable entrano nel `ctx` (popolato da `build_ctx_live` che
HA il `cfg`), e l'orchestrator filtra `ALL_DETECTORS` in base a un set di nomi
abilitati letto da `ctx`.

---

## STEP 0 — Branch

```bash
cd <repo-root>
git status
git checkout -b feat/enable-setup-flags-disable-b
git log --oneline -2
```

> Se la confluence-repair NON è ancora mergiata su main, parti da quel branch:
> `git checkout fix/confluence-repair-regime-spread && git checkout -b feat/enable-setup-flags-disable-b`
> così i due fix sono in catena. Documenta nel report da dove hai forkato.

---

## STEP 1 — Config: i 4 flag ENABLE_SETUP_*

In `config.py`, accanto agli altri `_get_bool`:

```python
ENABLE_SETUP_A: bool = _get_bool("ENABLE_SETUP_A", True)
ENABLE_SETUP_B: bool = _get_bool("ENABLE_SETUP_B", False)  # disabilitato: expectancy -52..-55 (2026-05-29)
ENABLE_SETUP_C: bool = _get_bool("ENABLE_SETUP_C", True)
ENABLE_SETUP_D: bool = _get_bool("ENABLE_SETUP_D", True)
```

Nota: **B default False**, gli altri True. Aggiorna `.env.example*` con le 4 righe
(B=false, gli altri true).

---

## STEP 2 — Propagare i flag nel context

In `strategy/context.py`, aggiungi al `StrategyContext` un campo per i setup
abilitati (additive, non rompe ProposalDraft frozen né il resto):

```python
enabled_setups: frozenset[str] | None = None  # None = tutti abilitati (backward-compat)
```

In `strategy/adapters/live.py`, dentro `build_ctx_live` (che ha `cfg`), popola il
campo costruendo il set dai flag:

```python
enabled = frozenset(
    name for name, on in (
        ("A_breakout",   getattr(cfg, "ENABLE_SETUP_A", True)),
        ("B_reversal",   getattr(cfg, "ENABLE_SETUP_B", True)),
        ("C_compression",getattr(cfg, "ENABLE_SETUP_C", True)),
        ("D_pullback",   getattr(cfg, "ENABLE_SETUP_D", True)),
    ) if on
)
# ... passa enabled_setups=enabled nel costruttore del context
```

> Backward-compat: se `enabled_setups is None`, l'orchestrator esegue tutti
> (comportamento attuale). Questo evita di rompere chiamate/test che costruiscono
> context senza il campo.

---

## STEP 3 — Filtrare in evaluate_proposal_for_bar

In `strategy/__init__.py`, modifica SOLO la riga che costruisce `drafts`:

```python
# PRIMA:
# drafts = [detect(bars, indicators, ctx) for detect in ALL_DETECTORS]

# DOPO:
enabled = getattr(ctx, "enabled_setups", None)
if enabled is None:
    active = ALL_DETECTORS
else:
    active = [d for d in ALL_DETECTORS if _detector_name(d) in enabled]
drafts = [detect(bars, indicators, ctx) for detect in active]
```

Serve un modo per mappare la funzione detector → nome setup. Due opzioni:
- **A (consigliata)**: un dict esplicito in `strategy/setups/__init__.py`:
  ```python
  DETECTOR_NAMES = {
      detect_a_breakout: "A_breakout",
      detect_b_reversal: "B_reversal",
      detect_c_compression: "C_compression",
      detect_d_pullback: "D_pullback",
  }
  ```
  e `_detector_name(d) = DETECTOR_NAMES[d]`.
- B: dedurre dal `__name__` della funzione (fragile, sconsigliato).

**Edge case da gestire**: se `active` è vuoto (tutti i flag False), `drafts` è
vuoto e il codice a valle fa `drafts[0]` (riga ~98) → IndexError. Aggiungi un
guard: se `active` è vuoto, ritorna un `ProposalDraft(setup_type="NONE",
reason="no_enabled_setups")`. Non dovrebbe succedere in pratica (A/C/D restano
True) ma il guard evita un crash silenzioso.

**Vincolo**: NON leggere `os.environ` né `cfg` dentro l'orchestrator o i detector.
I flag arrivano SOLO via `ctx.enabled_setups`. Mantiene la purezza STRAT-08.

---

## STEP 4 — Test

1. Gira la suite, verifica nessuna regressione inattesa:
   ```bash
   python -m pytest tests/ -q --tb=line 2>&1 | tail -40
   ```
   I fail noti pre-esistenti (smoke perf, legacy anthropic import) restano; non
   devono comparirne di nuovi.
2. **Test nuovi** (`tests/test_enable_setup_flags.py`):
   - `enabled_setups=None` → tutti e 4 i detector girano (backward-compat).
   - `enabled_setups=frozenset({"A_breakout","C_compression","D_pullback"})` →
     B_reversal NON compare nei drafts né come winner né come loser.
   - `enabled_setups=frozenset()` (vuoto) → ritorna NONE/no_enabled_setups, no crash.
   - Un test che parte dal VERO `build_ctx_live` con `cfg.ENABLE_SETUP_B=False` e
     verifica che `ctx.enabled_setups` non contenga "B_reversal".
3. Purity STRAT-08: PASS.
4. **Attenzione ML feature extraction**: l'orchestrator mette i `losers` in
   `setup_specific["losers"]` per la Phase 7. Con B disabilitato, B non sarà più
   tra i losers. Verifica che nessun test/codice ML assuma sempre 4 drafts. Se
   c'è, documentalo (non fixare la Phase 7 qui, solo segnalare).

---

## STEP 5 — Smoke di misurazione: impatto della disabilitazione

### 5.1 Tre run a confronto, stesso range (EURUSD H1 2020, 3 profili)
- **Run PRE**: tutti e 4 i setup attivi (B incluso) — è il POST del task precedente
- **Run POST**: B disabilitato (`ENABLE_SETUP_B=False`)

Stesso range del report confluence-repair per confrontabilità
(2020-01-01 → 2020-04-01 minimo; se hai tempo, anno intero).

### 5.2 Metriche (PRE vs POST, per profilo + aggregato)
```
n_trades
win_rate
mean_pnl_usd / median_pnl_usd
total_pnl_usd
expectancy_post_costs
```

### 5.3 Cosa aspettarsi e sanity
- Atteso: n_trades cala (spariscono i trade di B), total_pnl **migliora** (rimuovi
  trade a −52/−55), win_rate probabilmente sale (B era ~10% win).
- Attenzione al **crowding inverso**: con B disabilitato, alcuni bar dove B vinceva
  il tie-break D-06 ora lasciano spazio a un altro setup. Quindi NON è solo
  "togli i trade di B": altri setup potrebbero prenderne di nuovi. Misura l'effetto
  netto, non assumere.
- Se total_pnl PEGGIORA dopo aver tolto B, è un risultato importante e
  controintuitivo (forse B assorbiva bar che altri setup tradano peggio) →
  riportalo, non nasconderlo.

---

## STEP 6 — Report finale

````markdown
# Disable Setup B + ENABLE_SETUP_* mechanism — Report [data]

## 1. Meccanismo implementato
- config.py: 4 flag (B default False) [righe]
- context.py: campo enabled_setups [riga]
- live.py: popolamento set da cfg [righe]
- __init__.py: filtro ALL_DETECTORS + guard empty [righe]
- setups/__init__.py: DETECTOR_NAMES [righe]

## 2. Test
- Suite: N passed / N failed / N skipped (vs baseline)
- Test nuovi: [lista]
- Backward-compat (enabled_setups=None) verificato: [SI/NO]
- Purity STRAT-08: [PASS/FAIL]
- Impatto ML losers (4→3 drafts): [osservazione]

## 3. Smoke — impatto disabilitazione B (PRE = 4 setup, POST = B off)
| profilo | metrica | PRE | POST | Δ |
|---|---|---|---|---|
| CONSERVATIVE | n_trades / win% / total_pnl | | | |
| MODERATE | n_trades / win% / total_pnl | | | |
| AGGRESSIVE | n_trades / win% / total_pnl | | | |

## 4. Effetto crowding
- Trade di B rimossi: [N]
- Trade NUOVI presi da altri setup (che prima B spiazzava): [N stima]
- Effetto netto su n_trades

## 5. Interpretazione (solo dati)
- L'expectancy aggregata è migliorata? Di quanto, per profilo?
- La disabilitazione di B è netta-positiva, neutra, o sorprendente?

## 6. Anomalie

## 7. Git status
- Branch / commit / files changed
````

---

## Vincoli rigorosi

1. **Scope**: meccanismo ENABLE_SETUP_* + disabilitare B + misurare. NIENTE
   min_grade, NIENTE SL geometry, NIENTE altro.
2. **Purezza**: i flag arrivano via `ctx.enabled_setups`, MAI `os.environ`/`cfg`
   letti dentro orchestrator o detector.
3. **Backward-compat obbligatoria**: `enabled_setups=None` → comportamento attuale
   (tutti i detector). Non rompere test/chiamate esistenti.
4. **Guard empty-set**: tutti i flag False non deve crashare (no_enabled_setups).
5. **NON cancellare il codice di B_reversal.** Resta nel repo, solo disabilitato
   via flag. È riattivabile e potrà servire (es. validazione full-24y, o con
   filtri diversi).
6. **Misura l'effetto NETTO** (incluso crowding inverso), non assumere che
   togliere B = togliere solo i suoi trade.
7. **Se total_pnl peggiora togliendo B**, riportalo onestamente — è un finding.
8. **NON proporre il fix successivo.** Consegna il report.
9. **Tempo massimo**: 3 ore.

---

## Quando hai finito

Consegna il report markdown delle 7 sezioni. Niente preamboli. L'analisi esterna
deciderà sui dati PRE vs POST se la disabilitazione di B diventa permanente e
qual è il prossimo fix (probabilmente min_grade, ora che i grade sono corretti).
