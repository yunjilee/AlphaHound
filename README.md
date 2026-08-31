# AlphaHound

A Python stock scanner for finding quality growth stocks with strong fundamentals. Uses a **fundamentals-first approach** (Quality → Growth → Value) with insider buying as a bonus catalyst, not a filter.

**Strategy:** Finds institutional-quality companies ($2B+ market cap) with strong ROE, reasonable PEG ratios, and analyst buy ratings. Insider buying is tracked as a confirmation signal that adds to the score, not as a gating filter — so you won't miss stocks like MU that have excellent fundamentals but insider selling.

## Project Structure

```
AlphaHound/
├── discover.py          # Discovery script — run DAILY
├── main.py              # Scan script — run HOURLY  
├── config.py            # Configuration (watchlist, thresholds, API keys)
├── scoring.py           # Composite alpha scoring (max 20 pts)
├── alerts.py            # Direct SMS notifications
├── storage.py           # SQLite signal logging
├── data/
│   ├── discovery.py     # Fundamentals-first discovery (Finviz screens)
│   ├── fundamentals.py  # yfinance (ROE, margins, P/E, PEG, growth)
│   ├── reddit.py        # PRAW (mention velocity)
│   ├── insider.py       # SEC EDGAR (Form 4 insider trades)
│   ├── trends.py        # Google Trends (retail interest)
│   └── news.py          # RSS feeds (headlines, figure mentions)
├── test_setup.py        # Verify all APIs work
├── requirements.txt     # Dependencies
├── .env.example         # Credential template
└── stock_alpha_design_doc.md  # Full design documentation
```

## Investment Philosophy

This scanner is designed for **1-2 year investment horizon** targeting:

1. **Quality First** — High ROE (>15%), strong margins, low debt
2. **Growth at Reasonable Price (GARP)** — PEG < 2, earnings growing
3. **Value Confirmation** — Analyst buy ratings, upside to target price
4. **Insider as Bonus** — Insider buying adds to score but doesn't filter out great companies

**Why not insider-first?** Backtesting showed stocks like MU (Micron) have excellent fundamentals but insider selling (executives diversifying). A fundamentals-first approach catches these; insider-first would miss them.

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  DAILY: python discover.py (6 AM)                           │
│     ├── Quality Growth screen (ROE>15%, PEG<2)              │
│     ├── Undervalued Growth screen (PEG<1, analyst buy)      │
│     ├── Quality Value screen (low debt, good margins)       │
│     ├── Track insider buying as BONUS signal                │
│     └── Cache: data/watchlist_cache.json                    │
├─────────────────────────────────────────────────────────────┤
│  HOURLY: python main.py                                     │
│     ├── Load cached watchlist + insider/multi-screen flags  │
│     ├── Prioritize: new → top scorers → multi-screen        │
│     ├── Cap at 50 tickers (rate limit sustainable)          │
│     ├── Fetch: yfinance, Reddit, SEC, Trends, RSS           │
│     ├── Score each ticker (max 20 pts)                      │
│     ├── Quality+Growth+Value = core score                   │
│     ├── Insider/multi-screen = bonus points                 │
│     └── Alert if high conviction triggers                   │
└─────────────────────────────────────────────────────────────┘
```

## Scoring System (max 20 points)

| Category | Max | Components |
|----------|-----|------------|
| **Quality** | 5 pts | ROE (2), Profit margin (1.5), Low debt (1.5) |
| **Growth** | 4 pts | EPS growth (2), Forward P/E < Trailing (2) |
| **Value** | 4 pts | PEG ratio (2), Analyst upside (2) |
| **Catalyst** | 4 pts | Insider API (2), Insider discovery (1), Multi-screen (1) |
| **Sentiment** | 3 pts | Reddit (1), Google Trends (1), News (1) |

**Multi-screen bonus:** Stocks appearing in 2+ fundamental screens get +1 point (highest conviction).

## Data Sources (All Free)

| Source | What It Provides |
|--------|------------------|
| **Finviz** | Multi-variable screening: ROE, PEG, debt/equity, analyst ratings |
| **OpenInsider** | Cluster insider buying (2+ insiders buying same stock) |
| **yfinance** | Full fundamentals: ROE, margins, P/E, PEG, growth rates |
| **Reddit** (PRAW) | Mention velocity, sentiment spikes |
| **SEC EDGAR** | Insider buys/sells (Form 4 filings) |
| **Google Trends** | Retail search interest |
| **RSS News** | Headlines, public figure mentions |

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/youruser/AlphaHound.git
cd AlphaHound
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env with your SMS gateway and Reddit API settings

# 3. Test setup
python test_setup.py

# 4. Run discovery (daily)
python discover.py

# 5. Run scanner (hourly) — scans top 50 prioritized tickers
python main.py

# Or scan ALL discovered tickers (for weekends/first run)
python main.py --scan-all

# Or use core watchlist only
python main.py --core-only
```

