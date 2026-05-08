#!/usr/bin/env python3
"""
CMMC Watch Trend Collector - Collects CMMC/NIST compliance news.

Focused sources:
- Federal/Defense news RSS feeds
- CMMC-specific Reddit communities
- LinkedIn posts from key CMMC influencers
"""

import base64
import binascii
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from config import (
    CMMC_CORE_KEYWORDS,
    CMMC_KEYWORDS,
    CMMC_LINKEDIN_PROFILES,
    DATA_DIR,
    DEDUP_SEMANTIC_THRESHOLD,
    DEDUP_SIMILARITY_THRESHOLD,
    DELAYS,
    DIB_KEYWORDS,
    INSIDER_THREAT_KEYWORDS,
    INTELLIGENCE_KEYWORDS,
    LIMITS,
    NIST_KEYWORDS,
    TIMEOUTS,
    setup_logging,
)
from source_catalog import (
    DEFAULT_BROWSER_UA,
    DOMAIN_FETCH_PROFILES,
    HEADER_PROFILES,
    SourceSpec,
    get_collector_sources,
)
from source_registry import (
    format_source_label,
    source_metadata_dict,
    source_quality_multiplier,
)

# Import story validator for AI-powered validation
try:
    from story_validator import StoryValidator
except ImportError:
    StoryValidator = None

logger = setup_logging("collect_trends")


def _normalize_datetime(value: datetime) -> datetime:
    """Normalize timezone-aware datetimes to naive UTC."""
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Best-effort timestamp parser for API and feed values."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return _normalize_datetime(value)

    if isinstance(value, (int, float)):
        ts_value = float(value)
        if ts_value > 10_000_000_000:
            ts_value = ts_value / 1000.0
        try:
            return datetime.fromtimestamp(ts_value, tz=timezone.utc).replace(tzinfo=None)
        except (ValueError, OverflowError, OSError):
            return None

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None

        normalized = cleaned.replace("Z", "+00:00")
        try:
            return _normalize_datetime(datetime.fromisoformat(normalized))
        except ValueError:
            pass

        try:
            from email.utils import parsedate_to_datetime

            return _normalize_datetime(parsedate_to_datetime(cleaned))
        except (TypeError, ValueError):
            pass

        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue

    return None


def parse_feed_entry_timestamp(entry: Any) -> Optional[datetime]:
    """Extract timestamp from feedparser entry."""
    for parsed_key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed_value = entry.get(parsed_key)
        if parsed_value:
            try:
                return datetime(*parsed_value[:6])
            except (TypeError, ValueError) as e:
                logger.debug(f"Could not build datetime from {parsed_key}: {e}")
                continue

    for key in ("published", "updated", "created", "dc_date", "pubDate"):
        parsed = parse_timestamp(entry.get(key))
        if parsed:
            return parsed
    return None


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
    source_metadata: Dict[str, Optional[str]] = field(default_factory=dict)
    source_label: Optional[str] = None
    corroborating_sources: List[str] = field(default_factory=list)
    corroborating_urls: List[str] = field(default_factory=list)
    source_diversity: int = 1

    def __post_init__(self):
        parsed_timestamp = parse_timestamp(self.timestamp)
        # Match _normalize_datetime: store naive UTC for consistency
        self.timestamp = parsed_timestamp or datetime.now(timezone.utc).replace(tzinfo=None)

        if not self.source_metadata:
            self.source_metadata = source_metadata_dict(self.source)

        if not self.source_label:
            self.source_label = format_source_label(self.source)

        if not self.corroborating_sources:
            self.corroborating_sources = [self.source]
        elif self.source not in self.corroborating_sources:
            self.corroborating_sources.append(self.source)

        if not self.corroborating_urls:
            self.corroborating_urls = [self.url] if self.url else []
        elif self.url and self.url not in self.corroborating_urls:
            self.corroborating_urls.append(self.url)

        self.source_diversity = max(1, len(set(self.corroborating_sources)))

    def register_corroboration(self, other: "Trend") -> None:
        other_sources = other.corroborating_sources or [other.source]
        for source in other_sources:
            if source and source not in self.corroborating_sources:
                self.corroborating_sources.append(source)

        other_urls = other.corroborating_urls or ([other.url] if other.url else [])
        for url in other_urls:
            if url and url not in self.corroborating_urls:
                self.corroborating_urls.append(url)

        if other.description and len(other.description) > len(self.description or ""):
            self.description = other.description

        if not self.image_url and other.image_url:
            self.image_url = other.image_url

        if other.timestamp and (not self.timestamp or other.timestamp > self.timestamp):
            self.timestamp = other.timestamp

        self.source_diversity = max(1, len(set(self.corroborating_sources)))


