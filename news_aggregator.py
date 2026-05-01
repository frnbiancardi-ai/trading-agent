"""RSS news aggregator: fetch + cache + filter by lookback window.

Mai bloccare il loop di trading: timeout brevi, errori per-feed isolati,
fallback a cache se nessun feed risponde.
"""
import logging
import socket
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser

from config import Config
from models import NewsItem


_DEFAULT_TIMEOUT_SECONDS = 5


class NewsAggregator:
    def __init__(self, cfg: Config, logger: logging.Logger | None = None):
        self.cfg = cfg
        self.log = logger or logging.getLogger(__name__)
        self.cache: list[NewsItem] = []
        self.last_fetch: datetime | None = None

    # ─────────────────────────────────────────────────────────────────────

    def fetch_recent_news(self, force: bool = False, now: datetime | None = None) -> list[NewsItem]:
        now = now or datetime.now(tz=timezone.utc)
        interval = timedelta(minutes=self.cfg.NEWS_FETCH_INTERVAL_MINUTES)
        if (
            not force
            and self.last_fetch is not None
            and (now - self.last_fetch) < interval
            and self.cache
        ):
            return self._within_lookback(self.cache, now)

        new_items: list[NewsItem] = []
        for url in self.cfg.RSS_FEEDS:
            try:
                items = self.parse_feed(url)
            except Exception as exc:
                self.log.warning("RSS fetch failed for %s: %s", url, exc)
                continue
            new_items.extend(items)

        if new_items:
            self.cache = self._dedupe(self.cache + new_items)
            self.last_fetch = now

        self.clean_cache(now=now)
        return self._within_lookback(self.cache, now)

    def parse_feed(self, feed_url: str) -> list[NewsItem]:
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(_DEFAULT_TIMEOUT_SECONDS)
        try:
            parsed = feedparser.parse(feed_url)
        finally:
            socket.setdefaulttimeout(old_timeout)

        entries = getattr(parsed, "entries", []) or []
        if getattr(parsed, "bozo", False) and not entries:
            raise RuntimeError(
                f"feedparser bozo: {getattr(parsed, 'bozo_exception', None)}"
            )

        feed_meta = getattr(parsed, "feed", {}) or {}
        if isinstance(feed_meta, dict):
            source = feed_meta.get("title", feed_url)
        else:
            source = getattr(feed_meta, "title", feed_url)
        items: list[NewsItem] = []
        for entry in entries:
            title = entry.get("title", "").strip()
            if not title:
                continue
            summary = entry.get("summary", entry.get("description", "")).strip()
            link = entry.get("link", "").strip()
            published_raw = (
                entry.get("published")
                or entry.get("updated")
                or entry.get("pubDate")
                or ""
            )
            published = self.parse_date(published_raw) or datetime.now(tz=timezone.utc)
            items.append(NewsItem(
                source=str(source), title=title, summary=summary,
                link=link, published=published,
            ))
        return items

    def clean_cache(self, now: datetime | None = None) -> None:
        now = now or datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(hours=self.cfg.NEWS_CACHE_MAX_HOURS)
        self.cache = [n for n in self.cache if n.published >= cutoff]

    @staticmethod
    def parse_date(date_str: str) -> datetime | None:
        if not date_str:
            return None
        try:
            dt = parsedate_to_datetime(date_str)
            if dt is None:
                return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError):
            pass
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return None

    # ─────────────────────────────────────────────────────────────────────

    def _within_lookback(self, items: list[NewsItem], now: datetime) -> list[NewsItem]:
        cutoff = now - timedelta(hours=self.cfg.NEWS_LOOKBACK_HOURS)
        recent = [n for n in items if n.published >= cutoff]
        recent.sort(key=lambda n: n.published, reverse=True)
        return recent

    @staticmethod
    def _dedupe(items: list[NewsItem]) -> list[NewsItem]:
        seen: set[tuple[str, str]] = set()
        out: list[NewsItem] = []
        for item in items:
            key = (item.title, item.link or item.source)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out
