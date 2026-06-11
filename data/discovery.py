"""
Discovery module: Fundamentals-first stock screening.

Strategy: Quality > Growth > Value (with insider as scoring boost, not filter)
This approach would have caught MU in early 2025.

Screens:
1. Quality Growth (GARP): ROE > 15%, PEG < 1.5, market cap > $2B
2. Undervalued Growth: Forward P/E < Trailing, analyst buy, growth > 10%
3. Quality Value: Low debt, high margins, PEG < 2

Insider buying is tracked separately as a BONUS signal, not a filter.
"""

import requests
from bs4 import BeautifulSoup
import time
import re
import json
import os
from datetime import datetime
from typing import Set, Dict

try:
    from finvizfinance.screener.overview import Overview as FinvizOverview
    FINVIZ_AVAILABLE = True
except ImportError:
    FINVIZ_AVAILABLE = False
    print("[discovery] Warning: finvizfinance not installed. Run: pip install finvizfinance")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

CACHE_FILE = os.path.join(os.path.dirname(__file__), "watchlist_cache.json")


# =============================================================================
# STAGE 1: QUALITY GROWTH (GARP) - Primary Screen
# =============================================================================

def screen_quality_growth() -> Set[str]:
    """
    GARP screen: Growth At Reasonable Price.
    
    This is the PRIMARY screen - catches stocks like MU.
    
    Criteria:
    - Market cap > $2B (institutional quality, liquid)
    - PEG < 2 (reasonable price for growth)
    - ROE > 15% (quality business)
    - EPS growth next year > 0% (growing earnings)
    - Average volume > 500K (liquid)
    """
    if not FINVIZ_AVAILABLE:
        return set()
    
    tickers = set()
    try:
        foverview = FinvizOverview()
        filters = {
            'Market Cap.': '+Mid (over $2bln)',
            'PEG': 'Under 2',
            'Return on Equity': 'Over +15%',
            'EPS growthnext year': 'Positive (>0%)',
            'Average Volume': 'Over 500K',
        }
        foverview.set_filter(filters_dict=filters)
        df = foverview.screener_view()
        if df is not None and len(df) > 0:
            tickers = set(df['Ticker'].tolist())
        print(f"[discovery] Quality Growth (GARP): {len(tickers)} stocks")
    except Exception as e:
        print(f"[discovery] Quality Growth error: {e}")
    
    return tickers


# =============================================================================
# STAGE 2: UNDERVALUED GROWTH - Secondary Screen
# =============================================================================

def screen_undervalued_growth() -> Set[str]:
    """
    Undervalued growth stocks.
    
    Criteria:
    - Market cap > $2B
    - PEG < 1 (significantly undervalued vs growth)
    - Analyst recommendation: Buy or better
    - Average volume > 500K
    """
    if not FINVIZ_AVAILABLE:
        return set()
    
    tickers = set()
    try:
        foverview = FinvizOverview()
        filters = {
            'Market Cap.': '+Mid (over $2bln)',
            'PEG': 'Low (<1)',
            'Analyst Recom.': 'Buy or better',
            'Average Volume': 'Over 500K',
        }
        foverview.set_filter(filters_dict=filters)
        df = foverview.screener_view()
        if df is not None and len(df) > 0:
            tickers = set(df['Ticker'].tolist())
        print(f"[discovery] Undervalued Growth: {len(tickers)} stocks")
    except Exception as e:
        print(f"[discovery] Undervalued Growth error: {e}")
    
    return tickers


# =============================================================================
# STAGE 3: QUALITY VALUE - Tertiary Screen
# =============================================================================

def screen_quality_value() -> Set[str]:
    """
    Quality value stocks - strong fundamentals, reasonable price.
    
    Criteria:
    - Market cap > $2B
    - Debt/Equity < 1 (low leverage)
    - Profit margin > 10% (quality business)
    - P/E < 25 (not overvalued)
    - Analyst recommendation: Buy or better
    """
    if not FINVIZ_AVAILABLE:
        return set()
    
    tickers = set()
    try:
        foverview = FinvizOverview()
        filters = {
            'Market Cap.': '+Mid (over $2bln)',
            'Debt/Equity': 'Under 1',
            'Operating Margin': 'Positive (>0%)',
            'P/E': 'Under 25',
            'Analyst Recom.': 'Buy or better',
            'Average Volume': 'Over 300K',
        }
        foverview.set_filter(filters_dict=filters)
        df = foverview.screener_view()
        if df is not None and len(df) > 0:
            tickers = set(df['Ticker'].tolist())
        print(f"[discovery] Quality Value: {len(tickers)} stocks")
    except Exception as e:
        print(f"[discovery] Quality Value error: {e}")
    
    return tickers


