#!/usr/bin/env python3
"""
Stock Alpha Scanner — Main Entry Point

Scans watchlist tickers for alpha signals using:
- Fundamental data (yfinance)
- Reddit sentiment (PRAW)
- Insider trades (SEC EDGAR)
- Google Trends (pytrends)
- News headlines (RSS)

Run: python main.py
"""

import time
import sys

from data.fundamentals import get_fundamentals
from data.reddit import get_reddit_sentiment
from data.insider import get_insider_trades
from data.trends import get_search_trends
from data.news import get_news_for_ticker
from scoring import score_ticker, rank_watchlist
from alerts import send_alert, send_daily_digest
from storage import init_db, log_signal
from config import WATCHLIST, ALERT_SCORE_THRESHOLD


def scan_ticker(ticker: str) -> dict | None:
    """Fetch all data sources and score a single ticker."""
    # Fetch fundamentals (required)
    fundamentals = get_fundamentals(ticker)
    if not fundamentals:
        return None
    
    # Fetch alternative data (optional - failures don't block)
    reddit = get_reddit_sentiment(ticker)
    insider = get_insider_trades(ticker)
    trends = get_search_trends(ticker)
    news = get_news_for_ticker(ticker)
    
    # Score with all signals
    return score_ticker(fundamentals, reddit, insider, trends, news)


def main():
    """Main entry point."""
    print(f"\n{'='*60}")
    print(f"  STOCK ALPHA SCANNER")
    print(f"  Scanning {len(WATCHLIST)} tickers...")
    print(f"{'='*60}\n")
    
    init_db()
    
    scores = []
    for i, ticker in enumerate(WATCHLIST, 1):
        print(f"[{i:2}/{len(WATCHLIST)}] {ticker}...", end=" ", flush=True)
        
        score = scan_ticker(ticker)
        
        if score:
            scores.append(score)
            log_signal(score)
            triggers = score.get("alert_triggers", [])
            trigger_str = f" ⚡ {', '.join(triggers)}" if triggers else ""
            print(f"score={score['composite_score']:.1f}/15{trigger_str}")
        else:
            print("skipped (no data)")
        
        # Rate limit - be nice to free APIs
        time.sleep(1.5)
    
    # Rank and filter
    ranked = rank_watchlist(scores)
    
    # Print leaderboard
    print(f"\n{'='*60}")
    print(f"  TOP TICKERS (min {ALERT_SCORE_THRESHOLD:.0f}/15 to alert)")
    print(f"{'='*60}")
    
    if not ranked:
        print("  No tickers qualified (check ANALYST_UPSIDE_MIN threshold)")
    else:
        print(f"  {'TICKER':<8} {'SCORE':>8} {'UPSIDE':>8} {'TRIGGERS':<20}")
        print(f"  {'-'*8} {'-'*8} {'-'*8} {'-'*20}")
        for s in ranked[:10]:
            f = s["signals"]["fundamentals"]
            triggers = s.get("alert_triggers", [])
            trigger_str = ", ".join(triggers)[:20] if triggers else "-"
            upside = f.get('analyst_upside_pct', 0)
            print(f"  {s['ticker']:<8} {s['composite_score']:>7.1f} {upside*100:>7.0f}% {trigger_str:<20}")
    
    # Send alerts for high scorers or triggered signals
    alerts_sent = 0
    for s in ranked:
        if s["composite_score"] >= ALERT_SCORE_THRESHOLD or s.get("alert_triggers"):
            if send_alert(s):
                alerts_sent += 1
    
    # Send daily digest
    send_daily_digest(ranked)
    
    print(f"\n{'='*60}")
    print(f"  COMPLETE")
    print(f"  Processed: {len(scores)} tickers")
    print(f"  Qualified: {len(ranked)} tickers")
    print(f"  Alerts sent: {alerts_sent}")
    print(f"{'='*60}\n")
    
    return 0 if scores else 1


if __name__ == "__main__":
    sys.exit(main())
