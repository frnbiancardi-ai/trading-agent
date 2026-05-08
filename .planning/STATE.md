# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-07)

**Core value:** Every trade pre-filtered by a calibrated ML classifier whose probabilities match realized hit rate, trained on the agent's own decisions, improving with every cycle.

**Current milestone:** v2-ml-backtest
**Current focus:** Phase 2 — Indicators Library

---

## Milestone Status

| # | Phase | Status | Plans | Progress |
|---|-------|--------|-------|----------|
| 1 | Backtest Engine | ✓ complete | 8/8 | 100% |
| 2 | Indicators Library | ◐ in-progress | 6/9 | 67% |
| 3 | Patterns Catalog | ○ pending | 0/0 | 0% |
| 4 | Strategy Refactor | ○ pending | 0/0 | 0% |
| 5 | Baseline Backtest | ◐ planned | 9/9 | plans only |
| 6 | MCP Tools (part 1) | ○ pending | 0/0 | 0% |
| 7 | ML Classifier | ○ pending | 0/0 | 0% |
| 8 | MCP Tools (part 2) | ○ pending | 0/0 | 0% |
| 9 | Failure Analysis + Drift | ○ pending | 0/0 | 0% |
| 10 | Intermarket + News | ○ pending | 0/0 | 0% |
| 11 | Paper Deploy Gate | ○ pending | 0/0 | 0% |

**Overall progress:** 1/11 phases complete (9%)

---

## Active Work

Phase 2 — Indicators Library: Wave 0 (01) + Wave 1 (02, 03, 04) + Wave 2 (05, 06) COMPLETE 2026-05-08. Plan 06 (VWAP intraday + anchored) in ~4min: `vwap_intraday(bars)` cumula tp*v / v per sessione FX e resetta al boundary NY-17 via `_session_id_ny17` (DST-aware: winter 22:00 UTC, summer 21:00 UTC) riusato verbatim da Wave 0; `vwap_anchored(bars, anchor_ts)` cumula da prima bar con `bar.ts >= anchor_ts` (Pitfall 3 RESEARCH), ValueError fail-fast su anchor naive. `VWAPResult` dataclass length-N (vwap, cumulative_pv, cumulative_v) per D-04..D-06. Helper privati `_typical_price` + `_bar_volume` co-located. `avg_volume` Wave 0 preservato verbatim. Hand-calc test 7/7: single-bar tp=1.5, reset session winter (22:00 UTC) e summer (21:00 UTC), zero-volume → vwap=None (no div-by-zero), anchored before/at/raise. Leakage gate `test_no_future_leakage_vwap_intraday` 5/5 idx [50,100,250,400,499]. Spot-check fixture EURUSD H1 (500 bar): vwap_intraday last ≈ 1.16909, 500/500 non-None, anchored idx100 last ≈ 1.17357. 0 deviazioni — plan eseguito esattamente come scritto. Suite intera 317/317 verde + 1 skipped (305 → 317, +12: 7 hand-calc + 5 vwap_intraday leakage). INDIC-07 completato. Commits Wave 2 plan 06: ad5ed9a (feat), 78f85e5 (test). Wave 2 plan 07 (NR4/NR7+Closing Score) e plan 08 (MTF align) sbloccati.

Phase 2 — Indicators Library: Plan 05 (Donchian/Fibonacci/Pivots) in ~7min: `donchian(highs, lows, length=20)` rolling max/min/middle, `fibonacci_retracements(bars)` snapshot con livelli 0/0.382/0.5/0.618/1.0 sull'ultimo swing leg (riusa `find_support_resistance`, direction up/down via estremo più recente), `pivots(bars, anchor='daily'|'weekly')` classico P/R1..R3/S1..S3 + Camarilla `h1..h4/l1..l4` con multipliers verbatim 1.1/{12,6,4,2} (verificati LiteFinance/Babypips/Defcofx). Anchor NY-17 DST-aware via `_session_id_ny17` (winter 22:00 UTC, summer 21:00 UTC) — leakage-free by construction (bar usa H/L/C della sessione precedentemente CHIUSA). 2 deviazioni Rule 2 (guardie input: ValueError su length<=0 in donchian, anchor non valido in pivots). Hand-calc test esatto Camarilla (P=105, h1=105.91666, h4=110.5, l4=99.5) + 5+5 leakage idx parametrizzati. `find_support_resistance` + `check_breakout_quality` preservati invariati. Suite intera 305/305 verde + 1 skipped (286 → 305, +19: 9 hand-calc + 5 donchian + 5 pivots leakage). INDIC-05/08/09 completati. Commits Wave 2 plan 05: 4bb0150 (feat), b0f4c88 (test). Wave 2 plan 06 (VWAP) e 07/08 sbloccati.

Phase 7 — ML Classifier: CONTEXT.md captured (4 aree, 15 questions, 20 decisioni D-01..D-20 + 7 Claude discretion). Target: y=1 iff TP_HIT, TIMEOUT/BE=loss, scale_pos_weight per fold. Walk-forward expanding 10 fold, embargo timeout_bars[tf], train/val 80/20 temporal early-stop su Brier. Single LightGBM + categorical (symbol, timeframe, profile, setup_name, regime) + raw features. Hybrid hook: prediction in `evaluate_proposal_for_bar` (attacca prob a ProposalDraft, no filter), decision in `risk_engine.evaluate_trade` (threshold gate). Threshold profit-curve optimized per profile, mediana 10 fold. Artifact: joblib + sidecar metadata.json. Resume: `.planning/phases/07-ml-classifier/07-CONTEXT.md`. Next: `/gsd-plan-phase 7`.

