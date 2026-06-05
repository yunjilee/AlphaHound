"""Telegram alerting."""

import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_telegram(message: str) -> bool:
    """Send a message via Telegram bot. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("    [telegram] Not configured, skipping")
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
        print(f"    [telegram] Error: {e}")
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
    
    # Format prices safely
    current = f.get('current_price', 0)
    target = f.get('analyst_target_mean', 0)
    upside = f.get('analyst_upside_pct', 0)
    
    msg = f"""🔔 *{score['ticker']}* — Score: {score['composite_score']:.1f}/15

📊 *Fundamentals* ({fundamental_pts:.1f} pts)
   Analyst: +{upside*100:.0f}% upside (${current:.0f} → ${target:.0f})
   PEG: {f.get('peg_ratio') or 'N/A'}, {f.get('analyst_count', 0)} analysts
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
        upside = f.get('analyst_upside_pct', 0)
        lines.append(f"• *{s['ticker']}* — {s['composite_score']:.1f}/15 (+{upside*100:.0f}%){trigger_str}")
    
    return send_telegram("\n".join(lines))
