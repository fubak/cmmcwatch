#!/usr/bin/env python3
"""
CMMC Watch Trend Collector - Collects CMMC/NIST compliance news.

Focused sources:
- Federal/Defense news RSS feeds
- CMMC-specific Reddit communities
- LinkedIn posts from key CMMC influencers
"""

import os
import re
import time
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set
from difflib import SequenceMatcher

import requests
import feedparser
from bs4 import BeautifulSoup

from config import (
    LIMITS,
    TIMEOUTS,
    DELAYS,
    CMMC_KEYWORDS,
    CMMC_CORE_KEYWORDS,
    NIST_KEYWORDS,
    DIB_KEYWORDS,
    CMMC_LINKEDIN_PROFILES,
    CMMC_RSS_FEEDS,
    setup_logging,
)

logger = setup_logging("collect_trends")


@dataclass
class Trend:
    """Represents a single trending topic."""

    title: str
    source: str
    url: Optional[str] = None
    description: Optional[str] = None
    category: str = "cmmc"
    score: float = 1.0
    keywords: List[str] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    image_url: Optional[str] = None


class TrendCollector:
    """Collects CMMC/compliance trends from multiple sources."""

    def __init__(self):
        self.trends: List[Trend] = []
        self.global_keywords: List[str] = []
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; CMMCWatch/1.0; +https://cmmcwatch.info)"
            }
        )

    def collect_all(self) -> List[Trend]:
        """Collect trends from all CMMC sources."""
        logger.info("Collecting CMMC trends from all sources...")

        # Collect from RSS feeds
        self._collect_rss_feeds()

        # Collect from Reddit
        self._collect_reddit()

        # Collect from LinkedIn
        self._collect_linkedin()

        # Deduplicate
        self._deduplicate()

        # Fetch og:image for articles without images
        self._fetch_missing_images()

        # Extract global keywords
        self._extract_global_keywords()

        logger.info(f"Total unique CMMC trends: {len(self.trends)}")
        return self.trends

    def _collect_rss_feeds(self):
        """Collect from CMMC-related RSS feeds."""
        logger.info("Fetching from CMMC RSS feeds...")
        count = 0

        for feed_name, feed_url in CMMC_RSS_FEEDS.items():
            try:
                response = self.session.get(feed_url, timeout=TIMEOUTS.get("rss", 15))
                response.raise_for_status()
                feed = feedparser.parse(response.content)

                for entry in feed.entries[: LIMITS.get("rss", 20)]:
                    title = entry.get("title", "").strip()
                    description = entry.get("summary", "") or entry.get(
                        "description", ""
                    )

                    if not title or len(title) < 10:
                        continue

                    # Check if CMMC-related
                    content = (title + " " + description).lower()
                    is_cmmc = any(kw.lower() in content for kw in CMMC_KEYWORDS)

                    if is_cmmc:
                        trend = Trend(
                            title=title[:200],
                            source=f"cmmc_rss_{feed_name.lower().replace(' ', '_')}",
                            url=entry.get("link"),
                            description=self._clean_html(description),
                            category=self._categorize_trend(title, description),
                            score=self._calculate_score(title, description),
                            image_url=self._extract_image_from_entry(entry),
                            timestamp=self._extract_timestamp(entry),
                        )
                        self.trends.append(trend)
                        count += 1

                time.sleep(DELAYS.get("rss", 0.2))

            except Exception as e:
                logger.warning(f"RSS feed {feed_name} error: {e}")
                continue

        logger.info(f"  Found {count} CMMC stories from RSS feeds")

    def _collect_reddit(self):
        """Collect from CMMC-related subreddits."""
        logger.info("Fetching from CMMC Reddit communities...")

        subreddits = [
            ("CMMC", "https://www.reddit.com/r/CMMC/.rss"),
            ("NISTControls", "https://www.reddit.com/r/NISTControls/.rss"),
            ("FederalEmployees", "https://www.reddit.com/r/FederalEmployees/.rss"),
            ("cybersecurity", "https://www.reddit.com/r/cybersecurity/.rss"),
            # r/GovContracting removed - subreddit returns 404
        ]

        count = 0
        for name, url in subreddits:
            try:
                response = self.session.get(
                    url,
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; CMMCWatch/1.0)"},
                )
                response.raise_for_status()
                feed = feedparser.parse(response.content)

                for entry in feed.entries[:15]:
                    title = entry.get("title", "").strip()
                    description = entry.get("summary", "")

                    if not title or len(title) < 10:
                        continue

                    # For CMMC/NISTControls, include all; others need keyword match
                    include_post = False
                    if name in ["CMMC", "NISTControls"]:
                        include_post = True
                    else:
                        content = (title + " " + description).lower()
                        include_post = any(
                            kw.lower() in content for kw in CMMC_KEYWORDS
                        )

                    if include_post:
                        trend = Trend(
                            title=title,
                            source=f"cmmc_reddit_{name.lower()}",
                            url=entry.get("link"),
                            description=self._clean_html(description),
                            category=self._categorize_trend(title, description),
                            score=1.4,
                            image_url=self._extract_image_from_entry(entry),
                            timestamp=self._extract_timestamp(entry),
                        )
                        self.trends.append(trend)
                        count += 1

                time.sleep(0.3)

            except Exception as e:
                logger.warning(f"Reddit r/{name} error: {e}")
                continue

        logger.info(f"  Found {count} stories from Reddit")

    def _collect_linkedin(self):
        """Collect from LinkedIn influencers via Apify."""
        if not CMMC_LINKEDIN_PROFILES:
            return

        logger.info("Fetching from CMMC LinkedIn influencers...")

        try:
            from fetch_linkedin_posts import (
                fetch_linkedin_posts,
                linkedin_posts_to_trends,
            )

            posts = fetch_linkedin_posts(CMMC_LINKEDIN_PROFILES)
            trend_dicts = linkedin_posts_to_trends(posts)

            for td in trend_dicts:
                trend = Trend(
                    title=td["title"],
                    source=td["source"],
                    url=td.get("url"),
                    description=td.get("description"),
                    category=td.get("category", "cmmc"),
                    score=td.get("score", 1.5),
                    keywords=td.get("keywords", []),
                    image_url=td.get("image_url"),
                )
                self.trends.append(trend)

            logger.info(f"  Found {len(trend_dicts)} posts from LinkedIn")

        except ImportError:
            logger.debug("LinkedIn scraping not available")
        except Exception as e:
            logger.warning(f"LinkedIn collection error: {e}")

    def _categorize_trend(self, title: str, description: str) -> str:
        """Categorize a trend based on keywords."""
        content = (title + " " + description).lower()

        # Check categories in priority order
        if any(kw.lower() in content for kw in CMMC_CORE_KEYWORDS):
            return "cmmc_program"
        elif any(kw.lower() in content for kw in NIST_KEYWORDS):
            return "nist_compliance"
        elif any(kw.lower() in content for kw in DIB_KEYWORDS):
            return "defense_industrial_base"
        else:
            return "federal_cybersecurity"

    def _calculate_score(self, title: str, description: str) -> float:
        """Calculate relevance score based on keyword matches."""
        content = (title + " " + description).lower()
        score = 1.0

        # Boost for core CMMC keywords
        core_matches = sum(1 for kw in CMMC_CORE_KEYWORDS if kw.lower() in content)
        score += core_matches * 0.3

        # Boost for NIST keywords
        nist_matches = sum(1 for kw in NIST_KEYWORDS if kw.lower() in content)
        score += nist_matches * 0.2

        return min(score, 3.0)  # Cap at 3.0

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""
        if "<" not in text:
            return re.sub(r"\s+", " ", text.strip())[:500]
        soup = BeautifulSoup(text, "html.parser")
        clean = soup.get_text(separator=" ").strip()
        return re.sub(r"\s+", " ", clean)[:500]

    def _extract_timestamp(self, entry) -> Optional[datetime]:
        """Extract publication timestamp from RSS entry."""
        # Try published_parsed first (feedparser standard)
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6])
            except (TypeError, ValueError):
                pass

        # Try updated_parsed
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                return datetime(*entry.updated_parsed[:6])
            except (TypeError, ValueError):
                pass

        # Try parsing published string
        published = entry.get("published") or entry.get("updated")
        if published:
            try:
                # Common RSS date format
                from email.utils import parsedate_to_datetime

                return parsedate_to_datetime(published)
            except (TypeError, ValueError):
                pass

        return None

    def _extract_image_from_entry(self, entry) -> Optional[str]:
        """Extract image URL from RSS entry.

        Checks multiple sources in priority order:
        1. media_content (standard RSS media extension)
        2. media_thumbnail (common in many feeds)
        3. enclosures (RSS 2.0 standard)
        4. Images embedded in content HTML
        5. Images embedded in summary HTML
        """
        # Check media_content
        if hasattr(entry, "media_content") and entry.media_content:
            for media in entry.media_content:
                if media.get("medium") == "image" or media.get("type", "").startswith(
                    "image"
                ):
                    url = media.get("url")
                    if url and self._is_valid_image_url(url):
                        return url

        # Check media_thumbnail
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            for thumb in entry.media_thumbnail:
                url = thumb.get("url")
                if url and self._is_valid_image_url(url):
                    return url

        # Check enclosures
        if hasattr(entry, "enclosures") and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get("type", "").startswith("image"):
                    url = enc.get("href") or enc.get("url")
                    if url and self._is_valid_image_url(url):
                        return url

        # Check content HTML for img tags
        if hasattr(entry, "content") and entry.content:
            content_html = entry.content[0].get("value", "")
            img_url = self._extract_img_from_html(content_html)
            if img_url:
                return img_url

        # Check summary HTML for img tags
        summary = entry.get("summary", "")
        if summary and "<img" in summary:
            img_url = self._extract_img_from_html(summary)
            if img_url:
                return img_url

        return None

    def _extract_img_from_html(self, html: str) -> Optional[str]:
        """Extract first valid image URL from HTML content."""
        if not html or "<img" not in html:
            return None

        # Use regex to find img src attributes
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        matches = re.findall(img_pattern, html, re.IGNORECASE)

        for url in matches:
            if self._is_valid_image_url(url):
                return url
        return None

    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL is a valid image URL (not a tracking pixel or icon)."""
        if not url:
            return False

        url_lower = url.lower()

        # Skip tracking pixels and tiny images
        skip_patterns = [
            "pixel",
            "tracking",
            "beacon",
            "1x1",
            "spacer",
            "blank",
            "clear.gif",
            "gravatar",
            "avatar",
            "icon",
            "logo",
            "badge",
            "button",
            "sprite",
        ]
        if any(p in url_lower for p in skip_patterns):
            return False

        # Must be http(s) URL
        if not url.startswith(("http://", "https://")):
            return False

        # Should have image extension or be from known image CDNs
        image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp")
        image_cdns = [
            "images.",
            "img.",
            "cdn.",
            "media.",
            "wp-content/uploads",
            "cloudfront",
            "amazonaws",
            "imgix",
            "arcpublishing",
        ]

        has_extension = any(
            url_lower.endswith(ext) or f"{ext}?" in url_lower
            for ext in image_extensions
        )
        from_cdn = any(cdn in url_lower for cdn in image_cdns)

        return has_extension or from_cdn

    def _fetch_missing_images(self):
        """Fetch og:image from article pages for trends without images.

        Only fetches from sources known to have og:image on their pages.
        Limited to prevent slowdown.
        """
        # Sources known to have og:image on article pages
        sources_with_og_image = [
            "cmmc_rss_fedscoop",
            "cmmc_rss_defensescoop",
            "cmmc_rss_securityweek",
        ]

        trends_to_fetch = [
            t
            for t in self.trends
            if not t.image_url and any(s in t.source for s in sources_with_og_image)
        ]

        if not trends_to_fetch:
            return

        logger.info(f"Fetching og:image for {len(trends_to_fetch)} articles...")
        fetched = 0

        for trend in trends_to_fetch[:10]:  # Limit to 10 requests
            try:
                og_image = self._fetch_og_image(trend.url)
                if og_image:
                    trend.image_url = og_image
                    fetched += 1
                time.sleep(0.3)  # Rate limiting
            except Exception as e:
                logger.debug(f"Failed to fetch og:image for {trend.url}: {e}")

        if fetched:
            logger.info(f"  Fetched {fetched} og:images from article pages")

    def _fetch_og_image(self, url: str) -> Optional[str]:
        """Fetch og:image meta tag from article page."""
        if not url:
            return None

        try:
            response = self.session.get(
                url,
                timeout=5,
                headers={"User-Agent": "Mozilla/5.0 (compatible; CMMCWatch/1.0)"},
            )
            response.raise_for_status()

            # Look for og:image meta tag
            patterns = [
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
            ]

            for pattern in patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    img_url = match.group(1)
                    if self._is_valid_image_url(img_url):
                        return img_url

        except requests.RequestException:
            pass

        return None

    def _deduplicate(self):
        """Remove duplicate trends based on title similarity."""
        if not self.trends:
            return

        unique = []
        seen_titles = set()

        for trend in self.trends:
            # Normalize title for comparison
            normalized = re.sub(r"[^\w\s]", "", trend.title.lower())
            normalized = " ".join(normalized.split()[:8])  # First 8 words

            # Check for duplicates
            is_dup = False
            for seen in seen_titles:
                if SequenceMatcher(None, normalized, seen).ratio() > 0.8:
                    is_dup = True
                    break

            if not is_dup:
                unique.append(trend)
                seen_titles.add(normalized)

        removed = len(self.trends) - len(unique)
        if removed > 0:
            logger.info(f"Removed {removed} duplicate trends")
        self.trends = unique

    def _extract_global_keywords(self):
        """Extract global keywords from all trends."""
        keyword_counts: Dict[str, int] = {}

        for trend in self.trends:
            words = re.findall(r"\b[a-zA-Z]{4,}\b", trend.title.lower())
            for word in words:
                if word not in {
                    "this",
                    "that",
                    "with",
                    "from",
                    "have",
                    "been",
                    "will",
                    "what",
                    "when",
                    "where",
                    "their",
                    "there",
                    "about",
                }:
                    keyword_counts[word] = keyword_counts.get(word, 0) + 1

        # Sort by frequency
        sorted_keywords = sorted(
            keyword_counts.items(), key=lambda x: x[1], reverse=True
        )
        self.global_keywords = [kw for kw, _ in sorted_keywords[:100]]

        logger.info(f"Found {len(self.global_keywords)} global keywords")

    def get_global_keywords(self) -> List[str]:
        """Return extracted global keywords."""
        return self.global_keywords


if __name__ == "__main__":
    collector = TrendCollector()
    trends = collector.collect_all()
    print(f"\nCollected {len(trends)} CMMC trends")
    for t in trends[:10]:
        print(f"  - [{t.category}] {t.title[:60]}...")
