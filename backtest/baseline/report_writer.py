"""Markdown report writer per baseline backtest (D-18, INT-01).

Schema rigido D-18 (`.planning/phases/05-baseline-backtest/05-CONTEXT.md`):
  1. Header: data run, comando CLI, git_sha, total wall-clock, n_run completati/falliti
  2. Tabella 27-row metrics (symbol/tf/profile/n_trades/sharpe/sortino/max_dd_pct/
     hit_rate/expectancy_pips/profit_factor/avg_R/longest_dd_days)
  3. Per-slice mini-section (link equity PNG, n_trades, n_drafts emitted)
  4. Appendix: cost_yaml_sha256, strategy_yaml_sha256, baseline_yaml_sha256
     (FULL 64-char, WARNING 12 fix), slippage_seed, warm-up bars effettivi,
     longest_lookback usato, decision_count vs hard/soft gate (BLOCKER 2)

Output: file singolo `.planning/research/baseline-{date}.md`. UTF-8 encoding.

Module puro: legge result dict (lista) + meta dict (config/audit), produce file MD.
Nessuna dipendenza hard sulle Phase 1-4 — testabile in isolamento (mock-friendly).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger(__name__)


# Tabella header allineata a D-18 part 2 — colonne fisse, ordinamento sym→tf→profile.
_TABLE_HEADER = (
    "| symbol | tf | profile | n_trades | sharpe | sortino | max_dd_pct "
    "| hit_rate | expectancy_pips | profit_factor | avg_R | longest_dd_days |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|"
)


def _row(r: dict) -> str:
    """Formatta una riga della tabella metrics dal result dict.

    Result OK: leggi metrics dataclass via getattr (robusto a MagicMock nei test).
    Result FAILED/SKIPPED: riga con marker FAILED + error message troncato.
    """
    m = r.get("metrics")
    if r.get("status") != "OK" or m is None:
        # Riga di failure — preserve symbol/tf/profile per traccia, troncamento error a 40 char.
        err = (r.get("error") or "")[:40]
        return (f"| {r.get('symbol','-')} | {r.get('timeframe','-')} | {r.get('profile','-')} "
                f"| FAILED ({err}) | - | - | - | - | - | - | - | - |")
    return (f"| {r['symbol']} | {r['timeframe']} | {r['profile']} | {r['n_trades']} "
            f"| {getattr(m, 'sharpe', 0.0):.3f} | {getattr(m, 'sortino', 0.0):.3f} "
            f"| {getattr(m, 'max_drawdown_pct', 0.0):.2f} | {getattr(m, 'hit_rate', 0.0):.3f} "
            f"| {getattr(m, 'expectancy_usd', 0.0):.2f} | {getattr(m, 'profit_factor', 0.0):.2f} "
            f"| {getattr(m, 'avg_r', 0.0):.2f} | {getattr(m, 'longest_dd_days', 0.0):.1f} |")


def _per_slice_section(r: dict) -> str:
    """Mini-section per-slice (D-18 part 3).

    Include: header con run_id, link equity PNG, n_trades, n_drafts emitted.
    Per result FAILED, mostra solo lo status + error message.
    """
    if r.get("status") != "OK":
        return f"### {r['run_id']}\n\nStatus: **FAILED** — {r.get('error', '')}\n"
    lines = [
        f"### {r['run_id']}",
        f"- Equity curve: ![equity]({r.get('equity_path', '')})",
        f"- Trades: {r['n_trades']}",
        f"- Drafts emitted: {r.get('n_drafts', 0)}",
    ]
    return "\n".join(lines) + "\n"


def write_baseline_report(results: list[dict], out_path: Path, meta: dict) -> None:
    """Compone `.planning/research/baseline-{date}.md` (D-18, INT-01).

    Args:
        results: lista di result dict prodotti da slice_worker.run_slice_3profiles.
            Schema atteso per ogni elemento (D-13/D-15/D-18):
              - run_id (str): `baseline_{date}_{symbol}_{tf}_{profile}`
              - symbol, timeframe, profile (str)
              - status (str): "OK" | "SKIPPED" | "FAILED"
              - metrics (BacktestMetrics dataclass | None): None se non OK
              - n_trades, n_drafts (int)
              - equity_path (str): path relativo al PNG equity
              - error (str | None): popolato solo se status="FAILED"

        out_path: path destinazione (es. `.planning/research/baseline-2026-05-08.md`).
            Se la parent dir non esiste, viene creata.

        meta: dict con metadata audit per header + appendix.
            Keys richiesti:
              - cli_command (str)
              - git_sha (str)
              - total_wall_clock_seconds (float)
              - cost_yaml_sha256 (str): FULL 64-char hex (WARNING 12 fix)
              - strategy_yaml_sha256 (str): FULL 64-char hex (WARNING 12 fix)
              - baseline_yaml_sha256 (str): FULL 64-char hex (WARNING 12 fix)
              - slippage_seed (int): seed lockato da baseline.yaml (D-17)
              - warm_up_bars (dict[str, int]): mappa tf → warm-up effettivo
              - longest_lookback (int): max lookback usato (BLOCKER 3 D-07)
              - decision_count (int): totale decision rows scritte
              - min_decisions_hard (int): hard gate SC#3 BLOCKER 2
              - target_decisions_soft (int): soft target SC#3 BLOCKER 2

    Side effects:
        - Crea out_path.parent (mkdir parents=True, exist_ok=True)
        - Scrive il file MD UTF-8
        - Log info con path + size finale
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Conteggi per header (n_ok + n_failed + n_skipped vs n_total).
    n_total = len(results)
    n_ok = sum(1 for r in results if r.get("status") == "OK")
    n_failed = sum(1 for r in results if r.get("status") == "FAILED")
    n_skipped = sum(1 for r in results if r.get("status") == "SKIPPED")

    lines: list[str] = []

    # ─── D-18 part 1: Header ────────────────────────────────────────────────
    lines.append("## Header\n")
    # Timezone-aware UTC (datetime.utcnow() deprecato in Python 3.12+).
    lines.append(f"- **Data run**: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- **Comando CLI**: `{meta.get('cli_command', 'n/a')}`")
    lines.append(f"- **git_sha**: `{meta.get('git_sha', 'unknown')}`")
    lines.append(f"- **Total wall-clock**: {meta.get('total_wall_clock_seconds', 0):.1f}s")
    lines.append(
        f"- **Run completed**: {n_ok}/{n_total} (skipped: {n_skipped}, failed: {n_failed})"
    )
    lines.append("")

    # ─── D-18 part 2: Tabella 27-row metrics ────────────────────────────────
    lines.append("## Slice Metrics\n")
    lines.append(_TABLE_HEADER)
    # Ordine deterministico per leggibilità report (Claude's discretion: sym→tf→profile).
    sorted_results = sorted(
        results,
        key=lambda r: (r.get("symbol", ""), r.get("timeframe", ""), r.get("profile", "")),
    )
    for r in sorted_results:
        lines.append(_row(r))
    lines.append("")

    # ─── D-18 part 3: Per-slice mini-section ────────────────────────────────
    lines.append("## Per-slice details\n")
    for r in sorted_results:
        lines.append(_per_slice_section(r))

    # ─── D-18 part 4: Appendix (WARNING 12 fix: full 64-char sha256) ────────
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
    lines.append(
        f"- `decision_count`: {meta.get('decision_count', 'n/a')} "
        f"(hard gate ≥{meta.get('min_decisions_hard', 1000)}, "
        f"soft target ≥{meta.get('target_decisions_soft', 10000)})"
    )
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    _log.info("baseline report scritto: %s (%d byte)", out_path, out_path.stat().st_size)
