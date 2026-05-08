"""Test indicators.bars (INDIC-10/11) — hand-calc fixtures.

Verifica le definizioni canoniche Crabel (NR4/NR7), Inside Bar, Boomer (A2)
e Closing Score (Defendi) su sequenze costruite a mano. Output length-N con
warmup `None` e leakage-free per costruzione (verificato in
`tests/test_indicators_purity.py`).
"""
from __future__ import annotations

import random

import pytest

from indicators.bars import (
    ClosingScoreResult,
    NRResult,
    closing_score,
    narrow_range,
)


def _bar(h, l, c, t=0):
    """Helper: costruisce un dict bar con campi minimi richiesti dagli indicatori."""
    return {
        "time": t,
        "open": (h + l) / 2,
        "high": h,
        "low": l,
        "close": c,
        "volume": 1,
        "tick_volume": 1,
    }


# ---------------------------------------------------------------------------
# NR4
# ---------------------------------------------------------------------------


def test_nr4_basic():
    """Range strettamente decrescente: nr4 vero a i=3 e i=4, None nei warmup."""
    # ranges = [10, 8, 6, 4, 2]
    bars = [
        _bar(10, 0, 5, t=0),  # range 10
        _bar(9, 1, 5, t=1),   # range 8
        _bar(8, 2, 5, t=2),   # range 6
        _bar(7, 3, 5, t=3),   # range 4
        _bar(6, 4, 5, t=4),   # range 2
    ]
    r = narrow_range(bars)
    assert isinstance(r, NRResult)
    # warmup
    assert r.nr4[0] is None
    assert r.nr4[1] is None
    assert r.nr4[2] is None
    # i=3: range=4 < {10, 8, 6} → True
    assert r.nr4[3] is True
    # i=4: range=2 < {8, 6, 4} → True
    assert r.nr4[4] is True


def test_nr4_not_narrowest_returns_false():
    """Sanity: serve range strettamente minore di TUTTI i 3 priori, non solo
    dell'ultimo. Inoltre i<3 resta None (NR4 richiede 3 bar precedenti).
    """
    # ranges = [10, 8, 12, 4]
    bars = [
        _bar(10, 0, 5, t=0),  # range 10
        _bar(9, 1, 5, t=1),   # range 8
        _bar(13, 1, 5, t=2),  # range 12
        _bar(7, 3, 5, t=3),   # range 4
    ]
    r = narrow_range(bars)
    # i=0..2 sono warmup (NR4 richiede 3 priori)
    assert r.nr4[0] is None
    assert r.nr4[1] is None
    assert r.nr4[2] is None
    # i=3: range=4 < {10, 8, 12} → tutti True → nr4[3]=True
    assert r.nr4[3] is True


def test_nr4_false_when_a_prior_is_smaller():
    """nr4=False se un range precedente è uguale o minore al range corrente."""
    # ranges = [10, 8, 3, 4]
    # i=3: range=4 NOT strictly < range[i-1]=3 → nr4[3]=False
    bars = [
        _bar(10, 0, 5, t=0),
        _bar(9, 1, 5, t=1),
        _bar(6.5, 3.5, 5, t=2),  # range 3
        _bar(7, 3, 5, t=3),       # range 4
    ]
    r = narrow_range(bars)
    assert r.nr4[3] is False


# ---------------------------------------------------------------------------
# NR7
# ---------------------------------------------------------------------------


def test_nr7_basic():
    """Range monotonicamente decrescente su 8 bar: nr7 vero a i=6 e i=7."""
    # ranges = [10, 9, 8, 7, 6, 5, 4, 3]
    bars = [
        _bar(10, 0, 5, t=0),  # 10
        _bar(9.5, 0.5, 5, t=1),  # 9
        _bar(9, 1, 5, t=2),    # 8
        _bar(8.5, 1.5, 5, t=3),  # 7
        _bar(8, 2, 5, t=4),    # 6
        _bar(7.5, 2.5, 5, t=5),  # 5
        _bar(7, 3, 5, t=6),    # 4
        _bar(6.5, 3.5, 5, t=7),  # 3
    ]
    r = narrow_range(bars)
    # warmup nr7 None per i<6
    for i in range(6):
        assert r.nr7[i] is None, f"nr7[{i}] expected None, got {r.nr7[i]}"
    # i=6: range=4 < {10,9,8,7,6,5} → True
    assert r.nr7[6] is True
    # i=7: range=3 < {9,8,7,6,5,4} → True
    assert r.nr7[7] is True


# ---------------------------------------------------------------------------
# Inside bar
# ---------------------------------------------------------------------------


def test_inside_bar():
    """Inside vero quando high<=prev_high AND low>=prev_low."""
    bars = [
        _bar(10, 5, 7, t=0),
        _bar(9, 6, 7, t=1),    # inside: 9<=10 AND 6>=5 → True
        _bar(10, 5, 7, t=2),   # NON inside: 10<=9 is False
    ]
    r = narrow_range(bars)
    assert r.inside[0] is None
    assert r.inside[1] is True
    assert r.inside[2] is False


def test_inside_bar_equal_extremes():
    """Estremi uguali contano come inside (definizione `<=` e `>=`)."""
    bars = [
        _bar(10, 5, 7, t=0),
        _bar(10, 5, 7, t=1),  # inside: 10<=10 AND 5>=5 → True
    ]
    r = narrow_range(bars)
    assert r.inside[1] is True


# ---------------------------------------------------------------------------
# Boomer (A2: 2+ inside consecutivi dentro NR4/NR7)
# ---------------------------------------------------------------------------


