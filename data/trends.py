"""Monitor Google Trends for retail interest spikes."""

import warnings
from datetime import datetime

from config import TRENDS_ENABLED

_pytrends = None
_trends_disabled = not TRENDS_ENABLED


def _get_client():
    """Reuse one client for the scan."""
    global _pytrends
    if _trends_disabled:
        return None
    if _pytrends is None:
        from pytrends.request import TrendReq
        _pytrends = TrendReq(hl="en-US", tz=360)
    return _pytrends


def get_search_trends(ticker: str) -> dict | None:
    """Get Google Trends data for a ticker."""
    global _trends_disabled
    try:
        pytrends = _get_client()
        if pytrends is None:
            return None
        
        # Search for "TICKER stock" to filter non-financial results
        kw = f"{ticker} stock"
        pytrends.build_payload([kw], timeframe="today 1-m")
        
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Downcasting object dtype arrays",
                category=FutureWarning,
            )
            df = pytrends.interest_over_time()
        if df.empty:
            return None
        
        values = df[kw].tolist()
        
        # Calculate averages
        today = values[-1] if values else 0
        avg_7d = sum(values[-7:]) / min(7, len(values)) if values else 0
        avg_30d = sum(values) / len(values) if values else 0
        
        trend_ratio = today / avg_7d if avg_7d > 0 else 0
        
        return {
            "ticker": ticker,
            "interest_today": today,
            "interest_7d_avg": round(avg_7d, 1),
            "interest_30d_avg": round(avg_30d, 1),
            "trend_ratio": round(trend_ratio, 2),
            "is_spike": trend_ratio > 1.5,
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as error:
        if "429" in str(error):
            _trends_disabled = True
            print("    [trends] Rate limited; disabled for the rest of this scan")
        else:
            print(f"    [trends] Request failed for {ticker}: {error}")
        return None
