"""Monitor SEC EDGAR for insider trades (Form 4 filings)."""

import requests
from datetime import datetime, timedelta


def get_insider_trades(ticker: str, days: int = 90) -> dict | None:
    """Fetch insider trades from SEC EDGAR Form 4 filings."""
    try:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # SEC full-text search API
        params = {
            "q": f'"{ticker}"',
            "dateRange": "custom",
            "startdt": cutoff,
            "enddt": datetime.now().strftime("%Y-%m-%d"),
            "forms": "4",
        }
        
        headers = {
            "User-Agent": "stock-alpha-scanner contact@example.com",
            "Accept": "application/json",
        }
        
        resp = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params=params,
            headers=headers,
            timeout=15
        )
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        filings = data.get("hits", {}).get("hits", [])
        
        buys = 0
        sells = 0
        buy_value = 0
        notable_buys = []
        
        for filing in filings[:50]:
            source = filing.get("_source", {})
            # Parse basic info from search results
            file_desc = str(source.get("file_description", "")).lower()
            display_names = source.get("display_names", [])
            file_date = source.get("file_date", "")
            
            # Heuristic: check if it's a purchase or sale based on form description
            # Real implementation would fetch and parse the full XML
            if "purchase" in file_desc or "acquired" in file_desc:
                buys += 1
                if display_names and len(notable_buys) < 3:
                    notable_buys.append({
                        "insider": display_names[0] if display_names else "Unknown",
                        "date": file_date,
                        "type": "purchase",
                    })
            elif "sale" in file_desc or "disposed" in file_desc:
                sells += 1
        
        # Determine signal based on buy/sell ratio
        if buys >= 2 and buys > sells:
            signal = "bullish"
        elif sells > buys * 3:
            signal = "bearish"
        else:
            signal = "neutral"
        
        return {
            "ticker": ticker,
            "buys_90d": buys,
            "sells_90d": sells,
            "buy_value_total": buy_value,
            "notable_buys": notable_buys,
            "signal": signal,
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"    [insider] Error for {ticker}: {e}")
        return None
