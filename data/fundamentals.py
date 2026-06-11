"""Fetch fundamental data from Yahoo Finance."""

import yfinance as yf
from datetime import datetime


def get_fundamentals(ticker: str) -> dict | None:
    """
    Fetch fundamental data for a ticker.
    
    Returns comprehensive fundamentals for Quality > Growth > Value scoring:
    - Quality: ROE, profit margin, debt/equity
    - Growth: EPS growth, revenue growth, forward P/E
    - Value: PEG, trailing P/E, 52w range position
    
    Returns None on error.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info

        current = info.get("currentPrice") or info.get("regularMarketPrice")
        target_mean = info.get("targetMeanPrice")
        previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

        if not current:
            return None

        # Daily price change
        daily_change_pct = None
        if previous_close and previous_close > 0:
            daily_change_pct = (current - previous_close) / previous_close

        # 52-week range position
        low_52w = info.get("fiftyTwoWeekLow")
        high_52w = info.get("fiftyTwoWeekHigh")
        pct_above_low = None
        pct_below_high = None
        if low_52w and low_52w > 0:
            pct_above_low = (current - low_52w) / low_52w
        if high_52w and high_52w > 0:
            pct_below_high = (high_52w - current) / high_52w

        # Analyst upside
        analyst_upside = None
        if target_mean and current:
            analyst_upside = (target_mean - current) / current

        # Forward vs Trailing P/E
        forward_pe = info.get("forwardPE")
        trailing_pe = info.get("trailingPE")
        
        # EPS growth estimate (next year)
        eps_growth_next = info.get("earningsGrowth")  # TTM growth
        # Better: use earningsQuarterlyGrowth or estimate forward growth
        if not eps_growth_next:
            # Fallback: calculate from forward vs trailing EPS
            fwd_eps = info.get("forwardEps")
            trail_eps = info.get("trailingEps")
            if fwd_eps and trail_eps and trail_eps > 0:
                eps_growth_next = (fwd_eps - trail_eps) / trail_eps

        return {
            "ticker": ticker,
            
            # Price & Range
            "current_price": current,
            "previous_close": previous_close,
            "daily_change_pct": daily_change_pct,
            "52w_low": low_52w,
            "52w_high": high_52w,
            "pct_above_52w_low": pct_above_low,
            "pct_below_52w_high": pct_below_high,
            
            # Analyst
            "analyst_target_mean": target_mean,
            "analyst_target_low": info.get("targetLowPrice"),
            "analyst_target_high": info.get("targetHighPrice"),
            "analyst_count": info.get("numberOfAnalystOpinions", 0),
            "analyst_upside_pct": analyst_upside,
            "recommendation": info.get("recommendationKey"),
            
            # Valuation
            "trailing_pe": trailing_pe,
            "forward_pe": forward_pe,
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            
            # Quality - Key GARP metrics
            "return_on_equity": info.get("returnOnEquity"),  # ROE
            "return_on_assets": info.get("returnOnAssets"),  # ROA
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "gross_margin": info.get("grossMargins"),
            "debt_to_equity": info.get("debtToEquity"),  # Note: yfinance returns as ratio*100
            
            # Growth
            "eps_growth_next_year": eps_growth_next,
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
            
            # Cash flow
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
            
            # Other
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "avg_volume": info.get("averageVolume"),
            
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"    [fundamentals] Error fetching {ticker}: {e}")
        return None