class TrendCollector:
    """Collects CMMC/compliance trends from multiple sources."""

    def __init__(self):
        self.trends: List[Trend] = []
        self.global_keywords: List[str] = []
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_BROWSER_UA})
        self.default_timeout = float(TIMEOUTS.get("default", 15))
        self.feed_timeout = float(TIMEOUTS.get("rss_feed", self.default_timeout))
        self.request_delay = float(DELAYS.get("between_requests", 0.15))

        self.feed_cache_ttl_seconds = 10 * 60
        self.feed_persistent_ttl_seconds = 24 * 60 * 60
        self.feed_cooldown_seconds = 5 * 60
        self.feed_failure_threshold = 2
        self.feed_failures: Dict[str, Dict[str, float]] = {}
        self.feed_cache: Dict[str, Dict[str, Any]] = {}
        self.feed_cache_file = Path(DATA_DIR) / "feed_runtime_cache.json"
        self.persistent_feed_cache: Dict[str, Dict[str, Any]] = {}
        self._persistent_cache_dirty = False
        self._load_persistent_feed_cache()

    def _collector_sources(self, group: str) -> List[SourceSpec]:
        """Resolve collector feeds from canonical source catalog."""
        return get_collector_sources(group)

    def _load_persistent_feed_cache(self) -> None:
        if not self.feed_cache_file.exists():
            return
        try:
            with open(self.feed_cache_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                self.persistent_feed_cache = payload
        except Exception as exc:
            logger.debug(f"Failed to load persistent feed cache: {exc}")
            self.persistent_feed_cache = {}

    def _flush_persistent_feed_cache(self) -> None:
        if not self._persistent_cache_dirty:
            return
        try:
            self.feed_cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.feed_cache_file, "w", encoding="utf-8") as f:
                json.dump(self.persistent_feed_cache, f)
            self._persistent_cache_dirty = False
        except Exception as exc:
            logger.debug(f"Failed to flush persistent feed cache: {exc}")

    def _resolve_domain_profile(self, url: str) -> Dict[str, Any]:
        hostname = urlparse(url).hostname or ""
        return dict(DOMAIN_FETCH_PROFILES.get(hostname, {}))

    def _resolve_headers(
        self,
        headers: Optional[Dict[str, str]],
        headers_profile: str,
        domain_profile: Dict[str, Any],
    ) -> Dict[str, str]:
        merged: Dict[str, str] = {}
        merged.update(HEADER_PROFILES.get("default", {}))
        merged.update(HEADER_PROFILES.get(headers_profile, {}))

        profile_header_name = domain_profile.get("headers_profile")
        if isinstance(profile_header_name, str):
            merged.update(HEADER_PROFILES.get(profile_header_name, {}))

        if headers:
            merged.update(headers)
        return merged

    def _feed_scope(self, source_key: Optional[str], url: str) -> str:
        return source_key or url

    def _is_feed_on_cooldown(self, scope: str) -> bool:
        state = self.feed_failures.get(scope)
        if not state:
            return False
        cooldown_until = float(state.get("cooldown_until", 0))
        if time.time() < cooldown_until:
            return True
        if cooldown_until > 0:
            self.feed_failures.pop(scope, None)
        return False

    def _record_feed_failure(self, scope: str, error: str = "") -> None:
        state = self.feed_failures.get(scope, {"count": 0, "cooldown_until": 0.0})
        state["count"] = float(state.get("count", 0)) + 1
        if state["count"] >= self.feed_failure_threshold:
            state["cooldown_until"] = time.time() + self.feed_cooldown_seconds
            logger.warning(f"Feed {scope} on cooldown after {int(state['count'])} failures: {error}")
        self.feed_failures[scope] = state

    def _record_feed_success(self, scope: str) -> None:
        self.feed_failures.pop(scope, None)

    def _cache_feed_response(self, scope: str, response: requests.Response, url: str) -> None:
        now = time.time()
        headers = {k.lower(): v for k, v in response.headers.items()}
        content_bytes = response.content or b""

        self.feed_cache[scope] = {
            "timestamp": now,
            "content": content_bytes,
            "headers": headers,
            "status_code": response.status_code,
            "url": url,
        }
        self.persistent_feed_cache[scope] = {
            "timestamp": now,
            "content_b64": base64.b64encode(content_bytes).decode("ascii"),
            "headers": headers,
            "status_code": response.status_code,
            "url": url,
        }
        self._persistent_cache_dirty = True

    def _response_from_cached(
        self,
        cached: Dict[str, Any],
        fallback_url: Optional[str] = None,
    ) -> Optional[requests.Response]:
        content = cached.get("content")
        if content is None:
            content_b64 = cached.get("content_b64")
            if not isinstance(content_b64, str):
                return None
            try:
                content = base64.b64decode(content_b64.encode("ascii"))
            except (binascii.Error, ValueError, UnicodeEncodeError) as e:
                logger.debug(f"Failed to decode cached base64 content: {e}")
                return None

        if not isinstance(content, (bytes, bytearray)):
            return None

        response = requests.Response()
        response.status_code = int(cached.get("status_code", 200))
        response._content = bytes(content)
        response.headers = requests.structures.CaseInsensitiveDict(
            cached.get("headers", {"content-type": "application/rss+xml"})
        )
        response.url = str(cached.get("url") or fallback_url or "")
        return response

    def _get_cached_feed_response(
        self,
        scope: str,
        now_ts: Optional[float] = None,
    ) -> Optional[requests.Response]:
        now_ts = now_ts or time.time()

        cached = self.feed_cache.get(scope)
        if cached:
            if now_ts - float(cached.get("timestamp", 0)) <= self.feed_cache_ttl_seconds:
                response = self._response_from_cached(cached)
                if response is not None:
                    return response
            else:
                self.feed_cache.pop(scope, None)

        persistent = self.persistent_feed_cache.get(scope)
        if not persistent:
            return None
        if now_ts - float(persistent.get("timestamp", 0)) > self.feed_persistent_ttl_seconds:
            self.persistent_feed_cache.pop(scope, None)
            self._persistent_cache_dirty = True
            return None
        return self._response_from_cached(persistent)

    def _is_feed_response(self, response: requests.Response) -> bool:
        content_type = response.headers.get("content-type", "").lower()
        if "xml" in content_type or "rss" in content_type:
            return True
        head = (response.content or b"")[:120].lower()
        return b"<rss" in head or b"<?xml" in head or b"<feed" in head

    def _fetch_rss(
        self,
        url: str,
        timeout: Optional[float] = None,
        allowed_status: Tuple[int, ...] = (200, 301, 302),
        headers: Optional[Dict[str, str]] = None,
        source_key: Optional[str] = None,
        fallback_url: Optional[str] = None,
        headers_profile: str = "default",
        allow_fallback: bool = True,
    ) -> Optional[requests.Response]:
        scope = self._feed_scope(source_key, url)
        now_ts = time.time()

        if self._is_feed_on_cooldown(scope):
            cached = self._get_cached_feed_response(scope, now_ts=now_ts)
            if cached is not None:
                return cached
            return None

        metadata_fallback = source_metadata_dict(source_key or "").get("fallback_url")
        fallback_url = fallback_url or metadata_fallback

        domain_profile = self._resolve_domain_profile(url)
        effective_timeout = float(timeout or domain_profile.get("timeout") or self.feed_timeout)
        attempts = max(1, int(domain_profile.get("attempts") or 1))
        retry_delay = float(domain_profile.get("retry_delay") or 0.4)
        request_headers = self._resolve_headers(headers, headers_profile, domain_profile)

        errors: List[str] = []
        for attempt in range(1, attempts + 1):
            try:
                response = self.session.get(url, timeout=effective_timeout, headers=request_headers or None)
                if response.status_code not in allowed_status:
                    errors.append(f"HTTP {response.status_code}")
                elif not self._is_feed_response(response):
                    content_type = response.headers.get("content-type", "").lower()
                    errors.append(f"non-feed response ({content_type or 'unknown'})")
                else:
                    self._record_feed_success(scope)
                    self._cache_feed_response(scope, response, url)
                    return response
            except Exception as exc:
                errors.append(str(exc))

            if attempt < attempts:
                time.sleep(retry_delay * attempt)

        if allow_fallback and fallback_url and fallback_url != url:
            logger.warning(f"RSS fetch fallback for {scope}: {url} -> {fallback_url}")
            fallback_response = self._fetch_rss(
                fallback_url,
                timeout=timeout,
                allowed_status=allowed_status,
                headers=headers,
                source_key=source_key,
                fallback_url=None,
                headers_profile=headers_profile,
                allow_fallback=False,
            )
            if fallback_response is not None:
                self._record_feed_success(scope)
                return fallback_response

        error_text = "; ".join(errors[-3:])
        self._record_feed_failure(scope, error_text)
        cached = self._get_cached_feed_response(scope, now_ts=now_ts)
        if cached is not None:
            logger.warning(f"RSS fetch failed for {scope}; using cached feed data")
            return cached

        logger.warning(f"RSS fetch error for {url}: {error_text}")
        return None

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

        self._flush_persistent_feed_cache()
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
            trend_dicts.append(
                {
                    "title": t.title,
                    "description": t.description,
                    "category": t.category,
                    "source": t.source,
                    "url": t.url,
                    "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                    "score": t.score,
                    "keywords": t.keywords,
                    "image_url": t.image_url,
                }
            )

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
                        # Both formats failed — log so we know this happened.
                        # Trend.__post_init__ will fall back to "now", which
                        # would otherwise silently boost stale items in
                        # recency-weighted ranking.
                        logger.warning(
                            f"Unparseable timestamp from upstream: {timestamp!r}; "
                            f"falling back to current time for {td.get('source', 'unknown')} "
                            f"item {td.get('url', 'unknown')!r}"
                        )
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

        for source in self._collector_sources("cmmc_rss"):
            try:
                response = self._fetch_rss(
                    source.url,
                    timeout=source.timeout_seconds or self.feed_timeout,
                    source_key=source.source_key or source.key,
                    fallback_url=source.fallback_url,
                    headers_profile=source.headers_profile,
                )
                if not response:
                    continue
                feed = feedparser.parse(response.content)

                for entry in feed.entries[: LIMITS.get("cmmc_rss", 20)]:
                    title = entry.get("title", "").strip()
                    description = entry.get("summary", "") or entry.get("description", "")

                    if not title or len(title) < 10:
                        continue

                    # Check if CMMC-related
                    content = (title + " " + description).lower()
                    is_cmmc = any(kw.lower() in content for kw in CMMC_KEYWORDS)

                    if is_cmmc:
                        trend = Trend(
                            title=title[:200],
                            source=source.source_key or source.key,
                            url=entry.get("link"),
                            description=self._clean_html(description),
                            category=self._categorize_trend(title, description),
                            score=self._calculate_score(title, description),
                            image_url=self._extract_image_from_entry(entry),
                            timestamp=parse_feed_entry_timestamp(entry),
                        )
                        self.trends.append(trend)
                        count += 1

                time.sleep(self.request_delay)

            except Exception as e:
                logger.warning(f"RSS feed {source.name} error: {e}")
                continue

        logger.info(f"  Found {count} CMMC stories from RSS feeds")

    def _collect_reddit(self):
        """Collect from CMMC-related subreddits."""
        logger.info("Fetching from CMMC Reddit communities...")

        subreddits = self._collector_sources("cmmc_reddit")

        count = 0
        for source in subreddits:
            try:
                response = self._fetch_rss(
                    source.url,
                    timeout=source.timeout_seconds or self.feed_timeout,
                    source_key=source.source_key or source.key,
                    fallback_url=source.fallback_url,
                    headers_profile=source.headers_profile,
                )
                if not response:
                    continue
                feed = feedparser.parse(response.content)

                for entry in feed.entries[:15]:
                    title = entry.get("title", "").strip()
                    description = entry.get("summary", "")

                    if not title or len(title) < 10:
                        continue

                    # For CMMC/NISTControls, include all; others need keyword match
                    include_post = False
                    if source.key in ["cmmc_reddit_cmmc", "cmmc_reddit_nistcontrols"]:
                        include_post = True
                    else:
                        content = (title + " " + description).lower()
                        include_post = any(kw.lower() in content for kw in CMMC_KEYWORDS)

                    if include_post:
                        trend = Trend(
                            title=title,
                            source=source.source_key or source.key,
                            url=entry.get("link"),
                            description=self._clean_html(description),
                            category=self._categorize_trend(title, description),
                            score=1.4,
                            image_url=self._extract_image_from_entry(entry),
                            timestamp=parse_feed_entry_timestamp(entry),
                        )
                        self.trends.append(trend)
                        count += 1

                time.sleep(self.request_delay)

            except Exception as e:
                logger.warning(f"Reddit {source.name} error: {e}")
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
                    timestamp=parse_timestamp(td.get("timestamp") or td.get("published_at")),
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
            last_period = max(truncated.rfind(". "), truncated.rfind("! "), truncated.rfind("? "))

            # If found a good sentence boundary with reasonable content
            if last_period > 300:
                return clean[: last_period + 1]
            else:
                # Fall back to word boundary
                last_space = truncated.rfind(" ")
                if last_space > 200:
                    return clean[:last_space] + "..."
                else:
                    return clean[:max_length] + "..."

        return clean

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
                if media.get("medium") == "image" or media.get("type", "").startswith("image"):
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

        has_extension = any(url_lower.endswith(ext) or f"{ext}?" in url_lower for ext in image_extensions)
        from_cdn = any(cdn in url_lower for cdn in image_cdns)

        return has_extension or from_cdn

    def _fetch_missing_images(self):
        """Fetch og:image from article pages for trends without images.

        Only fetches from sources known to have og:image on their pages.
        Limited to prevent slowdown.
        """
        # Sources known to have og:image on article pages
        sources_with_og_image = {
            "cmmc_fedscoop",
            "cmmc_defensescoop",
            "cmmc_securityweek",
            "cmmc_executivegov",
            "cmmc_cyberscoop",
            "cmmc_fnn",
            # Legacy keys kept for backward compatibility with archived data/tests.
            "cmmc_rss_fedscoop",
            "cmmc_rss_defensescoop",
            "cmmc_rss_securityweek",
            "cmmc_rss_executivegov",
            "cmmc_rss_cyberscoop",
            "cmmc_rss_federal_news_network",
        }

        trends_to_fetch = [t for t in self.trends if not t.image_url and t.source in sources_with_og_image]

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
        """Cluster and deduplicate trends using token overlap + semantic similarity."""
        if not self.trends:
            return

        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "from",
            "after",
            "before",
            "about",
            "update",
            "latest",
            "news",
            "today",
        }

        normalized_titles: List[str] = []
        token_sets: List[Set[str]] = []
        inverted_index: Dict[str, List[int]] = {}

        for idx, trend in enumerate(self.trends):
            normalized = re.sub(r"[^\w\s]", " ", (trend.title or "").lower())
            normalized = re.sub(r"\s+", " ", normalized).strip()
            tokens = {
                token
                for token in normalized.split()
                if len(token) >= 3 and not token.isdigit() and token not in stop_words
            }
            if not tokens:
                tokens = {token for token in normalized.split() if token}

            normalized_titles.append(normalized)
            token_sets.append(tokens)

            for token in tokens:
                inverted_index.setdefault(token, []).append(idx)

        clusters: List[List[int]] = []
        assigned = set()

        for index, _trend in enumerate(self.trends):
            if index in assigned:
                continue

            cluster = [index]
            assigned.add(index)
            tokens_i = token_sets[index]
            normalized_i = normalized_titles[index]

            candidate_indices = set()
            for token in tokens_i:
                for candidate_idx in inverted_index.get(token, []):
                    if candidate_idx > index:
                        candidate_indices.add(candidate_idx)

            for candidate_idx in sorted(candidate_indices):
                if candidate_idx in assigned:
                    continue

                tokens_j = token_sets[candidate_idx]
                normalized_j = normalized_titles[candidate_idx]

                if not tokens_i or not tokens_j:
                    overlap_ratio = 0.0
                    jaccard = 0.0
                else:
                    intersection = len(tokens_i & tokens_j)
                    overlap_ratio = intersection / max(1, min(len(tokens_i), len(tokens_j)))
                    jaccard = intersection / max(1, len(tokens_i | tokens_j))

                semantic_ratio = SequenceMatcher(None, normalized_i, normalized_j).ratio()
                token_semantic_ratio = SequenceMatcher(
                    None,
                    " ".join(sorted(tokens_i)),
                    " ".join(sorted(tokens_j)),
                ).ratio()

                is_duplicate = (
                    overlap_ratio >= DEDUP_SIMILARITY_THRESHOLD
                    or jaccard >= max(0.55, DEDUP_SIMILARITY_THRESHOLD - 0.25)
                    or semantic_ratio >= DEDUP_SEMANTIC_THRESHOLD
                    or token_semantic_ratio >= DEDUP_SEMANTIC_THRESHOLD
                )
                if not is_duplicate:
                    continue

                cluster.append(candidate_idx)
                assigned.add(candidate_idx)

            clusters.append(cluster)

        unique_trends: List[Trend] = []
        for cluster in clusters:
            if len(cluster) == 1:
                unique_trends.append(self.trends[cluster[0]])
                continue

            def _quality(cluster_idx: int) -> Tuple[float, float]:
                candidate = self.trends[cluster_idx]
                quality = candidate.score * source_quality_multiplier(candidate.source)
                quality *= 1.0 + min((candidate.source_diversity - 1) * 0.05, 0.25)
                timestamp = candidate.timestamp.timestamp() if candidate.timestamp else 0.0
                return quality, timestamp

            canonical_idx = max(cluster, key=_quality)
            canonical = self.trends[canonical_idx]
            for cluster_idx in cluster:
                if cluster_idx == canonical_idx:
                    continue
                canonical.register_corroboration(self.trends[cluster_idx])
            unique_trends.append(canonical)

        removed_count = len(self.trends) - len(unique_trends)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate trends")

        self.trends = unique_trends

    def _apply_recency_and_sort(self):
        """Apply recency boost to scores and sort trends by combined score.

        Recency boost ensures today's articles rank higher than older ones,
        even if older articles have slightly higher keyword relevance.
        """
        # Use naive UTC to match _normalize_datetime() output stored on trend.timestamp
        now = datetime.now(timezone.utc).replace(tzinfo=None)

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

            quality_multiplier = source_quality_multiplier(trend.source)
            diversity_multiplier = 1.0
            if trend.source_diversity > 1:
                diversity_multiplier = 1.0 + min((trend.source_diversity - 1) * 0.08, 0.35)

            # Store combined score with source quality calibration.
            trend.score = (trend.score * quality_multiplier * diversity_multiplier) + recency_boost

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
        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
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