Phase 6 — MCP Tools (part 1): CONTEXT.md captured (4 areas, 11 questions, 12 decisioni dirette). Async backtest queue + cancel, in-process trail daemon (position_trails), additive backward-compat MCP-R1/R2/R3, BarSource adapter (live default + as_of_ts opt), replay_decision union lookup, mcp/ package split. Tool surface 25 totali (11 esistenti + 13 REQUIREMENTS + 1 derivato cancel_backtest). Resume: `.planning/phases/06-mcp-tools-part-1/06-CONTEXT.md`. Next: `/gsd-plan-phase 6`.

Phase 5 — Baseline Backtest: 9 PLAN.md scritti (W0..W4), checker PASS iter 2/3, 6 blocker risolti (parquet directory, SC#3 hard/soft, warmup adattivo, D-21 real test, engine slice_until dual-branch, preflight contract probe). Pronto per `/gsd-execute-phase 5` — bloccato in attesa che Phase 1-4 completino esecuzione (preflight gate in 05-08).

Phase 2 — Indicators Library: Wave 0 (01) + Wave 1 (02, 03, 04) COMPLETE 2026-05-08. Plan 04 (Hurst R/S) in ~3.5min: `hurst_rs(values, window=100)` ritorna `HurstResult(hurst, window)` con stima OLS log-log della pendenza R/S su sub-windows [10,20,40,80] (NON naive single-window log(R/S)/log(N)). 1 deviazione Rule 1 nel test sintetico: `random_walk` rinominato a `white_noise` perché R/S sui livelli di cumsum(gauss) → H≈1.0, NON 0.5; per H≈0.5 sui livelli serve serie i.i.d. (no auto-correlazione). Verifiche superate: rampa lineare → H≈0.998 (persistente), zigzag → H<0.45 (anti-persistente), white noise → H∈[0.35, 0.65], leakage-free a 5 indici, EURUSD H1 fixture media H≈0.965 (forte trend), purity runtime preservata (no pandas_ta), Mottl `hurst` parity test gated (skip se non installato). Suite 286/286 verde (275 → 286, +11). INDIC-12 completato. Commits Wave 1 plan 04: 172dcc3 (feat), b79e07c (test). Wave 2 (plan 05+) sbloccato.

Phase 2 — Indicators Library: Wave 0 (plan 01) + Wave 1 plan 02 + Wave 1 plan 03 COMPLETE 2026-05-08. Plan 03 in ~8.5min: `adx` (ADX/DMI 14 Wilder/RMA), `macd` (12/26/9 EMA-of-EMA), `stochastic` (14/3/3) implementati con dataclass-of-lists (ADXResult, MACDResult, StochasticResult), parity 1e-6 vs pandas-ta su 500 bar EURUSD H1 (>100 confronti per serie), leakage-free a 5 indici, runtime purity preservata. 2 deviazioni Rule 1: (1) ADX riscritto rispetto al RESEARCH Example 1 — pandas-ta usa pta.rma (ewm senza SMA-seed) e atr(prenan+presma), NON `_wilder_smooth` con SMA-seed e mask 2*period; aggiunti due helper privati `_rma_first_valid_seed`, `_atr_pta_compat`. (2) Test MACD signal-lag su parabola (i*i) invece di lineare (range): su lineare line e signal convergono per costruzione. Suite 275/275 verde (252 → 275, +23). INDIC-02 + INDIC-03 + INDIC-04 completati. Commits Wave 1 plan 03: 8c0c35a (feat), 5ae3e73 (test+bug-fix). Wave 1 plan 04 (Hurst) e Wave 2 sbloccati. Branch: `feature/update-pythono-pure-strategy`.

Phase 2 — Indicators Library: Wave 0 (plan 01) + Wave 1 plan 02 COMPLETE 2026-05-08. Plan 02 in ~5min: `bollinger_bands` (BB 20/2σ + BBW + squeeze percentile + squeeze TTM Carter) e `keltner` (EMA ± scalar·EMA(TR)) implementati con dataclass-of-lists (BollingerResult, KeltnerResult), parity 1e-6 vs pandas-ta su 500 bar EURUSD H1, leakage-free a 5 indici, runtime purity preservata. 3 deviazioni Rule 1 (ddof=1 per parity bbands, EMA-TR per parity kc, off-by-one nel test sanity keltner). Suite 252/252 verde (236 → 252, +16). INDIC-01 + INDIC-06 completati. Commits Wave 1 plan 02: 466fe97 (feat), e10e6d5 (test+bug-fix). Wave 1 plan 03 (ADX/MACD/Stoch) e plan 04 (Hurst) sbloccati. Branch: `feature/update-pythono-pure-strategy`.

Phase 1 — Backtest Engine: COMPLETE 2026-05-07. All 8 plans + VERIFICATION.md PASSED (6/6 truths). Engine event-driven, costs.yaml, walk-forward, metrics, smoke 12-month <60s (6.78s actual). Legacy RSI/SMA grid archived.

---

## Recent Decisions

See `.planning/PROJECT.md` Key Decisions table.

---

## Notes

- Brownfield project. Existing infra (MT5, scheduler, RSS, MCP server) untouched.
- Strategy backed up in git tag — safe to refactor.
- Historical data: 23.5y, 3 pairs × 3 TFs in `data/historical/`.
- Skills: `forex-trader-pro`, `forex-algo-dev`, `forex-strategy-builder`.

---
*Last updated: 2026-05-08 — Phase 2 plan 06 (Wave 2: VWAP intraday + anchored) complete*
