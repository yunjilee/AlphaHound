"""Data fetchers for Stock Alpha Scanner."""

from .fundamentals import get_fundamentals
from .reddit import get_reddit_sentiment
from .insider import get_insider_trades
from .trends import get_search_trends
from .news import get_news_for_ticker, scan_news
from .discovery import discover_candidates, load_watchlist, run_discovery_and_cache

__all__ = [
    "get_fundamentals",
    "get_reddit_sentiment",
    "get_insider_trades",
    "get_search_trends",
    "get_news_for_ticker",
    "scan_news",
    "discover_candidates",
    "load_watchlist",
    "run_discovery_and_cache",
]
