# Stock Alpha Detection System — MVP Design Doc

## Overview

A Python pipeline that identifies high-upside "sleeper" stocks by combining analyst price targets, fundamental valuation signals, Reddit sentiment, and real-time public figure mentions. Sends near-instant Telegram alerts and logs all signals for future backtesting.

**Goals:**
- Detect stocks with >25% analyst upside that are fundamentally undervalued
- Monitor for mentions of tickers by named high-signal public figures (Jensen Huang, Trump, Buffett, etc.)
- Score and rank stocks on a composite alpha score
- Alert via Telegram in near real-time for figure mentions; daily digest for top fundamental picks
- Log every signal to SQLite for backtesting

**Non-goals (MVP):**
- No live trading / brokerage integration
- No cloud deployment (runs locally)
- No ML model training (rule-based scoring only)

---

## Project Structure

```
stock-alpha/
├── main.py                  # Entry point, starts scheduler
├── config.py                # All config: watchlist, thresholds, API keys
├── data/
│   ├── fundamentals.py      # yfinance: price targets, P/E, earnings
│   ├── sentiment.py         # Reddit PRAW: mention volume + velocity
│   ├── news.py              # RSS / NewsAPI: news headlines
│   └── twitter.py           # Nitter scraper: public figure tweets
├── scoring/
│   └── engine.py            # Composite alpha score computation
├── alerts/
│   └── telegram.py          # Telegram bot: send formatted alerts
├── storage/
│   └── db.py                # SQLite: signal logging, dedup
├── dashboard/
│   └── app.py               # Streamlit: leaderboard + score breakdown
├── requirements.txt
└── .env                     # API keys (gitignored)
```

---

## Configuration (`config.py`)

```python
# Watchlist: tickers to monitor for fundamental signals
WATCHLIST = [
    "NVDA", "MRVL", "MU", "AMD", "INTC", "QCOM",
    "TSLA", "AAPL", "MSFT", "GOOGL", "META", "AMZN",
    "DELL", "HPE", "SMCI", "ARM", "AVGO", "TSM",
]

# High-signal public figures to monitor
# Maps display name -> list of identifiers to search for in text
SIGNAL_FIGURES = {
    "Jensen Huang":    ["Jensen Huang", "Jensen", "@nvidia_jensen"],
    "Donald Trump":    ["Trump", "Donald Trump", "@realDonaldTrump"],
    "Warren Buffett":  ["Buffett", "Warren Buffett", "Berkshire"],
    "Elon Musk":       ["Elon Musk", "@elonmusk"],
    "Cathie Wood":     ["Cathie Wood", "ARK Invest", "@CathieDWood"],
}

# Scoring thresholds
ANALYST_UPSIDE_MIN = 0.20        # 20% minimum analyst upside to be considered
ALERT_SCORE_THRESHOLD = 5.0      # Composite score to trigger a Telegram alert
SENTIMENT_SPIKE_MULTIPLIER = 3.0 # Reddit mention velocity vs 7-day avg to flag spike

# Scheduler intervals
FUNDAMENTALS_INTERVAL_HOURS = 24
NEWS_INTERVAL_MINUTES = 30
TWITTER_INTERVAL_MINUTES = 15

# Telegram
TELEGRAM_BOT_TOKEN = ""   # loaded from .env
TELEGRAM_CHAT_ID = ""     # loaded from .env

# Reddit (PRAW)
REDDIT_CLIENT_ID = ""
REDDIT_CLIENT_SECRET = ""
REDDIT_USER_AGENT = "stock-alpha-bot/1.0"

# NewsAPI
NEWS_API_KEY = ""         # optional; falls back to RSS if empty

# Subreddits to monitor
REDDIT_SUBREDDITS = ["stocks", "investing", "wallstreetbets", "SecurityAnalysis"]

# RSS feeds
RSS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://feeds.reuters.com/reuters/businessNews",
]

# Nitter instances (public figure Twitter monitoring)
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
]
TWITTER_ACCOUNTS_TO_MONITOR = [
    "realDonaldTrump",
    "elonmusk",
    "CathieDWood",
]
```

---

## Data Layer

### `data/fundamentals.py`

Fetch per-ticker fundamental data using `yfinance`. Called once daily.

**Function:** `get_fundamentals(ticker: str) -> dict`

