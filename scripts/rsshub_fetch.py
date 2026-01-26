#!/usr/bin/env python3
"""
RSSHub LinkedIn Fetcher - Pull LinkedIn posts via RSS feeds

Uses RSSHub to convert LinkedIn profiles to RSS feeds.
Free, reliable, no API limits when self-hosted.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import feedparser
import requests

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    setup_logging,
    CMMC_LINKEDIN_PROFILES,
    LINKEDIN_MAX_POSTS_PER_PROFILE,
    TIMEOUTS,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

logger = setup_logging(__name__)

# RSSHub endpoint (default: local Docker instance)
RSSHUB_URL = os.getenv("RSSHUB_URL", "http://localhost:1200")


def profile_url_to_rsshub(profile_url: str) -> str:
    """
    Convert LinkedIn profile URL to RSSHub feed URL.

    Examples:
        https://www.linkedin.com/in/katie-arrington-a6949425/
        → http://localhost:1200/linkedin/in/katie-arrington-a6949425

        https://www.linkedin.com/company/cyber-ab/
        → http://localhost:1200/linkedin/company/cyber-ab

    Args:
        profile_url: LinkedIn profile URL

    Returns:
        RSSHub feed URL
    """
    # Extract username from profile URL
    if "/in/" in profile_url:
        username = profile_url.split("/in/")[1].strip("/")
        return f"{RSSHUB_URL}/linkedin/in/{username}"
    elif "/company/" in profile_url:
        company = profile_url.split("/company/")[1].strip("/")
        return f"{RSSHUB_URL}/linkedin/company/{company}"
    else:
        logger.error(f"Invalid LinkedIn URL format: {profile_url}")
        return ""


def fetch_linkedin_posts_via_rsshub(
    profile_url: str, max_posts: int = 3
) -> List[Dict]:
    """
    Fetch LinkedIn posts from a profile via RSSHub.

    Args:
        profile_url: LinkedIn profile URL
        max_posts: Maximum number of posts to fetch

    Returns:
        List of post dictionaries
    """
    feed_url = profile_url_to_rsshub(profile_url)
    if not feed_url:
        return []

    try:
        # Test RSSHub availability first
        health_url = f"{RSSHUB_URL}/healthz"
        try:
            health_check = requests.get(health_url, timeout=5)
            if health_check.status_code != 200:
                logger.warning(f"RSSHub health check failed (using fallback)")
        except requests.exceptions.RequestException:
            logger.warning(f"RSSHub not responding at {RSSHUB_URL}")
            logger.warning(f"Is RSSHub running? See scripts/rsshub_setup.md")
            return []

        # Fetch RSS feed
        logger.info(f"Fetching LinkedIn posts from: {feed_url}")
        feed = feedparser.parse(feed_url, request_headers={
            "User-Agent": "CMMC-Watch/1.0"
        })

        if feed.bozo:
            logger.error(f"Failed to parse RSS feed: {feed.bozo_exception}")
            return []

        posts = []
        for entry in feed.entries[:max_posts]:
            # Extract post data
            post = {
                "title": entry.get("title", "").strip(),
                "url": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", "").strip(),
                "author": entry.get("author", "Unknown"),
                "source": "linkedin",
                "source_profile": profile_url,
            }

            # Parse publish date
            if entry.get("published_parsed"):
                pub_date = datetime(*entry.published_parsed[:6])
                post["published_iso"] = pub_date.isoformat()
            else:
                post["published_iso"] = None

            posts.append(post)

        logger.info(f"Fetched {len(posts)} posts from {profile_url}")
        return posts

    except Exception as e:
        logger.error(f"Error fetching posts from {profile_url}: {e}")
        return []


def fetch_all_cmmc_profiles(max_posts_per_profile: int = 3) -> List[Dict]:
    """
    Fetch LinkedIn posts from all CMMC profiles.

    Args:
        max_posts_per_profile: Maximum posts to fetch per profile

    Returns:
        List of all posts from all profiles
    """
    all_posts = []

    logger.info(f"Fetching posts from {len(CMMC_LINKEDIN_PROFILES)} CMMC profiles...")

    for profile_url in CMMC_LINKEDIN_PROFILES:
        posts = fetch_linkedin_posts_via_rsshub(profile_url, max_posts_per_profile)
        all_posts.extend(posts)

    logger.info(f"Total posts fetched: {len(all_posts)}")
    return all_posts


def test_rsshub_connection() -> bool:
    """Test RSSHub connection and return True if working"""
    try:
        # Try health check endpoint
        health_url = f"{RSSHUB_URL}/healthz"
        response = requests.get(health_url, timeout=5)

        if response.status_code == 200:
            logger.info(f"✅ RSSHub is running at {RSSHUB_URL}")
            return True
        else:
            logger.error(f"❌ RSSHub health check failed (status {response.status_code})")
            return False

    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Cannot connect to RSSHub at {RSSHUB_URL}")
        logger.error(f"   Is RSSHub running? Try: docker start rsshub")
        logger.error(f"   See scripts/rsshub_setup.md for installation")
        return False

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ RSSHub connection error: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Fetch LinkedIn posts via RSSHub"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test RSSHub connection and fetch from all CMMC profiles",
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        help="LinkedIn profile URLs to fetch (overrides config)",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=LINKEDIN_MAX_POSTS_PER_PROFILE,
        help=f"Maximum posts per profile (default: {LINKEDIN_MAX_POSTS_PER_PROFILE})",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path",
    )

    args = parser.parse_args()

    # Test mode
    if args.test:
        print("\n" + "=" * 60)
        print("RSSHub LinkedIn Fetcher - Connection Test")
        print("=" * 60)

        # Test RSSHub connection
        if not test_rsshub_connection():
            print("\n❌ RSSHub is not running or not accessible")
            print("\nTo start RSSHub:")
            print("  docker run -d --name rsshub -p 1200:1200 diygod/rsshub:latest")
            print("\nSee scripts/rsshub_setup.md for details")
            sys.exit(1)

        # Fetch from all CMMC profiles
        print(f"\nFetching posts from {len(CMMC_LINKEDIN_PROFILES)} CMMC profiles...")
        print("-" * 60)

        posts = fetch_all_cmmc_profiles(args.max_posts)

        if posts:
            print(f"\n✅ Successfully fetched {len(posts)} posts!\n")

            # Show sample
            for i, post in enumerate(posts[:5], 1):
                print(f"{i}. {post['author']}: {post['title'][:60]}...")
                print(f"   {post['url']}")
                print()

            if len(posts) > 5:
                print(f"... and {len(posts) - 5} more posts\n")
        else:
            print("\n❌ No posts fetched. Check logs above for errors.\n")

        return

    # Normal mode: fetch specific profiles or all CMMC profiles
    profiles = args.profiles or CMMC_LINKEDIN_PROFILES

    if not profiles:
        print("❌ No profiles specified. Use --profiles or --test")
        sys.exit(1)

    # Test connection first
    if not test_rsshub_connection():
        print("\n❌ RSSHub is not accessible. Exiting.")
        sys.exit(1)

    # Fetch posts
    all_posts = []
    for profile_url in profiles:
        posts = fetch_linkedin_posts_via_rsshub(profile_url, args.max_posts)
        all_posts.extend(posts)

    # Output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(all_posts, f, indent=2)
        print(f"✅ Saved {len(all_posts)} posts to {output_path}")
    else:
        print(json.dumps(all_posts, indent=2))


if __name__ == "__main__":
    main()
