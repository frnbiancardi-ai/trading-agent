"""Equity curve PNG writer (D-19, D-20). Matplotlib Agg headless per ProcessPool.

CRITICO: matplotlib.use("Agg") DEVE precedere QUALSIASI import che catena a pyplot.
Worker spawn su Windows non eredita backend dal main -> ogni worker re-imposta.

Source: matplotlib backend docs https://matplotlib.org/stable/users/explain/figure/backends.html,
RESEARCH.md Pattern 4.
"""
from __future__ import annotations

# OBBLIGATORIO prima di import pyplot -- vale per main + worker
import matplotlib

matplotlib.use("Agg")

import logging  # noqa: E402  -- ordine import vincolato dal backend setup
from pathlib import Path  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

_log = logging.getLogger(__name__)


def plot_equity_curve(equity: pd.DataFrame, out_path: Path) -> None:
    """Render equity + drawdown 2-subplot PNG (D-19, D-20).

    equity DataFrame DEVE avere colonne:
      - timestamp (datetime/iso)
      - equity_eur (float)
      - drawdown_pct (float, <= 0)

    Output: PNG dpi=100 figsize=(12,6). Equity steelblue lw=1; DD indianred fill alpha=0.5.

    plt.close(fig) esplicito mitiga T-05-10: senza la close esplicita matplotlib
    accumula handle leak su Windows -- 27 plot consecutivi -> exhaustion.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 6), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )
    ax1.plot(equity["timestamp"], equity["equity_eur"], color="steelblue", linewidth=1)
    ax1.set_ylabel("Equity (EUR)")
    ax1.set_title(out_path.stem.replace("_", " "))
    ax1.grid(True, alpha=0.3)

    ax2.fill_between(
        equity["timestamp"], equity["drawdown_pct"], 0,
        color="indianred", alpha=0.5,
    )
    ax2.set_ylabel("DD %")
    ax2.set_xlabel("Date")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)  # CRITICO -- libera memoria, evita Windows handle leak su 27 plot
    _log.debug("plot_equity_curve: scritto %s", out_path)