Returns:
```python
{
    "ticker": "MRVL",
    "current_price": 79.50,
    "analyst_target_mean": 112.00,
    "analyst_target_median": 108.00,
    "analyst_target_high": 140.00,
    "analyst_count": 28,
    "analyst_upside_pct": 0.358,      # (median_target - current) / current
    "pe_ratio": 18.2,
    "sector": "Technology",
    "sector_pe_median": 28.5,         # computed from peers
    "pe_discount": True,              # pe_ratio < sector_pe_median
    "next_earnings_date": "2025-03-05",
    "earnings_within_30_days": False,
    "52w_low": 44.21,
    "52w_high": 117.90,
    "pct_from_52w_low": 0.797,
    "market_cap": 68_000_000_000,
    "fetched_at": "2025-01-15T09:00:00",
}
```

Implementation notes:
- Use `yf.Ticker(ticker).info` for most fields
- Use `yf.Ticker(ticker).analyst_price_targets` for consensus targets
- For sector P/E median, fetch 5 peer tickers from the same sector and compute median
- Cache results in SQLite for 24 hours to avoid redundant API calls
- Handle missing fields gracefully (some tickers have no analyst coverage)

---

### `data/sentiment.py`

Monitor Reddit for ticker mention volume and velocity. Called every 30 minutes.

**Function:** `get_reddit_sentiment(ticker: str) -> dict`

Returns:
```python
{
    "ticker": "MRVL",
    "mentions_1h": 14,
    "mentions_24h": 89,
    "mentions_7d_avg_per_hour": 3.8,
    "velocity_ratio": 3.68,           # mentions_1h / 7d_avg_per_hour
    "is_spike": True,                 # velocity_ratio > SENTIMENT_SPIKE_MULTIPLIER
    "top_posts": [
        {"title": "...", "score": 412, "url": "..."},
    ],
    "fetched_at": "...",
}
```

Implementation notes:
- Use `praw.Reddit` to search each subreddit for `$TICKER` and `TICKER` (e.g. `$MRVL` and `MRVL`)
- Count posts + comments containing the ticker in the last 1h, 24h, 7d windows
- Store hourly counts in SQLite to compute rolling 7-day average
- Apply basic noise filter: skip posts with score < 5

---

### `data/news.py`

Scan RSS feeds and optionally NewsAPI for headlines. Extract (ticker, figure) pairs.

**Function:** `scan_news() -> list[dict]`

Returns a list of signal events:
```python
[
    {
        "type": "figure_mention",
        "figure": "Jensen Huang",
        "ticker": "MRVL",
        "headline": "Jensen Huang highlights Marvell as key AI infrastructure partner",
        "source": "CNBC",
        "url": "https://...",
        "published_at": "2025-01-15T14:32:00",
    },
    {
        "type": "ticker_news",
        "ticker": "DELL",
        "headline": "Dell Technologies surges after Trump mentions it at rally",
        "source": "Reuters",
        "url": "https://...",
        "published_at": "...",
    }
]
```

Implementation notes:
- Use `feedparser` to parse all RSS_FEEDS
- For each article, scan headline + summary for:
  1. Any ticker in WATCHLIST (word-boundary regex: `\bMRVL\b`)
  2. Any figure name in SIGNAL_FIGURES
- If both a figure and a ticker appear in the same article → emit `figure_mention` event
- Deduplicate by URL (store seen URLs in SQLite)
- If NEWS_API_KEY is set, also query NewsAPI with `q="Jensen Huang stock"` etc.

---

### `data/twitter.py`

Scrape Nitter for tweets from monitored accounts. Called every 15 minutes.

**Function:** `scan_twitter_accounts() -> list[dict]`

Returns same event schema as `scan_news()` with `type = "figure_mention"`.

