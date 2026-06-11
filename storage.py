"""SQLite storage for signal logging."""

import sqlite3
import os
from contextlib import contextmanager
from config import DB_PATH


@contextmanager
def get_db():
    """Context manager for database connections."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
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
                insider_signal TEXT,
                reddit_velocity REAL,
                trends_ratio REAL,
                news_count INTEGER,
                alert_triggers TEXT,
                scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);
            CREATE INDEX IF NOT EXISTS idx_signals_scored_at ON signals(scored_at);
        """)
        conn.commit()


def log_signal(score: dict):
    """Insert a scored signal into the database."""
    f = score["signals"]["fundamentals"]
    reddit = score["signals"].get("reddit") or {}
    insider = score["signals"].get("insider") or {}
    trends = score["signals"].get("trends") or {}
    news = score["signals"].get("news") or {}
    
    with get_db() as conn:
        conn.execute("""
            INSERT INTO signals (
                ticker, composite_score, analyst_upside_pct, current_price,
                target_price, peg_ratio, analyst_count, insider_signal,
                reddit_velocity, trends_ratio, news_count, alert_triggers
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            score["ticker"],
            score["composite_score"],
            f.get("analyst_upside_pct"),
            f.get("current_price"),
            f.get("analyst_target_mean"),
            f.get("peg_ratio"),
            f.get("analyst_count"),
            insider.get("signal"),
            reddit.get("velocity_ratio"),
            trends.get("trend_ratio"),
            news.get("news_count_24h"),
            ",".join(score.get("alert_triggers", [])),
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


def get_top_scored_tickers(limit: int = 50, hours: int = 48) -> list[tuple[str, float]]:
    """
    Get tickers with highest recent scores.
    
    Returns list of (ticker, max_score) tuples, sorted by score descending.
    Used to prioritize hourly scans on best candidates.
    """
    with get_db() as conn:
        rows = conn.execute("""
            SELECT ticker, MAX(composite_score) as max_score
            FROM signals 
            WHERE scored_at > datetime('now', ?)
            GROUP BY ticker
            ORDER BY max_score DESC
            LIMIT ?
        """, (f'-{hours} hours', limit)).fetchall()
        return [(r['ticker'], r['max_score']) for r in rows]


def get_new_tickers(tickers: list[str], hours: int = 48) -> list[str]:
    """
    Return tickers that have no score history in the given time window.
    These are new discoveries that should be scanned.
    """
    if not tickers:
        return []
    
    placeholders = ','.join('?' * len(tickers))
    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT DISTINCT ticker FROM signals 
            WHERE ticker IN ({placeholders})
            AND scored_at > datetime('now', ?)
        """, (*tickers, f'-{hours} hours')).fetchall()
        scored = {r['ticker'] for r in rows}
        return [t for t in tickers if t not in scored]


def get_previous_target(ticker: str, hours: int = 48) -> float | None:
    """
    Get the most recent analyst target price for a ticker.
    Used to detect target price reratings.
    
    Returns None if no previous data exists.
    """
    with get_db() as conn:
        row = conn.execute("""
            SELECT target_price FROM signals 
            WHERE ticker = ? 
            AND target_price IS NOT NULL
            AND scored_at > datetime('now', ?)
            ORDER BY scored_at DESC
            LIMIT 1
        """, (ticker, f'-{hours} hours')).fetchone()
        return row['target_price'] if row else None
