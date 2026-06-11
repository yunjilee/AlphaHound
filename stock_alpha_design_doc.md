# AlphaHound — Stock Discovery System Design Doc

## Overview

A Python-based stock scanner for retail investors seeking quality growth stocks for 1-2 year investment horizons. Uses a **fundamentals-first approach** (Quality → Growth → Value) with insider buying as a confirmation catalyst.

**Investment Philosophy:** Find institutional-quality companies ($2B+ market cap) with strong fundamentals that are reasonably priced relative to their growth. Insider buying is a bonus signal that adds conviction, not a gating filter.

**Why fundamentals-first?** Backtesting showed that insider-first approaches miss great opportunities. Example: MU (Micron) in early 2025 had excellent fundamentals (ROE 40%, PEG 0.08, Forward P/E << Trailing P/E) but insider selling. A fundamentals-first approach catches these; insider-first would filter them out.

**Goals:**
- Discover quality growth stocks via multi-factor Finviz screening
- Score stocks on fundamentals + alternative data (max 20 pts)
- Prioritize stocks appearing in multiple screens (highest conviction)
- Alert via Telegram for high-scoring tickers

**Non-goals (MVP):**
- No live trading / brokerage integration
- No ML model training (rule-based scoring only)
- No real-time streaming (batch scans only)

---

## Design Review: Quant Perspective

### Is This Realistically Useful?

**YES, with caveats.** This system provides genuine value for retail investors who:
1. Don't have Bloomberg/FactSet/Capital IQ subscriptions ($20K+/year)
2. Want systematic screening rather than stock tips from Reddit
3. Have a 1-2 year investment horizon (not day trading)

**What it does well:**
- Multi-factor fundamental screening (the core of institutional investing)
- Forward P/E < Trailing P/E check (a legitimate GARP signal)
- Multi-screen overlap detection (reduces false positives)
- Systematic logging for tracking performance over time

**What it cannot do:**
- Compete with institutional-grade data (their data is faster, cleaner, more granular)
- Predict short-term price moves (no one can reliably)
- Replace deep fundamental research (this is screening, not analysis)

### Is the Scoring Methodology Sound?

**Partially.** The current scoring has strengths and weaknesses:

**Strengths:**
| Component | Rationale | Academic Support |
|-----------|-----------|------------------|
| PEG ratio | Growth at Reasonable Price | Lynch (1989), widely used |
| ROE > 15% | Quality filter | Novy-Marx (2013) quality factor |
| Forward P/E < Trailing | Earnings growth confirmation | Implied by analyst estimates |
| Insider buying | Information asymmetry | Lakonishok & Lee (2001) |

**Weaknesses:**
| Issue | Problem | Mitigation |
|-------|---------|------------|
| Analyst targets are biased | Sell-side analysts have conflicts | Use as relative ranking, not absolute |
| PEG ignores balance sheet | High-growth + high-debt is risky | Added debt/equity check |
| Reddit/Trends are noise | Retail sentiment is unreliable | Low weight (1 pt max), treat as curiosity |
| No momentum factor | Missing proven alpha source | Could add RSI/price momentum in v2 |

**Recommendation:** The scoring is reasonable for a free tool. Institutional traders wouldn't use it as-is, but sophisticated retail investors could use it as a first-pass screener before doing their own research.

### Is Daily/Hourly Cadence Sustainable?

**Yes, but with careful rate limiting.**

| Source | Rate Limit | Sustainable Cadence | Notes |
|--------|------------|---------------------|-------|
| Finviz (finvizfinance) | ~100 pages/min | 1x daily | 4 screens × ~20 pages each = ~2 min |
| yfinance | ~2000/hour | 50 tickers hourly | 1.5s delay between tickers |
| Google Trends | ~10-20/hour | Skip or 1x daily | Very aggressive rate limiting |
| Reddit (PRAW) | 60 req/min | 50 tickers hourly | With proper OAuth |
| SEC EDGAR | 10 req/sec | 50 tickers hourly | Must include User-Agent |
| OpenInsider | Unknown | 1x daily | Be conservative |
| RSS feeds | Unlimited | Hourly | Most reliable source |

**Recommended cadence:**
```
Discovery (python discover.py):  1x daily at 6 AM
  - Finviz screens: 4 screens, ~5 min total
  - OpenInsider: 1 request
  - Output: Cached watchlist for the day

Scan (python main.py):           Hourly during market hours
  - 50 tickers × 5 sources = ~250 API calls
  - With 1.5s delays = ~6 min per scan
  - Skip Google Trends (rate limited) or sample 10 tickers
```

