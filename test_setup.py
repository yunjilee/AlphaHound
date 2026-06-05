#!/usr/bin/env python3
"""Test that all dependencies and APIs are working."""

import os
import sys


def test_env_vars():
    """Check required environment variables."""
    print("1. Checking environment variables...")
    from dotenv import load_dotenv
    load_dotenv()
    
    required = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"]
    missing = [v for v in required if not os.getenv(v)]
    
    if missing:
        print(f"   ⚠️  Missing (alerts/reddit may not work): {missing}")
        return False
    print("   ✅ All environment variables set")
    return True


def test_yfinance():
    """Test yfinance API."""
    print("\n2. Testing yfinance...")
    try:
        import yfinance as yf
        ticker = yf.Ticker("AAPL")
        price = ticker.info.get("currentPrice") or ticker.info.get("regularMarketPrice")
        if price:
            print(f"   ✅ yfinance working (AAPL: ${price:.2f})")
            return True
        else:
            print("   ❌ yfinance returned no price data")
            return False
    except Exception as e:
        print(f"   ❌ yfinance error: {e}")
        return False


def test_reddit():
    """Test Reddit API."""
    print("\n3. Testing Reddit API...")
    try:
        import praw
        from dotenv import load_dotenv
        load_dotenv()
        
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            print("   ⚠️  Reddit credentials not set, skipping")
            return True
        
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="stock-alpha-test/1.0"
        )
        sub = reddit.subreddit("stocks")
        post = next(sub.hot(limit=1))
        print(f"   ✅ Reddit working (r/stocks top: {post.title[:40]}...)")
        return True
    except Exception as e:
        print(f"   ❌ Reddit error: {e}")
        return False


def test_telegram():
    """Test Telegram API."""
    print("\n4. Testing Telegram...")
    try:
        import requests
        from dotenv import load_dotenv
        load_dotenv()
        
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            print("   ⚠️  Telegram token not set, skipping")
            return True
        
        resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
        if resp.status_code == 200:
            bot_name = resp.json()["result"]["username"]
            print(f"   ✅ Telegram working (bot: @{bot_name})")
            return True
        else:
            print(f"   ❌ Telegram error: {resp.text}")
            return False
    except Exception as e:
        print(f"   ❌ Telegram error: {e}")
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
            print(f"   ✅ Google Trends working ({len(df)} data points)")
            return True
        else:
            print("   ⚠️  Google Trends returned empty data")
            return True
    except Exception as e:
        print(f"   ❌ Google Trends error: {e}")
        return False


def test_rss():
    """Test RSS feeds."""
    print("\n6. Testing RSS feeds...")
    try:
        import feedparser
        feed = feedparser.parse("https://finance.yahoo.com/news/rssindex")
        if feed.entries:
            print(f"   ✅ RSS working ({len(feed.entries)} articles from Yahoo Finance)")
            return True
        else:
            print("   ⚠️  RSS feed empty (may be temporary)")
            return True
    except Exception as e:
        print(f"   ❌ RSS error: {e}")
        return False


def main():
    print("\n" + "="*50)
    print("  STOCK ALPHA SCANNER — Setup Test")
    print("="*50)
    
    results = [
        test_env_vars(),
        test_yfinance(),
        test_reddit(),
        test_telegram(),
        test_pytrends(),
        test_rss(),
    ]
    
    print("\n" + "="*50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"  ✅ All {total} tests passed!")
        print("  Run 'python main.py' to start scanning.")
    else:
        print(f"  ⚠️  {passed}/{total} tests passed")
        print("  Some features may not work. Check errors above.")
    
    print("="*50 + "\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