## Configuration

Edit `config.py` to customize:
- `CORE_WATCHLIST` — tickers always monitored (your high-conviction names)
- `MAX_HOURLY_TICKERS` — cap hourly scan for rate limits (default: 50)
- `MAX_WATCHLIST_SIZE` — cap discovery total (default: 100)
- `ALERT_SCORE_THRESHOLD` — minimum score to trigger alerts (default: 10/20)

## Sample Output

**Daily Discovery:**
```
============================================================
  ALPHAHOUND DISCOVERY (Fundamentals-First)
  Strategy: Quality > Growth > Value | Insider = Bonus
============================================================
[discovery] Quality Growth (GARP): 374 stocks
[discovery] Undervalued Growth: 465 stocks
[discovery] Quality Value: 374 stocks
[discovery] Insider Buying (bonus signal): 511 stocks
[discovery] Multi-screen overlap (highest conviction): 276 stocks

[discovery] Final watchlist: 50 tickers (18 core + 32 discovered)
--------------------------------------------
Core watchlist:       18 tickers
Discovered:           32 tickers
Multi-screen overlap: 276 tickers (highest conviction)
Insider buying bonus: 94 tickers
--------------------------------------------
```

**Hourly Scan:**
```
============================================================
  STOCK ALPHA SCANNER (Fundamentals-First)
  Strategy: Quality > Growth > Value | Insider = Bonus
  Scanning 50 tickers...
  Insider buying bonus: 12 tickers
  Multi-screen conviction: 28 tickers
============================================================

[ 1/50] NVDA (+multi)... score=14.5/20 [!] high_growth, pe_compression
[ 2/50] MU (+multi)... score=13.2/20 [!] high_growth, deep_value_peg
[ 3/50] AIG (+multi,+ins)... score=12.8/20 [!] insider_buying
...

============================================================
  TOP TICKERS (Score out of 20)
============================================================
  TICKER   SCORE  QUAL  GROW   VAL TRIGGERS
  -------- ------ ----- ----- ----- --------------------
  NVDA      14.5   4.5   3.0   4.0 high_growth, pe_comp
  MU        13.2   4.0   4.0   3.5 high_growth, deep_va
  AIG       12.8   3.5   2.0   3.0 insider_buying
```

## API Credentials

| Service | Required | How to Get |
|---------|----------|------------|
| SMS gateway | Yes | Gmail app password plus your carrier's email-to-SMS domain |
| Reddit | No | https://reddit.com/prefs/apps → Create an app, or set `REDDIT_ENABLED=false` |
| yfinance | No | Just works |
| SEC EDGAR | No | Public API |
| Google Trends | No | Just works (rate limited) |
| RSS | No | Public feeds |

See [stock_alpha_design_doc.md](stock_alpha_design_doc.md) for detailed setup instructions.

## Scheduling

**Linux/Mac (cron):**
```bash
# Discovery: Daily at 6am PT (before market open)
0 6 * * 1-5 cd /path/to/AlphaHound && python discover.py >> logs/discover.log 2>&1

# Scan: Hourly during market hours (6:30am - 1pm PT)
30 6-13 * * 1-5 cd /path/to/AlphaHound && python main.py >> logs/scan.log 2>&1
```

**Windows (Task Scheduler):**

| Task | Trigger | Action |
|------|---------|--------|
| AlphaHound Discovery | Daily 6:00 AM, weekdays | `python discover.py` |
| AlphaHound Scan | Hourly 6:30 AM-1 PM, weekdays | `python main.py` |

## License

MIT
