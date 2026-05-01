"""Sentiment keyword-based su titolo + summary RSS news.

Per coppia forex (es. EURUSD): sentiment netto = bias_base - bias_quote.
"""
from datetime import datetime, timezone

from config import Config
from models import NewsItem, SentimentAnalysis


class SimpleSentiment:
    BULLISH_KEYWORDS = (
        "rally", "rallies", "rallied",
        "surge", "surges", "surged", "surging",
        "breakout", "breakouts",
        "gains", "gained",
        "strengthen", "strengthens", "strengthened",
        "upbeat", "optimistic", "hawkish",
        "rate hike", "rate hikes",
        "strong data", "outperform", "outperforms",
        "bullish",
        "boost", "boosts", "boosted",
        "rise", "rises", "rising", "rose",
        "jump", "jumps", "jumped",
        "soar", "soars", "soared",
        "advance", "advances", "advanced",
        "climb", "climbs", "climbed",
        "higher",
    )

    BEARISH_KEYWORDS = (
        "plunge", "plunges", "plunged",
        "tumble", "tumbles", "tumbled",
        "crash", "crashes", "crashed",
        "weaken", "weakens", "weakened",
        "dovish",
        "rate cut", "rate cuts",
        "recession", "weak data", "concerns", "risk-off",
        "bearish",
        "drop", "drops", "dropped",
        "fall", "falls", "fell",
        "slump", "slumps", "slumped",
        "decline", "declines", "declined",
        "slide", "slides", "slid",
        "retreat", "retreats", "retreated",
        "selloff",
        "lower",
    )

    CURRENCY_MAP = {
        "EUR": ("euro", "eur", "ecb", "eurozone", "lagarde"),
        "USD": ("dollar", "usd", "fed", "federal reserve", "powell"),
        "GBP": ("pound", "sterling", "gbp", "bank of england", "boe"),
        "JPY": ("yen", "jpy", "boj", "bank of japan"),
        "AUD": ("aussie", "aud", "rba", "reserve bank of australia"),
        "CAD": ("loonie", "cad", "boc", "bank of canada"),
        "CHF": ("franc", "chf", "snb", "swiss national bank"),
        "NZD": ("kiwi", "nzd", "rbnz"),
        "XAU": ("gold", "xau", "bullion"),
        "XAG": ("silver", "xag"),
    }

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def analyze_news(self, news_items: list[NewsItem], symbol: str) -> SentimentAnalysis:
        symbol_upper = symbol.upper()
        base = symbol_upper[:3]
        quote = symbol_upper[3:6] if len(symbol_upper) >= 6 else ""
        now = datetime.now(tz=timezone.utc)

        if not news_items:
            return SentimentAnalysis(
                symbol=symbol, bias="NEUTRAL", strength=0.0,
                relevant_news_count=0, sample_headlines=[], timestamp=now,
            )

        base_score = 0
        quote_score = 0
        relevant_headlines: list[str] = []
        relevant_count = 0

        for item in news_items:
            text = f"{item.title} {item.summary}".lower()
            net = self.calculate_sentiment_score(text)
            base_hit = self.is_relevant_for_currency(text, base) if base else False
            quote_hit = self.is_relevant_for_currency(text, quote) if quote else False
            if not (base_hit or quote_hit):
                continue
            relevant_count += 1
            if base_hit:
                base_score += net
            if quote_hit:
                quote_score -= net  # bullish for quote = bearish for pair
            if len(relevant_headlines) < 3:
                relevant_headlines.append(item.title)

        if relevant_count == 0:
            return SentimentAnalysis(
                symbol=symbol, bias="NEUTRAL", strength=0.0,
                relevant_news_count=0, sample_headlines=[], timestamp=now,
            )

        pair_sentiment = base_score + quote_score
        threshold = 1
        if pair_sentiment >= threshold:
            bias = "BULLISH"
        elif pair_sentiment <= -threshold:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        denom = relevant_count * 2
        strength = min(1.0, abs(pair_sentiment) / denom) if denom > 0 else 0.0

        return SentimentAnalysis(
            symbol=symbol, bias=bias, strength=round(strength, 4),
            relevant_news_count=relevant_count,
            sample_headlines=relevant_headlines, timestamp=now,
        )

    def calculate_sentiment_score(self, text: str) -> int:
        bullish = sum(1 for kw in self.BULLISH_KEYWORDS if kw in text)
        bearish = sum(1 for kw in self.BEARISH_KEYWORDS if kw in text)
        return bullish - bearish

    def is_relevant_for_currency(self, text: str, currency: str) -> bool:
        if not currency:
            return False
        keywords = self.CURRENCY_MAP.get(currency.upper())
        if not keywords:
            return currency.lower() in text
        return any(kw in text for kw in keywords)