# =============================================================================
# BONUS SIGNAL: INSIDER BUYING (Not a filter - just tracking)
# =============================================================================

def get_insider_buying_tickers() -> Set[str]:
    """
    Get tickers with net insider buying.
    
    This is a BONUS signal, not a filter. Stocks are not excluded
    for lacking insider buying (MU had insider selling but great fundamentals).
    """
    if not FINVIZ_AVAILABLE:
        return set()
    
    tickers = set()
    try:
        foverview = FinvizOverview()
        filters = {
            'Market Cap.': '+Small (over $300mln)',
            'InsiderTransactions': 'Positive (>0%)',
            'Average Volume': 'Over 100K',
        }
        foverview.set_filter(filters_dict=filters)
        df = foverview.screener_view()
        if df is not None and len(df) > 0:
            tickers = set(df['Ticker'].tolist())
        print(f"[discovery] Insider Buying (bonus signal): {len(tickers)} stocks")
    except Exception as e:
        print(f"[discovery] Insider Buying error: {e}")
    
    return tickers


def get_openinsider_cluster() -> Set[str]:
    """
    Scrape OpenInsider for cluster buying (multiple insiders).
    
    This is a BONUS signal - strongest conviction when combined with fundamentals.
    """
    tickers = set()
    url = "http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=14&fdr=&td=0&tdr=&fdlyl=&fdlyh=&dtefrom=&dteto=&xp=1&vl=&vh=&ocl=&och=&session=on&cnt=100"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", {"class": "tinytable"})
        
        if not table:
            return tickers
            
        ticker_counts = {}
        rows = table.find_all("tr")[1:]
        
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 4:
                ticker_cell = cells[3] if len(cells) > 3 else cells[2]
                ticker_link = ticker_cell.find("a")
                if ticker_link:
                    ticker = ticker_link.text.strip().upper()
                    if ticker and re.match(r'^[A-Z]{1,5}$', ticker):
                        ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
        
        # Cluster = 2+ insider purchases
        tickers = {t for t, count in ticker_counts.items() if count >= 2}
        print(f"[discovery] OpenInsider cluster: {len(tickers)} stocks with 2+ insider buys")
        
    except requests.exceptions.Timeout:
        print("[discovery] OpenInsider: Request timed out")
    except Exception as e:
        print(f"[discovery] OpenInsider error: {e}")
    
    return tickers


# =============================================================================
# MAIN DISCOVERY FUNCTION
# =============================================================================

