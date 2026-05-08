"""Tests for backtest.baseline.determinism (D-17 seed + config hashes).

Wave 0 stub: scaffolding test-first. Sblocco al Plan 05-03 (determinism module).
VALIDATION.md row D-17: NO Python builtin hash() (cross-process non-deterministico) —
deve usare hashlib.sha256(run_id) per slippage_seed_effective.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.skip(reason="Wave 1: 05-03 implementa determinism.seed_for_run_id")
def test_seed_reproducibility() -> None:
    """D-17: `seed_for_run_id("baseline_2026-05-08_EURUSD_M15_MODERATE")` chiamato 2× → identico."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-03 implementa determinism.seed_for_run_id")
def test_seed_reproducibility_cross_process(tmp_path: Path) -> None:
    """D-17: subprocess `.venv\\Scripts\\python.exe -c "..."` produce identico digest cross-process.

    Verifica che il seed NON dipenda da `PYTHONHASHSEED` (che cambia per processo).
    """
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-03 implementa determinism.file_sha256")
def test_config_hash_matches(tmp_path: Path) -> None:
    """D-17: file_sha256(path) == hashlib.sha256(content).hexdigest() su costs/strategy/baseline.yaml."""
    raise NotImplementedError
