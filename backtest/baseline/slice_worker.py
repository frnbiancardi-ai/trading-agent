"""Worker per-slice per ProcessPoolExecutor (Phase 5 D-15).

Ogni worker carica CSV, calcola warm-up adattivo (D-07 BLOCKER 3), calcola indicator
cache UNA volta, gira 3 profile sequenziali riusando cache. Idempotency D-14: skip se
run_id esiste, --force pulisce prima.

CRITICO: il backend Agg di matplotlib DEVE precedere QUALSIASI import che catena a pyplot.
Su Windows spawn ctx, il backend non si propaga dal main → re-set qui.

Source: PATTERNS.md §slice_worker.py, CONTEXT.md §specifics.
"""
from __future__ import annotations

# CRITICO: backend Agg PRIMA di import indiretti pyplot
import matplotlib

matplotlib.use("Agg")

import functools  # noqa: E402  -- ordine import vincolato dal backend setup
import logging  # noqa: E402
import sqlite3  # noqa: E402
import subprocess  # noqa: E402
from datetime import date  # noqa: E402
from pathlib import Path  # noqa: E402

from backtest.loader import load_bars  # noqa: E402
from backtest.costs import load_cost_model  # noqa: E402
from backtest.ledger import LedgerWriter  # noqa: E402
from backtest.engine import BacktestEngine  # noqa: E402
from backtest.baseline.determinism import seed_for_run_id, file_sha256  # noqa: E402
from backtest.baseline.dataset_writer import (  # noqa: E402
    write_decisions_shard,
    write_drafts_shard,
)
from backtest.baseline.plot_writer import plot_equity_curve  # noqa: E402
from backtest.baseline.wal_setup import with_retry  # noqa: E402
from backtest.baseline.warmup import longest_lookback_required  # noqa: E402  -- BLOCKER 3 D-07

_log = logging.getLogger(__name__)

PROFILES = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")


# ─── Plan 05-09 — extended snapshot @ bar idx-1 (D-09-A/B + FIX 1/4/9 + FIX D iter 3) ───
#
# Helper modulo-level introdotti dal Plan 05-09 per arricchire le decisions_rows
# con uno snapshot di indicatori extended calcolato SU bars_dict[:idx] (esclusivo
# del bar di entry — no-leakage by construction D-09-B). Usati solo nel ciclo
# `for profile in PROFILES` post-engine.run().
#
# Isolamento FIX D iter 3: questi helper sono gli UNICI consumer di `regime_cfg`
# per-symbol. La chiamata top-level `compute_all_extended(bars_dict)` (linea ~270)
# resta SENZA regime_cfg — preserva esatta parity con Plan 05-08 sul detector
# flow (count trade atteso == 1076 ± 0).


def _build_bars_index_by_time(bars_dict: list[dict]) -> dict[int, int]:
    """Pre-computa mapping `{bar.time: idx}` per lookup O(1) post-engine.

    Plan 05-09 Task 2: i trade ledger row hanno `entry_time` come stringa
    ISO8601; per ricavare l'indice nel bars_dict basta passare per
    `int(datetime.fromisoformat(...).timestamp())` e fare lookup in questo
    dict. Pre-computato UNA volta per slice (3 profile lo condividono).
    """
    return {bar["time"]: idx for idx, bar in enumerate(bars_dict)}


