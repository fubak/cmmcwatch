#!/usr/bin/env python3
"""
LinkedIn Post Scraper - Fetches posts from key CMMC influencers via Apify.

Uses the apimaestro/linkedin-profile-posts actor on Apify to pull
recent posts from specified LinkedIn profiles.

Free tier limits (Apify):
- $5 credits per month
- 3 concurrent actors max
- 7-day data retention

To stay within free limits:
- Runs once daily (via main pipeline)
- Limited to 10 influencers max
- Fetches only 5 most recent posts per profile
- Tracks last fetch time to skip already-seen posts
"""

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import setup_logging

logger = setup_logging("linkedin_scraper")

# Default actor ID - can be overridden via environment variable
DEFAULT_APIFY_ACTOR = "apimaestro/linkedin-profile-posts"

# Conservative limits to stay within Apify free tier
MAX_PROFILES = 10  # Maximum profiles to scrape per run
MAX_POSTS_PER_PROFILE = 5  # Maximum posts per profile
SCRAPER_TIMEOUT_SECONDS = 120  # Max wait time for scraper

# Last-fetched tracking file
LAST_FETCHED_FILE = Path(__file__).parent.parent / "data" / "linkedin_last_fetched.json"


@dataclass
class LinkedInPost:
    """Represents a LinkedIn post from a CMMC influencer."""

    title: str  # Post excerpt or author name
    author_name: str
    author_title: str
    author_url: str
    post_url: str
    content: str
    timestamp: Optional[datetime] = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    profile_picture: Optional[str] = None
    headline: Optional[str] = None
    post_type: Optional[str] = None


def get_apify_client():
    """
    Get the Apify client, importing only when needed.

    Returns:
        ApifyClient instance or None if not available
    """
    api_key = os.getenv("APIFY_API_KEY")
    if not api_key:
        logger.warning("APIFY_API_KEY not set - LinkedIn scraping disabled")
        return None

    try:
        from apify_client import ApifyClient

        return ApifyClient(api_key)
    except ImportError:
        logger.warning("apify-client not installed - run: pip install apify-client")
        return None


def _get_profile_username(profile_url: str) -> str:
    """Extract username from LinkedIn profile URL.

    Example: https://www.linkedin.com/in/katie-arrington-a6949425/ -> katie-arrington-a6949425
    """
    match = re.search(r"linkedin\.com/in/([^/]+)", profile_url)
    if match:
        return match.group(1).rstrip("/")
    return profile_url


def _load_last_fetched() -> dict:
    """Load last-fetched tracking data."""
    try:
        if LAST_FETCHED_FILE.exists():
            with open(LAST_FETCHED_FILE) as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.debug(f"Could not load last-fetched data: {e}")
    return {}


def _save_last_fetched(data: dict) -> None:
    """Save last-fetched tracking data."""
    try:
        LAST_FETCHED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LAST_FETCHED_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        logger.warning(f"Could not save last-fetched data: {e}")


def fetch_linkedin_posts(
    profile_urls: List[str],
    max_posts_per_profile: int = MAX_POSTS_PER_PROFILE,
) -> List[LinkedInPost]:
    """
    Fetch recent posts from LinkedIn profiles using Apify.

    Args:
        profile_urls: List of LinkedIn profile URLs to scrape
        max_posts_per_profile: Maximum posts to fetch per profile

    Returns:
        List of LinkedInPost objects
    """
    client = get_apify_client()
    if not client:
        return []

    actor_id = os.getenv("APIFY_ACTOR_ID", DEFAULT_APIFY_ACTOR)

    # Respect free tier limits
    profiles_to_scrape = profile_urls[:MAX_PROFILES]
    if len(profile_urls) > MAX_PROFILES:
        logger.warning(f"Limiting to {MAX_PROFILES} profiles (requested: {len(profile_urls)})")

    # Load last-fetched timestamp for filtering old posts
    last_fetched = _load_last_fetched()
    last_fetched_ts = last_fetched.get("last_fetched_ts", 0)

    posts = []

    for profile_url in profiles_to_scrape:
        try:
            username = _get_profile_username(profile_url)
            logger.info(f"Fetching posts from: {username}")

            # Prepare input for the new actor
            run_input = {
                "username": username,
                "total_posts": max_posts_per_profile,
            }

            # Run the actor and wait for completion
            run = client.actor(actor_id).call(
                run_input=run_input,
                timeout_secs=SCRAPER_TIMEOUT_SECONDS,
            )

            # Fetch results from the dataset
            dataset_items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

            new_count = 0
            for item in dataset_items:
                # Filter out reposts
                post_type = item.get("post_type", "regular")
                if post_type == "repost":
                    continue

                # Filter out posts older than last fetch
                posted_at = item.get("posted_at", {})
                post_ts = posted_at.get("timestamp", 0)
                if last_fetched_ts and post_ts and post_ts <= last_fetched_ts:
                    continue

                post = _parse_linkedin_item(item)
                if post:
                    posts.append(post)
                    new_count += 1

            logger.info(f"  Found {len(dataset_items)} posts, {new_count} new (filtered reposts and old)")

            # Small delay between profiles to be respectful
            time.sleep(1)

        except Exception as e:
            logger.warning(f"Failed to fetch posts from {profile_url}: {e}")
            continue

    # Update last-fetched timestamp
    if posts:
        now = datetime.now()
        _save_last_fetched(
            {
                "last_fetched_ts": int(now.timestamp() * 1000),
                "last_fetched_date": now.isoformat(),
            }
        )

    logger.info(f"Total LinkedIn posts collected: {len(posts)}")
    return posts


