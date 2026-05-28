"""Walk-forward slice generator (BACK-05, D-06).

Bar-count boundaries (not calendar), default rolling mode, fold cap 10,
default train:test = 4:1. Test slices never overlap; train precedes test.
"""
from __future__ import annotations
from typing import Generator, Sequence, TypeVar

T = TypeVar("T")

_FOLD_CAP = 10  # D-06


def walk_forward_slices(
    bars: Sequence[T],
    n_folds: int,
    train_ratio: int = 4,
    mode: str = "rolling",
) -> Generator[tuple[list[T], list[T]], None, None]:
    """Yield (train_slice, test_slice) per fold.

    Bar-count boundaries; no overlap between any two test slices; train
    strictly precedes test (max(train.idx) < min(test.idx)).

    Args:
        bars: Sequence of bar-like items (ordered chronologically).
        n_folds: Number of folds, clamped to 1..10 (D-06 fold cap).
        train_ratio: train_size / test_size ratio (default 4 per D-06).
        mode: 'rolling' (sliding train window) or 'expanding' (train grows).

    Raises:
        ValueError: n_folds out of [1,10], train_ratio < 1, or unknown mode.
    """
    if n_folds < 1 or n_folds > _FOLD_CAP:
        raise ValueError(f"n_folds must be 1..{_FOLD_CAP}, got {n_folds}")
    if train_ratio < 1:
        raise ValueError(f"train_ratio must be >= 1, got {train_ratio}")
    if mode not in {"rolling", "expanding"}:
        raise ValueError(f"Unknown mode: {mode!r}")

    total = len(bars)

    if mode == "rolling":
        fold_size = total // n_folds
        test_size = max(1, fold_size // (1 + train_ratio))
        train_size = test_size * train_ratio
        for i in range(n_folds):
            test_start = i * fold_size + (fold_size - test_size)
            test_end = test_start + test_size
            train_start = max(0, test_start - train_size)
            yield list(bars[train_start:test_start]), list(bars[test_start:test_end])
        return

    # expanding
    test_size = max(1, total // (n_folds + train_ratio))
    for i in range(n_folds):
        test_start = train_ratio * test_size + i * test_size
        test_end = test_start + test_size
        yield list(bars[:test_start]), list(bars[test_start:test_end])
