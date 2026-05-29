# Disable Setup B + ENABLE_SETUP_* mechanism — Report 2026-05-29

> Branch `feat/enable-setup-flags-disable-b`, commit `207fd59` (NON merged), forkato
> da `fix/confluence-repair-regime-spread` @ `0839078` (i due fix sono in catena:
> confluence riparata → grade corretti → questo task). Smoke EURUSD H1 2020-Q1
> (2020-01-01→2020-04-01, 1560 bar), 3 profili. PRE = 4 setup attivi (B on),
> POST = B disabilitato.

## 1. Meccanismo implementato

Purezza STRAT-08 preservata: i flag viaggiano via `ctx.enabled_setups`, MAI letti da
`os.environ`/`cfg` dentro orchestrator o detector.

- **`config.py`** (≈190-197): `ENABLE_SETUP_A/C/D = True`, **`ENABLE_SETUP_B = False`**
  (via `_get_bool`, override env).
- **`strategy/context.py`**: campo additivo `enabled_setups: frozenset[str] | None = None`
  (`None` = tutti abilitati → backward-compat).
- **`strategy/adapters/live.py`** (in `build_ctx_live`, che ha `cfg`): costruisce
  `enabled_setups = frozenset(nomi con flag True)` e lo passa al `StrategyContext`.
- **`strategy/setups/__init__.py`**: `DETECTOR_NAMES = {funzione → nome canonico}`
  (esplicito, non da `__name__`).
- **`strategy/__init__.py`** (`evaluate_proposal_for_bar`): filtra `ALL_DETECTORS` via
  `ctx.enabled_setups` (`None` → tutti); **guard empty-set** → ritorna
  `ProposalDraft(setup_type="NONE", reason="no_enabled_setups")` prima del `drafts[0]`
  (no IndexError).
- **`.env.example*`** (5 file, incl. `.env.example.new` UTF-16): 4 righe
  `ENABLE_SETUP_*` (B=false, altri true).

**B_reversal NON cancellato** — solo flag-disabilitato, riattivabile via env.

## 2. Test

- **Suite completa** (esclusi 6 moduli con import rotti `anthropic`/`apscheduler`):
  **453 passed / 2 failed / 13 skipped / 8 xfailed**. I 2 fail sono i pre-esistenti
  (`test_smoke_12month_under_60s` perf; `test_legacy_entrypoint_imports` env `anthropic`).
  **Nessun nuovo fallimento.**
- **Test nuovi** (`tests/test_enable_setup_flags.py`, 8 test, verdi):
  - `enabled_setups=None` → 4 detector girano (3 losers). + variante `ctx=None`.
  - `enabled` senza B → 3 detector (2 losers).
  - `enabled_setups=frozenset()` → `NONE/no_enabled_setups`, niente crash.
  - VERO `build_ctx_live` con `cfg.ENABLE_SETUP_B=False` → `"B_reversal"` assente da
    `ctx.enabled_setups`, gli altri 3 presenti; `evaluate_proposal_for_bar` reale non
    produce mai draft con `setup_name=="B_reversal"`; default config disabilita B.
- **Backward-compat (`enabled_setups=None`)**: verificato SI (test dedicato + `ctx=None`).
- **Purity STRAT-08**: **PASS**.
- **Impatto ML losers (4→3 drafts)**: con B off, `setup_specific["losers"]` ha 2 entry
  invece di 3. Nessun codice/test assume esattamente 4 drafts; lo `slice_worker`
  `drafts_rows=[]` è DEFERRED (la Phase 7 non consuma ancora i losers). **Solo
  segnalato, non fixato** (vincolo task).

## 3. Smoke — impatto disabilitazione B (PRE = 4 setup, POST = B off)

| profilo | metrica | PRE (B on) | POST (B off) | Δ |
|---|---|---|---|---|
| **CONSERVATIVE** | n_trades | 125 | 104 | −21 |
| | win% | 21.6 | 26.0 | +4.4 |
| | mean_pnl_usd | −1.36 | +9.79 | +11.15 |
| | **total_pnl_usd** | **−169.63** | **+1017.85** | **+1187.48** |
| **MODERATE** | n_trades | 188 | 168 | −20 |
| | win% | 25.0 | 28.6 | +3.6 |
| | mean_pnl_usd | −1.18 | +6.19 | +7.37 |
| | **total_pnl_usd** | **−221.72** | **+1039.97** | **+1261.69** |
| **AGGRESSIVE** | n_trades | 373 | 355 | −18 |
| | win% | 35.7 | 37.7 | +2.0 |
| | mean_pnl_usd | +6.58 | +10.93 | +4.35 |
| | **total_pnl_usd** | **+2454.99** | **+3880.36** | **+1425.37** |

