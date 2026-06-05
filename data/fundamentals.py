"""Fetch fundamental data from Yahoo Finance."""

import yfinance as yf
from datetime import datetime


def get_fundamentals(ticker: str) -> dict | None:
    """Fetch fundamental data for a ticker. Returns None on error."""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        current = info.get("currentPrice") or info.get("regularMarketPrice")
        target_mean = info.get("targetMeanPrice")

        if not current or not target_mean:
            return None

        low_52w = info.get("fiftyTwoWeekLow")
        pct_above_low = None
        if low_52w and low_52w > 0:
            pct_above_low = (current - low_52w) / low_52w

        return {
            "ticker": ticker,
            "current_price": current,
            "analyst_target_mean": target_mean,
            "analyst_target_low": info.get("targetLowPrice"),
            "analyst_target_high": info.get("targetHighPrice"),
            "analyst_count": info.get("numberOfAnalystOpinions", 0),
            "analyst_upside_pct": (target_mean - current) / current,
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "sector": info.get("sector"),
            "52w_low": low_52w,
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "pct_above_52w_low": pct_above_low,
            "market_cap": info.get("marketCap"),
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"    [fundamentals] Error fetching {ticker}: {e}")
        return None
