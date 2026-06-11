#!/usr/bin/env python3
"""
Stock Alpha Scanner — Hourly Scan

Strategy: Quality > Growth > Value (with insider as bonus catalyst)

Scans watchlist tickers using:
- Fundamental data (yfinance)
- Reddit sentiment (PRAW)
- Insider trades (SEC EDGAR)
- Google Trends (pytrends)
- News headlines (RSS)

Uses cached watchlist from daily discovery run.

Run: python main.py              # Use cached watchlist (or core if no cache)
     python main.py --core-only  # Use core watchlist only
"""

import time
import sys
import argparse

from data.fundamentals import get_fundamentals
from data.reddit import get_reddit_sentiment
from data.insider import get_insider_trades
from data.trends import get_search_trends
from data.news import get_news_for_ticker
from data.discovery import load_watchlist
from scoring import score_ticker, rank_watchlist
from alerts import send_alert, send_daily_digest
from storage import init_db, log_signal, get_top_scored_tickers, get_new_tickers, get_previous_target
from config import CORE_WATCHLIST, ALERT_SCORE_THRESHOLD, MAX_HOURLY_TICKERS


def scan_ticker(
    ticker: str,
    has_insider_buying: bool = False,
    is_multi_screen: bool = False,
) -> dict | None:
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
    
    # Get previous target for rerate detection
    previous_target = get_previous_target(ticker)
    
    # Score with all signals + discovery bonuses
    return score_ticker(
        fundamentals, reddit, insider, trends, news,
        has_insider_buying=has_insider_buying,
        is_multi_screen=is_multi_screen,
        previous_target=previous_target,
    )


