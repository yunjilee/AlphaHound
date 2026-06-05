# AlphaHound

A lightweight Python pipeline to detect undervalued "sleeper" stocks. Combines fundamental valuation signals, analyst upside, and real-time sentiment tracking with Telegram alerts.

## Project Structure

```
AlphaHound/
├── main.py              # Entry point — run daily scan
├── config.py            # Configuration (watchlist, thresholds, API keys)
├── scoring.py           # Composite alpha scoring (max 15 pts)
├── alerts.py            # Telegram notifications
├── storage.py           # SQLite signal logging
├── data/
│   ├── fundamentals.py  # yfinance (analyst targets, P/E, PEG)
│   ├── reddit.py        # PRAW (mention velocity)
│   ├── insider.py       # SEC EDGAR (Form 4 insider trades)
│   ├── trends.py        # Google Trends (retail interest)
│   └── news.py          # RSS feeds (headlines, figure mentions)
├── test_setup.py        # Verify all APIs work
├── requirements.txt     # 6 dependencies
├── .env.example         # Credential template
└── stock_alpha_design_doc.md  # Full design documentation
```

## Data Sources (All Free)

| Source | What It Provides |
|--------|------------------|
| **yfinance** | Price targets, P/E, PEG ratio, 52w range |
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
# Edit .env with your Telegram bot token and Reddit API keys

# 3. Test setup
python test_setup.py

# 4. Run scanner
python main.py
```

## Configuration

Edit `config.py` to customize:
- `WATCHLIST` — tickers to monitor
- `ALERT_SCORE_THRESHOLD` — minimum score to trigger alerts (default: 6/15)
- `ANALYST_UPSIDE_MIN` — minimum analyst upside to qualify (default: 20%)

## Scoring System (max 15 points)

| Category | Max | Components |
|----------|-----|------------|
| **Fundamentals** | 8 pts | Analyst upside (4), PEG ratio (2), coverage (1), 52w position (1) |
| **Alternative Data** | 7 pts | Insider buying (2), Reddit spike (1.5), Google Trends (1.5), news/figure mentions (2) |

## API Credentials

| Service | Required | How to Get |
|---------|----------|------------|
| Telegram | Yes | Message @BotFather → `/newbot` |
| Reddit | Yes | https://reddit.com/prefs/apps → Create "script" app |
| yfinance | No | Just works |
| SEC EDGAR | No | Public API |
| Google Trends | No | Just works |
| RSS | No | Public feeds |

See [stock_alpha_design_doc.md](stock_alpha_design_doc.md) for detailed setup instructions.

## Output

```
============================================================
  STOCK ALPHA SCANNER
  Scanning 18 tickers...
============================================================

[ 1/18] NVDA... score=8.5/15 ⚡ reddit_spike
[ 2/18] MRVL... score=11.2/15 ⚡ insider_buying, figure_mention:Jensen Huang
...

============================================================
  TOP TICKERS (min 6/15 to alert)
============================================================
  TICKER     SCORE   UPSIDE TRIGGERS
  -------- -------- -------- --------------------
  MRVL         11.2     40% insider_buying, figur
  NVDA          8.5     28% reddit_spike
  ...
```

## Scheduling

**Linux/Mac (cron):**
```bash
# Run at 6am PT every weekday
0 6 * * 1-5 cd /path/to/AlphaHound && python main.py >> logs/scan.log 2>&1
```

**Windows (Task Scheduler):**
- Trigger: Daily at 6:00 AM
- Action: Start `python main.py`
- Start in: `C:\path\to\AlphaHound`

## License

MIT
