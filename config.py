"""Configuration for Stock Alpha Scanner."""

import os
from dotenv import load_dotenv

load_dotenv()

# Watchlist: tickers to monitor
WATCHLIST = [
    "NVDA", "MRVL", "MU", "AMD", "INTC", "QCOM",
    "TSLA", "AAPL", "MSFT", "GOOGL", "META", "AMZN",
    "DELL", "HPE", "SMCI", "ARM", "AVGO", "TSM",
]

# High-signal public figures (for news scanning)
SIGNAL_FIGURES = [
    "Jensen Huang", "Elon Musk", "Warren Buffett", "Tim Cook",
    "Satya Nadella", "Cathie Wood", "Jamie Dimon", "Powell",
]

# Scoring thresholds
ANALYST_UPSIDE_MIN = 0.20          # 20% minimum analyst upside
ALERT_SCORE_THRESHOLD = 6.0        # Composite score to trigger alert (out of 15)
MIN_ANALYST_COUNT = 5              # Require minimum analyst coverage

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Reddit
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "alpha.db")

# RSS feeds to monitor
RSS_FEEDS = [
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("MarketWatch", "http://feeds.marketwatch.com/marketwatch/topstories/"),
    ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml"),
]
