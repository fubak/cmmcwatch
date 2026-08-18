#!/usr/bin/env python3
"""
Configuration settings for CMMC Watch pipeline.

Centralizes all magic numbers, timeouts, and environment-specific settings.
"""

import logging
import os
import re
from pathlib import Path

from source_catalog import COLLECTOR_SOURCES

# ============================================================================
# SITE CONFIGURATION
# ============================================================================

SITE_NAME = "CMMC Watch"
SITE_URL = "https://cmmcwatch.com"
SITE_DESCRIPTION = "Daily CMMC & Compliance News Aggregator"

# ============================================================================
# ENVIRONMENT
# ============================================================================

# Detect environment
ENV = os.getenv("ENVIRONMENT", "production")
DEBUG = ENV == "development" or os.getenv("DEBUG", "").lower() == "true"

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data"
PUBLIC_DIR = PROJECT_ROOT / "public"

# ============================================================================
# LOGGING
# ============================================================================

LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ============================================================================
# TREND COLLECTION LIMITS
# ============================================================================

# Per-source limits (how many items to fetch from each source)
# Balanced for diverse content: World/General news gets more weight
LIMITS = {
    # General/World News (higher limits)
    "google_trends": 20,
    "news_rss": 10,  # Per feed - increased from 8
    "wikipedia": 20,
    # Reddit (balanced across categories)
    "reddit": 8,  # Per subreddit
    # Tech sources (reduced for balance)
    "tech_rss": 5,  # Per feed - reduced from 6
    "hackernews": 15,  # Reduced from 25
    "lobsters": 10,  # Reduced from 20
    "product_hunt": 8,  # Reduced from 15
    "devto": 8,  # Reduced from 15
    "slashdot": 6,  # Reduced from 10
    "ars_technica": 6,  # Reduced from 10
    "github_trending": 10,  # Reduced from 15
    # Other categories
    "science_rss": 8,  # Science news
    "politics_rss": 8,  # Politics news
    "finance_rss": 8,  # Finance/Business news
    "sports_rss": 6,  # Sports news
    "entertainment_rss": 6,  # Entertainment news
    "cmmc_rss": 8,  # CMMC/Federal compliance news
}

# ============================================================================
# CMMC RSS FEEDS
# ============================================================================

# Derived from the live catalog so this dict cannot drift from collection.
# Add or remove RSS sources in scripts/source_catalog.py, not here.
CMMC_RSS_FEEDS = {source.name: source.url for source in COLLECTOR_SOURCES if source.collector == "cmmc_rss"}

# ============================================================================
# CMMC WATCH KEYWORDS
# ============================================================================

# Keywords that indicate CMMC-specific content (highest priority)
CMMC_CORE_KEYWORDS = [
    "cmmc",
    "c3pao",
    "cyber-ab",
    "cyberab",
    "cmmc 2.0",
    "cmmc level",
    "cmmc certification",
    "cmmc assessment",
    "cmmc compliance",
]

# Keywords for NIST/Compliance content (second priority)
NIST_KEYWORDS = [
    "nist 800-171",
    "nist sp 800-171",
    "nist 800-172",
    "sp 800-172",
    "dfars",
    "dfars 252.204",
    "dfars 7012",
    "cui",
    "controlled unclassified",
    "fedramp",
    "fisma",
    "ato",
    "authority to operate",
]

# Keywords for Defense Industrial Base (third priority)
DIB_KEYWORDS = [
    "defense industrial base",
    "dib",
    "defense contractor",
    "dod contractor",
    "cleared contractor",
    "defense contract",
    "pentagon",
    "dod cybersecurity",
]

# Keywords for Intelligence Threats (espionage, counterintelligence, nation-state)
INTELLIGENCE_KEYWORDS = [
    # Espionage
    "espionage",
    "spy",
    "spying",
    "spied",
    "foreign agent",
    "foreign intelligence",
    "counterintelligence",
    "counterespionage",
    "intelligence officer",
    "covert",
    # Nation-state threat actors
    "apt",
    "advanced persistent threat",
    "state-sponsored",
    "nation-state",
    "chinese hackers",
    "russian hackers",
    "north korean hackers",
    "iranian hackers",
    "gru",
    "fsb",
    "mss",
    "pla",
    "lazarus group",
    "apt29",
    "apt28",
    "cozy bear",
    "fancy bear",
    "volt typhoon",
    "salt typhoon",
    # Intelligence agencies
    "cia",
    "fbi counterintelligence",
    "nsa",
    "dia",
    "five eyes",
    # Tradecraft
    "dead drop",
    "handler",
    "asset recruitment",
    "classified information",
    "national security",
    "treason",
]