**Google Trends caveat:** The pytrends library gets 429 errors aggressively. Either:
1. Skip it entirely (sentiment from Reddit/news is sufficient)
2. Only check top 10 scoring tickers
3. Use daily cadence only

### Would Real Traders Use This?

**Retail traders:** Yes, if they understand the limitations. This is comparable to free Finviz screeners but with automated monitoring and Telegram alerts.

**Professional traders:** No. They have:
- Bloomberg Terminal ($24K/year) with real-time data
- FactSet/Capital IQ with standardized financials
- Alternative data feeds (satellite imagery, credit card data)
- Execution algorithms and dark pool access

**This tool's niche:** Sophisticated retail investors who:
- Want to systematically screen the market
- Don't trust Reddit/Discord stock tips
- Can't afford professional tools
- Will do their own DD after screening

---

## Architecture

### Project Structure

```
AlphaHound/
├── discover.py          # Discovery script — run DAILY
├── main.py              # Scan script — run HOURLY  
├── config.py            # Configuration (watchlist, thresholds)
├── scoring.py           # Composite alpha scoring (max 20 pts)
├── alerts.py            # Telegram notifications
├── storage.py           # SQLite signal logging + prioritization
├── data/
│   ├── discovery.py     # Fundamentals-first discovery (Finviz screens)
│   ├── fundamentals.py  # yfinance (ROE, margins, P/E, PEG, growth)
│   ├── reddit.py        # PRAW (mention velocity)
│   ├── insider.py       # SEC EDGAR (Form 4 insider trades)
│   ├── trends.py        # Google Trends (retail interest)
│   └── news.py          # RSS feeds (headlines, figure mentions)
├── test_setup.py        # Verify all APIs work
├── requirements.txt     # Dependencies
└── .env                 # API keys (gitignored)
```

---

## Configuration (`config.py`)

```python
# Core watchlist: always monitored (your high-conviction names)
CORE_WATCHLIST = [
    "NVDA", "MRVL", "MU", "AMD", "INTC", "QCOM",
    "TSLA", "AAPL", "MSFT", "GOOGL", "META", "AMZN",
    "DELL", "HPE", "SMCI", "ARM", "AVGO", "TSM",
]

# Discovery settings
MAX_WATCHLIST_SIZE = 100         # Max unique tickers from discovery
MAX_HOURLY_TICKERS = 50          # Cap hourly scan (rate limit sustainable)

# High-signal public figures (for news scanning)
SIGNAL_FIGURES = [
    "Jensen Huang", "Elon Musk", "Warren Buffett", "Tim Cook",
    "Satya Nadella", "Cathie Wood", "Jamie Dimon", "Powell",
]

# Scoring thresholds
ALERT_SCORE_THRESHOLD = 10.0     # Composite score to trigger alert (out of 20)

# API credentials (from .env)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
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

## Scoring Engine (`scoring.py`)

**Function:** `score_ticker(fundamentals, reddit, insider, trends, news, has_insider_buying, is_multi_screen) -> dict | None`

### Score Components (max 20 points)

The scoring is organized by investment thesis priority: Quality → Growth → Value → Catalyst → Sentiment.

```
QUALITY (max 5 pts) — Foundation of the investment
──────────────────────────────────────────────────
1. roe_score  (0–2 pts)
   = 2.0 if ROE > 25%
   = 1.5 if ROE > 15%
   = 1.0 if ROE > 10%
   = 0.0 otherwise
   # Measures profitability efficiency

2. margin_score  (0–1.5 pts)
   = 1.5 if profit_margin > 20%
   = 1.0 if profit_margin > 10%
   = 0.0 otherwise
   # High margins = pricing power

3. debt_score  (0–1.5 pts)
   = 1.5 if debt/equity < 0.5
   = 1.0 if debt/equity < 1.0
   = 0.5 if debt/equity < 1.5
   = 0.0 otherwise
   # Low leverage = financial stability

GROWTH (max 4 pts) — Future earnings power
──────────────────────────────────────────
4. eps_growth_score  (0–2 pts)
   = 2.0 if EPS growth next year > 20% (triggers "high_growth")
   = 1.0 if EPS growth next year > 10%
   = 0.0 otherwise

5. pe_discount_score  (0–2 pts) — KEY GARP SIGNAL
   = 2.0 if Forward P/E is 30%+ below Trailing P/E (triggers "pe_compression")
   = 1.0 if Forward P/E is 15%+ below Trailing P/E
   = 0.5 if Forward P/E < Trailing P/E
   = 0.0 otherwise
   # This is the core GARP signal — market hasn't priced in growth

