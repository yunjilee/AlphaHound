# Stock Alpha Detection System — MVP Design Doc

## Overview

A Python pipeline that identifies high-upside "sleeper" stocks by combining analyst price targets with fundamental valuation signals. Sends Telegram alerts and logs all signals for future backtesting.

**Goals:**
- Detect stocks with ≥20% analyst upside that are fundamentally undervalued
- Score and rank stocks on a composite alpha score
- Alert via Telegram for high-scoring tickers; daily digest for top picks
- Log every signal to SQLite for backtesting

**Non-goals (MVP):**
- No live trading / brokerage integration
- No cloud deployment (runs locally)
- No ML model training (rule-based scoring only)
- No social media monitoring (Reddit/Twitter APIs are unreliable/costly — defer to v2)
- No real-time news monitoring (RSS polling adds complexity for marginal MVP value)

---

## Project Structure

```
stock-alpha/
├── main.py                  # Entry point, runs daily scan
├── config.py                # All config: watchlist, thresholds
├── data/
│   ├── fundamentals.py      # yfinance: price targets, P/E, PEG
│   ├── reddit.py            # PRAW: mention velocity
│   ├── insider.py           # SEC EDGAR: Form 4 insider trades
│   ├── trends.py            # Google Trends: retail interest
│   └── news.py              # RSS: headlines + figure mentions
├── scoring/
│   └── engine.py            # Composite alpha score computation
├── alerts/
│   └── telegram.py          # Telegram bot: send formatted alerts
├── storage/
│   └── db.py                # SQLite: signal logging
├── requirements.txt
└── .env                     # API keys (gitignored)
```

---

## Configuration (`config.py`)

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Watchlist: tickers to monitor
WATCHLIST = [
    "NVDA", "MRVL", "MU", "AMD", "INTC", "QCOM",
    "TSLA", "AAPL", "MSFT", "GOOGL", "META", "AMZN",
    "DELL", "HPE", "SMCI", "ARM", "AVGO", "TSM",
]

# High-signal public figures (for news scanning)
SIGNAL_FIGURES = [
    "Jensen Huang", "Elon Musk", "Warren Buffett", "Tim Cook",
    "Satya Nadella", "Cathie Wood", "Jamie Dimon", "Powell",
]

# Scoring thresholds
ANALYST_UPSIDE_MIN = 0.20          # 20% minimum analyst upside
ALERT_SCORE_THRESHOLD = 6.0        # Composite score to trigger alert (out of 15)
MIN_ANALYST_COUNT = 5              # Require minimum analyst coverage

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Reddit (free for personal use)
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")

# Database
DB_PATH = "./data/alpha.db"
```

---

## Data Layer

### `data/fundamentals.py`

Fetch per-ticker fundamental data using `yfinance`. Free, no API key required.

**Function:** `get_fundamentals(ticker: str) -> dict | None`

Returns:
```python
{
    "ticker": "MRVL",
    "current_price": 79.50,
    "analyst_target_mean": 112.00,
    "analyst_target_low": 85.00,
    "analyst_target_high": 140.00,
    "analyst_count": 28,
    "analyst_upside_pct": 0.409,      # (mean_target - current) / current
    "pe_ratio": 18.2,
    "forward_pe": 15.8,
    "peg_ratio": 1.2,                 # PE / growth rate — lower is better
    "sector": "Technology",
    "52w_low": 44.21,
    "52w_high": 117.90,
    "pct_above_52w_low": 0.797,       # (current - 52w_low) / 52w_low
    "market_cap": 68_000_000_000,
    "fetched_at": "2025-01-15T09:00:00",
}
```

Implementation:
```python
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
            "52w_low": info.get("fiftyTwoWeekLow"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "pct_above_52w_low": (current - info.get("fiftyTwoWeekLow", current)) / info.get("fiftyTwoWeekLow", current) if info.get("fiftyTwoWeekLow") else None,
            "market_cap": info.get("marketCap"),
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None
```

Notes:
- yfinance is free but unofficial — may break if Yahoo changes their site
- Rate limit yourself: add 0.5s sleep between tickers to avoid blocks
- Some fields may be None for smaller/foreign tickers

---

### `data/reddit.py`

Monitor Reddit for ticker mention velocity using PRAW. Free for personal/non-commercial use.

**Function:** `get_reddit_sentiment(ticker: str) -> dict | None`

Returns:
```python
{
    "ticker": "MRVL",
    "mentions_24h": 47,
    "mentions_7d": 156,
    "avg_daily_mentions": 22.3,
    "velocity_ratio": 2.1,           # mentions_24h / avg_daily_mentions
    "is_spike": True,                # velocity_ratio > 2.0
    "top_posts": [
        {"title": "MRVL DD - AI infrastructure play", "score": 342, "url": "..."},
    ],
    "fetched_at": "...",
}
```

Implementation:
```python
import praw
from datetime import datetime, timedelta
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET

# Initialize once at module load
reddit = None

def _get_reddit():
    global reddit
    if reddit is None:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent="stock-alpha-scanner/1.0"
        )
    return reddit


