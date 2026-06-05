"""Monitor Google Trends for retail interest spikes."""

from datetime import datetime


def get_search_trends(ticker: str) -> dict | None:
    """Get Google Trends data for a ticker."""
    try:
        from pytrends.request import TrendReq
        
        pytrends = TrendReq(hl='en-US', tz=360)
        
        # Search for "TICKER stock" to filter non-financial results
        kw = f"{ticker} stock"
        pytrends.build_payload([kw], timeframe='today 1-m')
        
        df = pytrends.interest_over_time()
        if df.empty:
            return None
        
        values = df[kw].tolist()
        
        # Calculate averages
        today = values[-1] if values else 0
        avg_7d = sum(values[-7:]) / min(7, len(values)) if values else 0
        avg_30d = sum(values) / len(values) if values else 0
        
        trend_ratio = today / avg_7d if avg_7d > 0 else 0
        
        # Get related queries
        related = []
        try:
            pytrends.build_payload([kw], timeframe='today 1-m')
            related_df = pytrends.related_queries()
            if kw in related_df and related_df[kw]['rising'] is not None:
                related = related_df[kw]['rising']['query'].head(5).tolist()
        except Exception:
            pass
        
        return {
            "ticker": ticker,
            "interest_today": today,
            "interest_7d_avg": round(avg_7d, 1),
            "interest_30d_avg": round(avg_30d, 1),
            "trend_ratio": round(trend_ratio, 2),
            "is_spike": trend_ratio > 1.5,
            "related_queries": related,
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"    [trends] Error for {ticker}: {e}")
        return None