# Keywords for Insider Threats
INSIDER_THREAT_KEYWORDS = [
    "insider threat",
    "insider risk",
    "malicious insider",
    "trusted insider",
    "employee threat",
    "internal threat",
    "data exfiltration",
    "unauthorized disclosure",
    "dark web recruitment",
    "employee recruitment",
    "bribery",
    "compromised employee",
    "security clearance",
    "clearance revoked",
    "access abuse",
    "privilege abuse",
    "sabotage",
    "whistleblower",  # Context matters
    "leaker",
    "unauthorized access",
    "credential theft",
    "social engineering",
    "phishing employee",
    "fake identity",
    "fraudulent identity",
    "remote worker fraud",
    "contractor fraud",
]

# ============================================================================
# CMMC LINKEDIN INFLUENCERS
# ============================================================================

# Key CMMC and national security influencers to track on LinkedIn
# Uses apimaestro/linkedin-profile-posts actor (~$0.01/profile/run)
CMMC_LINKEDIN_PROFILES = [
    # Government / CMMC Leadership:
    "https://www.linkedin.com/in/katie-arrington-a6949425/",  # Katie Arrington - DoD CIO
    "https://www.linkedin.com/in/stacy-bostjanick-a3b67173/",  # Stacy Bostjanick - CMMC implementation lead
    "https://www.linkedin.com/in/matthewtravisdc/",  # Matthew Travis - Cyber-AB CEO
    # CMMC Industry Experts:
    "https://www.linkedin.com/in/amira-armond/",  # Amira Armond - Kieri Solutions (C3PAO)
    "https://www.linkedin.com/in/mscottedwards/",  # Scott Edwards - Summit 7 CEO
    "https://www.linkedin.com/in/jacob-evan-horne/",  # Jacob Horne - Summit 7
    "https://www.linkedin.com/in/danielakridge/",  # Daniel Akridge - "That CMMC Show"
    "https://www.linkedin.com/in/jacobrhill/",  # Jacob Hill - Summit 7
    "https://www.linkedin.com/in/joybeland/",  # Joy Beland - CMMC consultant
]

# LinkedIn scraper limits (to stay within Apify's $5/month free tier).
# Uses apimaestro/linkedin-profile-posts actor on Apify. With 9 profiles, the full
# list is scraped every other day at 3 posts each — well under the free tier. The
# cadence is stateless (day-of-year parity) because CI wipes data/*.json each run,
# so a persisted "last fetched" timestamp would not survive between runs.
LINKEDIN_MAX_PROFILES = 10  # Max profiles scraped per run (9 currently configured)
LINKEDIN_MAX_POSTS_PER_PROFILE = 3  # Max posts per profile (reduced from 5 for cost)
LINKEDIN_FETCH_EVERY_N_DAYS = 2  # Scrape on 1-in-N days (by day-of-year); 2 = every other day

# ============================================================================
# CMMC WATCH KEYWORDS (COMPOSITE)
# ============================================================================

# Additional keywords not covered by category-specific lists above
_ADDITIONAL_KEYWORDS = [
    "nist framework",
    "nist cybersecurity",
    "dfars compliance",
    "industrial security",
    "department of defense",
    # Federal cybersecurity (broader)
    "federal cybersecurity",
    "dod cybersecurity",
    "government compliance",
    "federal zero trust",
    "cisa",
    "cybersecurity agency",
    "federal cio",
    "government cyber",
    "federal it security",
    "defense cyber",
    "military cyber",
    # Contract/Acquisition
    "defense contract",
    "dod contract",
    "federal contract",
    "government contract award",
    "cleared defense",
    # Supply chain security
    "supply chain security",
    "supply chain risk",
    "scrm",
]


def keyword_in_text(keyword: str, text: str) -> bool:
    """True if keyword occurs in text.

    Multi-word / punctuated phrases stay substring matches ("nist 800-171").
    Short tokens use word boundaries so "pla" does not match "platform".
    """
    if not keyword or not text:
        return False
    kw = keyword.lower()
    hay = text.lower()
    if any(ch.isspace() or ch in ".-/" for ch in kw):
        return kw in hay
    return re.search(r"\b" + re.escape(kw) + r"\b", hay) is not None


# Composite keyword list for filtering CMMC-relevant content from RSS feeds
# Composed from category-specific lists plus additional broader keywords
CMMC_KEYWORDS = list(
    dict.fromkeys(
        CMMC_CORE_KEYWORDS
        + NIST_KEYWORDS
        + DIB_KEYWORDS
        + INTELLIGENCE_KEYWORDS
        + INSIDER_THREAT_KEYWORDS
        + _ADDITIONAL_KEYWORDS
    )
)