Grade POST invariati per A/C/D (B non c'è più): es. MODERATE A+40/A86/B42/C0.

## 4. Effetto crowding

Misurato sull'effetto NETTO (non assunto):

| profilo | B rimossi (n, total_pnl) | nuovi trade da altri setup (tie-break) | Δn netto |
|---|---|---|---|
| CONSERVATIVE | 21, −1112.95 | **0** | −21 |
| MODERATE | 21, −1096.43 | **+1** (D_pullback) | −20 |
| AGGRESSIVE | 19, −1053.12 | **+1** (D_pullback) | −18 |

- **Crowding inverso da tie-break ≈ nullo** (0-1 trade): nei bar dove B era READY,
  in genere era l'UNICO setup READY → rimuoverlo non lascia spazio a un altro. Solo
  in MOD/AGG 1 bar passa a D_pullback.
- A_breakout / C_compression: conteggi **identici** PRE↔POST in tutti i profili.

## 5. Interpretazione (solo dati)

- **L'expectancy aggregata migliora nettamente in tutti e 3 i profili.** CONSERVATIVE
  e MODERATE **passano da negativi a positivi** (−169→+1018, −222→+1040); AGGRESSIVE,
  già positivo, sale +58% (+2455→+3880). Win rate su in tutti.
- **La disabilitazione di B è netta-positiva**, e il guadagno è MAGGIORE della pura
  rimozione dei trade di B. Esempio CONSERVATIVE (crowding 0): il PnL dei soli trade
  non-B PRE era −169.63 −(−1112.95) = **+943.32**, ma POST è **+1017.85** (+74.53 in
  più). Spiegazione: il sizing del risk_engine dipende dal balance; le perdite di B
  (−1113) PRE erodevano l'equity → i trade A/C/D successivi venivano dimensionati su un
  capitale più basso. Senza B, lo stesso set di trade A/C/D gira su un equity-path più
  alto → size/PnL leggermente più favorevoli. È un effetto di **interazione equity-path/
  sizing**, non di tie-break. In MOD/AGG si aggiunge anche 1 trade D_pullback (crowding).
- Sintesi: rimuovere B ≈ togliere una zavorra ~−1.1k USD/trimestre per profilo, PIÙ un
  secondo-ordine positivo perché smette di degradare il sizing dei setup buoni.

## 6. Anomalie

- **Il guadagno eccede la somma dei PnL di B** (per l'effetto equity-path/sizing sopra):
  l'effetto NON è puramente additivo. Riportato come da vincolo "misura l'effetto netto".
- **`total_pnl` non peggiora in nessun profilo** (l'ipotesi controintuitiva del task non
  si verifica): B era zavorra pura, senza assorbire bar che altri tradano peggio.
- **ML losers 4→3** (vedi §2): la Phase 7 (drafts deferred) vedrà 3 candidati per bar,
  non 4. Da tenere presente quando il dataset drafts verrà popolato.
- Smoke su 3 mesi (Q1 2020) per budget tempo; il pattern per-setup era già stabile sui 3
  profili nel report precedente. Validazione full-history non in scope.
- Perf invariata rispetto al branch precedente (il filtro è O(1) sui 4 detector).

## 7. Git status

- Branch: `feat/enable-setup-flags-disable-b` (NON merged/pushed), fork da
  `fix/confluence-repair-regime-spread`.
- Commit: `207fd59` "feat(strat): ENABLE_SETUP_* flags + disable B_reversal by default".
- Files changed (committati): `config.py`, `strategy/context.py`,
  `strategy/adapters/live.py`, `strategy/__init__.py`, `strategy/setups/__init__.py`,
  `.env.example`(+4 varianti), `tests/test_enable_setup_flags.py`.
- Script smoke temporaneo (`scripts/_audit_smoke_grade.py`) **rimosso** (non committato).
  PRE/POST ottenuti con toggle `cfg.ENABLE_SETUP_B` sullo stesso range. Report in
  `.planning/research/` (untracked).
