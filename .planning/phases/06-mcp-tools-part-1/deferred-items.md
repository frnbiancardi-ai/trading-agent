# Deferred Items — Phase 6 MCP Tools Part 1

Issue scoperte durante l'esecuzione di Plan 06-02 ma **fuori scope** Phase 6.
Tracking per riferimento futuro; NON da risolvere in questo plan.

## Test pre-esistenti falliti (out-of-scope)

### test_backtest_engine.py::test_smoke_12month_under_60s

- **Scope**: Phase 1 (backtest engine performance)
- **Stato**: pre-esistente al Plan 06-02 (verificato con `git stash` prima delle modifiche, fail confermato anche su HEAD pre-Plan-06-02: 104.19s > 60s).
- **Causa**: macchina devcontainer più lenta del target locale dev. Soglia SC-6 (60s) tarata su workstation Windows; su Linux container può raggiungere ~110s.
- **Azione**: NON correggere in Plan 06-02. Da valutare in Phase 1 retro: alzare soglia, sklippare in CI container, o ottimizzare.

### Moduli mancanti (4 test collection errors)

- `tests/test_daily_orchestrator.py` — manca `apscheduler` (Phase 14)
- `tests/test_news_aggregator.py` — manca `feedparser` (Phase 15)
- `tests/test_phase16.py` — manca `apscheduler` (Phase 14)
- `tests/test_scheduler.py` — manca `apscheduler` (Phase 14)
- **Scope**: Phase 14-15 (scheduler/news), non Phase 6
- **Azione**: NON installare nel devcontainer di Phase 6; risolvere in Phase 14/15 quando si attiveranno.

## File untracked non Phase 6

- `data/training/baseline_decisions.pre-05-09/` — output Plan 05-09 (Phase 5)
- `trades.db` — runtime DB
- `C:\trading-agent\logs\agent.log` — log path Windows letto su Linux (pre-esistente)
- **Azione**: NON includere nei commit Plan 06-02 (out-of-scope).
