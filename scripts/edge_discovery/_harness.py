"""Edge-discovery harness (research, 2026-05-29).

Misura il FORWARD RETURN di segnali atomici — NON è un backtest (niente SL/TP/sizing).
Domanda: "quando succede X, il prezzo nei prossimi h bar si muove in direzione D
più di quanto spiegherebbe il caso?"

ANTI-LEAKAGE (assoluto): le feature sono calcolate in modo CAUSALE (rolling trailing,
features[i] dipende solo da bars[:i+1]); un signal_fn vede SOLO features all'indice i;
il forward return usa close[i+h] ma è l'OUTCOME, mai un input del segnale. Guard runtime
in `assert_causal_features`. Inoltre `random_signal` DEVE dare hit~50% / t~0 (sanity).

Riusa backtest.loader.load_bars (Bar: time, open, high, low, close, volume, symbol, tf).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Features:
    """Array allineati 1:1 ai bar, tutti CAUSALI (index i usa solo dati ≤ i)."""
    time: np.ndarray        # unix UTC seconds (bar OPEN time)
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    ema20: np.ndarray       # EMA20 causale
    atr14: np.ndarray       # ATR(14) causale (rolling mean del true range)
    atr_pctile: np.ndarray  # rank percentile di atr14 nella finestra trailing 200 (0..1), NaN in warmup
    bb_upper: np.ndarray    # SMA20 + 2*std20 (causale)
    bb_lower: np.ndarray
    consec: np.ndarray      # +k se k barre consecutive up, -k se down (close vs close prev)
    hour: np.ndarray        # ora UTC del bar (0..23)
    weekday: np.ndarray     # giorno settimana UTC (0=lun .. 6=dom) — per flat-by-friday
    rv_short: np.ndarray    # realized vol = std log-return 20 bar (causale), NaN in warmup
    rv_long: np.ndarray     # media 100-bar di rv_short (causale) — baseline per vol-spike


def _ema(x: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1.0)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out


def _atr(high, low, close, period=14) -> np.ndarray:
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    out = np.full(n, np.nan)
    # rolling mean causale del TR
    csum = np.cumsum(tr)
    for i in range(period - 1, n):
        s = csum[i] - (csum[i - period] if i - period >= 0 else 0.0)
        out[i] = s / period
    return out


def _atr_pctile(atr: np.ndarray, window=200) -> np.ndarray:
    n = len(atr)
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        w = atr[i - window + 1 : i + 1]
        if np.isnan(w).any():
            continue
        cur = atr[i]
        out[i] = np.sum(w <= cur) / window  # rank trailing, MAI globale (no leakage)
    return out


def _bollinger(close: np.ndarray, length=20, mult=2.0):
    n = len(close)
    up = np.full(n, np.nan)
    lo = np.full(n, np.nan)
    for i in range(length - 1, n):
        w = close[i - length + 1 : i + 1]
        m = w.mean()
        s = w.std(ddof=0)
        up[i] = m + mult * s
        lo[i] = m - mult * s
    return up, lo


def _consecutive(close: np.ndarray) -> np.ndarray:
    n = len(close)
    out = np.zeros(n)
    for i in range(1, n):
        d = close[i] - close[i - 1]
        if d > 0:
            out[i] = out[i - 1] + 1 if out[i - 1] > 0 else 1
        elif d < 0:
            out[i] = out[i - 1] - 1 if out[i - 1] < 0 else -1
        else:
            out[i] = 0
    return out


def _realized_vol(close: np.ndarray, short=20, long=100):
    """rv_short = std rolling dei log-return (short bar); rv_long = media rolling
    (long bar) di rv_short. Entrambi causali (solo dati ≤ i). NaN in warmup."""
    n = len(close)
    logret = np.zeros(n)
    logret[1:] = np.log(close[1:] / close[:-1])
    rv_s = np.full(n, np.nan)
    for i in range(short, n):
        rv_s[i] = logret[i - short + 1 : i + 1].std(ddof=0)
    rv_l = np.full(n, np.nan)
    for i in range(short + long, n):
        w = rv_s[i - long + 1 : i + 1]
        if not np.isnan(w).any():
            rv_l[i] = w.mean()
    return rv_s, rv_l


def _weekday(t: np.ndarray) -> np.ndarray:
    # 1970-01-01 (unix 0) era un giovedì (weekday=3). days_since_epoch + 3 mod 7.
    days = (t // 86400)
    return ((days + 3) % 7).astype(int)


def compute_features(bars: list) -> Features:
    close = np.array([b.close for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)
    low = np.array([b.low for b in bars], dtype=float)
    openp = np.array([b.open for b in bars], dtype=float)
    t = np.array([int(b.time) for b in bars], dtype=np.int64)
    atr = _atr(high, low, close, 14)
    bbu, bbl = _bollinger(close, 20, 2.0)
    rv_s, rv_l = _realized_vol(close, 20, 100)
    return Features(
        time=t, open=openp, high=high, low=low, close=close,
        ema20=_ema(close, 20), atr14=atr, atr_pctile=_atr_pctile(atr, 200),
        bb_upper=bbu, bb_lower=bbl, consec=_consecutive(close),
        hour=((t // 3600) % 24).astype(int), weekday=_weekday(t),
        rv_short=rv_s, rv_long=rv_l,
    )


def assert_causal_features(bars: list, features: Features, probe_idx=None) -> None:
    """Guard: ricalcolando le feature su bars[:k+1], il valore al last index deve
    coincidere con features[k] calcolato sul full array → causalità (no future leak).
    Verifica su un paio di indici sonda (EMA20 e ATR14, sensibili al passato).
    """
    n = len(bars)
    probes = probe_idx or [n // 3, 2 * n // 3]
    for k in probes:
        if k < 250 or k >= n:
            continue
        sub = compute_features(bars[: k + 1])
        for name in ("ema20", "atr14"):
            full_v = getattr(features, name)[k]
            sub_v = getattr(sub, name)[-1]
            if not (math.isnan(full_v) and math.isnan(sub_v)):
                assert abs(full_v - sub_v) < 1e-9, (
                    f"LEAKAGE: {name}[{k}] full={full_v} != prefix={sub_v}"
                )


def evaluate_signal(features: Features, signal_fn, horizon: int,
                    cost_pips: float, pip_size: float,
                    lo: int = 250, hi: int | None = None) -> dict:
    """Forward return netto a `horizon` bar dei segnali emessi in [lo, hi).

    signal_fn(features, i) -> +1 (long) / -1 (short) / 0 (no-trade), usa SOLO index ≤ i.
    ret_pips = side * (close[i+h]-close[i])/pip_size - cost_pips.
    """
    close = features.close
    n = len(close)
    hi = (n - horizon) if hi is None else min(hi, n - horizon)
    rets = []
    longs = shorts = 0
    for i in range(lo, hi):
        s = signal_fn(features, i)
        if s == 0:
            continue
        fwd_pips = (close[i + horizon] - close[i]) / pip_size
        r = s * fwd_pips - cost_pips
        rets.append(r)
        if s > 0:
            longs += 1
        else:
            shorts += 1
    a = np.array(rets, dtype=float)
    nsig = len(a)
    if nsig < 2:
        return {"n_signals": nsig, "hit_rate": None, "mean_pips": None,
                "median_pips": None, "t_stat": None, "sharpe": None,
                "longs": longs, "shorts": shorts}
    mean = float(a.mean())
    std = float(a.std(ddof=1))
    t_stat = mean / (std / math.sqrt(nsig)) if std > 0 else 0.0
    return {
        "n_signals": nsig,
        "hit_rate": round(100 * float((a > 0).mean()), 1),
        "mean_pips": round(mean, 3),
        "median_pips": round(float(np.median(a)), 3),
        "t_stat": round(t_stat, 2),
        "sharpe": round(mean / std, 4) if std > 0 else 0.0,
        "longs": longs, "shorts": shorts,
    }


def evaluate_signal_intraday(features: Features, signal_fn, max_horizon: int,
                             cost_pips: float, pip_size: float,
                             lo: int = 250, hi: int | None = None,
                             rollover_hour: int = 22, friday_cutoff_hour: int = 20,
                             overnight: bool = False, swap_pips_per_night: float = 0.75) -> dict:
    """Forward return con chiusura forzata intraday (vincolo NO-overnight / flat-by-friday).

    Entra al bar i (close). Esce al PRIMO fra:
      - i + max_horizon
      - (se NOT overnight) primo bar j>i con hour>=rollover_hour, oppure venerdì hour>=friday_cutoff_hour
    Skip entry se fired dentro la finestra di rollover (hour>=rollover_hour) o venerdì
    dopo il cutoff → nessun trade intraday possibile.

    overnight=True: ignora i cutoff (horizon pieno) ma sottrae swap_pips_per_night ×
    notti UTC attraversate (stima conservativa del costo overnight).

    Anti-leakage invariato: signal_fn vede solo ≤ i; l'uscita è OUTCOME, non input.
    """
    close, hour, wd, t = features.close, features.hour, features.weekday, features.time
    n = len(close)
    hi = (n - 1) if hi is None else min(hi, n - 1)
    rets, held, nights_list = [], [], []
    longs = shorts = skipped_window = 0
    for i in range(lo, hi):
        s = signal_fn(features, i)
        if s == 0:
            continue
        if not overnight:
            # niente entry nella finestra non-tradeable (chiuderebbe subito / overnight)
            if hour[i] >= rollover_hour or (wd[i] == 4 and hour[i] >= friday_cutoff_hour):
                skipped_window += 1
                continue
        exit_idx = min(i + max_horizon, n - 1)
        if not overnight:
            j = i + 1
            while j <= exit_idx:
                if hour[j] >= rollover_hour or (wd[j] == 4 and hour[j] >= friday_cutoff_hour):
                    exit_idx = j
                    break
                j += 1
        nights = int(t[exit_idx] // 86400 - t[i] // 86400)  # midnights UTC attraversati
        fwd_pips = (close[exit_idx] - close[i]) / pip_size
        r = s * fwd_pips - cost_pips
        if overnight and nights > 0:
            r -= swap_pips_per_night * nights
        rets.append(r); held.append(exit_idx - i); nights_list.append(nights)
        if s > 0:
            longs += 1
        else:
            shorts += 1
    a = np.array(rets, dtype=float)
    nsig = len(a)
    if nsig < 2:
        return {"n_signals": nsig, "hit_rate": None, "mean_pips": None, "median_pips": None,
                "t_stat": None, "sharpe": None, "bars_held_median": None,
                "nights_median": None, "longs": longs, "shorts": shorts,
                "skipped_window": skipped_window}
    mean = float(a.mean()); std = float(a.std(ddof=1))
    return {
        "n_signals": nsig,
        "hit_rate": round(100 * float((a > 0).mean()), 1),
        "mean_pips": round(mean, 3),
        "median_pips": round(float(np.median(a)), 3),
        "t_stat": round(mean / (std / math.sqrt(nsig)), 2) if std > 0 else 0.0,
        "sharpe": round(mean / std, 4) if std > 0 else 0.0,
        "bars_held_median": float(np.median(held)),
        "nights_median": float(np.median(nights_list)),
        "longs": longs, "shorts": shorts, "skipped_window": skipped_window,
    }


def date_index_range(features: Features, start_iso: str, end_iso: str) -> tuple[int, int]:
    """[lo, hi) indici dei bar con start <= bar.time < end (date ISO 'YYYY-MM-DD' UTC)."""
    import datetime as _dt
    lo_ts = int(_dt.datetime.fromisoformat(start_iso).replace(tzinfo=_dt.timezone.utc).timestamp())
    hi_ts = int(_dt.datetime.fromisoformat(end_iso).replace(tzinfo=_dt.timezone.utc).timestamp())
    t = features.time
    idx = np.where((t >= lo_ts) & (t < hi_ts))[0]
    if len(idx) == 0:
        return (0, 0)
    return (int(idx[0]), int(idx[-1]) + 1)


def year_index_range(features: Features, year: int) -> tuple[int, int]:
    """[lo, hi) indici dei bar il cui anno UTC == year (bar.time)."""
    import datetime as _dt
    lo_ts = int(_dt.datetime(year, 1, 1, tzinfo=_dt.timezone.utc).timestamp())
    hi_ts = int(_dt.datetime(year + 1, 1, 1, tzinfo=_dt.timezone.utc).timestamp())
    t = features.time
    idx = np.where((t >= lo_ts) & (t < hi_ts))[0]
    if len(idx) == 0:
        return (0, 0)
    return (int(idx[0]), int(idx[-1]) + 1)