def _extract_extended_snapshot_at_entry(
    bars_dict: list[dict],
    bars_idx_by_time: dict[int, int],
    entry_time_iso: str,
    regime_cfg: dict | None,
) -> dict:
    """D-09-B: snapshot extended al bar PRIMA del entry (no-leakage by construction).

    bars_view = bars_dict[:idx] e' EXCLUSIVE di bars_dict[idx], cioe' il
    bar di entry NON entra nel calcolo. Replica le condizioni live: la
    strategy decide all'open di una nuova barra basandosi sulla history
    conclusa.

    FIX D iter 3 — isolamento: questa funzione e' L'UNICO consumer di
    `regime_cfg` per-symbol. La chiamata top-level
    `compute_all_extended(bars_dict)` a `slice_worker.py:~270` resta
    senza regime_cfg, preservando parity con Plan 05-08 sul detector.

    Pattern: `bars_view = bars_dict[:idx]` (chiavata da key_links regex,
    FIX 8 plan-checker iter 1).

    Edge cases:
      - entry_ts_iso non in bars_idx_by_time -> dict vuoto (defensive)
      - idx == 0 (entry al primo bar post-warmup, impossibile in pratica)
        -> dict vuoto (no leakage residuo)
      - bars_view vuoto -> dict vuoto
    """
    # Lazy import per evitare cost top-level (matplotlib backend gia' settato).
    from datetime import datetime, timezone

    # Converti ISO -> unix int (compatibile con bars_dict[i]["time"]).
    # entry_time_iso e' formato `datetime.fromtimestamp(...).isoformat()`
    # (vedi engine._iso linea 75-76 — output `datetime.isoformat()` UTC-aware).
    dt = datetime.fromisoformat(entry_time_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    entry_ts = int(dt.timestamp())
    idx = bars_idx_by_time.get(entry_ts)
    if idx is None or idx == 0:
        # Edge: entry_time non in cache (NON dovrebbe succedere: engine
        # itera sugli stessi bars) oppure entry al primo bar (impossibile
        # post-warmup ma defensive). Ritorna dict vuoto -> writer
        # produrra' NaN nelle colonne extended.
        return {}
    # No-leakage: vista fino a (exclusive) idx — variabile esplicita
    # `bars_view` per key_links regex (FIX 8).
    bars_view = bars_dict[:idx]
    if not bars_view:
        return {}
    from indicators import compute_all_extended  # lazy import Phase 2 dep
    snapshot = compute_all_extended(bars_view, regime_cfg=regime_cfg)
    return snapshot


def _build_run_id(symbol: str, tf: str, profile: str, run_date: str | None = None) -> str:
    """D-13: run_id = baseline_{date}_{symbol}_{tf}_{profile}."""
    d = run_date or date.today().isoformat()
    return f"baseline_{d}_{symbol}_{tf}_{profile}"


def _run_id_exists(db_path: Path, run_id: str) -> bool:
    """Check idempotency D-14 — esiste già un run con questo run_id?"""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM backtest_runs WHERE run_id=?", (run_id,)
        ).fetchone()
    return row is not None


def _force_clear_run(db_path: Path, run_id: str) -> None:
    """RESEARCH §Pitfall: AUTOINCREMENT su backtest_trades duplica righe in --force.

    DELETE FROM backtest_trades + backtest_runs PRIMA di re-insert. Single connection
    con busy_timeout — WARNING 8 fix: non wrappare con `with_retry` (riapre conn ogni
    retry); usa busy_timeout built-in.
    """
    # WARNING 8 fix: single connection, busy_timeout, no with_retry wrapper.
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("DELETE FROM backtest_trades WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM backtest_runs WHERE run_id=?", (run_id,))
        conn.commit()
    finally:
        conn.close()