VALUE (max 4 pts) — Reasonable entry price
──────────────────────────────────────────
6. peg_score  (0–2 pts)
   = 2.0 if PEG < 0.5 (triggers "deep_value_peg")
   = 1.5 if PEG < 1.0
   = 1.0 if PEG < 1.5
   = 0.5 if PEG < 2.0
   = 0.0 otherwise

7. analyst_upside_score  (0–2 pts)
   = 2.0 if analyst upside > 30%
   = 1.0 if analyst upside > 15%
   = 0.5 if analyst upside > 5%
   = 0.0 otherwise

CATALYST (max 4 pts) — Confirmation signals (BONUS, not filter)
───────────────────────────────────────────────────────────────
8. insider_api_score  (0–2 pts)
   = 2.0 if insider signal is "bullish" from SEC EDGAR (triggers "insider_buying")
   = 0.0 otherwise

9. insider_discovery_score  (0–1 pt)
   = 1.0 if discovered via Finviz/OpenInsider insider screen
   # Bonus for being in insider buying screen

10. multi_screen_score  (0–1 pt)
    = 1.0 if appeared in 2+ fundamental screens (triggers "multi_screen_conviction")
    # Highest conviction — multiple independent signals

SENTIMENT (max 3 pts) — Alternative data confirmation
─────────────────────────────────────────────────────
11. reddit_score  (0–1 pt)
    = 1.0 if velocity_ratio > 2.0 (triggers "reddit_spike")
    = 0.5 if velocity_ratio > 1.5
    = 0.0 otherwise

12. trends_score  (0–1 pt)
    = 1.0 if trend_ratio > 2.0 (triggers "google_trends_spike")
    = 0.5 if trend_ratio > 1.5
    = 0.0 otherwise
    # Note: Google Trends has aggressive rate limits

13. news_score  (0–1 pt)
    = 1.0 if figure_mention detected (triggers "figure_mention:NAME")
    = 0.5 if any news in last 24h
    = 0.0 otherwise

composite_score = sum of all components (max 20)
```

### Why This Weighting?

| Category | Weight | Rationale |
|----------|--------|-----------|
| Quality | 5 pts (25%) | Foundation — bad businesses don't become good investments |
| Growth | 4 pts (20%) | Forward-looking — we want improving earnings |
| Value | 4 pts (20%) | Entry price matters for returns |
| Catalyst | 4 pts (20%) | Confirmation that others see the opportunity |
| Sentiment | 3 pts (15%) | Weakest signal — treat as curiosity, not conviction |

### Alert Thresholds

```python
# Recommended thresholds
ALERT_SCORE_THRESHOLD = 10.0   # Score to trigger alert (out of 20)
MIN_QUALITY_SCORE = 2.0        # Minimum Quality component to qualify

# Alert triggers (fire regardless of score)
# - "high_growth" (EPS growth > 20%)
# - "pe_compression" (Forward P/E 30%+ below Trailing)
# - "insider_buying" (SEC EDGAR bullish signal)
# - "multi_screen_conviction" (appeared in 2+ screens)
```

### Example Output

```python
{
    "ticker": "MU",
    "composite_score": 15.5,
    "score_breakdown": {
        "roe": 2.0,           # 39.8% ROE
        "margin": 1.5,        # 41.5% profit margin
        "debt": 1.5,          # 0.15 D/E
        "eps_growth": 2.0,    # 74% EPS growth next year
        "pe_discount": 2.0,   # Forward 9.7 vs Trailing 47
        "peg": 2.0,           # PEG 0.08
        "analyst_upside": 0.0,# Target below current (analysts late)
        "insider_api": 0.0,   # No recent insider buying
        "insider_discovery": 0.0,
        "multi_screen": 1.0,  # In Quality Growth AND Undervalued Growth
        "reddit": 0.5,
        "trends": 0.5,
        "news": 0.5,
    },
    "alert_triggers": ["high_growth", "pe_compression", "deep_value_peg", "multi_screen_conviction"],
    "scored_at": "2026-06-04T19:45:00",
}
```

---

## Discovery Engine (`data/discovery.py`)

The discovery module finds new stock candidates using Finviz multi-factor screens.

### Discovery Screens

```
SCREEN 1: Quality Growth (GARP) — Primary Screen
────────────────────────────────────────────────
Filters:
  Market Cap > $2B
  PEG < 2
  ROE > 15%
  EPS growth next year > 0%
  Avg Volume > 500K

Expected results: 300-400 stocks
Would catch: MU, NVDA, GOOGL, ADBE

