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
            ("GovContracting", "https://www.reddit.com/r/GovContracting/.rss"),
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

    def _extract_image_from_entry(self, entry) -> Optional[str]:
        """Extract image URL from RSS entry."""
        # Check media_content
        if hasattr(entry, "media_content") and entry.media_content:
            for media in entry.media_content:
                if media.get("medium") == "image" or media.get("type", "").startswith(
                    "image"
                ):
                    return media.get("url")

        # Check enclosures
        if hasattr(entry, "enclosures") and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get("type", "").startswith("image"):
                    return enc.get("href") or enc.get("url")

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
