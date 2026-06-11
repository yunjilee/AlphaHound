"""
Composite alpha score computation.

Strategy: Fundamentals-first scoring with insider as bonus catalyst.
Max score: 10 points

Scoring breakdown:
- Quality (0-2.5 pts): ROE, margins, low debt
- Growth (0-2 pts): EPS growth, Forward P/E < Trailing
- Value (0-2 pts): PEG ratio, position in 52w range
- Catalyst (0-2 pts): Insider buying, cluster buying, multi-screen discovery
- Sentiment (0-1.5 pts): Reddit, Google Trends, news mentions
"""

from datetime import datetime


def score_ticker(
    fundamentals: dict,
    reddit: dict = None,
    insider: dict = None,
    trends: dict = None,
    news: dict = None,
    has_insider_buying: bool = False,
    is_multi_screen: bool = False,
    previous_target: float = None,
) -> dict | None:
    """
    Score a ticker using fundamentals-first approach.
    
    Args:
        fundamentals: Core financial data
        reddit: Reddit sentiment data
        insider: Insider trading data from API
        trends: Google Trends data
        news: RSS news data
        has_insider_buying: True if discovered via insider buying screen (bonus)
        is_multi_screen: True if appeared in 2+ fundamental screens (highest conviction)
        previous_target: Previous analyst target price (for rerate detection)
    
    Returns:
        Scored ticker dict or None if invalid fundamentals
    """
    if not fundamentals:
        return None
    
    f = fundamentals
    breakdown = {}
    triggers = []
    
    # ==========================================================================
    # QUALITY (max 2.5 pts) - Foundation of the investment
    # ==========================================================================
    
    # 1. ROE quality (0-1 pts)
    roe = f.get("return_on_equity", 0) or 0
    if roe > 0.25:  # 25%+
        breakdown["roe"] = 1.0
    elif roe > 0.15:  # 15%+
        breakdown["roe"] = 0.75
    elif roe > 0.10:  # 10%+
        breakdown["roe"] = 0.5
    else:
        breakdown["roe"] = 0.0
    
    # 2. Profit margin (0-0.75 pts)
    margin = f.get("profit_margin", 0) or 0
    if margin > 0.20:  # 20%+
        breakdown["margin"] = 0.75
    elif margin > 0.10:  # 10%+
        breakdown["margin"] = 0.5
    else:
        breakdown["margin"] = 0.0
    
    # 3. Debt health (0-0.75 pts)
    de = f.get("debt_to_equity", 999) or 999
    if de < 0.5:
        breakdown["debt"] = 0.75
    elif de < 1.0:
        breakdown["debt"] = 0.5
    elif de < 1.5:
        breakdown["debt"] = 0.25
    else:
        breakdown["debt"] = 0.0
    
    # ==========================================================================
    # GROWTH (max 2 pts) - Future earnings power
    # ==========================================================================
    
    # 4. EPS growth (0-1 pts)
    eps_growth = f.get("eps_growth_next_year", 0) or 0
    if eps_growth > 0.20:  # 20%+
        breakdown["eps_growth"] = 1.0
        triggers.append("high_growth")
    elif eps_growth > 0.10:  # 10%+
        breakdown["eps_growth"] = 0.5
    else:
        breakdown["eps_growth"] = 0.0
    
    # 5. Forward P/E < Trailing P/E (0-1 pts) - Key GARP signal
    fwd_pe = f.get("forward_pe", 0) or 0
    trail_pe = f.get("trailing_pe", 0) or 0
    if fwd_pe > 0 and trail_pe > 0 and fwd_pe < trail_pe:
        pe_discount = (trail_pe - fwd_pe) / trail_pe
        if pe_discount > 0.30:  # 30%+ cheaper on forward
            breakdown["pe_discount"] = 1.0
            triggers.append("pe_compression")
        elif pe_discount > 0.15:
            breakdown["pe_discount"] = 0.5
        else:
            breakdown["pe_discount"] = 0.25
    else:
        breakdown["pe_discount"] = 0.0
    
    # ==========================================================================
    # VALUE (max 2 pts) - Reasonable entry price
    # ==========================================================================
    
    # 6. PEG ratio (0-1 pts) - Core GARP metric
    peg = f.get("peg_ratio")
    if peg and 0 < peg < 0.5:
        breakdown["peg"] = 1.0
        triggers.append("deep_value_peg")
    elif peg and 0 < peg < 1.0:
        breakdown["peg"] = 0.75
    elif peg and 0 < peg < 1.5:
        breakdown["peg"] = 0.5
    elif peg and 0 < peg < 2.0:
        breakdown["peg"] = 0.25
    else:
        breakdown["peg"] = 0.0
    
    # 7. Analyst upside (0-1 pts)
    upside = f.get("analyst_upside_pct", 0) or 0
    if upside > 0.30:  # 30%+ upside
        breakdown["analyst_upside"] = 1.0
    elif upside > 0.15:  # 15%+ upside
        breakdown["analyst_upside"] = 0.5
    elif upside > 0.05:  # 5%+ upside
        breakdown["analyst_upside"] = 0.25
    else:
        breakdown["analyst_upside"] = 0.0
    
    # ==========================================================================
    # CATALYST (max 2 pts) - Confirmation signals (BONUS, not filter)
    # ==========================================================================
    
    # 8. Insider buying - API data (0-1 pts)
    breakdown["insider_api"] = 0.0
    if insider and insider.get("signal") == "bullish":
        breakdown["insider_api"] = 1.0
        triggers.append("insider_buying")
    
    # 9. Discovered via insider screen (0-0.5 pt) - From Finviz/OpenInsider
    breakdown["insider_discovery"] = 0.0
    if has_insider_buying:
        breakdown["insider_discovery"] = 0.5
        if "insider_buying" not in triggers:
            triggers.append("insider_discovery")
    
    # 10. Multi-screen discovery (0-0.5 pt) - Highest conviction
    breakdown["multi_screen"] = 0.0
    if is_multi_screen:
        breakdown["multi_screen"] = 0.5
        triggers.append("multi_screen_conviction")
    
    # 11. Analyst target rerate detection (trigger only, no points)
    current_target = f.get("analyst_target_mean")
    if previous_target and current_target and previous_target > 0:
        target_change = (current_target - previous_target) / previous_target
        if target_change >= 0.10:  # 10%+ target increase
            triggers.append(f"target_raised_{target_change*100:.0f}%")
        elif target_change <= -0.10:  # 10%+ target decrease (warning)
            triggers.append(f"target_lowered_{abs(target_change)*100:.0f}%")
    
    # ==========================================================================
    # SENTIMENT (max 1.5 pts) - Alternative data confirmation
    # ==========================================================================
    
    # 12. Reddit velocity (0-0.5 pt)
    breakdown["reddit"] = 0.0
    if reddit:
        vel = reddit.get("velocity_ratio", 0)
        if vel > 2.0:
            breakdown["reddit"] = 0.5
            triggers.append("reddit_spike")
        elif vel > 1.5:
            breakdown["reddit"] = 0.25
    
    # 13. Google Trends (0-0.5 pt)
    breakdown["trends"] = 0.0
    if trends:
        ratio = trends.get("trend_ratio", 0)
        if ratio > 2.0:
            breakdown["trends"] = 0.5
            triggers.append("google_trends_spike")
        elif ratio > 1.5:
            breakdown["trends"] = 0.25
    
    # 14. News / figure mentions (0-0.5 pt)
    breakdown["news"] = 0.0
    if news:
        if news.get("has_figure_mention"):
            breakdown["news"] = 0.5
            triggers.append(f"figure_mention:{news.get('figure_mentioned')}")
        elif news.get("news_count_24h", 0) > 0:
            breakdown["news"] = 0.25
    
    # ==========================================================================
    # RESULT
    # ==========================================================================
    
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
        "has_insider_buying": has_insider_buying,
        "is_multi_screen": is_multi_screen,
        "alert_triggers": triggers,
        "scored_at": datetime.now().isoformat(),
    }


def rank_watchlist(scores: list[dict], min_quality_score: float = 2.0) -> list[dict]:
    """
    Filter and rank scored tickers.
    
    Args:
        scores: List of scored ticker dicts
        min_quality_score: Minimum quality component (ROE + margin + debt) to include
    
    Returns:
        Sorted list of valid tickers by composite score
    """
    def quality_score(s: dict) -> float:
        bd = s.get("score_breakdown", {})
        return bd.get("roe", 0) + bd.get("margin", 0) + bd.get("debt", 0)
    
    filtered = [
        s for s in scores
        if s and quality_score(s) >= min_quality_score
    ]
    
    return sorted(filtered, key=lambda x: x["composite_score"], reverse=True)
