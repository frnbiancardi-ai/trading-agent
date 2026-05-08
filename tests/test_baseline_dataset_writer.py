"""Tests for backtest.baseline.dataset_writer (D-01, D-02, D-03).

Wave 0 stub: scaffolding test-first. Sblocco al Plan 05-04 (dataset writer + parquet).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd  # noqa: F401 — usato post-skip-removal
import pytest


@pytest.mark.skip(reason="Wave 1: 05-04 implementa dataset_writer")
def test_decisions_shard_round_trip(tmp_path: Path) -> None:
    """D-01: round-trip write_decisions_shard → pd.read_parquet conserva schema."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-04 implementa dataset_writer")
def test_decisions_schema(tmp_path: Path) -> None:
    """D-02: column set per-trade — identità + ProposalDraft + ExtendedIndicators + ctx + outcome."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-04 implementa dataset_writer")
def test_drafts_schema(tmp_path: Path) -> None:
    """D-03: column set per-bar per-detector — A/B/C/D × {READY,FORMING,NONE}."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-04 implementa dataset_writer")
def test_finalize_concatenates_shards(tmp_path: Path) -> None:
    """D-01: pyarrow.dataset.write_dataset finalize concatena shards/, no full-load memory."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-04 implementa dataset_writer")
def test_empty_rows_no_crash(tmp_path: Path) -> None:
    """Edge: shard con 0 righe non crasha (slice senza trade chiusi)."""
    raise NotImplementedError


@pytest.mark.skip(reason="Wave 1: 05-04 implementa dataset_writer")
def test_finalize_handles_empty_shards(tmp_path: Path) -> None:
    """WARNING 11 fix: 1 shard empty + 1 shard 1-row, finalize round-trip preserva schema."""
    raise NotImplementedError
