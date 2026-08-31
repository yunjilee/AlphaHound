"""SMS alerting through a carrier email-to-SMS gateway."""

import smtplib
from email.message import EmailMessage

from config import (
    SMS_CARRIER,
    SMS_ENABLED,
    SMS_GMAIL_APP_PASSWORD,
    SMS_GMAIL_USER,
    SMS_PHONE_NUMBER,
)


def send_sms(message: str) -> bool:
    """Send a text using Gmail and the recipient carrier's SMS gateway."""
    required = (
        SMS_PHONE_NUMBER,
        SMS_CARRIER,
        SMS_GMAIL_USER,
        SMS_GMAIL_APP_PASSWORD,
    )
    if not SMS_ENABLED or not all(required):
        print("    [sms] Not configured, skipping")
        return False

    email = EmailMessage()
    email["From"] = SMS_GMAIL_USER
    email["To"] = f"{SMS_PHONE_NUMBER}@{SMS_CARRIER}"
    email.set_content(message)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(SMS_GMAIL_USER, SMS_GMAIL_APP_PASSWORD)
            smtp.send_message(email)
        return True
    except (OSError, smtplib.SMTPException) as error:
        print(f"    [sms] Error: {error}")
        return False


def send_alert(score: dict) -> bool:
    """Format and send alert for a high-scoring ticker."""
    f = score["signals"]["fundamentals"]
    b = score["score_breakdown"]
    triggers = score.get("alert_triggers", [])
    
    # Build trigger list (replace underscores for display)
    trigger_lines = ""
    if triggers:
        display_triggers = [t.replace("_", " ") for t in triggers]
        trigger_lines = "\nTriggers: " + ", ".join(display_triggers)
    
    # Calculate category scores (raw)
    quality_raw = b.get("roe", 0) + b.get("margin", 0) + b.get("debt", 0)
    growth_raw = b.get("eps_growth", 0) + b.get("pe_discount", 0)
    value_raw = b.get("peg", 0) + b.get("analyst_upside", 0)
    
    # Scale to /10 for display (max: quality=2.5, growth=2, value=2)
    quality = (quality_raw / 2.5) * 10
    growth = (growth_raw / 2.0) * 10
    value = (value_raw / 2.0) * 10
    
    # Format prices safely
    current = f.get('current_price', 0) or 0
    target = f.get('analyst_target_mean', 0) or 0
    upside = f.get('analyst_upside_pct', 0) or 0
    daily_change = f.get('daily_change_pct', 0) or 0
    
    # PEG with context
    peg = f.get('peg_ratio')
    if peg:
        if peg < 1.0:
            peg_str = f"{peg:.2f} (cheap)"
        elif peg < 2.0:
            peg_str = f"{peg:.2f} (fair)"
        else:
            peg_str = f"{peg:.2f} (expensive)"
    else:
        peg_str = "N/A"
    
    # Analysts with context
    analyst_count = f.get('analyst_count', 0) or 0
    if analyst_count >= 30:
        analyst_str = f"{analyst_count} (high)"
    elif analyst_count >= 10:
        analyst_str = f"{analyst_count} (moderate)"
    elif analyst_count > 0:
        analyst_str = f"{analyst_count} (low)"
    else:
        analyst_str = "N/A"
    
    # Score conclusion
    composite = score['composite_score']
    if composite >= 7.0:
        conclusion = "strong buy"
    elif composite >= 5.0:
        conclusion = "buy"
    elif composite >= 3.0:
        conclusion = "hold"
    else:
        conclusion = "weak"
    
    # Format daily change with +/- sign
    daily_sign = "+" if daily_change >= 0 else ""
    
    msg = f"""{score['ticker']} - {score['composite_score']:.1f}/10 ({conclusion})

Quality: {quality:.0f}/10 | Growth: {growth:.0f}/10 | Value: {value:.0f}/10
Price: ${current:.2f} ({daily_sign}{daily_change*100:.1f}% today)
Target Price: ${target:.2f} ({upside*100:+.0f}%)
PEG: {peg_str} | Analysts: {analyst_str}{trigger_lines}"""
    
    return send_sms(msg)


def send_daily_digest(scores: list[dict]) -> bool:
    """Send daily digest of top tickers."""
    if not scores:
        return send_sms("Daily digest: No qualifying tickers today.")
    
    lines = ["Daily Report (Current -> Target)\n"]
    for s in scores[:5]:
        f = s["signals"]["fundamentals"]
        triggers = s.get("alert_triggers", [])
        trigger_count = f" [{len(triggers)} signals]" if triggers else ""
        
        # Price data
        current = f.get('current_price', 0) or 0
        target = f.get('analyst_target_mean', 0) or 0
        upside = f.get('analyst_upside_pct', 0) or 0
        
        # PEG
        peg = f.get('peg_ratio')
        peg_str = f"PEG {peg:.1f}" if peg else ""
        
        lines.append(
            f"{s['ticker']} {s['composite_score']:.1f} | "
            f"${current:.0f} -> ${target:.0f} ({upside*100:+.0f}%) | "
            f"{peg_str}{trigger_count}"
        )
    
    lines.append("\nPEG: <1 cheap, 1-2 fair, >2 expensive")
    
    return send_sms("\n".join(lines))
