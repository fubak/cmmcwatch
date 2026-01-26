#!/usr/bin/env python3
"""
LinkedIn API - Fetch Posts from Profiles

Uses official LinkedIn API instead of Apify scraping.
More reliable, free tier, and won't get blocked.

Note: LinkedIn API has limited access to personal profile posts.
This script focuses on organization/company page posts which are publicly accessible.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
import requests
from typing import List, Dict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import setup_logging, TIMEOUTS
from dotenv import load_dotenv

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

logger = setup_logging(__name__)

# LinkedIn API endpoints
API_BASE = "https://api.linkedin.com/v2"
USERINFO_URL = f"{API_BASE}/userinfo"  # Get your profile info
SHARES_URL = f"{API_BASE}/ugcPosts"  # Fetch posts


class LinkedInAPI:
    """LinkedIn API client"""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    def get_profile_info(self) -> Dict:
        """Get authenticated user's profile info"""
        try:
            response = requests.get(
                USERINFO_URL, headers=self.headers, timeout=TIMEOUTS["default"]
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch profile info: {e}")
            return {}

    def get_organization_posts(
        self, org_id: str, max_results: int = 10
    ) -> List[Dict]:
        """
        Fetch posts from an organization/company page.

        Args:
            org_id: LinkedIn organization URN (e.g., "urn:li:organization:123456")
            max_results: Maximum number of posts to fetch

        Returns:
            List of post objects
        """
        params = {
            "q": "authors",
            "authors": f"List({org_id})",
            "count": max_results,
            "sortBy": "LAST_MODIFIED",
        }

        try:
            response = requests.get(
                SHARES_URL, headers=self.headers, params=params, timeout=TIMEOUTS["default"]
            )
            response.raise_for_status()
            data = response.json()

            posts = []
            for element in data.get("elements", []):
                post = self._parse_post(element)
                if post:
                    posts.append(post)

            logger.info(f"Fetched {len(posts)} posts from organization {org_id}")
            return posts

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch organization posts: {e}")
            return []

    def _parse_post(self, element: Dict) -> Dict:
        """Parse a LinkedIn post element into a simplified format"""
        try:
            # Extract text content
            text = ""
            if "specificContent" in element:
                share_content = element["specificContent"].get(
                    "com.linkedin.ugc.ShareContent", {}
                )
                share_commentary = share_content.get("shareCommentary", {})
                text = share_commentary.get("text", "")

            # Extract timestamps
            created_ts = element.get("created", {}).get("time", 0)
            modified_ts = element.get("lastModified", {}).get("time", 0)

            # Convert timestamps to ISO format
            created_at = (
                datetime.fromtimestamp(created_ts / 1000).isoformat()
                if created_ts
                else None
            )
            modified_at = (
                datetime.fromtimestamp(modified_ts / 1000).isoformat()
                if modified_ts
                else None
            )

            # Extract post ID
            post_id = element.get("id", "")

            # Build post URL (may not work for all posts)
            post_url = ""
            if post_id:
                # Extract numeric ID from URN
                numeric_id = post_id.split(":")[-1] if ":" in post_id else post_id
                post_url = f"https://www.linkedin.com/feed/update/{post_id}"

            return {
                "id": post_id,
                "url": post_url,
                "text": text,
                "created_at": created_at,
                "modified_at": modified_at,
                "author": element.get("author", ""),
            }

        except Exception as e:
            logger.error(f"Failed to parse post: {e}")
            return None


def get_profile_username_from_url(profile_url: str) -> str:
    """Extract username from LinkedIn profile URL"""
    # https://www.linkedin.com/in/username/ -> username
    # https://www.linkedin.com/company/company-name/ -> company-name
    if "/in/" in profile_url:
        return profile_url.split("/in/")[1].strip("/")
    elif "/company/" in profile_url:
        return profile_url.split("/company/")[1].strip("/")
    return ""


def fetch_posts_for_profiles(
    profiles: List[str], max_posts_per_profile: int = 3
) -> List[Dict]:
    """
    Fetch posts from a list of LinkedIn profile URLs.

    Note: This is a placeholder for the full implementation.
    LinkedIn API v2 has limited access to personal profile posts.

    For production use:
    1. Convert profile URLs to organization URNs (if company pages)
    2. Use LinkedIn API to fetch organization posts
    3. For personal profiles, consider using RSSHub or Apify as fallback

    Args:
        profiles: List of LinkedIn profile URLs
        max_posts_per_profile: Maximum posts to fetch per profile

    Returns:
        List of post objects
    """
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")

    if not access_token:
        logger.error("LINKEDIN_ACCESS_TOKEN not set in .env")
        logger.error("Run: python3 scripts/linkedin_oauth.py")
        return []

    client = LinkedInAPI(access_token)

    # Test: Get profile info
    profile_info = client.get_profile_info()
    if profile_info:
        logger.info(f"Authenticated as: {profile_info.get('name', 'Unknown')}")

    all_posts = []

    # Note: This is a simplified implementation
    # You'll need to map profile URLs to organization URNs
    # or use a different approach for personal profiles

    logger.warning(
        "LinkedIn API has limited access to personal profile posts."
    )
    logger.warning(
        "For production, consider using RSSHub or keeping Apify for personal profiles."
    )
    logger.warning(
        "This script works best for organization/company pages."
    )

    return all_posts


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Fetch LinkedIn posts via official API"
    )
    parser.add_argument(
        "--test", action="store_true", help="Test API connection and credentials"
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        help="LinkedIn profile URLs to fetch",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=3,
        help="Maximum posts per profile (default: 3)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path",
    )

    args = parser.parse_args()

    # Test mode
    if args.test:
        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        if not access_token:
            print("❌ LINKEDIN_ACCESS_TOKEN not set in .env")
            print("   Run: python3 scripts/linkedin_oauth.py")
            sys.exit(1)

        client = LinkedInAPI(access_token)
        profile_info = client.get_profile_info()

        if profile_info:
            print("\n✅ LinkedIn API connection successful!")
            print(f"   Authenticated as: {profile_info.get('name', 'Unknown')}")
            print(f"   Email: {profile_info.get('email', 'Unknown')}")
            print(f"   Profile: {profile_info.get('sub', 'Unknown')}")
        else:
            print("\n❌ Failed to connect to LinkedIn API")
            sys.exit(1)

        return

    # Fetch posts
    profiles = args.profiles or []
    if not profiles:
        print("❌ No profiles specified. Use --profiles or see --help")
        sys.exit(1)

    posts = fetch_posts_for_profiles(profiles, args.max_posts)

    # Output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(posts, f, indent=2)
        print(f"✅ Saved {len(posts)} posts to {output_path}")
    else:
        print(json.dumps(posts, indent=2))


if __name__ == "__main__":
    main()