def test_boomer_two_consecutive_inside_in_nr_window():
    """Boomer a i=3 quando inside[3] AND inside[2] AND nr4[3]=True.

    Sequenza:
      bar0: h=20, l=0  (range 20)
      bar1: h=18, l=2  (range 16) — inside bar0
      bar2: h=15, l=5  (range 10) — inside bar1
      bar3: h=14, l=6  (range 8)  — inside bar2; NR4 (8 < {20,16,10})
    """
    bars = [
        _bar(20, 0, 10, t=0),
        _bar(18, 2, 10, t=1),
        _bar(15, 5, 10, t=2),
        _bar(14, 6, 10, t=3),
    ]
    r = narrow_range(bars)
    assert r.nr4[3] is True
    assert r.inside[2] is True
    assert r.inside[3] is True
    assert r.boomer[3] is True


def test_boomer_requires_inside_pair():
    """Boomer falso se bar i è NR4+inside ma bar i-1 NON è inside.

    Sequenza:
      bar0: h=20, l=0  (range 20)
      bar1: h=18, l=2  (range 16) — inside bar0
      bar2: h=22, l=8  (range 14) — NON inside bar1 (high 22 > 18)
      bar3: h=14, l=10 (range 4)  — inside bar2; NR4 (4 < {20,16,14})
    """
    bars = [
        _bar(20, 0, 10, t=0),
        _bar(18, 2, 10, t=1),
        _bar(22, 8, 10, t=2),
        _bar(14, 10, 12, t=3),
    ]
    r = narrow_range(bars)
    assert r.nr4[3] is True
    assert r.inside[3] is True
    assert r.inside[2] is False
    assert r.boomer[3] is False


def test_boomer_requires_nr_window():
    """Boomer falso se bar i e bar i-1 inside ma nessun NR4/NR7 vero a i.

    Sequenza con range allargato a i=3 (NON narrow):
      bar0: h=10, l=0  (range 10)
      bar1: h=9,  l=1  (range 8)  — inside bar0
      bar2: h=8,  l=2  (range 6)  — inside bar1
      bar3: h=8,  l=2  (range 6)  — inside bar2; NR4 falso (6 NOT < range[i-1]=6)
    """
    bars = [
        _bar(10, 0, 5, t=0),
        _bar(9, 1, 5, t=1),
        _bar(8, 2, 5, t=2),
        _bar(8, 2, 5, t=3),
    ]
    r = narrow_range(bars)
    assert r.inside[2] is True
    assert r.inside[3] is True
    assert r.nr4[3] is False
    # nr7 None (warmup, n<7)
    assert r.nr7[3] is None
    assert r.boomer[3] is False


# ---------------------------------------------------------------------------
# Closing Score (Defendi)
# ---------------------------------------------------------------------------


def test_closing_score_three_canonical():
    """Tre casi canonici + degenere: 50%, 100%, 0%, None su h==l."""
    bars = [
        _bar(2, 1, 1.5, t=0),  # close a metà → 50.0
        _bar(2, 1, 2.0, t=1),  # close = high → 100.0
        _bar(2, 1, 1.0, t=2),  # close = low → 0.0
        _bar(1, 1, 1.0, t=3),  # h == l → None
    ]
    r = closing_score(bars)
    assert isinstance(r, ClosingScoreResult)
    assert abs(r.score[0] - 50.0) < 1e-9
    assert abs(r.score[1] - 100.0) < 1e-9
    assert abs(r.score[2] - 0.0) < 1e-9
    assert r.score[3] is None


def test_closing_score_full_range():
    """100 bar deterministiche: ogni score è None oppure ∈ [0, 100]."""
    rng = random.Random(42)
    bars = []
    for i in range(100):
        low = rng.uniform(0.0, 5.0)
        high = low + rng.uniform(0.001, 10.0)  # mai degenere
        # close uniformemente nel range [low, high]
        close = low + rng.random() * (high - low)
        bars.append(_bar(high, low, close, t=i))
    r = closing_score(bars)
    assert len(r.score) == 100
    for i, s in enumerate(r.score):
        assert s is not None, f"score[{i}] None inatteso (range > 0)"
        assert 0.0 <= s <= 100.0, f"score[{i}]={s} fuori range"


def test_closing_score_empty():
    """Lista vuota → ClosingScoreResult con score vuota."""
    r = closing_score([])
    assert r.score == []


def test_narrow_range_empty():
    """Lista vuota → NRResult con tutte serie vuote."""
    r = narrow_range([])
    assert r.nr4 == []
    assert r.nr7 == []
    assert r.inside == []
    assert r.boomer == []


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


def test_output_length_matches_input():
    """Tutte le serie di output sono lunghe esattamente come l'input."""
    bars = [_bar(10 - i * 0.5, i * 0.5, 5, t=i) for i in range(10)]
    nr = narrow_range(bars)
    cs = closing_score(bars)
    assert len(nr.nr4) == 10
    assert len(nr.nr7) == 10
    assert len(nr.inside) == 10
    assert len(nr.boomer) == 10
    assert len(cs.score) == 10


@pytest.mark.parametrize("idx", [0, 1, 2])
def test_nr4_warmup_none(idx):
    """nr4 None per i<3 indipendentemente dai dati."""
    bars = [_bar(10 - i, i, 5, t=i) for i in range(5)]
    r = narrow_range(bars)
    assert r.nr4[idx] is None


@pytest.mark.parametrize("idx", [0, 1, 2, 3, 4, 5])
def test_nr7_warmup_none(idx):
    """nr7 None per i<6 indipendentemente dai dati."""
    bars = [_bar(10 - i * 0.5, i * 0.5, 5, t=i) for i in range(8)]
    r = narrow_range(bars)
    assert r.nr7[idx] is None