def get_reddit_sentiment(ticker: str) -> dict | None:
    """Get Reddit mention velocity for a ticker."""
    try:
        r = _get_reddit()
        subreddits = r.subreddit("stocks+investing+wallstreetbets+stockmarket")
        
        now = datetime.utcnow()
        day_ago = (now - timedelta(days=1)).timestamp()
        week_ago = (now - timedelta(days=7)).timestamp()
        
        mentions_24h = 0
        mentions_7d = 0
        top_posts = []
        
        # Search for ticker mentions (both $MRVL and MRVL)
        for post in subreddits.search(f"${ticker} OR {ticker}", sort="new", time_filter="week", limit=200):
            if post.created_utc > week_ago:
                mentions_7d += 1
                if post.created_utc > day_ago:
                    mentions_24h += 1
                    if post.score >= 50 and len(top_posts) < 3:
                        top_posts.append({
                            "title": post.title[:100],
                            "score": post.score,
                            "url": f"https://reddit.com{post.permalink}"
                        })
        
        avg_daily = mentions_7d / 7 if mentions_7d > 0 else 1
        velocity = mentions_24h / avg_daily if avg_daily > 0 else 0
        
        return {
            "ticker": ticker,
            "mentions_24h": mentions_24h,
            "mentions_7d": mentions_7d,
            "avg_daily_mentions": round(avg_daily, 1),
            "velocity_ratio": round(velocity, 2),
            "is_spike": velocity > 2.0,
            "top_posts": top_posts,
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Reddit error for {ticker}: {e}")
        return None
```

Setup:
1. Go to https://www.reddit.com/prefs/apps
2. Create app → "script" type
3. Copy `client_id` (under app name) and `client_secret` to `.env`

---

### `data/insider.py`

Monitor SEC EDGAR Form 4 filings for insider buys/sells. **Completely free, no auth.**

Insider buying is one of the strongest bullish signals — insiders must file within 2 business days.

**Function:** `get_insider_trades(ticker: str, days: int = 90) -> dict | None`

Returns:
```python
{
    "ticker": "MRVL",
    "buys_90d": 3,
    "sells_90d": 12,
    "net_shares_bought": -45000,
    "buy_value_total": 125000,       # Total $ spent on buys
    "notable_buys": [
        {
            "insider": "John Smith",
            "title": "CEO",
            "shares": 5000,
            "price": 78.50,
            "value": 392500,
            "date": "2025-01-10",
        }
    ],
    "signal": "neutral",              # "bullish" if net buyer, "neutral", "bearish"
    "fetched_at": "...",
}
```

Implementation:
```python
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

SEC_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
SEC_FILING_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

def get_insider_trades(ticker: str, days: int = 90) -> dict | None:
    """Fetch insider trades from SEC EDGAR Form 4 filings."""
    try:
        # Use SEC full-text search API
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        params = {
            "q": f'"{ticker}"',
            "dateRange": "custom",
            "startdt": cutoff,
            "enddt": datetime.now().strftime("%Y-%m-%d"),
            "forms": "4",
            "owner": "include",
        }
        
        headers = {"User-Agent": "stock-alpha-scanner admin@example.com"}  # SEC requires this
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
        
        buys = []
        sells = []
        
        for filing in filings[:50]:  # Limit to recent 50
            source = filing.get("_source", {})
            # Parse filing details (simplified - real impl would fetch full XML)
            form_data = _parse_form4_summary(source)
            if form_data:
                if form_data["transaction_type"] == "P":  # Purchase
                    buys.append(form_data)
                elif form_data["transaction_type"] == "S":  # Sale
                    sells.append(form_data)
        
        buy_value = sum(b.get("value", 0) for b in buys)
        sell_value = sum(s.get("value", 0) for s in sells)
        
        # Determine signal
        if len(buys) >= 2 and buy_value > sell_value:
            signal = "bullish"
        elif len(sells) > len(buys) * 3:
            signal = "bearish"
        else:
            signal = "neutral"
        
        return {
            "ticker": ticker,
            "buys_90d": len(buys),
            "sells_90d": len(sells),
            "buy_value_total": buy_value,
            "sell_value_total": sell_value,
            "notable_buys": sorted(buys, key=lambda x: x.get("value", 0), reverse=True)[:3],
            "signal": signal,
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"SEC EDGAR error for {ticker}: {e}")
        return None


def _parse_form4_summary(source: dict) -> dict | None:
    """Parse Form 4 filing summary from SEC search results."""
    try:
        # This is simplified - full implementation would parse the XML
        return {
            "insider": source.get("display_names", ["Unknown"])[0],
            "title": "",
            "transaction_type": "P" if "Purchase" in str(source) else "S",
            "shares": 0,
            "price": 0,
            "value": 0,
            "date": source.get("file_date", ""),
        }
    except:
        return None
```

Notes:
- SEC requires a `User-Agent` header with contact info
- Form 4 filings appear within hours of the trade
- Focus on **cluster buying** (multiple insiders buying) — strongest signal
- Ignore routine sells (often pre-planned via 10b5-1 plans)

---

### `data/trends.py`

Monitor Google Trends for retail interest spikes. **Free, no auth** (via `pytrends`).

Retail search interest often spikes *before* price moves — people Google stocks they're about to buy.

**Function:** `get_search_trends(ticker: str) -> dict | None`

Returns:
```python
{
    "ticker": "MRVL",
    "interest_today": 78,            # 0-100 scale (100 = peak interest)
    "interest_7d_avg": 42,
    "interest_30d_avg": 35,
    "trend_ratio": 1.86,             # today / 7d_avg
    "is_spike": True,                # trend_ratio > 1.5
    "related_queries": ["MRVL stock", "Marvell earnings", "MRVL price target"],
    "fetched_at": "...",
}
```

Implementation:
```python
from pytrends.request import TrendReq
from datetime import datetime
import time

def get_search_trends(ticker: str) -> dict | None:
    """Get Google Trends data for a ticker."""
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        
        # Search for "TICKER stock" to filter out non-financial results
        kw = f"{ticker} stock"
        pytrends.build_payload([kw], timeframe='today 1-m')  # Last 30 days
        
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
        except:
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
        print(f"Google Trends error for {ticker}: {e}")
        return None
```

Notes:
- `pytrends` is unofficial — may break if Google changes their site
- Rate limit: add 1-2s delay between requests to avoid blocks
- Interest values are relative (0-100 scale, not absolute search volume)
- Best for detecting *spikes*, not comparing between tickers

---

### `data/news.py`

Scan RSS feeds for ticker mentions and figure quotes. **Free, no auth.**

News articles often quote tweets/statements within hours — acts as a Twitter proxy.

**Function:** `scan_news(tickers: list[str]) -> list[dict]`

Returns:
```python
[
    {
        "ticker": "NVDA",
        "headline": "Jensen Huang says AI demand approach-ing 'the next industrial revolution'",
        "source": "CNBC",
        "url": "https://...",
        "published_at": "2025-01-15T14:32:00",
        "mentions_figure": "Jensen Huang",  # None if no figure mentioned
    },
]
```

Implementation:
```python
import feedparser
import re
from datetime import datetime, timedelta
from config import WATCHLIST

# RSS feeds to monitor (all free, no auth)
RSS_FEEDS = [
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("Reuters Business", "https://www.reutersagency.com/feed/?best-topics=business-finance"),
    ("MarketWatch", "http://feeds.marketwatch.com/marketwatch/topstories/"),
    ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml"),
]

# High-signal figures to detect
SIGNAL_FIGURES = [
    "Jensen Huang", "Elon Musk", "Warren Buffett", "Tim Cook",
    "Satya Nadella", "Cathie Wood", "Jamie Dimon", "Powell",
]

def scan_news(tickers: list[str] = None) -> list[dict]:
    """Scan RSS feeds for ticker mentions and figure quotes."""
    if tickers is None:
        tickers = WATCHLIST
    
    ticker_pattern = re.compile(r'\b(' + '|'.join(tickers) + r')\b', re.IGNORECASE)
    figure_pattern = re.compile(r'(' + '|'.join(SIGNAL_FIGURES) + r')', re.IGNORECASE)
    
    results = []
    seen_urls = set()
    cutoff = datetime.now() - timedelta(hours=24)
    
    for source_name, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:30]:  # Last 30 articles per feed
                url = entry.get("link", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Combine title and summary for matching
                text = f"{entry.get('title', '')} {entry.get('summary', '')}"
                
                # Find ticker mentions
                ticker_matches = ticker_pattern.findall(text)
                if not ticker_matches:
                    continue
                
                # Check for figure mentions
                figure_match = figure_pattern.search(text)
                
                # Parse date
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = datetime(*published[:6])
                    if pub_dt < cutoff:
                        continue
                else:
                    pub_dt = datetime.now()
                
                for ticker in set(ticker_matches):
                    results.append({
                        "ticker": ticker.upper(),
                        "headline": entry.get("title", "")[:200],
                        "source": source_name,
                        "url": url,
                        "published_at": pub_dt.isoformat(),
                        "mentions_figure": figure_match.group(1) if figure_match else None,
                    })
        except Exception as e:
            print(f"RSS error for {source_name}: {e}")
            continue
    
    return results


def get_news_for_ticker(ticker: str) -> dict:
    """Get news summary for a single ticker."""
    all_news = scan_news([ticker])
    ticker_news = [n for n in all_news if n["ticker"] == ticker]
    
    return {
        "ticker": ticker,
        "news_count_24h": len(ticker_news),
        "has_figure_mention": any(n["mentions_figure"] for n in ticker_news),
        "figure_mentioned": next((n["mentions_figure"] for n in ticker_news if n["mentions_figure"]), None),
        "top_headlines": ticker_news[:3],
        "fetched_at": datetime.now().isoformat(),
    }
```

Notes:
- RSS is extremely reliable — no auth, no rate limits
- Acts as Twitter proxy: news articles quote tweets within hours
- `mentions_figure` flag can trigger alerts for high-signal figure mentions
- Run every 30 minutes to catch breaking news

---

## Scoring Engine (`scoring/engine.py`)

**Function:** `score_ticker(fundamentals, reddit, insider, trends, news) -> dict | None`

### Score Components (max 15 points)

```
FUNDAMENTALS (max 8 pts)
─────────────────────────
1. analyst_upside_score  (0–4 pts)
   = min(analyst_upside_pct / 0.125, 4.0)
   # 12.5% upside = 1pt, 50%+ upside = 4pts

2. peg_score  (0–2 pts)
   = 2.0 if peg_ratio < 1.0 (undervalued growth)
   = 1.0 if peg_ratio < 1.5
   = 0.0 otherwise

3. analyst_coverage_score  (0–1 pt)
   = 1.0 if analyst_count >= 10

4. position_in_range_score  (0–1 pt)
   = 1.0 if in bottom 40% of 52w range

ALTERNATIVE DATA (max 7 pts)
─────────────────────────────
5. insider_score  (0–2 pts)
   = 2.0 if insider signal is "bullish" (cluster buying)
   = 0.0 otherwise
   # Strongest predictive signal

6. reddit_score  (0–1.5 pts)
   = 1.5 if velocity_ratio > 2.0 (mention spike)
   = 0.5 if velocity_ratio > 1.5
   = 0.0 otherwise

7. trends_score  (0–1.5 pts)
   = 1.5 if trend_ratio > 2.0 (Google interest spike)
   = 0.5 if trend_ratio > 1.5
   = 0.0 otherwise

8. news_score  (0–2 pts)
   = 2.0 if figure_mention detected (Jensen, Buffett, etc.)
   = 0.5 if any news in last 24h
   = 0.0 otherwise

composite_score = sum of all components (max 15)
```

Returns:
```python
{
    "ticker": "MRVL",
    "composite_score": 11.5,
    "score_breakdown": {
        "analyst_upside": 3.2,
        "peg": 2.0,
        "analyst_coverage": 1.0,
        "position_in_range": 1.0,
        "insider": 2.0,
        "reddit": 1.5,
        "trends": 0.5,
        "news": 2.0,
    },
    "signals": {
        "fundamentals": { ... },
        "reddit": { ... },
        "insider": { ... },
        "trends": { ... },
        "news": { ... },
    },
    "alert_triggers": ["insider_buying", "figure_mention:Jensen Huang", "reddit_spike"],
    "scored_at": "2025-01-15T14:45:00",
}
```

Implementation:
```python
from datetime import datetime

def score_ticker(
    fundamentals: dict,
    reddit: dict = None,
    insider: dict = None,
    trends: dict = None,
    news: dict = None,
) -> dict | None:
    """Score a ticker using all available signals."""
    if not fundamentals:
        return None
    
    f = fundamentals
    breakdown = {}
    triggers = []
    
    # === FUNDAMENTALS (max 8 pts) ===
    
    # 1. Analyst upside (0-4 pts)
    upside = f.get("analyst_upside_pct", 0)
    breakdown["analyst_upside"] = min(upside / 0.125, 4.0) if upside > 0 else 0.0
    
    # 2. PEG ratio (0-2 pts)
    peg = f.get("peg_ratio")
    if peg and 0 < peg < 1.0:
        breakdown["peg"] = 2.0
    elif peg and 0 < peg < 1.5:
        breakdown["peg"] = 1.0
    else:
        breakdown["peg"] = 0.0
    
    # 3. Analyst coverage (0-1 pt)
    breakdown["analyst_coverage"] = 1.0 if f.get("analyst_count", 0) >= 10 else 0.0
    
    # 4. Position in 52w range (0-1 pt)
    low, high, current = f.get("52w_low"), f.get("52w_high"), f.get("current_price")
    if low and high and current and high > low:
        range_pos = (current - low) / (high - low)
        breakdown["position_in_range"] = 1.0 if range_pos < 0.4 else 0.0
    else:
        breakdown["position_in_range"] = 0.0
    
    # === ALTERNATIVE DATA (max 7 pts) ===
    
    # 5. Insider trading (0-2 pts) — strongest signal
    breakdown["insider"] = 0.0
    if insider and insider.get("signal") == "bullish":
        breakdown["insider"] = 2.0
        triggers.append("insider_buying")
    
    # 6. Reddit velocity (0-1.5 pts)
    breakdown["reddit"] = 0.0
    if reddit:
        vel = reddit.get("velocity_ratio", 0)
        if vel > 2.0:
            breakdown["reddit"] = 1.5
            triggers.append("reddit_spike")
        elif vel > 1.5:
            breakdown["reddit"] = 0.5
    
    # 7. Google Trends (0-1.5 pts)
    breakdown["trends"] = 0.0
    if trends:
        ratio = trends.get("trend_ratio", 0)
        if ratio > 2.0:
            breakdown["trends"] = 1.5
            triggers.append("google_trends_spike")
        elif ratio > 1.5:
            breakdown["trends"] = 0.5
    
    # 8. News / figure mentions (0-2 pts)
    breakdown["news"] = 0.0
    if news:
        if news.get("has_figure_mention"):
            breakdown["news"] = 2.0
            triggers.append(f"figure_mention:{news.get('figure_mentioned')}")
        elif news.get("news_count_24h", 0) > 0:
            breakdown["news"] = 0.5
    
    return {
        "ticker": f["ticker"],
        "composite_score": round(sum(breakdown.values()), 2),
        "score_breakdown": breakdown,
        "signals": {
            "fundamentals": fundamentals,
            "reddit": reddit,
            "insider": insider,
            "trends": trends,
            "news": news,
        },
        "alert_triggers": triggers,
        "scored_at": datetime.now().isoformat(),
    }


def rank_watchlist(scores: list[dict]) -> list[dict]:
    """Filter and rank scored tickers."""
    from config import ANALYST_UPSIDE_MIN, MIN_ANALYST_COUNT
    
    filtered = [
        s for s in scores
        if s and s["signals"]["fundamentals"].get("analyst_upside_pct", 0) >= ANALYST_UPSIDE_MIN
        and s["signals"]["fundamentals"].get("analyst_count", 0) >= MIN_ANALYST_COUNT
    ]
    return sorted(filtered, key=lambda x: x["composite_score"], reverse=True)
```

---

## Alerts (`alerts/telegram.py`)

**Function:** `send_alert(score: dict) -> bool`

Sends a Telegram message when `composite_score >= ALERT_SCORE_THRESHOLD` or high-signal triggers detected.

Message format:
```
🔔 MRVL — Score: 11.5/15

📊 Fundamentals (7.2 pts)
   Analyst: +40% upside ($79 → $111), 28 analysts
   PEG: 0.9 (undervalued), near 52w low

⚡ Triggers
   • Insider buying detected
   • Figure mention: Jensen Huang
   • Reddit 2.3x mention spike

📈 Alt Data: insider=2.0, reddit=1.5, trends=0.5, news=2.0
```

Implementation:
```python
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram(message: str) -> bool:
    """Send a message via Telegram bot. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured, skipping alert")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
        }, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def send_alert(score: dict) -> bool:
    """Format and send alert for a high-scoring ticker."""
    f = score["signals"]["fundamentals"]
    b = score["score_breakdown"]
    triggers = score.get("alert_triggers", [])
    
    # Build trigger list
    trigger_lines = ""
    if triggers:
        trigger_lines = "\n⚡ *Triggers*\n" + "\n".join(f"   • {t}" for t in triggers)
    
    fundamental_pts = b["analyst_upside"] + b["peg"] + b["analyst_coverage"] + b["position_in_range"]
    alt_pts = b["insider"] + b["reddit"] + b["trends"] + b["news"]
    
    msg = f"""🔔 *{score['ticker']}* — Score: {score['composite_score']:.1f}/15

📊 *Fundamentals* ({fundamental_pts:.1f} pts)
   Analyst: +{f['analyst_upside_pct']*100:.0f}% upside (${f['current_price']:.0f} → ${f['analyst_target_mean']:.0f})
   PEG: {f.get('peg_ratio', 'N/A')}, {f.get('analyst_count', 0)} analysts
{trigger_lines}

📈 Alt data: insider={b['insider']:.1f}, reddit={b['reddit']:.1f}, trends={b['trends']:.1f}, news={b['news']:.1f}"""
    
    return send_telegram(msg)


def send_daily_digest(scores: list[dict]) -> bool:
    """Send daily digest of top tickers."""
    if not scores:
        return send_telegram("📋 Daily digest: No qualifying tickers today.")
    
    lines = ["📋 *Daily Alpha Digest*\n"]
    for s in scores[:5]:
        f = s["signals"]["fundamentals"]
        triggers = s.get("alert_triggers", [])
        trigger_str = f" ⚡{len(triggers)}" if triggers else ""
        lines.append(f"• *{s['ticker']}* — {s['composite_score']:.1f}/15 (+{f['analyst_upside_pct']*100:.0f}%){trigger_str}")
    
    return send_telegram("\n".join(lines))
```

---

## Storage (`storage/db.py`)

SQLite database at `./data/alpha.db`. Minimal schema for MVP.

### Tables

**`signals`** — every scored ticker instance (for backtesting)
```sql
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    composite_score REAL,
    analyst_upside_pct REAL,
    current_price REAL,
    target_price REAL,
    peg_ratio REAL,
    analyst_count INTEGER,
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);
CREATE INDEX IF NOT EXISTS idx_signals_scored_at ON signals(scored_at);
```

Implementation:
```python
import sqlite3
from contextlib import contextmanager
from config import DB_PATH

@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                composite_score REAL,
                analyst_upside_pct REAL,
                current_price REAL,
                target_price REAL,
                peg_ratio REAL,
                analyst_count INTEGER,
                scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);
            CREATE INDEX IF NOT EXISTS idx_signals_scored_at ON signals(scored_at);
        """)
        conn.commit()


