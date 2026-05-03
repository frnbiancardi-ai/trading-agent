"""Test pullback engine (fase 17.3)."""

from pullback_engine import detect_pullback


def _bar(o, h, l, c, vol=100):
    return {"open": o, "high": h, "low": l, "close": c, "tick_volume": vol}


def _make_pullback_long_scenario():
    """Scenario:

    - 20 barre di consolidamento intorno a 1.1000 (R = 1.1010)
    - 1 barra breakout (close 1.1030 > 1.1010)
    - 4 barre di pullback con close che ridiscende verso 1.1010
    - ultima barra: Inside vs precedente, volume ridotto
    Totale ~25-26 barre.
    """
    bars = []
    # consolidamento, R massimo 1.1010
    for i in range(20):
        rng = 0.0010
        c = 1.1000 + (i % 3) * 0.0003
        bars.append(_bar(o=c - 0.0001, h=c + rng / 2, l=c - rng / 2, c=c, vol=200))
    # breakout candle: close > 1.1010
    bars.append(_bar(o=1.1015, h=1.1035, l=1.1010, c=1.1030, vol=400))
    # pullback graduale verso 1.1010
    bars.append(_bar(o=1.1028, h=1.1030, l=1.1015, c=1.1020, vol=300))
    bars.append(_bar(o=1.1020, h=1.1022, l=1.1010, c=1.1015, vol=250))
    bars.append(_bar(o=1.1015, h=1.1018, l=1.1009, c=1.1012, vol=200))
    # ultima barra: Inside vs precedente con volume contratto
    last = _bar(o=1.1012, h=1.1015, l=1.1010, c=1.1011, vol=80)
    bars.append(last)
    return bars


def _make_pullback_short_scenario():
    bars = []
    for i in range(20):
        rng = 0.0010
        c = 1.1000 + (i % 3) * 0.0003
        bars.append(_bar(o=c - 0.0001, h=c + rng / 2, l=c - rng / 2, c=c, vol=200))
    # breakdown candle: close < 1.0990
    bars.append(_bar(o=1.0993, h=1.0994, l=1.0975, c=1.0980, vol=400))
    # rimbalzo verso 1.0995 (ex-supporto, ora resistenza)
    bars.append(_bar(o=1.0982, h=1.0992, l=1.0980, c=1.0990, vol=300))
    bars.append(_bar(o=1.0990, h=1.0993, l=1.0989, c=1.0992, vol=250))
    bars.append(_bar(o=1.0992, h=1.0994, l=1.0991, c=1.0993, vol=200))
    # ultima barra: Inside vs precedente, vicino a 1.0995, volume contratto
    last = _bar(o=1.0993, h=1.0993, l=1.0992, c=1.09925, vol=80)
    bars.append(last)
    return bars


def test_pullback_long_detected():
    bars = _make_pullback_long_scenario()
    res = detect_pullback(bars, atr_value=0.0005)
    assert res["pullback"] is True
    assert res["direction"] == "BUY"
    assert res["breakout_level"] is not None


def test_pullback_short_detected():
    bars = _make_pullback_short_scenario()
    res = detect_pullback(bars, atr_value=0.0005)
    assert res["pullback"] is True
    assert res["direction"] == "SELL"


def test_pullback_no_breakout():
    bars = [_bar(1.0, 1.001, 0.999, 1.0, vol=100) for _ in range(30)]
    res = detect_pullback(bars, atr_value=0.001)
    assert res["pullback"] is False
    assert "no_recent_breakout" in res["reason"]


def test_pullback_atr_invalid_returns_false():
    bars = _make_pullback_long_scenario()
    assert detect_pullback(bars, atr_value=None)["pullback"] is False
    assert detect_pullback(bars, atr_value=0.0)["pullback"] is False


def test_pullback_too_few_bars():
    bars = [_bar(1.0, 1.005, 0.995, 1.0, vol=100) for _ in range(5)]
    res = detect_pullback(bars, atr_value=0.001)
    assert res["pullback"] is False


def test_pullback_skipped_when_volume_expanding():
    bars = _make_pullback_long_scenario()
    bars[-1]["tick_volume"] = 5000
    res = detect_pullback(bars, atr_value=0.0005)
    assert res["pullback"] is False
    assert "volume_not_in_contraction" in res["reason"]


def test_pullback_volume_contraction_disabled():
    bars = _make_pullback_long_scenario()
    bars[-1]["tick_volume"] = 5000
    res = detect_pullback(bars, atr_value=0.0005, require_volume_contraction=False)
    assert res["pullback"] is True


def test_pullback_skipped_if_low_broke_level():
    bars = _make_pullback_long_scenario()
    # last bar low molto sotto livello
    bars[-1]["low"] = 1.0900
    res = detect_pullback(bars, atr_value=0.0005)
    assert res["pullback"] is False
    assert (
        "low_broke_below_level" in res["reason"]
        or "price_far_from_breakout_level" in res["reason"]
    )


def test_pullback_skipped_if_no_trigger():
    bars = _make_pullback_long_scenario()
    # ultima barra: ampio range (non Inside, non NR7), low vicino a level
    bars[-1] = _bar(o=1.1010, h=1.1025, l=1.1009, c=1.1011, vol=80)
    res = detect_pullback(bars, atr_value=0.0005)
    assert res["pullback"] is False
    assert "no_continuation_trigger" in res["reason"]


def test_pullback_carries_trigger_name():
    bars = _make_pullback_long_scenario()
    res = detect_pullback(bars, atr_value=0.0005)
    assert res["pullback"] is True
    assert res["trigger_pattern"] in ("INSIDE", "NR7")
    assert res["bars_since_breakout"] >= 2