Implementation notes:
- For each account in TWITTER_ACCOUNTS_TO_MONITOR, fetch `{NITTER_INSTANCE}/{account}` with `requests` + `BeautifulSoup`
- Parse `.timeline-item` elements for tweet text and timestamp
- Only process tweets from the last 30 minutes (to avoid reprocessing)
- Scan tweet text for tickers using same regex as news.py
- Try fallback Nitter instances if primary fails
- Gracefully skip if all Nitter instances are down (log warning, don't crash)
- Store seen tweet IDs in SQLite

---

## Scoring Engine (`scoring/engine.py`)

**Function:** `score_ticker(ticker: str, fundamentals: dict, sentiment: dict, events: list[dict]) -> dict`

### Score Components

```
1. analyst_upside_score  (0–4 pts)
   = min(analyst_upside_pct / 0.10, 4.0)
   # 10% upside = 1pt, 40%+ upside = 4pts

2. pe_discount_score  (0–2 pts)
   = 2.0 if pe_discount else 0.0
   # Only if P/E is below sector median

3. analyst_conviction_score  (0–1 pt)
   = 1.0 if analyst_count >= 10 else analyst_count / 10
   # Reward broad analyst coverage

4. sentiment_score  (0–2 pts)
   = min(velocity_ratio / SENTIMENT_SPIKE_MULTIPLIER, 2.0)
   # Caps at 2pts for 3x+ spike

5. figure_mention_boost  (0–3 pts)
   = 3.0 if any figure_mention event in last 24h else 0.0
   # Big signal: named figure mentioned this ticker

6. earnings_proximity_penalty  (-1 pt)
   = -1.0 if earnings_within_30_days else 0.0
   # De-risk: upcoming earnings = uncertainty

composite_score = sum of all components
```

Returns:
```python
{
    "ticker": "MRVL",
    "composite_score": 8.4,
    "score_breakdown": {
        "analyst_upside": 3.58,
        "pe_discount": 2.0,
        "analyst_conviction": 1.0,
        "sentiment": 0.82,
        "figure_mention_boost": 3.0,
        "earnings_penalty": 0.0,
    },
    "analyst_upside_pct": 0.358,
    "trigger_events": [
        {"figure": "Jensen Huang", "ticker": "MRVL", "headline": "...", "source": "CNBC"}
    ],
    "alert_reason": "Figure mention: Jensen Huang (CNBC) + 36% analyst upside + P/E discount",
    "scored_at": "2025-01-15T14:45:00",
}
```

**Function:** `rank_watchlist(all_scores: list[dict]) -> list[dict]`
- Returns scores sorted descending by `composite_score`
- Filters to only tickers with `analyst_upside_pct >= ANALYST_UPSIDE_MIN`

---

## Alerts (`alerts/telegram.py`)

**Function:** `send_alert(score: dict)`

Formats and sends a Telegram message when `composite_score >= ALERT_SCORE_THRESHOLD` or a `figure_mention` event is detected.

Message format:
```
🔔 MRVL — Marvell Technology

Score: 8.4 / 12.0
Analyst upside: +36% ($79 → $108 target, 28 analysts)
P/E: 18.2 vs sector 28.5 → undervalued
Reddit: 3.7x mention spike (last 1h)

⚡ Trigger: Jensen Huang mentioned MRVL on CNBC
"Jensen Huang highlights Marvell as key AI infrastructure partner"
→ https://cnbc.com/...

52w range: $44 – $118 | Now: $79
```

**Function:** `send_daily_digest(ranked_scores: list[dict])`
- Sends top 5 tickers by score as a morning digest (8am daily)
- Compact format: one line per ticker with score + upside %

Implementation notes:
- Use `python-telegram-bot` library (async)
- Load TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from `.env`
- Rate-limit: max 1 alert per ticker per 4-hour window (store last_alerted_at in SQLite)
- Use `parse_mode="Markdown"` for formatting

---

## Storage (`storage/db.py`)

SQLite database at `./data/alpha.db`.

### Tables

**`signals`** — every scored ticker instance
```sql
CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    composite_score REAL,
    analyst_upside_pct REAL,
    pe_ratio REAL,
    sector_pe_median REAL,
    sentiment_velocity REAL,
    figure_mention_boost REAL,
    alert_reason TEXT,
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**`events`** — figure mentions and news hits
```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT,          -- 'figure_mention' | 'ticker_news'
    figure TEXT,
    ticker TEXT,
    headline TEXT,
    source TEXT,
    url TEXT UNIQUE,          -- dedup key
    published_at TIMESTAMP,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**`alerts_sent`** — rate-limiting log
```sql
CREATE TABLE alerts_sent (
    ticker TEXT PRIMARY KEY,
    last_alerted_at TIMESTAMP
);
```

**`reddit_hourly`** — for computing 7-day rolling average
```sql
CREATE TABLE reddit_hourly (
    ticker TEXT,
    hour TIMESTAMP,
    mention_count INTEGER,
    PRIMARY KEY (ticker, hour)
);
```

**Function:** `log_signal(score: dict)` — insert into `signals`
**Function:** `log_event(event: dict)` — insert into `events` (ignore on URL conflict)
**Function:** `can_alert(ticker: str) -> bool` — returns True if last alert was >4h ago
**Function:** `get_signal_history(ticker: str, days: int) -> list[dict]` — for dashboard

---

## Scheduler (`main.py`)

Use `APScheduler` (`BackgroundScheduler`) to orchestrate all jobs.

```python
scheduler.add_job(run_fundamentals_job,  'interval', hours=24,   id='fundamentals')
scheduler.add_job(run_news_job,          'interval', minutes=30,  id='news')
scheduler.add_job(run_twitter_job,       'interval', minutes=15,  id='twitter')
scheduler.add_job(send_daily_digest_job, 'cron',     hour=8,      id='digest')
```

**`run_fundamentals_job()`:**
1. For each ticker in WATCHLIST: call `get_fundamentals()`, `get_reddit_sentiment()`
2. Call `score_ticker()` for each
3. Log all scores to SQLite
4. Send alert for any ticker with score >= ALERT_SCORE_THRESHOLD (subject to rate limit)

**`run_news_job()`:**
1. Call `scan_news()` → list of events
2. Log all new events to SQLite
3. For each `figure_mention` event: re-score the mentioned ticker immediately
4. If re-score >= threshold → send alert

**`run_twitter_job()`:**
1. Same as `run_news_job()` but calls `scan_twitter_accounts()`

**Startup behavior:**
- Run `run_fundamentals_job()` immediately on start (don't wait 24h for first data)
- Print top 10 ranked tickers to console on startup

---

## Dashboard (`dashboard/app.py`)

Streamlit app. Run with `streamlit run dashboard/app.py`.

### Pages / Sections

**1. Leaderboard (main view)**
- Table: Ticker | Score | Analyst Upside | P/E vs Sector | Sentiment | Last Trigger
- Color-coded score column (green >7, yellow 4–7, red <4)
- Refresh button to re-fetch from SQLite

**2. Ticker Detail (click a row)**
- Score breakdown bar chart (each component as a stacked bar)
- 30-day signal history chart (composite score over time)
- Recent events/news that triggered alerts
- yfinance price chart (last 90 days)

**3. Event Feed**
- Live feed of all `figure_mention` events, newest first
- Filterable by figure name and ticker

**4. Alert Log**
- Table of all Telegram alerts sent with timestamp and reason

---

## Setup Instructions

### `.env` file
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
NEWS_API_KEY=optional_newsapi_key
```

### `requirements.txt`
```
yfinance>=0.2.36
praw>=7.7.1
feedparser>=6.0.10
requests>=2.31.0
beautifulsoup4>=4.12.0
python-telegram-bot>=20.7
apscheduler>=3.10.4
streamlit>=1.30.0
pandas>=2.1.0
plotly>=5.18.0
python-dotenv>=1.0.0
newsapi-python>=0.2.7
lxml>=4.9.0
```

### Getting API credentials

**Telegram bot:**
1. Message @BotFather on Telegram → `/newbot`
2. Copy the token to `.env`
3. Send a message to your bot, then visit `https://api.telegram.org/bot{TOKEN}/getUpdates` to find your `chat_id`

**Reddit (PRAW):**
1. Go to https://www.reddit.com/prefs/apps → Create app → Script type
2. Copy client_id (under app name) and client_secret to `.env`

**NewsAPI (optional):**
1. Register at https://newsapi.org → free tier gives 100 req/day
2. Copy API key to `.env`

### Running
```bash
pip install -r requirements.txt
python main.py                        # starts scheduler + runs first scan
streamlit run dashboard/app.py        # open dashboard in browser
```

---

## Error Handling & Resilience

- All data fetchers must catch exceptions and return `None` / empty list — never crash the scheduler
- Nitter: try each instance in NITTER_INSTANCES in order; log warning if all fail
- yfinance: some tickers return incomplete data — handle `None` fields by excluding that score component
- PRAW: respect rate limits; wrap in try/except for `prawcore.exceptions`
- SQLite: use `INSERT OR IGNORE` for dedup tables; wrap writes in transactions
- Log all errors to `./data/errors.log` with timestamp and traceback

---

## Future Extensions (post-MVP)

- **Backtesting module:** query `signals` table to measure whether high-score signals predicted actual price gains at 30/60/90 day windows
- **SEC filings monitor:** track 13F filings for large institutional position changes in watchlist tickers
- **Options flow:** free options unusual activity from `unusualwhales.com` RSS
- **Earnings surprise model:** compare EPS estimate vs actual on earnings date
- **Score decay:** reduce figure_mention_boost over 24h window instead of binary on/off
