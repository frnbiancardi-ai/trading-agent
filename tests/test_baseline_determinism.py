"""Tests for backtest.baseline.determinism (D-17).

Wave 1 (Plan 05-03): seed sha256 + file hashes + RNG cross-process determinism.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from backtest.baseline.determinism import file_sha256, make_rng, seed_for_run_id


def test_seed_reproducibility() -> None:
    """D-17: stesso run_id → stesso seed dentro lo stesso processo."""
    rid = "baseline_2026-05-08_EURUSD_M15_MODERATE"
    s1 = seed_for_run_id(rid)
    s2 = seed_for_run_id(rid)
    assert s1 == s2
    assert 0 <= s1 < 2**31


def test_seed_reproducibility_cross_process() -> None:
    """D-17: subprocess deve ottenere stesso seed (no PYTHONHASHSEED dependency).

    Dimostra che sha256 è deterministico cross-process — Python hash() non lo è
    perché PYTHONHASHSEED è randomizzato per processo (a meno di env override).
    """
    rid = "baseline_2026-05-08_EURUSD_M15_MODERATE"
    expected = seed_for_run_id(rid)
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backtest.baseline.determinism import seed_for_run_id; "
            f"print(seed_for_run_id('{rid}'))",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(repo_root),
    )
    child_seed = int(result.stdout.strip())
    assert child_seed == expected


def test_config_hash_matches(tmp_path: Path) -> None:
    """D-17: file_sha256 == hashlib.sha256(content).hexdigest() (full 64-char hex)."""
    path = tmp_path / "cfg.yaml"
    content = b"foo: bar\nbaz: 42\n"
    path.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert file_sha256(path) == expected
    assert len(file_sha256(path)) == 64  # SHA256 = 64 hex chars


def test_make_rng_reproducible() -> None:
    """D-17: 2 RNG dallo stesso run_id producono sequenza identica."""
    rng1 = make_rng("rid")
    rng2 = make_rng("rid")
    seq1 = [rng1.uniform(-1, 1) for _ in range(5)]
    seq2 = [rng2.uniform(-1, 1) for _ in range(5)]
    assert seq1 == seq2