# Quality gates
MIN_TRENDS = 5  # Minimum trends required to build
MIN_FRESH_RATIO = 0.5  # At least 50% of trends must be from past 24h
TREND_FRESHNESS_HOURS = 24  # How old a trend can be to count as "fresh"

# ============================================================================
# API TIMEOUTS & RETRIES
# ============================================================================

# HTTP request timeouts (seconds)
TIMEOUTS = {
    "default": 15,
    "hackernews_story": 5,
    "rss_feed": 20,  # Increased for slow feeds like Washington Post
    "image_api": 15,
    "ai_api": 30,
}

# Retry settings
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2  # Exponential backoff: 1s, 2s, 4s
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]
MAX_RETRY_WAIT_SECONDS = 10  # Cap retry waits to prevent long delays (e.g., 360s from Groq)

# Rate limiting delays (seconds)
DELAYS = {
    "between_sources": 0.5,
    "between_requests": 0.15,
    "between_images": 0.3,
}

# ============================================================================
# IMAGE SETTINGS
# ============================================================================

# Cache settings
IMAGE_CACHE_DIR = DATA_DIR / "image_cache"
IMAGE_CACHE_MAX_AGE_DAYS = 7
IMAGE_CACHE_MAX_ENTRIES = 500

# Fetching settings
IMAGES_PER_KEYWORD = 3  # Images to fetch per keyword (was 2)
MAX_IMAGE_KEYWORDS = 10  # Max keywords to search for (was 8)
MIN_IMAGES_REQUIRED = 5  # Total: 30 images (10 × 3) for better variety


# ============================================================================
# API KEY ROTATION
# ============================================================================


def get_api_keys(env_var: str) -> list:
    """
    Get API keys from environment variable, supporting comma-separated multiple keys.

    Example: PEXELS_API_KEY="key1,key2,key3"

    Args:
        env_var: Environment variable name

    Returns:
        List of API keys (empty if not set)
    """
    value = os.getenv(env_var, "")
    if not value:
        return []
    # Split by comma and strip whitespace
    keys = [k.strip() for k in value.split(",") if k.strip()]
    return keys


# API key collections (supports multiple keys per service for rotation)
PEXELS_KEYS = get_api_keys("PEXELS_API_KEY")
UNSPLASH_KEYS = get_api_keys("UNSPLASH_ACCESS_KEY")
PIXABAY_KEYS = get_api_keys("PIXABAY_API_KEY")
GROQ_KEYS = get_api_keys("GROQ_API_KEY")
OPENROUTER_KEYS = get_api_keys("OPENROUTER_API_KEY")

# ============================================================================
# DEDUPLICATION
# ============================================================================

# Similarity threshold for considering two titles as duplicates
DEDUP_SIMILARITY_THRESHOLD = 0.8
DEDUP_SEMANTIC_THRESHOLD = 0.7  # Lower threshold for semantic matching

# ============================================================================
# DESIGN SETTINGS
# ============================================================================

# Font whitelist (prevents injection via font names)
ALLOWED_FONTS = [
    "Space Grotesk",
    "Inter",
    "Playfair Display",
    "Roboto",
    "Open Sans",
    "Lato",
    "Montserrat",
    "Oswald",
    "Raleway",
    "Poppins",
    "Merriweather",
    "Source Sans Pro",
    "Nunito",
    "Work Sans",
    "Fira Sans",
    "IBM Plex Sans",
    "IBM Plex Mono",
    "JetBrains Mono",
    "Courier Prime",
    "DM Sans",
    "Outfit",
    "Plus Jakarta Sans",
    "Sora",
    "Lexend",
    "Manrope",
    "Archivo",
]

# ============================================================================
# ARCHIVE SETTINGS
# ============================================================================

ARCHIVE_KEEP_DAYS = 30
ARCHIVE_SUBDIR = "archive"

# ============================================================================
# RSS FEED SETTINGS
# ============================================================================

RSS_FEED_TITLE = "CMMC Watch"
RSS_FEED_DESCRIPTION = "Daily CMMC, NIST 800-171, and federal cybersecurity compliance news aggregator"
RSS_FEED_LINK = "https://cmmcwatch.com"
RSS_FEED_MAX_ITEMS = 50

# ============================================================================
# KEYWORD TRENDING
# ============================================================================

KEYWORD_HISTORY_FILE = DATA_DIR / "keyword_history.json"
KEYWORD_HISTORY_DAYS = 30  # How many days to keep keyword history


def setup_logging(name: str = "cmmcwatch") -> logging.Logger:
    """Configure and return a logger instance."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        logger.addHandler(handler)

    logger.setLevel(LOG_LEVEL)
    return logger
