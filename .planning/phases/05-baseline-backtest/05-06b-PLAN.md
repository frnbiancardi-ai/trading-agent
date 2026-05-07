---
phase: 05-baseline-backtest
plan: 06b
type: execute
wave: 2
depends_on: [05-01, 05-02, 05-03, 05-04, 05-05, 05-06a]
files_modified:
  - backtest/baseline/report_writer.py
  - tests/test_baseline_report_writer.py
autonomous: true
requirements: [BACK-07, INT-01]
tags: [phase-5, baseline-backtest, wave-2, report]

phase1_dependency_risk: |
  report_writer è puro (legge result dict + meta dict, scrive Markdown). Nessuna dependency
  hard sulle Phase 1-4 — può essere implementato e testato indipendentemente. Smoke E2E
  in 05-08 (vincolato dal preflight).

  WARNING 14 fix: questo plan è la PARTE B del split 05-06 originale (report_writer only).
  Plan 05-06a copre slice_worker.

must_haves:
  truths:
    - "write_baseline_report(results, path, meta) produce MD con header + tabella 27-row + per-slice mini-section + appendix"
    - "Report contiene tutti i 27 run_id citati nelle mini-section (D-18)"
    - "Appendix contiene cost_yaml_sha256, strategy_yaml_sha256, baseline_yaml_sha256 full 64-char (WARNING 12 fix)"
  artifacts:
    - path: "backtest/baseline/report_writer.py"
      provides: "write_baseline_report (D-18)"
      contains: "## Header"
      contains: "## Per-slice"
      contains: "## Appendix"
      contains: "cost_yaml_sha256"
      min_lines: 80
  key_links:
    - from: "backtest/baseline/report_writer.py::write_baseline_report"
      to: "backtest/baseline/runner.py (Wave 3 — Plan 05-07)"
      via: "main process post-pool aggrega 27 result e chiama write_baseline_report"
---

<objective>
Wave 2 (parte report_writer — split B di WARNING 14 fix). Implementa il report writer
Markdown D-18.

**`backtest/baseline/report_writer.py`** — funzione `write_baseline_report(results, path, meta)`
compone il file `.planning/research/baseline-{date}.md` secondo schema D-18: header +
tabella 27-row + per-slice mini-section + appendix con hashes (full sha256 64-char per
audit trail; WARNING 12 fix).

Test: 3 test in `test_baseline_report_writer.py` (rimuove skip).

Output:
- `backtest/baseline/report_writer.py` (NEW)
- 3 test in `test_baseline_report_writer.py` implementati
</objective>

<execution_context>
@C:/trading-agent/.claude/get-shit-done/workflows/execute-plan.md
@C:/trading-agent/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@C:/trading-agent/.planning/phases/05-baseline-backtest/05-CONTEXT.md
@C:/trading-agent/.planning/phases/05-baseline-backtest/05-PATTERNS.md
@C:/trading-agent/.planning/phases/05-baseline-backtest/05-VALIDATION.md

<interfaces>
From 05-06a slice_worker results:
  Each result dict: {run_id, profile, status, metrics (BacktestMetrics dataclass),
                     n_trades, n_drafts, equity_path, symbol, timeframe, error}

From CONTEXT.md §D-18 (report schema):
  1. Header: data run, comando CLI, git_sha, total wall-clock, n_run completati/falliti
  2. Tabella 27-row: symbol, tf, profile, n_trades, sharpe, sortino, max_dd_pct, hit_rate,
     expectancy_pips, profit_factor, avg_R, longest_dd_days
  3. Per-slice mini-section (27): link equity PNG, top setup_name distribution,
     exit_reason breakdown, avg bars_held
  4. Appendix: cost_yaml_sha256 (full 64), strategy_yaml_sha256 (full 64),
     baseline_yaml_sha256 (full 64), slippage_seed, warm-up bars effettivi,
     longest_lookback usato

