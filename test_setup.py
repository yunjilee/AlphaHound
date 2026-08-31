#!/usr/bin/env python3
"""Test that all dependencies and APIs are working."""

import os
import sys


def test_env_vars():
    """Check required environment variables."""
    print("1. Checking environment variables...")
    from config import (
        SMS_CARRIER,
        SMS_ENABLED,
        SMS_GMAIL_APP_PASSWORD,
        SMS_GMAIL_USER,
        SMS_PHONE_NUMBER,
    )

    sms_configured = SMS_ENABLED and all([
        SMS_PHONE_NUMBER,
        SMS_CARRIER,
        SMS_GMAIL_USER,
        SMS_GMAIL_APP_PASSWORD,
    ])
    if not sms_configured:
        print("   [WARN] SMS notification settings are incomplete")
        return False
    print("   [OK] SMS notification settings loaded")
    return True


def test_yfinance():
    """Test yfinance API."""
    print("\n2. Testing yfinance...")
    try:
        import yfinance as yf
        ticker = yf.Ticker("AAPL")
        price = ticker.info.get("currentPrice") or ticker.info.get("regularMarketPrice")
        if price:
            print(f"   [OK] yfinance working (AAPL: ${price:.2f})")
            return True
        else:
            print("   [FAIL] yfinance returned no price data")
            return False
    except Exception as e:
        print(f"   [FAIL] yfinance error: {e}")
        return False


def test_reddit():
    """Test Reddit API."""
    print("\n3. Testing Reddit API...")
    try:
        import praw
        from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_ENABLED

        if not REDDIT_ENABLED:
            print("   [OK] Reddit integration disabled")
            return True
        
        if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
            print("   [WARN] Reddit credentials not set, skipping")
            return True
        
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent="stock-alpha-test/1.0"
        )
        sub = reddit.subreddit("stocks")
        post = next(sub.hot(limit=1))
        print(f"   [OK] Reddit working (r/stocks top: {post.title[:40]}...)")
        return True
    except Exception as e:
        print(f"   [FAIL] Reddit error: {e}")
        return False


def test_sms():
    """Test Gmail authentication without sending a text."""
    print("\n4. Testing SMS gateway authentication...")
    try:
        import smtplib
        from config import SMS_GMAIL_APP_PASSWORD, SMS_GMAIL_USER

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(SMS_GMAIL_USER, SMS_GMAIL_APP_PASSWORD)
        print("   [OK] SMS gateway Gmail authentication working")
        return True
    except (OSError, smtplib.SMTPException) as e:
        print(f"   [FAIL] SMS gateway error: {e}")
        return False


def test_pytrends():
    """Test Google Trends API."""
    print("\n5. Testing Google Trends...")
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq()
        pytrends.build_payload(["AAPL stock"], timeframe="today 1-m")
        df = pytrends.interest_over_time()
        if not df.empty:
            print(f"   [OK] Google Trends working ({len(df)} data points)")
            return True
        else:
            print("   [WARN] Google Trends returned empty data")
            return True
    except Exception as e:
        print(f"   [FAIL] Google Trends error: {e}")
        return False


def test_rss():
    """Test RSS feeds."""
    print("\n6. Testing RSS feeds...")
    try:
        import feedparser
        feed = feedparser.parse("https://finance.yahoo.com/news/rssindex")
        if feed.entries:
            print(f"   [OK] RSS working ({len(feed.entries)} articles from Yahoo Finance)")
            return True
        else:
            print("   [WARN] RSS feed empty (may be temporary)")
            return True
    except Exception as e:
        print(f"   [FAIL] RSS error: {e}")
        return False


def main():
    print("\n" + "="*50)
    print("  STOCK ALPHA SCANNER - Setup Test")
    print("="*50)
    
    results = [
        test_env_vars(),
        test_yfinance(),
        test_reddit(),
        test_sms(),
        test_pytrends(),
        test_rss(),
    ]
    
    print("\n" + "="*50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"  [OK] All {total} tests passed!")
        print("  Run 'python main.py' to start scanning.")
    else:
        print(f"  [WARN] {passed}/{total} tests passed")
        print("  Some features may not work. Check errors above.")
    
    print("="*50 + "\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
