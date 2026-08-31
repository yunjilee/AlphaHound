"""Configuration for Stock Alpha Scanner."""

import json
import os
from dotenv import load_dotenv

load_dotenv()


def _env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_sms_settings() -> dict:
    """Load SMS settings from env vars or a shared JSON config."""
    enabled_override = os.getenv("SMS_ENABLED")
    settings = {
        "enabled": (
            _env_flag("SMS_ENABLED")
            if enabled_override is not None
            else None
        ),
        "phone_number": os.getenv("SMS_PHONE_NUMBER", ""),
        "carrier": os.getenv("SMS_CARRIER", ""),
        "gmail_user": os.getenv("SMS_GMAIL_USER", ""),
        "gmail_app_password": os.getenv("SMS_GMAIL_APP_PASSWORD", ""),
    }

    config_path = os.getenv("SMS_CONFIG_PATH", "")
    if not config_path:
        settings["enabled"] = bool(settings["enabled"])
        return settings

    try:
        with open(config_path, encoding="utf-8") as config_file:
            shared_sms = json.load(config_file).get("sms", {})
    except (OSError, json.JSONDecodeError) as error:
        print(f"[sms] Could not load SMS_CONFIG_PATH: {error}")
        return settings

    gmail = shared_sms.get("gmail", {})
    if settings["enabled"] is None:
        settings["enabled"] = bool(shared_sms.get("enabled"))
    settings["phone_number"] = settings["phone_number"] or shared_sms.get("phoneNumber", "")
    settings["carrier"] = settings["carrier"] or shared_sms.get("carrier", "")
    settings["gmail_user"] = settings["gmail_user"] or gmail.get("user", "")
    settings["gmail_app_password"] = (
        settings["gmail_app_password"] or gmail.get("appPassword", "")
    )
    return settings

# Core watchlist: always monitored (your high-conviction names)
CORE_WATCHLIST = [
    "NVDA", "MRVL", "MU", "AMD", "INTC", "QCOM",
    "TSLA", "AAPL", "MSFT", "GOOGL", "META", "AMZN",
    "DELL", "HPE", "SMCI", "ARM", "AVGO", "TSM",
]

# Discovery settings
MAX_WATCHLIST_SIZE = 100         # Max unique tickers from discovery
MAX_HOURLY_TICKERS = 50          # Cap hourly scan (rate limit: ~50/hour sustainable)

# High-signal public figures (for news scanning)
SIGNAL_FIGURES = [
    "Jensen Huang", "Elon Musk", "Warren Buffett", "Tim Cook",
    "Satya Nadella", "Cathie Wood", "Jamie Dimon", "Powell",
]

# Scoring thresholds
ALERT_SCORE_THRESHOLD = 5.0       # Composite score to trigger alert (out of 10)

# SMS via Gmail email-to-SMS gateway
_SMS_SETTINGS = _load_sms_settings()
SMS_ENABLED = _SMS_SETTINGS["enabled"]
SMS_PHONE_NUMBER = _SMS_SETTINGS["phone_number"]
SMS_CARRIER = _SMS_SETTINGS["carrier"]
SMS_GMAIL_USER = _SMS_SETTINGS["gmail_user"]
SMS_GMAIL_APP_PASSWORD = _SMS_SETTINGS["gmail_app_password"]

# Reddit
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_ENABLED = _env_flag("REDDIT_ENABLED", True)

# Google Trends
TRENDS_ENABLED = _env_flag("TRENDS_ENABLED", True)

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "alpha.db")

# RSS feeds to monitor
RSS_FEEDS = [
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("MarketWatch", "http://feeds.marketwatch.com/marketwatch/topstories/"),
    ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml"),
]
