"""Monitor Reddit for ticker mention velocity."""

import praw
from datetime import datetime, timedelta
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET

_reddit = None


def _get_reddit():
    """Lazy-initialize Reddit client."""
    global _reddit
    if _reddit is None:
        if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
            return None
        _reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent="stock-alpha-scanner/1.0"
        )
    return _reddit


def get_reddit_sentiment(ticker: str) -> dict | None:
    """Get Reddit mention velocity for a ticker."""
    try:
        r = _get_reddit()
        if r is None:
            return None

        subreddits = r.subreddit("stocks+investing+wallstreetbets+stockmarket")

        now = datetime.utcnow()
        day_ago = (now - timedelta(days=1)).timestamp()
        week_ago = (now - timedelta(days=7)).timestamp()

        mentions_24h = 0
        mentions_7d = 0
        top_posts = []

        # Search for ticker mentions
        search_query = f"${ticker} OR {ticker}"
        for post in subreddits.search(search_query, sort="new", time_filter="week", limit=200):
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
        print(f"    [reddit] Error for {ticker}: {e}")
        return None
