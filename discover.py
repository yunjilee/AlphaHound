#!/usr/bin/env python3
"""
Discovery Script — Run Daily

Finds high-quality growth stocks using fundamentals-first screening:
- Quality Growth (GARP): ROE > 15%, PEG < 2
- Undervalued Growth: PEG < 1, analyst buy
- Quality Value: Low debt, high margins

Insider buying is tracked as a BONUS signal, not a filter.
This approach would have caught MU in early 2025.

Run: python discover.py
Schedule: Daily at 6:00 AM (before market open)
"""

import sys
from data.discovery import run_discovery_and_cache
from config import CORE_WATCHLIST, MAX_WATCHLIST_SIZE


def main():
    print("\n" + "="*60)
    print("  ALPHAHOUND DISCOVERY (Fundamentals-First)")
    print("  Strategy: Quality > Growth > Value | Insider = Bonus")
    print("="*60)
    
    # Run discovery and cache results
    result = run_discovery_and_cache(CORE_WATCHLIST, MAX_WATCHLIST_SIZE)
    
    tickers = result["tickers"]
    insider_tickers = result.get("insider_tickers", set())
    multi_screen = result.get("multi_screen", set())
    
    # Show results
    discovered = [t for t in tickers if t not in CORE_WATCHLIST]
    
    print("\n" + "-"*40)
    print(f"Core watchlist:       {len(CORE_WATCHLIST)} tickers")
    print(f"Discovered:           {len(discovered)} tickers")
    print(f"Multi-screen overlap: {len(multi_screen)} tickers (highest conviction)")
    print(f"Insider buying bonus: {len(insider_tickers & set(tickers))} tickers")
    print(f"Total:                {len(tickers)} tickers")
    print("-"*40)
    
    if discovered:
        print("\nNew discoveries:")
        for i, t in enumerate(discovered[:25], 1):
            markers = []
            if t in multi_screen:
                markers.append("multi-screen")
            if t in insider_tickers:
                markers.append("insider+")
            marker_str = f" ({', '.join(markers)})" if markers else ""
            print(f"  {i:2}. {t}{marker_str}")
        if len(discovered) > 25:
            print(f"  ... and {len(discovered) - 25} more")
    
    print("\n[OK] Watchlist cached for hourly scans")
    print("="*60 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