SCREEN 2: Undervalued Growth — Secondary Screen
───────────────────────────────────────────────
Filters:
  Market Cap > $2B
  PEG < 1 (deep value)
  Analyst Recommendation: Buy or better
  Avg Volume > 500K

Expected results: 400-500 stocks

SCREEN 3: Quality Value — Tertiary Screen
─────────────────────────────────────────
Filters:
  Market Cap > $2B
  Debt/Equity < 1
  Operating Margin > 0%
  P/E < 25
  Analyst Recommendation: Buy or better
  Avg Volume > 300K

Expected results: 300-400 stocks

BONUS: Insider Buying (tracked, not filtered)
─────────────────────────────────────────────
Finviz: InsiderTransactions > 0%
OpenInsider: 2+ insider purchases in 14 days

These stocks get +1 pt in scoring, but aren't filtered out if missing.
```

### Multi-Screen Overlap (Highest Conviction)

Stocks appearing in 2+ screens are flagged as "multi-screen" and get +1 pt bonus.

```python
# Example discovery results
{
    "tickers": ["AAPL", "NVDA", "MU", "GOOGL", ...],  # Final watchlist
    "multi_screen": {"MU", "NVDA", "ADBE", ...},      # Highest conviction
    "insider_tickers": {"AIG", "XYZ", ...},           # For scoring bonus
}
```

### Caching

Discovery results are cached to `data/watchlist_cache.json` for hourly scans:

```json
{
    "updated_at": "2026-06-04T06:00:00",
    "tickers": ["AAPL", "NVDA", "MU", ...],
    "insider_tickers": ["AIG", "XYZ"],
    "multi_screen": ["MU", "NVDA", "ADBE"]
}
```

---

## Alerts (`alerts.py`)

**Function:** `send_alert(score: dict) -> bool`

Sends a Telegram message when `composite_score >= ALERT_SCORE_THRESHOLD` or high-signal triggers detected.

Message format:
```
*MU* — Score: 15.5/20

Quality: 5.0/5 | Growth: 4.0/4 | Value: 2.0/4
Price: $108.42 -> $145.00 (+34%)
PEG: 0.08 | Analysts: 31
[triggers] high_growth, pe_compression, deep_value_peg
```

---

## Storage (`storage.py`)

SQLite database at `./data/alpha.db` for signal logging and backtesting.

---

## Main Entry Points

### `discover.py` — Daily Discovery (6 AM)

```bash
python discover.py
```

Runs Finviz screens, caches results for hourly scans.

### `main.py` — Hourly Scan

```bash
python main.py              # Scan top 50 prioritized tickers
python main.py --scan-all   # Scan ALL discovered tickers (for first run/weekends)
python main.py --core-only  # Use core watchlist only
```

Prioritization order: core watchlist → new discoveries → top scorers → multi-screen → insider.

Scans tickers, scores, alerts on triggers.

---

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required:
- **Telegram**: Message @BotFather → `/newbot` → get token
- **Reddit**: https://reddit.com/prefs/apps → Create "script" app

Optional (work without auth):
- yfinance, SEC EDGAR, RSS, Finviz

### 3. Test Setup

```bash
python test_setup.py
```

### 4. Run

```bash
# Daily discovery
python discover.py

# Hourly scan
python main.py
```

---

## Scheduling

### Linux/Mac (cron)

```bash
# Discovery: Daily at 6am PT
0 6 * * 1-5 cd /path/to/AlphaHound && python discover.py >> logs/discover.log 2>&1

# Scan: Hourly during market hours
30 6-13 * * 1-5 cd /path/to/AlphaHound && python main.py >> logs/scan.log 2>&1
```

### Windows (Task Scheduler)

| Task | Trigger | Action |
|------|---------|--------|
| AlphaHound Discovery | Daily 6:00 AM, weekdays | `python discover.py` |
| AlphaHound Scan | Hourly 6:30 AM-1 PM, weekdays | `python main.py` |

---

## Known Limitations

1. **Google Trends rate limits** — May get 429 errors. Consider skipping or using daily only.
2. **yfinance is unofficial** — May break if Yahoo changes their site.
3. **Analyst targets are biased** — Sell-side analysts have conflicts. Use as relative ranking.
4. **No momentum factor** — Could add RSI/price momentum in v2.
5. **No position sizing** — This is screening, not portfolio construction.

---

## Future Enhancements (v2)

- [ ] Add momentum factor (RSI, 6-month price performance)
- [ ] Backtest scoring thresholds against historical returns
- [ ] Add exit signals (trailing stop, target hit, degrading fundamentals)
- [ ] Discord alerts as alternative to Telegram
- [ ] Web dashboard for viewing results