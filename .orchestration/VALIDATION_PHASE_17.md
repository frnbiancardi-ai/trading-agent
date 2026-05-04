# Phase 17 Validation Checklist

User sign-off checklist for Strategy v2 (Defendi-based) before merge to main.

## Sub-phases Code Completion

- [x] 17.1 — Indicatori avanzati (indicators_advanced.py)
- [x] 17.2 — Compressione volatilità (volatility_compression.py)
- [x] 17.3 — Pullback engine (pullback_engine.py)
- [x] 17.4 — Multi-timeframe + divergenze attive (strategy.py integrazione)
- [x] 17.5 — Position management attiva (position_manager.py)
- [x] 17.6 — Backtest harness (backtest.py)
- [ ] 17.7 — Calibrazione + validazione (scripts/run_calibration.py, PHASE_17_VALIDATION.md)

## Test Coverage

- [x] All 173 existing tests pass (legacy compatibility)
- [ ] All new tests pass (17.1–17.6 test suites)
- [ ] Test coverage >90% for new modules
- [ ] Backtest deterministicità verificata (same dataset → same output)

## Backtest Results (6m EURUSD+GBPUSD M15)

- [ ] v2 dataset backtest completed
- [ ] v1.2.0 dataset backtest completed (baseline for comparison)
- [ ] v2 beats v1.2.0 on ≥2 metrics among: {expectancy, profit factor, Sharpe, max DD}
  - [ ] Expectancy: v2 > v1.2.0
  - [ ] Profit Factor: v2 > v1.2.0
  - [ ] Sharpe Ratio: v2 > v1.2.0
  - [ ] Max Drawdown: v2 < v1.2.0 (lower is better)

## Documentation

- [ ] `.env.example` updated with all v2 config flags
- [ ] README.md section added: "Strategy v2 (Defendi-based)" overview
- [ ] PHASE_17_VALIDATION.md completed with calibration results
- [ ] Inline comments/docstrings for all new modules reviewed

## Live Validation (optional, before merge)

- [ ] Shadow mode tested 24h+ on live market with v2
- [ ] No degradation in execution latency (<500ms per symbol)
- [ ] Error logs reviewed for any anomalies
- [ ] MT5 connection stability confirmed

## Integration Readiness

- [ ] Scheduler loop integration confirmed (17.5 position management active)
- [ ] Risk engine gate functional (no bypass)
- [ ] MCP server contract unchanged
- [ ] Backward compatibility maintained (can revert to v1.2.0 if needed)

## Merge Decision

Gate: v2 backtest beats v1.2.0 on ≥2 metrics.

**Result**: [ ] APPROVED FOR MERGE | [ ] REQUEST CHANGES | [ ] HOLD (needs more work)

**User signature**: ___________________________ **Date**: __________

**Notes**:
```
[User notes / observations from live testing, if any]
```

---

## Timeline

- Phase 17 started: 2026-05-04
- Phase 17.1–17.6 completed: [TARGET: 2026-05-15]
- Phase 17.7 calibration: [TARGET: 2026-05-17]
- Merge decision: [TARGET: 2026-05-18]
- Merge to main + tag v2.0.0: [TARGET: 2026-05-19]
