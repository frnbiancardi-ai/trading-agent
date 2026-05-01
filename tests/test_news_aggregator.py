"""Test NewsAggregator: parse_feed, fetch_recent_news, clean_cache, parse_date."""
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from models import NewsItem
from news_aggregator import NewsAggregator


def _make_cfg(**overrides):
    cfg = MagicMock()
    cfg.RSS_FEEDS = ["https://example.com/feed1", "https://example.com/feed2"]
    cfg.NEWS_FETCH_INTERVAL_MINUTES = 15
    cfg.NEWS_LOOKBACK_HOURS = 2
    cfg.NEWS_CACHE_MAX_HOURS = 24
    cfg.ENABLE_NEWS_SENTIMENT = True
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _fake_parsed(entries: list[dict], title: str = "MockFeed", bozo: bool = False):
    parsed = SimpleNamespace()
    parsed.feed = {"title": title}
    parsed.entries = entries
    parsed.bozo = bozo
    parsed.bozo_exception = None
    return parsed


def _entry(title: str, published: str = "Mon, 01 May 2026 12:00:00 +0000",
           summary: str = "", link: str = "https://x") -> dict:
    return {"title": title, "summary": summary, "link": link, "published": published}


# ──────────────────────────────────────────────────────────────────────────────


def test_parse_date_rfc822():
    dt = NewsAggregator.parse_date("Mon, 01 May 2026 12:00:00 +0000")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 1
    assert dt.tzinfo is not None


def test_parse_date_iso():
    dt = NewsAggregator.parse_date("2026-05-01T12:00:00Z")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_date_invalid_returns_none():
    assert NewsAggregator.parse_date("garbage") is None
    assert NewsAggregator.parse_date("") is None


def test_parse_feed_valid_returns_news_items():
    cfg = _make_cfg()
    agg = NewsAggregator(cfg, logging.getLogger("t"))
    parsed = _fake_parsed([
        _entry("EUR rallies on hawkish ECB"),
        _entry("USD weakens after dovish Fed"),
    ])
    with patch("news_aggregator.feedparser.parse", return_value=parsed):
        items = agg.parse_feed("https://example.com/feed1")
    assert len(items) == 2
    assert all(isinstance(i, NewsItem) for i in items)
    assert "ECB" in items[0].title


def test_parse_feed_bozo_no_entries_raises():
    cfg = _make_cfg()
    agg = NewsAggregator(cfg, logging.getLogger("t"))
    parsed = _fake_parsed([], bozo=True)
    parsed.bozo_exception = "URLError"
    with patch("news_aggregator.feedparser.parse", return_value=parsed):
        with pytest.raises(RuntimeError):
            agg.parse_feed("https://broken.example/feed")


def test_parse_feed_skips_entries_without_title():
    cfg = _make_cfg()
    agg = NewsAggregator(cfg, logging.getLogger("t"))
    parsed = _fake_parsed([
        {"title": "", "summary": "x", "link": "y", "published": ""},
        _entry("Real headline"),
    ])
    with patch("news_aggregator.feedparser.parse", return_value=parsed):
        items = agg.parse_feed("https://example.com/feed1")
    assert len(items) == 1
    assert items[0].title == "Real headline"


def test_fetch_recent_news_uses_cache_within_interval():
    cfg = _make_cfg(NEWS_FETCH_INTERVAL_MINUTES=15)
    agg = NewsAggregator(cfg, logging.getLogger("t"))
    now = datetime.now(tz=timezone.utc)
    cached = NewsItem(
        source="MockFeed", title="cached headline", summary="", link="x",
        published=now - timedelta(minutes=5),
    )
    agg.cache = [cached]
    agg.last_fetch = now - timedelta(minutes=5)

    with patch("news_aggregator.feedparser.parse") as mock_parse:
        items = agg.fetch_recent_news(now=now)
    mock_parse.assert_not_called()
    assert len(items) == 1


def test_fetch_recent_news_force_refetches():
    cfg = _make_cfg()
    agg = NewsAggregator(cfg, logging.getLogger("t"))
    now = datetime.now(tz=timezone.utc)
    pub = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    parsed = _fake_parsed([_entry("Fresh news", published=pub)])
    with patch("news_aggregator.feedparser.parse", return_value=parsed) as mock_parse:
        items = agg.fetch_recent_news(force=True, now=now)
    assert mock_parse.call_count == len(cfg.RSS_FEEDS)
    assert any(i.title == "Fresh news" for i in items)


def test_fetch_recent_news_filters_lookback():
    cfg = _make_cfg(NEWS_LOOKBACK_HOURS=1)
    agg = NewsAggregator(cfg, logging.getLogger("t"))
    now = datetime.now(tz=timezone.utc)
    agg.cache = [
        NewsItem(source="x", title="recent", summary="", link="r",
                 published=now - timedelta(minutes=30)),
        NewsItem(source="x", title="old", summary="", link="o",
                 published=now - timedelta(hours=3)),
    ]
    agg.last_fetch = now
    items = agg.fetch_recent_news(now=now)
    assert [i.title for i in items] == ["recent"]


def test_fetch_recent_news_handles_feed_failure_gracefully():
    cfg = _make_cfg(RSS_FEEDS=["https://broken.example/feed"])
    agg = NewsAggregator(cfg, logging.getLogger("t"))
    now = datetime.now(tz=timezone.utc)

    def boom(_url):
        raise RuntimeError("network down")

    with patch("news_aggregator.feedparser.parse", side_effect=boom):
        items = agg.fetch_recent_news(force=True, now=now)
    assert items == []


def test_clean_cache_removes_old_news():
    cfg = _make_cfg(NEWS_CACHE_MAX_HOURS=2)
    agg = NewsAggregator(cfg, logging.getLogger("t"))
    now = datetime.now(tz=timezone.utc)
    agg.cache = [
        NewsItem(source="x", title="recent", summary="", link="r",
                 published=now - timedelta(minutes=30)),
        NewsItem(source="x", title="old", summary="", link="o",
                 published=now - timedelta(hours=5)),
    ]
    agg.clean_cache(now=now)
    assert [n.title for n in agg.cache] == ["recent"]


def test_dedupe_keeps_first_only():
    cfg = _make_cfg()
    agg = NewsAggregator(cfg, logging.getLogger("t"))
    now = datetime.now(tz=timezone.utc)
    items = [
        NewsItem(source="A", title="same headline", summary="", link="L1", published=now),
        NewsItem(source="B", title="same headline", summary="", link="L1", published=now),
        NewsItem(source="C", title="other", summary="", link="L2", published=now),
    ]
    out = NewsAggregator._dedupe(items)
    titles = [i.title for i in out]
    assert titles.count("same headline") == 1
    assert "other" in titles
