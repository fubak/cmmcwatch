#!/usr/bin/env python3
"""
CMMC Watch Trend Collector - Collects CMMC/NIST compliance news.

Focused sources:
- Federal/Defense news RSS feeds
- CMMC-specific Reddit communities
- LinkedIn posts from key CMMC influencers
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from config import (
    CMMC_CORE_KEYWORDS,
    CMMC_KEYWORDS,
    CMMC_LINKEDIN_PROFILES,
    CMMC_RSS_FEEDS,
    DELAYS,
    DIB_KEYWORDS,
    INSIDER_THREAT_KEYWORDS,
    INTELLIGENCE_KEYWORDS,
    LIMITS,
    NIST_KEYWORDS,
    TIMEOUTS,
    setup_logging,
)

# Import story validator for AI-powered validation
try:
    from story_validator import StoryValidator
except ImportError:
    StoryValidator = None

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
                "User-Agent": "Mozilla/5.0 (compatible; CMMCWatch/1.0; +https://cmmcwatch.com)"
            }
        )

    def collect_all(self, use_ai_validation: bool = True) -> List[Trend]:
        """Collect trends from all CMMC sources.

        Args:
            use_ai_validation: If True, use AI to validate relevance and categories.
                              Requires GROQ_API_KEY, OPENROUTER_API_KEY, or GOOGLE_AI_API_KEY.
        """
        logger.info("Collecting CMMC trends from all sources...")

        # Collect from RSS feeds
        self._collect_rss_feeds()

        # Collect from Reddit
        self._collect_reddit()

        # Collect from LinkedIn
        self._collect_linkedin()

        # Basic deduplicate (quick, rule-based)
        self._deduplicate()

        # AI-powered validation (relevance, categories, semantic dedup)
        if use_ai_validation and StoryValidator is not None:
            self._ai_validate()

        # Apply recency boost and sort by combined score
        self._apply_recency_and_sort()

        # Fetch og:image for articles without images
        self._fetch_missing_images()

        # Extract global keywords
        self._extract_global_keywords()

        logger.info(f"Total unique CMMC trends: {len(self.trends)}")
        return self.trends

    def _ai_validate(self):
        """Use AI to validate story relevance, correct categories, and find semantic duplicates."""
        if not self.trends:
            return

        logger.info("Running AI-powered story validation...")

        # Convert Trend objects to dicts for the validator
        trend_dicts = []
        for t in self.trends:
            trend_dicts.append({
                "title": t.title,
                "description": t.description,
                "category": t.category,
                "source": t.source,
                "url": t.url,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "score": t.score,
                "keywords": t.keywords,
                "image_url": t.image_url,
            })

        # Run validation
        validator = StoryValidator()
        valid_dicts, rejected_dicts = validator.validate_stories(trend_dicts, use_ai=True)

        # Log rejections
        if rejected_dicts:
            logger.info(f"AI validation rejected {len(rejected_dicts)} stories:")
            for r in rejected_dicts[:5]:
                logger.info(f"  - {r.get('title', '')[:50]}: {r.get('rejection_reason', 'unknown')}")
            if len(rejected_dicts) > 5:
                logger.info(f"  ... and {len(rejected_dicts) - 5} more")

        # Convert back to Trend objects
        self.trends = []
        for td in valid_dicts:
            timestamp = td.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        timestamp = None

            trend = Trend(
                title=td.get("title", ""),
                source=td.get("source", ""),
                url=td.get("url"),
                description=td.get("description"),
                category=td.get("category", "federal_cybersecurity"),
                score=td.get("score", 1.0),
                keywords=td.get("keywords", []),
                timestamp=timestamp,
                image_url=td.get("image_url"),
            )
            self.trends.append(trend)

        logger.info(f"AI validation complete: {len(self.trends)} stories remaining")

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
        """Categorize a trend based on keywords.

        Categories (in priority order):
        1. cmmc_program - Core CMMC certification news
        2. nist_compliance - NIST frameworks, DFARS, FedRAMP
        3. intelligence_threats - Espionage, nation-state actors, APTs
        4. insider_threats - Insider risks, employee recruitment, data theft
        5. defense_industrial_base - DoD contractors, defense contracts
        6. federal_cybersecurity - General federal cyber news (fallback)
        """
        content = (title + " " + description).lower()

        # Check categories in priority order
        if any(kw.lower() in content for kw in CMMC_CORE_KEYWORDS):
            return "cmmc_program"
        elif any(kw.lower() in content for kw in NIST_KEYWORDS):
            return "nist_compliance"
        elif any(kw.lower() in content for kw in INTELLIGENCE_KEYWORDS):
            return "intelligence_threats"
        elif any(kw.lower() in content for kw in INSIDER_THREAT_KEYWORDS):
            return "insider_threats"
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
        """Remove HTML tags from text and apply smart truncation."""
        if not text:
            return ""
        
        # Clean HTML if present
        if "<" in text:
            soup = BeautifulSoup(text, "html.parser")
            clean = soup.get_text(separator=" ").strip()
        else:
            clean = text.strip()
        
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean)
        
        # Smart truncation at sentence boundaries (up to 1500 chars)
        max_length = 1500
        if len(clean) > max_length:
            truncated = clean[:max_length]
            # Find last sentence boundary
            last_period = max(
                truncated.rfind('. '),
                truncated.rfind('! '),
                truncated.rfind('? ')
            )
            
            # If found a good sentence boundary with reasonable content
            if last_period > 300:
                return clean[:last_period + 1]
            else:
                # Fall back to word boundary
                last_space = truncated.rfind(' ')
                if last_space > 200:
                    return clean[:last_space] + "..."
                else:
                    return clean[:max_length] + "..."
        
        return clean

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
            "cmmc_rss_executivegov",
            "cmmc_rss_cyberscoop",
            "cmmc_rss_federal_news_network",
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

        for trend in trends_to_fetch[:15]:  # Limit to 15 requests
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

    def _apply_recency_and_sort(self):
        """Apply recency boost to scores and sort trends by combined score.

        Recency boost ensures today's articles rank higher than older ones,
        even if older articles have slightly higher keyword relevance.
        """
        now = datetime.now()
        now.replace(hour=0, minute=0, second=0, microsecond=0)

        for trend in self.trends:
            recency_boost = 0.0

            if trend.timestamp:
                age = now - trend.timestamp
                hours_old = age.total_seconds() / 3600

                if hours_old < 6:
                    # Very fresh (< 6 hours): major boost
                    recency_boost = 2.0
                elif hours_old < 12:
                    # Fresh (< 12 hours): strong boost
                    recency_boost = 1.5
                elif hours_old < 24:
                    # Today (< 24 hours): good boost
                    recency_boost = 1.0
                elif hours_old < 48:
                    # Yesterday (< 48 hours): small boost
                    recency_boost = 0.5
                elif hours_old < 72:
                    # 2-3 days old: minimal boost
                    recency_boost = 0.2
                # Older articles get no recency boost (0.0)

            # Store the combined score (original score + recency boost)
            trend.score = trend.score + recency_boost

        # Sort by combined score (highest first)
        self.trends.sort(key=lambda t: t.score, reverse=True)

        logger.info(f"Applied recency boost and sorted {len(self.trends)} trends")

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