def _parse_linkedin_item(item: Dict) -> Optional[LinkedInPost]:
    """
    Parse a raw Apify result item into a LinkedInPost.

    Handles the apimaestro/linkedin-profile-posts output format.
    """
    try:
        # Extract content
        content = item.get("text") or ""
        if not content:
            return None

        # Extract author info
        author = item.get("author", {})
        first_name = author.get("first_name", "")
        last_name = author.get("last_name", "")
        author_name = f"{first_name} {last_name}".strip() or "Unknown"

        author_title = author.get("headline", "")
        author_url = author.get("profile_url", "")
        profile_picture = author.get("profile_picture", "")

        post_url = item.get("url", "")

        # Extract timestamp
        timestamp = None
        posted_at = item.get("posted_at", {})
        date_str = posted_at.get("date", "")
        if date_str:
            try:
                # Format: "2026-02-01 14:20:41"
                timestamp = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                pass

        # Extract engagement metrics
        stats = item.get("stats", {})
        likes = int(stats.get("total_reactions", 0) or 0)
        comments = int(stats.get("comments", 0) or 0)
        shares = int(stats.get("reposts", 0) or 0)

        # Post type
        post_type = item.get("post_type", "regular")

        # Create title from content excerpt
        title = content[:100].replace("\n", " ").strip()
        if len(content) > 100:
            title += "..."

        return LinkedInPost(
            title=title,
            author_name=author_name,
            author_title=author_title,
            author_url=author_url,
            post_url=post_url,
            content=content,
            timestamp=timestamp,
            likes=likes,
            comments=comments,
            shares=shares,
            profile_picture=profile_picture,
            headline=author_title,
            post_type=post_type,
        )

    except Exception as e:
        logger.debug(f"Failed to parse LinkedIn item: {e}")
        return None


def linkedin_posts_to_trends(posts: List[LinkedInPost]) -> List[Dict]:
    """
    Convert LinkedIn posts to the trend format used by the pipeline.

    Args:
        posts: List of LinkedInPost objects

    Returns:
        List of trend dictionaries compatible with Trend dataclass
    """
    trends = []

    for post in posts:
        # Create a trend-compatible dictionary
        trend = {
            "title": f"{post.author_name}: {post.title}",
            "source": "cmmc_linkedin",
            "url": post.post_url or post.author_url,
            "description": post.content[:500],
            "category": "cmmc",
            "score": _calculate_post_score(post),
            "keywords": _extract_keywords(post.content),
            "timestamp": post.timestamp.isoformat() if post.timestamp else None,
            "image_url": None,
            # LinkedIn-specific metadata for influencer sidebar
            "linkedin_author_picture": post.profile_picture,
            "linkedin_author_headline": post.headline,
            "linkedin_engagement": {
                "total_reactions": post.likes,
                "comments": post.comments,
                "reposts": post.shares,
            },
        }
        trends.append(trend)

    return trends


def _calculate_post_score(post: LinkedInPost) -> float:
    """
    Calculate a relevance score for a LinkedIn post.

    Based on engagement metrics and recency.
    """
    base_score = 1.5  # LinkedIn posts from key people are valuable

    # Engagement boost (capped)
    engagement = post.likes + (post.comments * 2) + (post.shares * 3)
    engagement_boost = min(engagement / 100, 1.0)  # Max 1.0 boost

    # Recency boost
    recency_boost = 0.0
    if post.timestamp:
        age_hours = (datetime.now() - post.timestamp).total_seconds() / 3600
        if age_hours < 24:
            recency_boost = 0.5
        elif age_hours < 72:
            recency_boost = 0.25

    return base_score + engagement_boost + recency_boost


def _extract_keywords(content: str) -> List[str]:
    """Extract meaningful keywords from post content."""
    # CMMC-specific keywords to look for
    cmmc_terms = {
        "cmmc",
        "nist",
        "dfars",
        "c3pao",
        "cui",
        "fedramp",
        "cybersecurity",
        "compliance",
        "dod",
        "defense",
        "certification",
        "assessment",
        "800-171",
        "contractor",
        "security",
    }

    # Extract words
    words = re.findall(r"\b[a-zA-Z0-9-]{3,}\b", content.lower())

    # Find CMMC-related keywords
    keywords = []
    seen = set()
    for word in words:
        if word in cmmc_terms and word not in seen:
            keywords.append(word)
            seen.add(word)

    return keywords[:5]  # Top 5 keywords


def test_connection() -> bool:
    """
    Test the Apify connection without running a full scrape.

    Returns:
        True if connection is working, False otherwise
    """
    client = get_apify_client()
    if not client:
        return False

    try:
        # Just check we can access the API
        user_info = client.user().get()
        logger.info(f"Apify connection OK - User: {user_info.get('username', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Apify connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test mode
    print("LinkedIn Post Scraper for CMMC Watch")
    print("=" * 40)

    if test_connection():
        print("✓ Apify connection successful")
    else:
        print("✗ Apify connection failed")
        print("  Set APIFY_API_KEY environment variable")
