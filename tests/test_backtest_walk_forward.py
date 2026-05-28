"""Tests for backtest.walk_forward (BACK-05, D-06)."""
from __future__ import annotations
import pytest

from backtest.walk_forward import walk_forward_slices


def test_no_overlap_rolling() -> None:
    bars = list(range(1000))
    folds = list(walk_forward_slices(bars, n_folds=4, train_ratio=4, mode="rolling"))
    assert len(folds) == 4
    seen: set[int] = set()
    for _, test in folds:
        for b in test:
            assert b not in seen, f"overlap on bar {b}"
            seen.add(b)


def test_expanding_mode() -> None:
    bars = list(range(1000))
    folds = list(walk_forward_slices(bars, n_folds=4, train_ratio=4, mode="expanding"))
    assert len(folds) == 4
    train_sizes = [len(t) for t, _ in folds]
    test_sizes = [len(s) for _, s in folds]
    # train grows
    for i in range(1, len(train_sizes)):
        assert train_sizes[i] > train_sizes[i - 1], train_sizes
    # test constant
    assert len(set(test_sizes)) == 1, test_sizes


def test_fold_cap_high() -> None:
    bars = list(range(1000))
    with pytest.raises(ValueError, match=r"1\.\.10"):
        list(walk_forward_slices(bars, n_folds=11, train_ratio=4))


def test_fold_cap_low() -> None:
    bars = list(range(1000))
    with pytest.raises(ValueError, match=r"1\.\.10"):
        list(walk_forward_slices(bars, n_folds=0, train_ratio=4))


def test_unknown_mode() -> None:
    bars = list(range(1000))
    with pytest.raises(ValueError, match="Unknown mode"):
        list(walk_forward_slices(bars, n_folds=2, mode="bogus"))


def test_temporal_order_ints() -> None:
    bars = list(range(1000))
    for train, test in walk_forward_slices(bars, n_folds=5, mode="rolling"):
        if train and test:
            assert max(train) < min(test), (max(train), min(test))


def test_default_mode_and_ratio() -> None:
    """Defaults per D-06: mode='rolling', train_ratio=4."""
    bars = list(range(1000))
    folds_default = list(walk_forward_slices(bars, n_folds=4))
    folds_explicit = list(walk_forward_slices(bars, n_folds=4, train_ratio=4, mode="rolling"))
    assert folds_default == folds_explicit
