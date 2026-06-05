"""Scan RSS feeds for ticker mentions and figure quotes."""

import re
import feedparser
from datetime import datetime, timedelta
from config import WATCHLIST, SIGNAL_FIGURES, RSS_FEEDS


def scan_news(tickers: list[str] = None) -> list[dict]:
    """Scan RSS feeds for ticker mentions and figure quotes."""
    if tickers is None:
        tickers = WATCHLIST
    
    ticker_pattern = re.compile(r'\b(' + '|'.join(tickers) + r')\b', re.IGNORECASE)
    figure_pattern = re.compile(r'(' + '|'.join(SIGNAL_FIGURES) + r')', re.IGNORECASE)
    
    results = []
    seen_urls = set()
    cutoff = datetime.now() - timedelta(hours=24)
    
    for source_name, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:30]:
                url = entry.get("link", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Combine title and summary for matching
                text = f"{entry.get('title', '')} {entry.get('summary', '')}"
                
                # Find ticker mentions
                ticker_matches = ticker_pattern.findall(text)
                if not ticker_matches:
                    continue
                
                # Check for figure mentions
                figure_match = figure_pattern.search(text)
                
                # Parse date
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = datetime(*published[:6])
                    if pub_dt < cutoff:
                        continue
                else:
                    pub_dt = datetime.now()
                
                for ticker in set(ticker_matches):
                    results.append({
                        "ticker": ticker.upper(),
                        "headline": entry.get("title", "")[:200],
                        "source": source_name,
                        "url": url,
                        "published_at": pub_dt.isoformat(),
                        "mentions_figure": figure_match.group(1) if figure_match else None,
                    })
        except Exception as e:
            print(f"    [news] RSS error for {source_name}: {e}")
            continue
    
    return results


def get_news_for_ticker(ticker: str) -> dict:
    """Get news summary for a single ticker."""
    all_news = scan_news([ticker])
    ticker_news = [n for n in all_news if n["ticker"] == ticker]
    
    return {
        "ticker": ticker,
        "news_count_24h": len(ticker_news),
        "has_figure_mention": any(n["mentions_figure"] for n in ticker_news),
        "figure_mentioned": next((n["mentions_figure"] for n in ticker_news if n["mentions_figure"]), None),
        "top_headlines": ticker_news[:3],
        "fetched_at": datetime.now().isoformat(),
    }