WARNING 12 fix: appendix scrive sha256 FULL 64-char (non md5 16-char troncato).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: backtest/baseline/report_writer.py — Markdown D-18 schema</name>
  <files>backtest/baseline/report_writer.py, tests/test_baseline_report_writer.py</files>
  <read_first>
    - C:/trading-agent/.planning/phases/05-baseline-backtest/05-PATTERNS.md §`report_writer.py` lines 238-256
    - C:/trading-agent/.planning/phases/05-baseline-backtest/05-CONTEXT.md §D-18 lines 86-90 (schema esatto)
  </read_first>
  <behavior>
    - Test 1: `test_report_structure(tmp_path)` — Mock 27 result dict, chiamare `write_baseline_report(results, path, meta)`. Verifica che il file MD contiene sezioni `## Header`, `## Slice Metrics` (tabella), `## Per-slice details`, `## Appendix`.
    - Test 2: `test_report_contains_all_27_run_ids(tmp_path)` — Su 27 result mock con run_id distinti, verifica che ogni run_id compare almeno una volta nel file MD.
    - Test 3: `test_report_appendix_hashes(tmp_path)` — Verifica che `meta["cost_yaml_sha256"]` (full 64), `meta["strategy_yaml_sha256"]` (full 64), `meta["baseline_yaml_sha256"]` (full 64), `meta["slippage_seed"]` figurano nell'appendix con length 64 (WARNING 12 fix).
  </behavior>
  <action>
    **Sub-task 1a — Crea `backtest/baseline/report_writer.py`:**

    ```python
    """Markdown report writer per baseline backtest (D-18, INT-01).

    Schema rigido D-18:
      1. Header: data run, comando CLI, git_sha, total wall-clock, n_run completati/falliti
      2. Tabella 27-row metrics
      3. Per-slice mini-section (link equity PNG, top setup distribution, exit_reason
         breakdown, avg bars_held)
      4. Appendix: cost_yaml_sha256, strategy_yaml_sha256, baseline_yaml_sha256 (FULL 64-char,
         WARNING 12 fix), slippage_seed, warm-up bars effettivi, longest_lookback usato

    Output: file singolo `.planning/research/baseline-{date}.md`. UTF-8 encoding.
    """
    from __future__ import annotations

    import logging
    from datetime import datetime
    from pathlib import Path

    _log = logging.getLogger(__name__)


    _TABLE_HEADER = (
        "| symbol | tf | profile | n_trades | sharpe | sortino | max_dd_pct "
        "| hit_rate | expectancy_pips | profit_factor | avg_R | longest_dd_days |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|"
    )


    def _row(r: dict) -> str:
        m = r.get("metrics")
        if r.get("status") != "OK" or m is None:
            return (f"| {r.get('symbol','-')} | {r.get('timeframe','-')} | {r.get('profile','-')} "
                    f"| FAILED ({r.get('error','')[:40]}) | - | - | - | - | - | - | - | - |")
        return (f"| {r['symbol']} | {r['timeframe']} | {r['profile']} | {r['n_trades']} "
                f"| {getattr(m, 'sharpe', 0.0):.3f} | {getattr(m, 'sortino', 0.0):.3f} "
                f"| {getattr(m, 'max_drawdown_pct', 0.0):.2f} | {getattr(m, 'hit_rate', 0.0):.3f} "
                f"| {getattr(m, 'expectancy_usd', 0.0):.2f} | {getattr(m, 'profit_factor', 0.0):.2f} "
                f"| {getattr(m, 'avg_r', 0.0):.2f} | {getattr(m, 'longest_dd_days', 0.0):.1f} |")


    def _per_slice_section(r: dict) -> str:
        if r.get("status") != "OK":
            return f"### {r['run_id']}\n\nStatus: **FAILED** — {r.get('error','')}\n"
        lines = [
            f"### {r['run_id']}",
            f"- Equity curve: ![equity]({r.get('equity_path','')})",
            f"- Trades: {r['n_trades']}",
            f"- Drafts emitted: {r.get('n_drafts', 0)}",
        ]
        return "\n".join(lines) + "\n"


    def write_baseline_report(results: list[dict], out_path: Path, meta: dict) -> None:
        """Compone .planning/research/baseline-{date}.md (D-18).

        meta keys richiesti: cli_command, git_sha, total_wall_clock_seconds,
          cost_yaml_sha256, strategy_yaml_sha256, baseline_yaml_sha256 (TUTTI full 64-char,
          WARNING 12 fix), slippage_seed, warm_up_bars (dict tf→int), longest_lookback (int)
        """
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        n_total = len(results)
        n_ok = sum(1 for r in results if r.get("status") == "OK")
        n_failed = sum(1 for r in results if r.get("status") == "FAILED")
        n_skipped = sum(1 for r in results if r.get("status") == "SKIPPED")

        lines: list[str] = []
        # Header (D-18 part 1)
        lines.append("## Header\n")
        lines.append(f"- **Data run**: {datetime.utcnow().isoformat()}Z")
        lines.append(f"- **Comando CLI**: `{meta.get('cli_command', 'n/a')}`")
        lines.append(f"- **git_sha**: `{meta.get('git_sha', 'unknown')}`")
        lines.append(f"- **Total wall-clock**: {meta.get('total_wall_clock_seconds', 0):.1f}s")
        lines.append(f"- **Run completed**: {n_ok}/{n_total} (skipped: {n_skipped}, failed: {n_failed})")
        lines.append("")

        # Tabella 27-row (D-18 part 2)
        lines.append("## Slice Metrics\n")
        lines.append(_TABLE_HEADER)
        sorted_results = sorted(
            results, key=lambda r: (r.get("symbol", ""), r.get("timeframe", ""), r.get("profile", "")),
        )
        for r in sorted_results:
            lines.append(_row(r))
        lines.append("")

        # Per-slice mini-section (D-18 part 3)
        lines.append("## Per-slice details\n")
        for r in sorted_results:
            lines.append(_per_slice_section(r))

        # Appendix (D-18 part 4) — WARNING 12 fix: full 64-char sha256
        lines.append("## Appendix\n")
        lines.append(f"- `cost_yaml_sha256`: `{meta.get('cost_yaml_sha256', 'n/a')}`")
        lines.append(f"- `strategy_yaml_sha256`: `{meta.get('strategy_yaml_sha256', 'n/a')}`")
        lines.append(f"- `baseline_yaml_sha256`: `{meta.get('baseline_yaml_sha256', 'n/a')}`")
        lines.append(f"- `slippage_seed`: {meta.get('slippage_seed', 42)}")
        warm = meta.get("warm_up_bars", {})
        if warm:
            lines.append(f"- `warm_up_bars`: {warm}")
        lines.append(f"- `longest_lookback`: {meta.get('longest_lookback', 'n/a')}")
        # SC#3 thresholds documentation (BLOCKER 2 hard/soft gates):
        lines.append(f"- `decision_count`: {meta.get('decision_count', 'n/a')} "
                     f"(hard gate ≥{meta.get('min_decisions_hard', 1000)}, "
                     f"soft target ≥{meta.get('target_decisions_soft', 10000)})")
        lines.append("")

        out_path.write_text("\n".join(lines), encoding="utf-8")
        _log.info("baseline report scritto: %s (%d byte)", out_path, out_path.stat().st_size)
    ```

    **Sub-task 1b — Implementa 3 test in `tests/test_baseline_report_writer.py`** (rimuove skip):

    ```python
    """Tests for backtest.baseline.report_writer (D-18, INT-01)."""
    from __future__ import annotations

    from pathlib import Path
    from unittest.mock import MagicMock

    import pytest

    from backtest.baseline.report_writer import write_baseline_report


    def _mk_metrics():
        m = MagicMock()
        m.sharpe = 1.2
        m.sortino = 1.5
        m.max_drawdown_pct = -8.0
        m.hit_rate = 0.55
        m.expectancy_usd = 0.5
        m.profit_factor = 1.3
        m.avg_r = 0.6
        m.longest_dd_days = 12.5
        return m


    def _mk_results():
        results = []
        for sym in ("EURUSD", "GBPUSD", "USDJPY"):
            for tf in ("M15", "M30", "H1"):
                for prof in ("CONSERVATIVE", "MODERATE", "AGGRESSIVE"):
                    results.append({
                        "run_id": f"baseline_2026-05-08_{sym}_{tf}_{prof}",
                        "symbol": sym, "timeframe": tf, "profile": prof,
                        "status": "OK", "metrics": _mk_metrics(),
                        "n_trades": 100, "n_drafts": 1000,
                        "equity_path": f".planning/research/baseline-equity-curves/{sym}_{tf}_{prof}.png",
                    })
        return results


    def _mk_meta():
        # WARNING 12 fix: tutti gli hash sono FULL 64-char sha256
        return {
            "cli_command": "python scripts/run_baseline_backtest.py",
            "git_sha": "abcdef1234567890",
            "total_wall_clock_seconds": 1234.5,
            "cost_yaml_sha256": "deadbeef" * 8,        # 64 char
            "strategy_yaml_sha256": "cafebabe" * 8,    # 64 char
            "baseline_yaml_sha256": "feedface" * 8,    # 64 char
            "slippage_seed": 42,
            "warm_up_bars": {"M15": 200, "M30": 200, "H1": 200},
            "longest_lookback": 200,
            "decision_count": 12345,
            "min_decisions_hard": 1000,
            "target_decisions_soft": 10000,
        }


    def test_report_structure(tmp_path: Path) -> None:
        out = tmp_path / "baseline-2026-05-08.md"
        write_baseline_report(_mk_results(), out, _mk_meta())
        text = out.read_text(encoding="utf-8")
        assert "## Header" in text
        assert "## Slice Metrics" in text
        assert "## Per-slice details" in text
        assert "## Appendix" in text


    def test_report_contains_all_27_run_ids(tmp_path: Path) -> None:
        out = tmp_path / "baseline.md"
        results = _mk_results()
        assert len(results) == 27
        write_baseline_report(results, out, _mk_meta())
        text = out.read_text(encoding="utf-8")
        for r in results:
            assert r["run_id"] in text, f"missing {r['run_id']} in report"


    def test_report_appendix_hashes(tmp_path: Path) -> None:
        """WARNING 12 fix: appendix contiene FULL 64-char sha256."""
        out = tmp_path / "baseline.md"
        meta = _mk_meta()
        write_baseline_report(_mk_results(), out, meta)
        text = out.read_text(encoding="utf-8")
        # Hash FULL 64-char visibili
        assert meta["cost_yaml_sha256"] in text
        assert meta["strategy_yaml_sha256"] in text
        assert meta["baseline_yaml_sha256"] in text
        # Length check: ognuno deve apparire come 64-char hex string
        assert len(meta["cost_yaml_sha256"]) == 64
        assert len(meta["strategy_yaml_sha256"]) == 64
        assert len(meta["baseline_yaml_sha256"]) == 64
        assert "slippage_seed" in text
        assert "42" in text
    ```
  </action>
  <verify>
    <automated>.venv\Scripts\python.exe -m pytest tests/test_baseline_report_writer.py -x --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - File `backtest/baseline/report_writer.py` esiste, ≥80 righe
    - `grep -c "def write_baseline_report" backtest/baseline/report_writer.py` == 1
    - `grep -c "## Header" backtest/baseline/report_writer.py` ≥ 1
    - `grep -c "## Appendix" backtest/baseline/report_writer.py` ≥ 1
    - `grep -c "cost_yaml_sha256" backtest/baseline/report_writer.py` ≥ 1 (WARNING 12)
    - `grep -c "strategy_yaml_sha256" backtest/baseline/report_writer.py` ≥ 1
    - `grep -c "baseline_yaml_sha256" backtest/baseline/report_writer.py` ≥ 1
    - `pytest tests/test_baseline_report_writer.py -x` exit 0 (3 test pass)
  </acceptance_criteria>
  <done>
    Report writer implementato. D-18 schema verificato + WARNING 12 (full sha256) verificato.
    3 test verdi.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Markdown content → user filesystem | Path-controlled (`.planning/research/baseline-{date}.md`) — no path traversal vector |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-16 | Information Disclosure | report contains git_sha + paths | accept | report committato in `.planning/research/` — repo interno, paths assoluti accettabili |
| T-05-26 | Repudiation | sha256 truncation hides config drift | mitigate | WARNING 12: full 64-char sha256 nelle appendix — collision practically impossible |
</threat_model>

<verification>
- 1 modulo implementato (report_writer)
- 3 test pass
- D-18 schema verificato + WARNING 12 closure
- VALIDATION.md row D-18 spostata a green
</verification>

<success_criteria>
- Plan 05-07 (runner) può consumare `write_baseline_report(results, path, meta)` post-pool
- D-18 + WARNING 12 chiusi
- Phase 5 split fix (WARNING 14) chiuso: 05-06 ≈ 850 righe → 05-06a (~500) + 05-06b (~350)
</success_criteria>

<output>
Dopo completamento: `.planning/phases/05-baseline-backtest/05-06b-SUMMARY.md`.
Sezioni: Files Created, Tests Passing, D-18 Verification, WARNING 12 Closure (full sha256),
Next Wave (05-07 runner + CLI).
</output>
</content>
</invoke>