def discover_candidates(
    core_watchlist: list[str],
    max_total: int = 50
) -> Dict:
    """
    Run fundamentals-first discovery pipeline.
    
    Strategy: Quality > Growth > Value (insider is bonus, not filter)
    
    Returns dict with:
    - tickers: Final watchlist
    - insider_tickers: Set of tickers with insider buying (for scoring boost)
    """
    print("\n" + "="*60)
    print("DISCOVERY SCAN - Fundamentals First (Quality > Growth > Value)")
    print("="*60)
    
    core_set = set(t.upper() for t in core_watchlist)
    
    # === PRIMARY SCREENS (fundamentals-based) ===
    
    # Screen 1: Quality Growth (GARP) - would catch MU
    quality_growth = screen_quality_growth()
    time.sleep(2)
    
    # Screen 2: Undervalued Growth (PEG < 1)
    undervalued_growth = screen_undervalued_growth()
    time.sleep(2)
    
    # Screen 3: Quality Value (low debt, good margins)
    quality_value = screen_quality_value()
    time.sleep(2)
    
    # === BONUS SIGNALS (for scoring, not filtering) ===
    
    insider_finviz = get_insider_buying_tickers()
    time.sleep(1)
    
    insider_openinsider = get_openinsider_cluster()
    
    all_insider = insider_finviz | insider_openinsider
    
    # === BUILD PRIORITIZED LIST ===
    
    # Start with core watchlist
    result = list(core_watchlist)
    seen = set(core_set)
    
    # Priority 1: Stocks in MULTIPLE fundamental screens (highest conviction)
    multi_screen = (quality_growth & undervalued_growth) | (quality_growth & quality_value) | (undervalued_growth & quality_value)
    for t in sorted(multi_screen - seen):
        if len(result) < max_total:
            result.append(t)
            seen.add(t)
    
    print(f"[discovery] Multi-screen overlap (highest conviction): {len(multi_screen)} stocks")
    
    # Priority 2: Fundamental screens + insider (bonus boost)
    fundamentals_with_insider = (quality_growth | undervalued_growth | quality_value) & all_insider
    for t in sorted(fundamentals_with_insider - seen):
        if len(result) < max_total:
            result.append(t)
            seen.add(t)
    
    print(f"[discovery] Fundamentals + insider bonus: {len(fundamentals_with_insider)} stocks")
    
    # Priority 3: Quality Growth (GARP) - main screen
    for t in sorted(quality_growth - seen):
        if len(result) < max_total:
            result.append(t)
            seen.add(t)
    
    # Priority 4: Undervalued Growth
    for t in sorted(undervalued_growth - seen):
        if len(result) < max_total:
            result.append(t)
            seen.add(t)
    
    # Priority 5: Quality Value
    for t in sorted(quality_value - seen):
        if len(result) < max_total:
            result.append(t)
            seen.add(t)
    
    result = result[:max_total]
    
    core_count = len(core_set)
    discovered = len(result) - core_count
    
    print(f"\n[discovery] Final watchlist: {len(result)} tickers ({core_count} core + {discovered} discovered)")
    print("="*60 + "\n")
    
    return {
        "tickers": result,
        "insider_tickers": all_insider,  # For scoring boost
        "multi_screen": multi_screen,     # Highest conviction
    }


# =============================================================================
# CACHE FUNCTIONS
# =============================================================================

def save_watchlist(data: Dict) -> None:
    """Save discovery results to cache file."""
    cache = {
        "updated_at": datetime.now().isoformat(),
        "tickers": data["tickers"],
        "insider_tickers": list(data.get("insider_tickers", [])),
        "multi_screen": list(data.get("multi_screen", [])),
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"[discovery] Saved {len(data['tickers'])} tickers to cache")


def load_watchlist(core_watchlist: list[str]) -> Dict:
    """
    Load watchlist from cache, falling back to core if missing/stale.
    
    Returns dict with tickers, insider_tickers, from_cache flag.
    """
    default = {
        "tickers": list(core_watchlist),
        "insider_tickers": set(),
        "multi_screen": set(),
        "from_cache": False,
    }
    
    if not os.path.exists(CACHE_FILE):
        return default
    
    try:
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
        
        cached_date = datetime.fromisoformat(cache["updated_at"]).date()
        if cached_date == datetime.now().date():
            print(f"[discovery] Using cached watchlist ({len(cache['tickers'])} tickers from {cache['updated_at'][:16]})")
            return {
                "tickers": cache["tickers"],
                "insider_tickers": set(cache.get("insider_tickers", [])),
                "multi_screen": set(cache.get("multi_screen", [])),
                "from_cache": True,
            }
        else:
            print(f"[discovery] Cache stale (from {cached_date}), using core watchlist")
            return default
            
    except Exception as e:
        print(f"[discovery] Cache read error: {e}")
        return default


def run_discovery_and_cache(core_watchlist: list[str], max_total: int = 50) -> Dict:
    """Run discovery and save results to cache."""
    data = discover_candidates(core_watchlist, max_total)
    save_watchlist(data)
    return data


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    test_core = ["AAPL", "NVDA", "MSFT", "MU"]
    result = discover_candidates(test_core, max_total=30)
    
    print("\nDiscovered candidates:")
    for i, t in enumerate(result["tickers"], 1):
        markers = []
        if t in test_core:
            markers.append("core")
        if t in result.get("multi_screen", set()):
            markers.append("multi-screen")
        if t in result.get("insider_tickers", set()):
            markers.append("insider+")
        marker = f"({', '.join(markers)})" if markers else ""
        print(f"  {i:2}. {t} {marker}")
