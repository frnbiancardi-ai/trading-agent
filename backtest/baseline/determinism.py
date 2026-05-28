"""Determinism helpers per baseline backtest (D-17).

Sostituisce Python `hash()` (seed Python randomizzato per processo, non riproducibile
cross-run) con `hashlib.sha256` esplicito. Espone:
  - seed_for_run_id(run_id): int 31-bit deterministico per BacktestBroker slippage RNG
  - file_sha256(path): hex digest completo per audit trail (cost.yaml, strategy.yaml,
    baseline.yaml hashes scritti in backtest_runs)
  - make_rng(run_id): np.random.Generator pre-seedato

Source: hashlib stdlib, numpy.random.default_rng. RESEARCH.md §Pitfall 1.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np


def seed_for_run_id(run_id: str) -> int:
    """31-bit seed deterministico cross-run, cross-machine.

    Usa SHA256 dei primi 4 byte → int big-endian → mask 0x7FFFFFFF (positive 31-bit).
    """
    digest = hashlib.sha256(run_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def file_sha256(path: Path) -> str:
    """Config file hash per backtest_runs audit trail (D-17).

    Hex digest completo (64 char). Letto come bytes — encoding-agnostic, line-ending
    sensible (CRLF vs LF cambia hash; gestito a CI livello).
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_rng(run_id: str) -> np.random.Generator:
    """Crea numpy Generator pre-seedato deterministicamente da run_id."""
    return np.random.default_rng(seed_for_run_id(run_id))