def _git_sha() -> str:
    """Best-effort git rev-parse HEAD per audit trail (D-17)."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(Path(__file__).resolve().parents[2]),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:  # noqa: BLE001 -- best-effort, no propagation
        return "unknown"


def _build_equity_dataframe(
    balances: list[float],
    trades: list[dict],
    initial_eur: float,
    bars: list,
):
    """Bridge format mismatch (Plan 05-08 deviation Rule 3 — Blocker).

    engine.run() ritorna `equity_curve: list[float]` (1 sample iniziale +
    1 sample dopo ogni evento di chiusura: SL, TP, timeout, end). Niente
    timestamp né drawdown. plot_writer.plot_equity_curve attende un
    `pd.DataFrame` con colonne `timestamp`, `equity_eur`, `drawdown_pct`.

    Strategia di mapping:
      - balance[0] = initial_eur → timestamp = bars[0].time (warm-up gia
        applicato dal caller, primo bar utile post-warm-up).
      - balance[k] = post-evento k → timestamp = trade[k-1].exit_time
        (ISO 8601 stringa da `_row_for_ledger`).
      - drawdown_pct[t] = (eq[t] - peak[t]) / peak[t] * 100  (≤ 0).

    Edge cases:
      - balances vuoto → DataFrame vuoto (caller logga warning + skip plot).
      - trade meno di balances - 1 → trunca al min(len(balances), len(trades)+1).
      - peak iniziale = initial_eur (no division-by-zero se balance[0]=0).
    """
    import pandas as pd  # noqa: E402 -- lazy import, dep solo quando si plotta
    from datetime import datetime, timezone  # noqa: E402

    if not balances:
        return pd.DataFrame({"timestamp": [], "equity_eur": [], "drawdown_pct": []})

    # Costruisci timestamp allineati a balances.
    timestamps: list[datetime] = []
    # Primo punto: usa il time del primo bar processato come anchor.
    if bars:
        timestamps.append(datetime.fromtimestamp(int(bars[0].time), tz=timezone.utc))
    else:
        timestamps.append(datetime.now(timezone.utc))

    for t in trades:
        ts_iso = t.get("exit_time") or t.get("entry_time")
        if ts_iso is None:
            timestamps.append(timestamps[-1])  # carry forward
            continue
        try:
            timestamps.append(datetime.fromisoformat(str(ts_iso)))
        except (TypeError, ValueError):
            timestamps.append(timestamps[-1])

    n = min(len(timestamps), len(balances))
    timestamps = timestamps[:n]
    balances = list(balances[:n])

    # Drawdown running peak (peak iniziale = max(balance[0], initial_eur)).
    peak = max(balances[0], float(initial_eur))
    drawdowns: list[float] = []
    for b in balances:
        if b > peak:
            peak = b
        dd = ((b - peak) / peak * 100.0) if peak > 0 else 0.0
        drawdowns.append(dd)

    return pd.DataFrame({
        "timestamp": timestamps,
        "equity_eur": balances,
        "drawdown_pct": drawdowns,
    })


def _audit_update_run(
    db_path: Path,
    run_id: str,
    seed_eff: int,
    cost_sha256: str,
    strategy_sha256: str,
    baseline_sha256: str,
    git: str,
) -> None:
    """Update backtest_runs con audit trail Phase 5 (D-17 + WARNING 12 sha256 full-64).

    WARNING 7 fix: helper esplicito (NO lambda con `and conn.commit()` truthiness bug).
    Single connection con busy_timeout — il caller può wrappare con `with_retry`.
    """
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute(
            "UPDATE backtest_runs SET slippage_seed_effective=?, "
            "strategy_yaml_hash=?, baseline_yaml_hash=?, git_sha=?, "
            "cost_yaml_sha256=?, strategy_yaml_sha256=?, baseline_yaml_sha256=? "
            "WHERE run_id=?",
            (
                seed_eff,
                strategy_sha256[:16],   # legacy md5[:16]-style column
                baseline_sha256[:16],
                git,
                cost_sha256,            # Phase 5 sha256 full-64 (WARNING 12 fix)
                strategy_sha256,
                baseline_sha256,
                run_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def run_slice_3profiles(
    symbol: str,
    tf: str,
    baseline_cfg,             # BaselineConfig (frozen dataclass — Plan 05-07 definisce loader)
    costs_cfg_path: Path,     # Path al costs.yaml (load_cost_model lo richiede)
    strategy_cfg_path: Path,  # Path al strategy.yaml
    force: bool = False,
    ledger_db_path: Path | None = None,
    run_date: str | None = None,
    csv_path: Path | None = None,
) -> list[dict]:
    """Worker entry per ProcessPoolExecutor. Esegue 3 run sequenziali su (symbol, tf).

    Returns: list[dict] di 3 result, ciascuno con keys: run_id, profile, status,
    metrics, n_trades, n_drafts, equity_path, error (se status=FAILED).
    """
    ledger_db = Path(ledger_db_path) if ledger_db_path else Path("logs/trades.db")

    # 1. Load CSV (Phase 1 loader). csv_path opzionale — se None, runner lo deduce.
    if csv_path is None:
        # Convention Phase 1: data/{symbol}_{tf}.csv (placeholder; runner lo passa esplicito).
        csv_path = Path(f"data/{symbol}_{tf}.csv")
    # Plan 05-08 Option B (scope reduction 10y): filtra date_start/date_end dal
    # baseline_cfg PRIMA del warm_up slicing per evitare il full-history 23.5y
    # (engine O(N^2) → smoke fuori budget BACK-07 SC#1 <30min). load_bars
    # supporta datetime|None inclusive/exclusive (backtest/loader.py:30-31).
    from datetime import datetime  # noqa: E402 -- lazy import per evitare cost top-level
    ds = (
        datetime.fromisoformat(baseline_cfg.date_start)
        if getattr(baseline_cfg, "date_start", None) else None
    )
    de = (
        datetime.fromisoformat(baseline_cfg.date_end)
        if getattr(baseline_cfg, "date_end", None) else None
    )
    bars = load_bars(csv_path, symbol, tf, date_start=ds, date_end=de)

    # 2. Warm-up adaptive (D-07 BLOCKER 3 fix): max(warm_up_min_bars, longest_lookback)
    # Reads strategy.yaml indicator config; fallback 200 se non parseable.
    try:
        import yaml
        with open(strategy_cfg_path, encoding="utf-8") as f:
            strategy_cfg = yaml.safe_load(f) or {}
    except Exception:  # noqa: BLE001
        strategy_cfg = {}
    warm_up = max(
        baseline_cfg.warm_up_min_bars,
        longest_lookback_required(strategy_cfg),
    )
    bars = bars[warm_up:]
    _log.info(
        "slice %s %s warm_up=%d (cfg=%d, longest_lookback=%d)",
        symbol, tf, warm_up, baseline_cfg.warm_up_min_bars,
        longest_lookback_required(strategy_cfg),
    )

    # 3. Indicator cache UNA volta per slice (D-15)
    # Plan 05-08 deviation Rule 3 — Blocker: indicators.compute_all_extended
    # accetta list[dict] (Phase 2 API reale, indicators/aggregate.py:68
    # accede `b["close"]`), MA backtest.engine.BacktestEngine accetta
    # list[Bar] (dataclass). Convertiamo Bar->dict SOLO per il calcolo
    # indicatori, lasciando bars come list[Bar] per il resto del worker.
    from indicators import compute_all_extended  # noqa: E402  -- lazy import Phase 2 dep
    bars_dict = [
        {
            "time": b.time,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ]
    indicators_full = compute_all_extended(bars_dict)

    # Plan 05-09 D-09-A/B + FIX 1 + FIX D iter 3 — isolamento regime_cfg:
    # carica regime_cfg PER-SYMBOL una volta (cache locale, scope worker).
    # I 3 profile sequenziali nello stesso worker condividono questo dict
    # (immutable, safe da riusare).
    #
    # FIX D iter 3 ISOLAMENTO: regime_cfg viene caricato qui ma usato
    # SOLO dentro `_extract_extended_snapshot_at_entry` (post-engine
    # enrichment). La chiamata `compute_all_extended(bars_dict)` di sopra
    # NON riceve regime_cfg, preservando esatta parity con Plan 05-08
    # sul flow strategy detector -> proposal -> trade generation.
    # Count trade atteso == 1076 ± 0 (invariante).
    from indicators.volatility import load_regime_config  # noqa: E402 — lazy
    regime_cfg = load_regime_config(symbol, Path("data/configs/regime.yaml"))

    # Pre-computa lookup O(1) `{bar.time: idx}` per snapshot post-engine
    # (Task 2 Plan 05-09). 3 profile lo condividono.
    bars_idx_by_time = _build_bars_index_by_time(bars_dict)

    # 4. Cost model (Phase 1 contract richiede entry_price per pip-value JPY)
    entry_price_hint = float(bars[0].close) if bars else 1.0
    cost = load_cost_model(symbol, entry_price_hint, costs_cfg_path)

    # 5. Hashes audit trail (D-17 + WARNING 12 fix: full 64-char sha256)
    cost_sha256 = file_sha256(Path(costs_cfg_path))
    strategy_sha256 = file_sha256(strategy_cfg_path)
    baseline_sha256 = file_sha256(Path("data/configs/baseline.yaml"))
    git = _git_sha()

    results: list[dict] = []
    timeout = baseline_cfg.timeout_bars[tf]  # D-05 per-TF cap

    for profile in PROFILES:
        run_id = _build_run_id(symbol, tf, profile, run_date)

        # Idempotency D-14
        if _run_id_exists(ledger_db, run_id):
            if not force:
                _log.warning(
                    "skip %s: già esistente, usa --force per overwrite", run_id,
                )
                results.append({
                    "run_id": run_id,
                    "profile": profile,
                    "symbol": symbol,
                    "timeframe": tf,
                    "status": "SKIPPED",
                })
                continue
            _log.info("force: pulisco run_id %s prima di re-insert", run_id)
            # WARNING 8 fix: NO with_retry wrapper — _force_clear_run ha busy_timeout interno.
            _force_clear_run(ledger_db, run_id)

        try:
            seed_eff = seed_for_run_id(run_id)
            ledger = LedgerWriter(ledger_db)
            engine = BacktestEngine(
                bars=bars,
                symbol=symbol,
                timeframe=tf,
                cost_model=cost,
                initial_balance=baseline_cfg.equity_initial_eur,
                run_id=run_id,
                ledger=ledger,
                cost_yaml_hash=cost_sha256[:16],  # legacy md5[:16]-style backwards compat Phase 1
                indicators_full=indicators_full,
                risk_profile=profile,
                timeout_bars=timeout,
                equity_initial=baseline_cfg.equity_initial_eur,
            )
            engine_result = engine.run()

            # Plan 05-08 deviation Rule 3 — Blocker: D-21 contract gap fra
            # engine.run() (Phase 1, plan 01-05) e slice_worker (Phase 5,
            # plan 05-06a). Engine ritorna {run_id, trades, equity_curve,
            # bars_processed}; slice_worker assumeva chiavi `decisions_rows`
            # / `drafts_rows` / `metrics` mai prodotte. Bridge in-worker:
            #
            #   decisions_rows ← engine_result["trades"] (1-1 mapping
            #     per trade chiuso registrato a ledger; D-01/D-02 schema OK).
            #   drafts_rows ← [] (DEFERRED a plan 05-09: engine non cattura
            #     drafts FORMING/NONE; richiede hook in engine.run() per
            #     persistere ogni proposta strategy. Phase 7 ML failure
            #     analysis avrà dataset parziale finché non chiuso).
            #   metrics ← compute_metrics(trades, tf) — calcolo locale.
            shard_dir = Path(baseline_cfg.training_data_dir)
            trades = engine_result.get("trades", []) or []

            # Plan 05-09 Task 2 (D-09-A + D-09-B + FIX 1/4/9 + FIX C/D iter 3):
            # arricchisci ogni trade con:
            #   - 5 meta/timestamps: profile, run_id, decision_ts_utc (bar idx-1 open),
            #     entry_ts_utc (bar idx open), exit_ts_utc (variable per exit_reason)
            #   - 33 indicator extended cols (compute_all_extended @ bars_view = bars_dict[:idx])
            # Mutate in-place per evitare duplicazione lista.
            #
            # FIX C iter 3 — anchor conservativa vs D-22:
            # - decision_ts_utc = open del bar idx-1 (1 bar PRE-entry in convenzione
            #   MT5 bar.time = bar OPEN). PIU' conservativa di D-22 stretta che
            #   richiederebbe close di idx-1 == open di idx == entry_ts (gap=0).
            #   Razionale: 1 bar di safety buffer al feature snapshot Phase 7.
            # - entry_ts_utc = open del bar di entry (idx) — gia' calcolato da engine
            # - exit_ts_utc = exit timestamp (variable per exit_reason)
            # Phase 7 walk-forward split usa decision_ts_utc (NON entry_ts_utc).
            # Gap atteso = timeframe_delta (15min M15, 30min M30, 60min H1).
            from datetime import datetime, timezone  # noqa: E402 — lazy
            for trade in trades:
                entry_iso = trade.get("entry_time")
                if not entry_iso:
                    continue  # defensive: trade senza entry_time non puo' essere snapshotato
                snapshot = _extract_extended_snapshot_at_entry(
                    bars_dict, bars_idx_by_time, entry_iso, regime_cfg,
                )
                # Calcolo decision_ts_utc (anchor conservativa D-09-B)
                dt_e = datetime.fromisoformat(entry_iso)
                if dt_e.tzinfo is None:
                    dt_e = dt_e.replace(tzinfo=timezone.utc)
                entry_ts_unix = int(dt_e.timestamp())
                idx_entry = bars_idx_by_time.get(entry_ts_unix)
                if idx_entry is not None and idx_entry >= 1:
                    # Bar idx-1 open = decision timestamp (anchor conservativa)
                    decision_ts_unix = bars_dict[idx_entry - 1]["time"]
                    decision_ts_iso = datetime.fromtimestamp(
                        decision_ts_unix, tz=timezone.utc,
                    ).isoformat()
                else:
                    # Edge defensivo: impossibile post-warmup. Fallback su entry_iso
                    # (test invariant catchera' se accade in pratica).
                    decision_ts_iso = entry_iso
                # 5 meta/timestamps (D-09-A + FIX 4 + FIX 9)
                trade["run_id"] = run_id
                trade["profile"] = profile
                trade["decision_ts_utc"] = decision_ts_iso  # bar idx-1 open (anchor conservativa)
                trade["entry_ts_utc"] = entry_iso             # bar idx open (engine row)
                trade["exit_ts_utc"] = trade.get("exit_time")  # exit timestamp (variable)
                # FIX 9: NO alias `regime` (deduplicate). Solo `regime_state` canonical
                # name (gia' presente in snapshot da compute_all_extended). setdefault
                # garantisce che se snapshot e' vuoto (edge) NON soprascriva con None.
                if "regime_state" not in trade and snapshot:
                    trade["regime_state"] = snapshot.get("regime_state")
                # Merge snapshot completo (le 33+ keys); setdefault evita override
                # di keys gia' presenti nel _row_for_ledger (paranoia: al momento
                # NON ci sono collisioni — engine usa entry_time/exit_price/ecc.,
                # disjoint dalle keys di compute_all_extended).
                for k, v in snapshot.items():
                    trade.setdefault(k, v)

            decisions_rows = trades  # mutate in-place; reference per chiarezza nominale
            drafts_rows: list[dict] = []  # DEFERRED — vedi sopra

            # Lazy import per evitare cost top-level (metrics dep solo qui).
            from backtest.metrics import compute_metrics  # noqa: E402
            metrics_obj = compute_metrics(trades, tf)
            n_trades = len(decisions_rows)
            n_drafts = len(drafts_rows)
            write_decisions_shard(decisions_rows, run_id, shard_dir)
            write_drafts_shard(drafts_rows, run_id, shard_dir)

            # Plot equity (D-19) — bridge format mismatch.
            # engine.run() ritorna `equity_curve: list[float]` (solo balance
            # post-evento, niente timestamp/drawdown). plot_writer richiede
            # DataFrame[timestamp, equity_eur, drawdown_pct]. Costruiamo qui.
            png_path = (
                Path(baseline_cfg.equity_curves_dir)
                / f"{symbol}_{tf}_{profile}.png"
            )
            equity_df = _build_equity_dataframe(
                engine_result.get("equity_curve", []) or [],
                trades,
                baseline_cfg.equity_initial_eur,
                bars,
            )
            if not equity_df.empty:
                plot_equity_curve(equity_df, png_path)
            else:
                _log.warning(
                    "skip plot_equity_curve %s: equity_df vuoto (no trade)", run_id,
                )

            # Audit trail extra: aggiorna backtest_runs con campi Phase 5
            # WARNING 7 fix: NO lambda — uso functools.partial (no truthiness bug,
            # binding esplicito dei parametri).
            # WARNING 12 fix: scrivi sha256 FULL 64-char nelle nuove colonne; legacy
            # cost_yaml_hash mantiene formato md5[:16] per backwards compat Phase 1.
            audit_call = functools.partial(
                _audit_update_run,
                ledger_db, run_id, seed_eff,
                cost_sha256, strategy_sha256, baseline_sha256, git,
            )
            with_retry(audit_call)

            # metrics_obj è BacktestMetrics (dataclass). Convert to dict per
            # report_writer (D-18) e Phase 7 ML downstream consumability.
            from dataclasses import asdict  # noqa: E402
            metrics_dict = asdict(metrics_obj)
            results.append({
                "run_id": run_id,
                "profile": profile,
                "status": "OK",
                "metrics": metrics_dict,
                "n_trades": n_trades,
                "n_drafts": n_drafts,
                "equity_path": str(png_path),
                "symbol": symbol,
                "timeframe": tf,
            })
        except Exception as exc:  # noqa: BLE001 -- worker boundary, errori serializzabili al main
            _log.error("run_id=%s fallito: %s", run_id, exc, exc_info=True)
            results.append({
                "run_id": run_id,
                "profile": profile,
                "status": "FAILED",
                "error": str(exc),
                "symbol": symbol,
                "timeframe": tf,
            })

    return results
