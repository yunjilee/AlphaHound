"""Composite alpha score computation."""

from datetime import datetime


def score_ticker(
    fundamentals: dict,
    reddit: dict = None,
    insider: dict = None,
    trends: dict = None,
    news: dict = None,
) -> dict | None:
    """Score a ticker using all available signals. Max score: 15 points."""
    if not fundamentals:
        return None
    
    f = fundamentals
    breakdown = {}
    triggers = []
    
    # === FUNDAMENTALS (max 8 pts) ===
    
    # 1. Analyst upside (0-4 pts)
    upside = f.get("analyst_upside_pct", 0)
    breakdown["analyst_upside"] = round(min(upside / 0.125, 4.0), 2) if upside > 0 else 0.0
    
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
    low = f.get("52w_low")
    high = f.get("52w_high")
    current = f.get("current_price")
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
