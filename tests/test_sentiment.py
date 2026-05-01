"""Test SimpleSentiment: keyword scoring, currency relevance, pair sentiment."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from models import NewsItem
from sentiment import SimpleSentiment


def _cfg():
    cfg = MagicMock()
    cfg.SENTIMENT_MIN_STRENGTH_FILTER = 0.6
    return cfg


def _news(title: str, summary: str = "") -> NewsItem:
    return NewsItem(
        source="t", title=title, summary=summary,
        link="https://x", published=datetime.now(tz=timezone.utc),
    )


# ──────────────────────────────────────────────────────────────────────────────
# calculate_sentiment_score
# ──────────────────────────────────────────────────────────────────────────────


def test_calculate_score_pure_bullish():
    s = SimpleSentiment(_cfg())
    score = s.calculate_sentiment_score("euro rally surge gains")
    assert score >= 3


def test_calculate_score_pure_bearish():
    s = SimpleSentiment(_cfg())
    score = s.calculate_sentiment_score("dollar plunge crash decline")
    assert score <= -3


def test_calculate_score_mixed():
    s = SimpleSentiment(_cfg())
    score = s.calculate_sentiment_score("rally then plunge")
    assert score == 0


# ──────────────────────────────────────────────────────────────────────────────
# is_relevant_for_currency
# ──────────────────────────────────────────────────────────────────────────────


def test_is_relevant_eur():
    s = SimpleSentiment(_cfg())
    assert s.is_relevant_for_currency("ecb hikes rates", "EUR") is True
    assert s.is_relevant_for_currency("euro reacts to data", "EUR") is True
    assert s.is_relevant_for_currency("yen weakens", "EUR") is False


def test_is_relevant_xau():
    s = SimpleSentiment(_cfg())
    assert s.is_relevant_for_currency("gold hits new highs", "XAU") is True
    assert s.is_relevant_for_currency("nothing to see", "XAU") is False


# ──────────────────────────────────────────────────────────────────────────────
# analyze_news pair-level
# ──────────────────────────────────────────────────────────────────────────────


def test_analyze_eurusd_bullish_when_eur_strong():
    s = SimpleSentiment(_cfg())
    items = [
        _news("Euro rallies as ECB turns hawkish on inflation"),
        _news("EUR surge continues, ECB rate hike expected"),
        _news("Eurozone outperforms with strong data"),
    ]
    result = s.analyze_news(items, "EURUSD")
    assert result.bias == "BULLISH"
    assert result.strength > 0
    assert result.relevant_news_count == 3


def test_analyze_eurusd_bearish_when_usd_strong():
    s = SimpleSentiment(_cfg())
    items = [
        _news("Dollar surges as Fed turns hawkish"),
        _news("USD rally on strong data, Powell upbeat"),
        _news("Federal Reserve signals rate hike, dollar gains"),
    ]
    result = s.analyze_news(items, "EURUSD")
    # Strong USD = bearish for EURUSD pair
    assert result.bias == "BEARISH"
    assert result.relevant_news_count == 3


def test_analyze_neutral_when_no_relevant_news():
    s = SimpleSentiment(_cfg())
    items = [
        _news("Cricket world cup results"),
        _news("Tech stocks slide on chip concerns"),
    ]
    result = s.analyze_news(items, "EURUSD")
    assert result.bias == "NEUTRAL"
    assert result.strength == 0.0
    assert result.relevant_news_count == 0


def test_analyze_empty_returns_neutral():
    s = SimpleSentiment(_cfg())
    result = s.analyze_news([], "EURUSD")
    assert result.bias == "NEUTRAL"
    assert result.strength == 0.0


def test_analyze_strength_is_in_unit_range():
    s = SimpleSentiment(_cfg())
    items = [
        _news("Euro rally surge gains breakout strengthen"),
        _news("ECB hawkish boost outperform"),
    ] * 3
    result = s.analyze_news(items, "EURUSD")
    assert 0.0 <= result.strength <= 1.0


def test_analyze_caps_sample_headlines_to_three():
    s = SimpleSentiment(_cfg())
    items = [
        _news(f"Euro headline {i}", summary="ecb rally") for i in range(10)
    ]
    result = s.analyze_news(items, "EURUSD")
    assert len(result.sample_headlines) <= 3


def test_analyze_xauusd_with_gold_news():
    s = SimpleSentiment(_cfg())
    items = [
        _news("Gold rallies to new highs", summary="bullion gains as inflation hedge"),
        _news("Bullion surges on hawkish ECB"),
    ]
    result = s.analyze_news(items, "XAUUSD")
    assert result.bias == "BULLISH"
    assert result.relevant_news_count >= 1