def prioritize_watchlist(
    all_tickers: list[str],
    insider_tickers: set[str],
    multi_screen: set[str],
    max_tickers: int = MAX_HOURLY_TICKERS,
) -> list[str]:
    """
    Prioritize which tickers to scan within rate limits.
    
    Priority order:
    1. New discoveries (never scored) - always scan to establish baseline
    2. High scorers from recent scans - track our best candidates  
    3. Core watchlist - always included
    4. Multi-screen tickers - high conviction from fundamentals
    5. Insider buying tickers - catalyst bonus
    
    Returns up to max_tickers in priority order.
    """
    # Start with core watchlist (always included)
    core_set = set(CORE_WATCHLIST)
    prioritized = list(CORE_WATCHLIST)
    
    # Get new discoveries that need baseline scoring
    new_tickers = get_new_tickers(all_tickers)
    for t in new_tickers:
        if t not in core_set and len(prioritized) < max_tickers:
            prioritized.append(t)
    
    # Get top scorers from last 48 hours
    top_scored = get_top_scored_tickers(limit=max_tickers, hours=48)
    top_scored_tickers = [t for t, _ in top_scored]
    
    # Add top scorers
    for t in top_scored_tickers:
        if t not in prioritized and len(prioritized) < max_tickers:
            prioritized.append(t)
    
    # Add multi-screen (high conviction fundamentals)
    for t in multi_screen:
        if t not in prioritized and len(prioritized) < max_tickers:
            prioritized.append(t)
    
    # Add insider buying tickers
    for t in insider_tickers:
        if t not in prioritized and len(prioritized) < max_tickers:
            prioritized.append(t)
    
    return prioritized[:max_tickers]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Stock Alpha Scanner (Hourly)")
    parser.add_argument(
        "--core-only", action="store_true",
        help="Use core watchlist only, ignore discovery cache"
    )
    parser.add_argument(
        "--scan-all", action="store_true",
        help="Scan all discovered tickers (ignore rate limit cap)"
    )
    args = parser.parse_args()
    
    # Load watchlist from cache (or fall back to core)
    if args.core_only:
        watchlist_data = {
            "tickers": list(CORE_WATCHLIST),
            "insider_tickers": set(),
            "multi_screen": set(),
            "from_cache": False,
        }
        print("\n[info] Using core watchlist only (--core-only)")
    else:
        watchlist_data = load_watchlist(CORE_WATCHLIST)
        if not watchlist_data.get("from_cache"):
            print("[info] No fresh cache - run 'python discover.py' for discovery")
    
    watchlist = watchlist_data["tickers"]
    insider_tickers = watchlist_data.get("insider_tickers", set())
    multi_screen = watchlist_data.get("multi_screen", set())
    
    # Prioritize within rate limits (unless --scan-all)
    full_count = len(watchlist)
    if not args.scan_all:
        watchlist = prioritize_watchlist(
            watchlist, insider_tickers, multi_screen, MAX_HOURLY_TICKERS
        )
    
    print(f"\n{'='*60}")
    print(f"  STOCK ALPHA SCANNER (Fundamentals-First)")
    print(f"  Strategy: Quality > Growth > Value | Insider = Bonus")
    if full_count > len(watchlist):
        print(f"  Discovered: {full_count} | Scanning top {len(watchlist)} (rate limited)")
    else:
        print(f"  Scanning {len(watchlist)} tickers...")
    if insider_tickers:
        print(f"  Insider buying bonus: {len(insider_tickers)} tickers")
    if multi_screen:
        print(f"  Multi-screen conviction: {len(multi_screen)} tickers")
    print(f"{'='*60}\n")
    
    init_db()
    
    scores = []
    for i, ticker in enumerate(watchlist, 1):
        has_insider = ticker in insider_tickers
        is_multi = ticker in multi_screen
        
        markers = []
        if has_insider:
            markers.append("+ins")
        if is_multi:
            markers.append("+multi")
        marker_str = f" ({','.join(markers)})" if markers else ""
        
        print(f"[{i:2}/{len(watchlist)}] {ticker}{marker_str}...", end=" ", flush=True)
        
        score = scan_ticker(ticker, has_insider_buying=has_insider, is_multi_screen=is_multi)
        
        if score:
            scores.append(score)
            log_signal(score)
            triggers = score.get("alert_triggers", [])
            trigger_str = f" [!] {', '.join(triggers)}" if triggers else ""
            print(f"score={score['composite_score']:.1f}/10{trigger_str}")
        else:
            print("skipped (no data)")
        
        # Rate limit - be nice to free APIs
        time.sleep(1.5)
    
    # Rank and filter by quality (min 1.0 out of 2.5 = 40% quality)
    ranked = rank_watchlist(scores, min_quality_score=1.0)
    
    # Print leaderboard
    print(f"\n{'='*60}")
    print(f"  TOP TICKERS (Score out of 10)")
    print(f"{'='*60}")
    
    if not ranked:
        print("  No tickers qualified (need min quality score of 2.0)")
    else:
        print(f"  {'TICKER':<8} {'SCORE':>6} {'QUAL':>5} {'GROW':>5} {'VAL':>5} {'TRIGGERS':<20}")
        print(f"  {'-'*8} {'-'*6} {'-'*5} {'-'*5} {'-'*5} {'-'*20}")
        for s in ranked[:15]:
            bd = s.get("score_breakdown", {})
            quality = bd.get("roe", 0) + bd.get("margin", 0) + bd.get("debt", 0)
            growth = bd.get("eps_growth", 0) + bd.get("pe_discount", 0)
            value = bd.get("peg", 0) + bd.get("analyst_upside", 0)
            triggers = s.get("alert_triggers", [])
            trigger_str = ", ".join(triggers)[:20] if triggers else "-"
            print(f"  {s['ticker']:<8} {s['composite_score']:>5.1f} {quality:>5.1f} {growth:>5.1f} {value:>5.1f} {trigger_str:<20}")
    
    # Send alerts ONLY for significant events (not routine scans)
    # Significant = target rerate OR major daily price move (>5%)
    alerts_sent = 0
    for s in ranked:
        triggers = s.get("alert_triggers", [])
        fundamentals = s.get("signals", {}).get("fundamentals", {})
        daily_change = abs(fundamentals.get("daily_change_pct", 0) or 0)
        
        has_rerate = any("target_raised" in t or "target_lowered" in t for t in triggers)
        has_major_move = daily_change >= 0.05  # 5%+ price move
        
        if has_rerate or has_major_move:
            if send_alert(s):
                alerts_sent += 1
                print(f"  [ALERT] {s['ticker']}: rerate={has_rerate}, move={daily_change*100:.1f}%")
    
    # Send daily digest (always, summarizes top picks)
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