def log_signal(score: dict):
    """Insert a scored signal into the database."""
    f = score["fundamentals"]
    with get_db() as conn:
        conn.execute("""
            INSERT INTO signals (ticker, composite_score, analyst_upside_pct, 
                                 current_price, target_price, peg_ratio, analyst_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            score["ticker"],
            score["composite_score"],
            f.get("analyst_upside_pct"),
            f.get("current_price"),
            f.get("analyst_target_mean"),
            f.get("peg_ratio"),
            f.get("analyst_count"),
        ))
        conn.commit()


def get_signal_history(ticker: str, days: int = 30) -> list[dict]:
    """Get historical signals for backtesting."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM signals 
            WHERE ticker = ? AND scored_at > datetime('now', ?)
            ORDER BY scored_at DESC
        """, (ticker, f'-{days} days')).fetchall()
        return [dict(r) for r in rows]
```

---

## Main Entry Point (`main.py`)

Simple script that runs once per invocation. Schedule via cron or Windows Task Scheduler.

```python
#!/usr/bin/env python3
"""Stock Alpha Scanner - Run daily via cron."""

import time
from data.fundamentals import get_fundamentals
from data.reddit import get_reddit_sentiment
from data.insider import get_insider_trades
from data.trends import get_search_trends
from data.news import get_news_for_ticker
from scoring.engine import score_ticker, rank_watchlist
from alerts.telegram import send_alert, send_daily_digest
from storage.db import init_db, log_signal
from config import WATCHLIST, ALERT_SCORE_THRESHOLD


def main():
    print(f"Scanning {len(WATCHLIST)} tickers...")
    init_db()
    
    scores = []
    for ticker in WATCHLIST:
        print(f"  {ticker}...", end=" ", flush=True)
        
        # Fetch all data sources
        fundamentals = get_fundamentals(ticker)
        if not fundamentals:
            print("fetch failed")
            continue
        
        reddit = get_reddit_sentiment(ticker)
        insider = get_insider_trades(ticker)
        trends = get_search_trends(ticker)
        news = get_news_for_ticker(ticker)
        
        # Score with all signals
        score = score_ticker(fundamentals, reddit, insider, trends, news)
        if score:
            scores.append(score)
            log_signal(score)
            triggers = score.get("alert_triggers", [])
            trigger_str = f" ⚡{','.join(triggers)}" if triggers else ""
            print(f"score={score['composite_score']:.1f}/15{trigger_str}")
        else:
            print("insufficient data")
        
        time.sleep(1.0)  # Rate limit (be nice to free APIs)
    
    # Rank and filter
    ranked = rank_watchlist(scores)
    
    # Print leaderboard
    print(f"\n{'='*60}")
    print(f"TOP TICKERS (score >= {ALERT_SCORE_THRESHOLD})")
    print(f"{'='*60}")
    for s in ranked[:10]:
        f = s["signals"]["fundamentals"]
        triggers = s.get("alert_triggers", [])
        trigger_str = f" ⚡{len(triggers)}" if triggers else ""
        print(f"{s['ticker']:6} | {s['composite_score']:5.1f}/15 | +{f['analyst_upside_pct']*100:4.0f}% upside{trigger_str}")
    
    # Send alerts for high scorers or triggered signals
    for s in ranked:
        if s["composite_score"] >= ALERT_SCORE_THRESHOLD or s.get("alert_triggers"):
            send_alert(s)
    
    # Send daily digest
    send_daily_digest(ranked)
    
    print(f"\nDone. Processed {len(scores)} tickers, {len(ranked)} qualified.")


if __name__ == "__main__":
    main()
```

### Running

**Manual:**
```bash
python main.py
```

**Daily via cron (Linux/Mac):**
```bash
# Run at 9am every weekday
0 9 * * 1-5 cd /path/to/stock-alpha && python main.py >> logs/scan.log 2>&1
```

**Daily via Task Scheduler (Windows):**
- Action: Start a program
- Program: `python`
- Arguments: `main.py`
- Start in: `C:\path\to\stock-alpha`

---

## Setup

### Prerequisites

- **Python 3.10+** installed ([download](https://www.python.org/downloads/))
- **Telegram account** (for receiving alerts)
- **Reddit account** (for sentiment API access)
- **~10 minutes** to set up all credentials

---

### Step 1: Create project structure

```bash
# Create project directory
mkdir stock-alpha && cd stock-alpha

# Create subdirectories
mkdir -p data logs

# Create Python package structure
mkdir -p data scoring alerts storage
touch data/__init__.py scoring/__init__.py alerts/__init__.py storage/__init__.py

# Create empty files (you'll fill these from the design doc)
touch config.py main.py
touch data/fundamentals.py data/reddit.py data/insider.py data/trends.py data/news.py
touch scoring/engine.py
touch alerts/telegram.py
touch storage/db.py
```

---

### Step 2: Create `.env` file

Create a file named `.env` in the project root (**do not commit this file**):

```env
# === REQUIRED ===

# Telegram Bot (for receiving alerts)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Reddit API (for sentiment tracking)
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
```

Add `.env` to `.gitignore`:
```bash
echo ".env" >> .gitignore
echo "data/alpha.db" >> .gitignore
echo "logs/" >> .gitignore
```

---

### Step 3: Get API credentials

#### 🤖 Telegram Bot — ~2 minutes

| What you need | Where it goes |
|---------------|---------------|
| Bot token | `TELEGRAM_BOT_TOKEN` |
| Your chat ID | `TELEGRAM_CHAT_ID` |

**Steps:**

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts to choose a name (e.g., "Stock Alpha Bot")
4. BotFather replies with a token like:
   ```
   110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
   ```
5. Copy this token to `.env` as `TELEGRAM_BOT_TOKEN`

**Find your chat ID:**

6. Open your new bot in Telegram and send it any message (e.g., "hello")
7. Open this URL in your browser (replace `<TOKEN>` with your actual token):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
8. Look for `"chat":{"id":123456789}` in the response
9. Copy the number (e.g., `123456789`) to `.env` as `TELEGRAM_CHAT_ID`

---

#### 🔴 Reddit API — ~3 minutes

| What you need | Where it goes |
|---------------|---------------|
| Client ID | `REDDIT_CLIENT_ID` |
| Client Secret | `REDDIT_CLIENT_SECRET` |

**Steps:**

1. Go to https://www.reddit.com/prefs/apps (log in if needed)
2. Scroll to the bottom, click **"create another app..."**
3. Fill in the form:
   - **name**: `stock-alpha-scanner`
   - **App type**: Select **script** ✅
   - **description**: (leave blank)
   - **about url**: (leave blank)
   - **redirect uri**: `http://localhost:8080` (required but not used)
4. Click **"create app"**
5. Find your credentials:
   ```
   stock-alpha-scanner
   personal use script
   ─────────────────────
   Ab3_xyzABC123def    ← This is your CLIENT_ID
   
   secret: Gh7_secretKeyHere123   ← This is your CLIENT_SECRET
   ```
6. Copy both to `.env`

---

#### ✅ No credentials needed

These sources are completely free with no signup:

| Source | Notes |
|--------|-------|
| **yfinance** | Unofficial Yahoo Finance wrapper — just works |
| **SEC EDGAR** | US government public API |
| **Google Trends** | Unofficial API via `pytrends` |
| **RSS Feeds** | Public feeds from Yahoo Finance, CNBC, Reuters, etc. |

---

### Step 4: Install dependencies

Create `requirements.txt`:
```
yfinance>=0.2.36
requests>=2.31.0
python-dotenv>=1.0.0
praw>=7.7.1
pytrends>=4.9.0
feedparser>=6.0.10
```

Install:
```bash
pip install -r requirements.txt
```

---

### Step 5: Test the setup

Create a quick test script `test_setup.py`:

```python
#!/usr/bin/env python3
"""Test that all APIs are working."""

import os
from dotenv import load_dotenv
load_dotenv()

print("Testing setup...\n")

# 1. Test environment variables
print("1. Checking .env variables...")
required = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"]
missing = [v for v in required if not os.getenv(v)]
if missing:
    print(f"   ❌ Missing: {missing}")
else:
    print("   ✅ All environment variables set")

# 2. Test yfinance
print("\n2. Testing yfinance...")
try:
    import yfinance as yf
    ticker = yf.Ticker("AAPL")
    price = ticker.info.get("currentPrice")
    print(f"   ✅ yfinance working (AAPL: ${price})")
except Exception as e:
    print(f"   ❌ yfinance error: {e}")

# 3. Test Reddit
print("\n3. Testing Reddit API...")
try:
    import praw
    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent="stock-alpha-test/1.0"
    )
    sub = reddit.subreddit("stocks")
    post = next(sub.hot(limit=1))
    print(f"   ✅ Reddit working (top post: {post.title[:50]}...)")
except Exception as e:
    print(f"   ❌ Reddit error: {e}")

# 4. Test Telegram
print("\n4. Testing Telegram...")
try:
    import requests
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
    if resp.status_code == 200:
        bot_name = resp.json()["result"]["username"]
        print(f"   ✅ Telegram working (bot: @{bot_name})")
    else:
        print(f"   ❌ Telegram error: {resp.text}")
except Exception as e:
    print(f"   ❌ Telegram error: {e}")

# 5. Test pytrends
print("\n5. Testing Google Trends...")
try:
    from pytrends.request import TrendReq
    pytrends = TrendReq()
    pytrends.build_payload(["AAPL stock"], timeframe="today 1-m")
    df = pytrends.interest_over_time()
    print(f"   ✅ Google Trends working ({len(df)} data points)")
except Exception as e:
    print(f"   ❌ Google Trends error: {e}")

# 6. Test RSS
print("\n6. Testing RSS feeds...")
try:
    import feedparser
    feed = feedparser.parse("https://finance.yahoo.com/news/rssindex")
    if feed.entries:
        print(f"   ✅ RSS working ({len(feed.entries)} articles)")
    else:
        print("   ⚠️  RSS feed empty (may be temporary)")
except Exception as e:
    print(f"   ❌ RSS error: {e}")

print("\n" + "="*50)
print("Setup complete! Run 'python main.py' to start scanning.")
```

Run it:
```bash
python test_setup.py
```

Expected output:
```
Testing setup...

1. Checking .env variables...
   ✅ All environment variables set

2. Testing yfinance...
   ✅ yfinance working (AAPL: $198.5)

3. Testing Reddit API...
   ✅ Reddit working (top post: Daily Discussion Thread...)

4. Testing Telegram...
   ✅ Telegram working (bot: @YourStockAlphaBot)

5. Testing Google Trends...
   ✅ Google Trends working (30 data points)

6. Testing RSS feeds...
   ✅ RSS working (20 articles)

==================================================
Setup complete! Run 'python main.py' to start scanning.
```

---

### Step 6: Run the scanner

```bash
python main.py
```

---

### Step 7: Schedule daily runs (optional)

**Linux/Mac (cron):**
```bash
crontab -e

# Add: Run at 6:00 AM Pacific (market opens 6:30 AM PT)
0 6 * * 1-5 cd /path/to/stock-alpha && python main.py >> logs/scan.log 2>&1
```

**Windows (Task Scheduler):**
1. Open Task Scheduler → **Create Basic Task**
2. Name: "Stock Alpha Scanner"
3. Trigger: **Daily** at 6:00 AM
4. Action: **Start a program**
   - Program: `C:\Python310\python.exe` (adjust path)
   - Arguments: `main.py`
   - Start in: `C:\path\to\stock-alpha`

---

### Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `KeyError: TELEGRAM_BOT_TOKEN` | `.env` file missing or not loaded | Ensure `.env` exists in project root |
| `prawcore.exceptions.ResponseException: 401` | Invalid Reddit credentials | Regenerate client secret at reddit.com/prefs/apps |
| `prawcore.exceptions.OAuthException` | Wrong app type | Delete app, recreate as **script** type |
| `yfinance: No price data found` | Ticker delisted or no coverage | Remove ticker from watchlist |
| `pytrends: 429 Too Many Requests` | Rate limited by Google | Increase delay to 2-3s between tickers |
| `Telegram: chat not found` | Wrong chat ID | Re-send message to bot, check getUpdates again |

---

## Error Handling

- All data fetchers return `None` on error — never crash the main loop
- `score_ticker()` handles missing signals gracefully (treats as 0 pts)
- `send_telegram()` catches network errors and logs them
- Rate limiting: 1s delay between tickers (be nice to free APIs)
- All errors print to stdout (redirect to log file via cron)
- pytrends/yfinance are unofficial — may break if upstream sites change

---

## Future Extensions (post-MVP)

1. **Backtesting module** — Query `signals` table to measure whether high-score signals predicted actual price gains at 30/60/90 day windows

2. **Streamlit dashboard** — Visual leaderboard if you want a UI:
   - Table with color-coded scores
   - Historical score charts per ticker
   - ~50 lines of code with `streamlit`

3. **13F institutional tracking** — Parse quarterly 13F filings to see what Buffett/institutions bought (45-day delay, less actionable than Form 4)

4. **Twitter/X Basic tier** — If you want real-time tweets, $100/month gets 7-day search

5. **Score decay** — Time-weight signals (recent insider buys worth more than 60-day-old ones)

6. **Watchlist expansion** — Screen all S&P 500 instead of fixed list

7. **Options flow** — Unusual options activity from CBOE RSS feeds
