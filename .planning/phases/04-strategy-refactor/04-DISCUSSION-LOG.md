# Phase 4: Strategy Refactor — Discussion Log

**Date:** 2026-05-07
**Mode:** discuss (4 aree, multiSelect)
**Decisions captured in:** `04-CONTEXT.md`

This log is for human reference only — not consumed by downstream agents.

---

## Areas Discussed

User selected all 4 gray areas:
1. API + module layout
2. Setup priority + multi-match
3. Confluence + SL/TP per-setup
4. Live↔backtest IF + regression fixture

---

## Area 1 — API + module layout

### Q1.1 — Module layout per strategy/ package
- Options: `strategy/` package | flat `strategy.py` + `strategy_setups.py` | `strategy/` + drop class
- **User chose:** `strategy/` package (Recommended)
- **Why:** mirror del Phase 2 `indicators/`, scheduler/MCP non si rompono via shim re-export

### Q1.2 — Detector signature
- Options: `(bars, indicators, ctx)` | espliciti | `(MarketSnapshot, profile)`
- **User chose:** `(bars, indicators, ctx)` (Recommended)
- **Why:** ctx dataclass evita esplosione parametri, pure-fn pulita

### Q1.3 — ProposalDraft = nuovo o reuse TradeProposal?
- Options: nuovo `ProposalDraft` | reuse `TradeProposal` | `ProposalDraft` + setup-specific
- **User chose:** nuovo `ProposalDraft` (Recommended)
- **Why:** detector output staccato da messaggio finale, conversione `draft_to_trade_proposal` esplicita; preserva campi ML-friendly

### Q1.4 — Backward-compat per `IntradayStrategy`
- Options: shim → pure fn | drop class | shim + DeprecationWarning
- **User chose:** Shim class → pure fn (Recommended)
- **Why:** scheduler/MCP/tests non si rompono. Cleanup futuro se serve

### Q1.5 — ctx dataclass: cosa include
- Options: minimal | full | minimal + factor-data sub-dataclass
- **User chose:** Minimal: profile + sr + regime + patterns + symbol_info (Recommended)
- **Why:** strict pure detector. Sentiment + env vivono in layer separato post-detector (esistente shim)

### Q1.6 — Live + backtest: chi costruisce ctx
- Options: adapter per ambiente | ctx_builder generico | caller-built
- **User chose:** Adapter per ambiente (Recommended)
- **Why:** detector agnostic. `live_adapter` usa MT5 client, `backtest_adapter` usa engine state

---

## Area 2 — Setup priority + multi-match

### Q2.1 — Quando >1 detector matcha sullo stesso bar
- Options: highest grade + tie A>C>B>D | highest confidence | first-match | reject ambiguity
- **User chose:** Highest grade, tie→priority A>C>B>D (Recommended)
- **Why:** trend-with prevale su mean-revert. Deterministico via grade-then-priority

### Q2.2 — Detector contro-trend (B reversal vs D pullback): allow?
- Options: B solo se grade A | B sempre se confluences ≥2 | block B contro-trend
- **User chose:** B reversal solo se grade A (Recommended)
- **Why:** skill rule ("counter-trend counts only if A-grade reversal stack"). Riduce falsi reversal

### Q2.3 — Detector che ritorna None: fa logging del why?
- Options: ProposalDraft con setup_type=NONE + reason | None puro + log esterno | RejectionDraft separato
- **User chose:** ProposalDraft con setup_type=NONE + reason (Recommended)
- **Why:** detector ritorna sempre Draft. Useful per ML Phase 7 + debug

---

## Area 3 — Confluence + SL/TP per-setup

### Q3.1 — 5 confluence factors: dove vivono le soglie
- Options: `config/strategy.yaml` | const in confluence.py | `.env` vars
- **User chose:** `config/strategy.yaml` (Recommended)
- **Why:** mirror pattern Phase 2/3. Tunable per Phase 5 backtest e Phase 7 ML. .env già saturo

### Q3.2 — Adjuster Phase 10-dipendenti
- Options: stub callable + zero-impact default | skip ora | implementa con dato disponibile
- **User chose:** Stub callable + zero-impact default (Recommended)
- **Why:** zero-churn quando Phase 10 inietta callable reali. Spread/recent_trades adjuster già implementati ora

### Q3.3 — SL/TP: per-setup o uniforme?
- Options: per-setup | strategy-wide switch | uniforme attuale
- **User chose:** Per-setup, fn dedicata in ogni setup module (Recommended)
- **Why:** skill prescrive specifico per ogni setup. Cap 1.5×ATR universale; buffer 0.3-0.5×ATR universale

### Q3.4 — Confidence calibration: dove vivono start values + adjusters
- Options: `config/strategy.yaml` | hard-coded const | per-profile YAML
- **User chose:** `config/strategy.yaml` (Recommended)
- **Why:** stesso file di soglie. Single source. Profile filters vivono nello stesso schema

---

## Area 4 — Live↔backtest IF + regression fixture

### Q4.1 — Indicators pre-computed o calcolati dal detector?
- Options: pre-computed da adapter | detector calcola internally | lazy IndicatorsView
- **User chose:** Pre-computed da adapter (Recommended)
- **Why:** 1 sola compute per bar invece di 4. Critico per Phase 5 backtest 23.5y × 3 pair × 3 TF

### Q4.2 — Backtest adapter: come riceve bar storica?
- Options: BacktestEngine itera + adapter.evaluate_bar | detector iterabile su full series | generator
- **User chose:** BacktestEngine itera bar, chiama adapter.evaluate_bar (Recommended)
- **Why:** no future leakage by construction (detector vede bars[:i+1])

### Q4.3 — Regression fixture (SC#5): formato + cattura
- Options: snapshot JSON 10 decisioni live + bars input | synthetic deterministic | replay decision DB
- **User chose:** Snapshot JSON 10 decisioni live + bars input (Recommended)
- **Why:** cattura comportamento legacy reale. Synthetic non garantisce parità con prod attuale

### Q4.4 — Cattura snapshot pre-refactor: quando?
- Options: Wave 0 prima di toccare strategy.py | da logs esistenti | skip fixture
- **User chose:** Wave 0 prima di toccare strategy.py (Recommended)
- **Why:** garantisce baseline riproducibile. Logs incompleti per ricostruzione input

---

## Deferred Ideas Captured

(vedi `04-CONTEXT.md` § Deferred Ideas)

- ML-driven setup ranking → Phase 8
- Per-symbol strategy.yaml override → backlog post-Phase 5
- Vectorized detector → Phase 5 se backtest lento
- Detector ensemble voting → backlog ML tuning
- Real-time multi-TF confluence → Phase 6
- Setup E (channel/range) → out of scope canonical
- Confidence calibration ML-based → Phase 7
- Failed breakout auto-flip → backlog
- Strict purity runtime decorator → Phase 4 only AST test

---

## Claude's Discretion (delegato a planner/researcher)

- Esatto AST-introspection check in `tests/test_strategy_purity.py` (which import names da bloccare).
- Scelta `RiskProfile` enum location (`models.py` vs `risk_engine.py`).
- Schema esatto `ExtendedIndicators` dataclass (estende Phase 2 `IndicatorSnapshot` ma quali campi aggiuntivi).
- Scenario set per `tests/capture_regression_baseline.py` (10 sample, mix READY/FORMING/NONE — planner sceglie offset esatti).
- Whether `ALL_DETECTORS` registry vive in `strategy/setups/__init__.py` o in `strategy/__init__.py` (preferenza autore).
- File location per `RiskProfile` filtering (in `confluence.py::filter_by_profile` o nel proposal adapter).
