#!/usr/bin/env python3
"""
Website Builder - Generates modern news-style websites using Jinja2 templates.

Features:
- Multiple layout templates (newspaper, magazine, dashboard, minimal, bold)
- Source-grouped sections (News, Tech, Reddit, etc.)
- Word cloud visualization
- Dynamic hero styles
- Responsive design with CSS Grid
- Jinja2 templating
"""

import html
import json
import os
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from fetch_images import FallbackImageGenerator
from jinja2 import Environment, FileSystemLoader, select_autoescape

LAYOUT_TEMPLATES = ["newspaper", "magazine", "bold", "mosaic"]
HERO_STYLES = [
    "cinematic",
    "glassmorphism",
    "neon",
    "duotone",
    "particles",
    "waves",
    "geometric",
    "spotlight",
    "glitch",
    "aurora",
    "mesh",
    "retro",
]


@dataclass
class BuildContext:
    """Context for building the website."""

    trends: List[Dict]
    images: List[Dict]
    design: Dict
    keywords: List[str]
    enriched_content: Optional[Dict] = None
    why_this_matters: Optional[List[Dict]] = None
    yesterday_trends: Optional[List[Dict]] = None
    editorial_article: Optional[Dict] = None
    keyword_history: Optional[Dict] = None
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().strftime("%B %d, %Y")


class WebsiteBuilder:
    """Builds dynamic news-style websites using Jinja2 templates."""

    def __init__(self, context: BuildContext):
        self.ctx = context
        self.design = context.design
        self._description_cache = {}

        # Setup Jinja2 environment
        # Assuming templates are in a 'templates' folder at the project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_dir = os.path.join(project_root, "templates")

        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Use timestamp as seed for unique randomization on each generation
        timestamp_seed = datetime.now().isoformat()
        self.rng = random.Random(timestamp_seed)

        if isinstance(self.design, dict):
            layout_style = self.design.get("layout_style")
            hero_style = self.design.get("hero_style")
        else:
            layout_style = (
                self.design.layout_style
                if self.design and hasattr(self.design, "layout_style")
                else None
            )
            hero_style = (
                self.design.hero_style
                if self.design and hasattr(self.design, "hero_style")
                else None
            )

        self.layout = layout_style or self.rng.choice(LAYOUT_TEMPLATES)
        self.hero_style = hero_style or self.rng.choice(HERO_STYLES)

        # Group trends by category
        self.grouped_trends = self._group_trends()

        # Calculate keyword frequencies for word cloud
        self.keyword_freq = self._calculate_keyword_freq()

        # Find the best hero image based on headline content
        self._hero_image = self._find_relevant_hero_image()
        self._category_card_limit = 8  # 2 rows × 4 columns (must be multiple of 4)

    def _choose_column_count(self, count: int) -> int:
        """Always use 4-column layout for consistency."""
        # Always return 4 columns for uniform grid layout
        # Card counts should be multiples of 4 for even distribution
        return 4

    # Class-level mapping for CMMC category display names
    CATEGORY_DISPLAY_MAP = {
        "cmmc_program": "🎯 CMMC Program News",
        "nist_compliance": "📋 NIST & Compliance",
        "defense_industrial_base": "🛡️ Defense Industrial Base",
        "federal_cybersecurity": "🔒 Federal Cybersecurity",
    }

    def _prepare_categories(self) -> List[dict]:
        """Map raw category keys to display-friendly names.

        Excludes Reddit sources from categories (shown in dedicated section).
        """
        categories = []
        sorted_groups = sorted(
            self.grouped_trends.items(), key=lambda x: len(x[1]), reverse=True
        )
        for title, stories in sorted_groups:
            # Filter out Reddit sources from category sections
            filtered_stories = [
                s for s in stories if not self._is_reddit_source(s.get("source", ""))
            ]

            if not filtered_stories:
                continue  # Skip empty categories after filtering

            display_stories = filtered_stories[: self._category_card_limit]
            columns = self._choose_column_count(len(display_stories))

            # Use display-friendly title if available, otherwise clean up the raw title
            display_title = self.CATEGORY_DISPLAY_MAP.get(
                title, title.replace("_", " ").title()
            )

            categories.append(
                {
                    "title": display_title,
                    "stories": display_stories,
                    "count": len(display_stories),
                    "columns": columns,
                }
            )
        return categories

    # Reddit source prefixes for filtering
    REDDIT_SOURCE_PREFIXES = ("reddit_", "cmmc_reddit_")

    def _is_reddit_source(self, source: str) -> bool:
        """Check if a source is from Reddit."""
        return source.startswith(self.REDDIT_SOURCE_PREFIXES)

    # Source display name mapping
    SOURCE_DISPLAY_MAP = {
        # RSS feeds
        "cmmc_rss_fedscoop": "FedScoop",
        "cmmc_rss_defensescoop": "DefenseScoop",
        "cmmc_rss_federal_news_network": "Federal News Network",
        "cmmc_rss_nextgov_cybersecurity": "Nextgov",
        "cmmc_rss_breaking_defense": "Breaking Defense",
        "cmmc_rss_defense_one": "Defense One",
        "cmmc_rss_defense_news": "Defense News",
        "cmmc_rss_executivegov": "ExecutiveGov",
        "cmmc_rss_securityweek": "SecurityWeek",
        "cmmc_rss_cyberscoop": "Cyberscoop",
        "cmmc_rss_govcon_wire": "GovCon Wire",
        # Reddit
        "cmmc_reddit_cmmc": "r/CMMC",
        "cmmc_reddit_nistcontrols": "r/NISTControls",
        "cmmc_reddit_federalemployees": "r/FederalEmployees",
        "cmmc_reddit_cybersecurity": "r/cybersecurity",
        "cmmc_reddit_govcontracting": "r/GovContracting",
        # LinkedIn
        "cmmc_linkedin": "LinkedIn",
    }

    def _get_source_display_name(self, source: str) -> str:
        """Get display-friendly name for a source."""
        if source in self.SOURCE_DISPLAY_MAP:
            return self.SOURCE_DISPLAY_MAP[source]
        # Fallback: clean up the source name
        name = (
            source.replace("cmmc_rss_", "")
            .replace("cmmc_reddit_", "r/")
            .replace("cmmc_", "")
        )
        return name.replace("_", " ").title()

    def _find_relevant_hero_image(self) -> Optional[Dict]:
        """Find an image that matches the headline/top story content.

        Priority:
        1. Article image from top story's RSS feed (most relevant)
        2. Stock photo matching headline keywords
        3. First available image
        """
        # Priority 1: Check if top trend has an article image from RSS
        if self.ctx.trends:
            top_trend = self.ctx.trends[0]
            article_image_url = top_trend.get("image_url")
            if article_image_url:
                return {
                    "url_large": article_image_url,
                    "url_medium": article_image_url,
                    "url_original": article_image_url,
                    "photographer": "Article Image",
                    "source": "article",
                    "alt": top_trend.get("title", "Today's trending topic"),
                    "id": f"article_{hash(article_image_url) % 100000}",
                }

        # Priority 2: Fall back to stock photo matching
        if not self.ctx.images:
            return None

        # Get the headline and top trend for keyword matching
        headline = self.design.get("headline", "").lower()
        top_trend_title = ""
        if self.ctx.trends:
            top_trend_title = (self.ctx.trends[0].get("title") or "").lower()

        # Extract keywords from headline and top trend
        search_text = f"{headline} {top_trend_title}"
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "of",
            "in",
            "to",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "and",
            "or",
            "but",
            "if",
            "then",
            "than",
            "so",
            "that",
            "this",
            "what",
            "which",
            "who",
            "whom",
            "how",
            "when",
            "where",
            "why",
            "today's",
            "trends",
            "trending",
            "world",
            "talking",
            "about",
        }
        words = [w.strip(".,!?()[]{}ப்படாத") for w in search_text.split()]
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]

        # Score each image based on keyword matches in query/description
        best_image = None
        best_score = 0

        for img in self.ctx.images:
            img_text = f"{img.get('query', '')} {img.get('description', '')}".lower()
            score = sum(1 for kw in keywords if kw in img_text)

            # Prefer larger images
            if img.get("width", 0) >= 1200:
                score += 0.5

            if score > best_score:
                best_score = score
                best_image = img

        # If no good match, use the first image
        if best_score == 0 and self.ctx.images:
            return self.ctx.images[0]

        return best_image

    def _group_trends(self) -> Dict[str, List[Dict]]:
        """Group trends by their source category."""
        groups = defaultdict(list)

        category_map = {
            # RSS feeds by category prefix
            "news_": "World News",
            "tech_": "Technology",
            "science_": "Science",
            "politics_": "Politics",
            "finance_": "Finance",
            "entertainment_": "Entertainment",
            "sports_": "Sports",
            # Reddit - News & World
            "reddit_news": "World News",
            "reddit_worldnews": "World News",
            "reddit_politics": "Politics",
            "reddit_upliftingnews": "World News",
            # Reddit - Tech & Science
            "reddit_technology": "Technology",
            "reddit_science": "Science",
            "reddit_space": "Science",
            # Reddit - Business & Finance
            "reddit_business": "Business",
            "reddit_economics": "Finance",
            "reddit_personalfinance": "Finance",
            # Reddit - Entertainment & Culture
            "reddit_movies": "Entertainment",
            "reddit_television": "Entertainment",
            "reddit_music": "Entertainment",
            "reddit_books": "Entertainment",
            # Reddit - Sports
            "reddit_sports": "Sports",
            "reddit_nba": "Sports",
            "reddit_soccer": "Sports",
            # Reddit - Health & Lifestyle
            "reddit_health": "Health",
            "reddit_food": "Lifestyle",
            # Reddit - General
            "reddit_todayilearned": "World News",
            # Tech-specific sources
            "hackernews": "Hacker News",
            "lobsters": "Technology",
            "product_hunt": "Technology",
            "devto": "Technology",
            "slashdot": "Technology",
            "ars_features": "Technology",
            "github_trending": "Technology",
            # Other
            "wikipedia_current": "World News",
            "google_trends": "Trending",
        }

        for trend in self.ctx.trends:
            source = trend.get("source", "unknown")
            category = "Other"

            # Check for explicit category override (from NLP)
            if trend.get("category"):
                category = trend["category"]
            else:
                # Fallback to source-based mapping
                for prefix, cat in category_map.items():
                    if source.startswith(prefix):
                        category = cat
                        break

            # Set display-friendly category name for badge
            trend["category"] = category
            trend["category_display"] = self.CATEGORY_DISPLAY_MAP.get(
                category, category.replace("_", " ").title()
            )

            # Set display-friendly source name
            trend["source_display"] = self._get_source_display_name(source)

            # Format timestamp for display
            ts = None
            if trend.get("timestamp"):
                ts_raw = trend["timestamp"]
                if isinstance(ts_raw, str):
                    try:
                        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    except ValueError:
                        ts = None
                elif isinstance(ts_raw, datetime):
                    ts = ts_raw

            if ts:
                # Store ISO format for datetime attribute
                trend["timestamp_iso"] = ts.isoformat()

                # Calculate time ago with better formatting
                now = datetime.now()
                if ts.tzinfo:
                    now = datetime.now(ts.tzinfo)
                diff = now - ts
                hours = int(diff.total_seconds() / 3600)
                days = int(diff.total_seconds() / 86400)

                if hours < 1:
                    trend["time_ago"] = "Just now"
                elif hours < 24:
                    trend["time_ago"] = f"{hours}h ago"
                elif days == 1:
                    trend["time_ago"] = "Yesterday"
                elif days < 7:
                    trend["time_ago"] = f"{days}d ago"
                else:
                    # Show date for older articles
                    trend["time_ago"] = ts.strftime("%b %d")
            else:
                trend["timestamp_iso"] = datetime.now().isoformat()
                trend["time_ago"] = "Today"

            groups[category].append(trend)

        return dict(groups)

    def _select_top_stories(self) -> List[Dict]:
        """
        Select top stories using the 'Diversity Mix' algorithm.
        Ensures representation from World, Tech, and Finance.
        Enforces source diversity: max 2 stories per source.
        Excludes Reddit content (shown separately at bottom of page).
        """
        selected_urls = set()
        top_stories = []
        source_counts = defaultdict(int)  # Track stories per source
        MAX_PER_SOURCE = 2

        def can_add_story(story: Dict) -> bool:
            """Check if story can be added based on source diversity limits."""
            source = story.get("source", "unknown")
            # Exclude Reddit sources from top stories
            if self._is_reddit_source(source):
                return False
            return source_counts[source] < MAX_PER_SOURCE

        def add_story(story: Dict) -> None:
            """Add story and update tracking."""
            selected_urls.add(story.get("url"))
            source_counts[story.get("source", "unknown")] += 1
            top_stories.append(story)

        # Helper to find best available story from a category
        def get_best_from_category(category_names: List[str]) -> Optional[Dict]:
            candidates = []
            for cat in category_names:
                candidates.extend(self.grouped_trends.get(cat, []))

            # Sort by score
            candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

            for story in candidates:
                # Skip Reddit sources
                if self._is_reddit_source(story.get("source", "")):
                    continue
                if story.get("url") not in selected_urls and can_add_story(story):
                    return story
            return None

        # Slot 1: Hero - Absolute highest scoring non-Reddit story
        if self.ctx.trends:
            # Find first non-Reddit story for hero
            hero = None
            for trend in self.ctx.trends:
                if not self._is_reddit_source(trend.get("source", "")):
                    hero = trend
                    break

            if hero:
                # Ensure the hero story has the same image as the hero section
                if self._hero_image and not hero.get("image_url"):
                    hero_img_url = (
                        self._hero_image.get("url_large")
                        or self._hero_image.get("url_medium")
                        or self._hero_image.get("url_original")
                    )
                    if hero_img_url:
                        hero["image_url"] = hero_img_url
                add_story(hero)

        # Slot 2: World News
        world = get_best_from_category(["World News", "Politics", "Current Events"])
        if world:
            add_story(world)

        # Slot 3: Technology
        tech = get_best_from_category(["Technology", "Hacker News", "Science"])
        if tech:
            add_story(tech)

        # Slot 4: Finance/Business
        finance = get_best_from_category(["Finance", "Business"])
        if finance:
            add_story(finance)

        # Fill remaining slots (up to 9 total) with highest scoring remaining stories
        # while respecting source diversity
        remaining_slots = 9 - len(top_stories)
        if remaining_slots > 0:
            for story in self.ctx.trends:
                if story.get("url") not in selected_urls and can_add_story(story):
                    add_story(story)
                    if len(top_stories) >= 9:
                        break

        for story in top_stories:
            self._ensure_story_description(story)

        return top_stories

    def _get_reddit_stories(self) -> List[Dict]:
        """Get all Reddit stories for the dedicated Reddit section.

        Returns Reddit stories sorted by score, limited to 12 items.
        """
        reddit_stories = []
        for trend in self.ctx.trends:
            source = trend.get("source", "")
            if self._is_reddit_source(source):
                reddit_stories.append(trend)

        # Sort by score (highest first)
        reddit_stories.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Limit to 12 stories (3 rows of 4)
        return reddit_stories[:12]

    def _get_hero_story(self) -> Dict:
        """Get the hero story, excluding Reddit sources."""
        if not self.ctx.trends:
            return {}

        for trend in self.ctx.trends:
            if not self._is_reddit_source(trend.get("source", "")):
                return trend

        # Fallback to first trend if all are Reddit (unlikely)
        return self.ctx.trends[0] if self.ctx.trends else {}

    def _fetch_story_description(self, url: str) -> str:
        """Fetch a concise meta description for a story URL."""
        if not url or not url.startswith(("http://", "https://")):
            return ""
        if url in self._description_cache:
            return self._description_cache[url]

        description = ""
        try:
            response = requests.get(
                url, timeout=6, headers={"User-Agent": "DailyTrendingBot/1.0"}
            )
            if response.status_code >= 400:
                self._description_cache[url] = ""
                return ""

            soup = BeautifulSoup(response.text, "lxml")
            for attr, key in (
                ("property", "og:description"),
                ("name", "description"),
                ("name", "twitter:description"),
            ):
                tag = soup.find("meta", attrs={attr: key})
                if tag and tag.get("content"):
                    description = tag.get("content", "").strip()
                    break
        except Exception:
            description = ""

        description = html.unescape(description)
        description = re.sub(r"\s+", " ", description).strip()
        if len(description) > 220:
            description = description[:217].rsplit(" ", 1)[0] + "..."

        self._description_cache[url] = description
        return description

    def _ensure_story_description(self, story: Dict) -> None:
        """Add a non-AI summary when a story lacks description content."""
        if story.get("summary") or story.get("description"):
            return
        description = self._fetch_story_description(story.get("url", ""))
        if description:
            story["description"] = description

    def _calculate_keyword_freq(self) -> List[Tuple[str, int, int]]:
        """Calculate keyword frequencies and assign size classes 1-6.

        Extracts keywords from trend titles and descriptions since individual
        trends may not have keywords populated.
        """
        # Common stopwords to exclude
        stopwords = {
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
            "would",
            "could",
            "should",
            "which",
            "these",
            "those",
            "them",
            "they",
            "were",
            "being",
            "more",
            "some",
            "other",
            "into",
            "than",
            "then",
            "also",
            "just",
            "only",
            "over",
            "such",
            "after",
            "before",
            "most",
            "said",
            "says",
            "year",
            "years",
            "first",
            "last",
            "news",
            "report",
            "reports",
            "reported",
            "story",
            "stories",
        }

        freq = defaultdict(int)

        for trend in self.ctx.trends:
            # First try using existing keywords
            keywords = trend.get("keywords", [])
            if keywords:
                for kw in keywords:
                    freq[kw.lower()] += 1
            else:
                # Extract keywords from title and description
                text = (
                    trend.get("title", "") + " " + trend.get("description", "")
                ).lower()
                words = re.findall(r"\b[a-zA-Z]{4,}\b", text)
                for word in words:
                    if word not in stopwords:
                        freq[word] += 1

        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:50]

        if not sorted_freq:
            return []

        max_freq = sorted_freq[0][1]
        min_freq = sorted_freq[-1][1]

        result = []
        for word, count in sorted_freq:
            if max_freq == min_freq:
                size = 3
            else:
                size = 1 + int((count - min_freq) / (max_freq - min_freq) * 5)
            result.append((word, count, size))

        return result

    def _get_top_topic(self) -> str:
        """Get the main topic for SEO title - ONLY use for non-homepage pages."""
        if self.ctx.trends:
            return self.ctx.trends[0].get("title", "")[:60]
        return "Today's Top Trends"

    def _build_page_title(self) -> str:
        """Build SEO-optimized page title - static for homepage to build domain authority."""
        return "CMMC Watch | Daily CMMC & NIST Compliance News Aggregator"

    def _build_meta_description(self) -> str:
        """Build SEO-optimized meta description with consistent keywords."""
        return (
            "Daily aggregation of CMMC, NIST 800-171, and federal cybersecurity compliance news. "
            "Automated collection from government, defense industry, and compliance sources. "
            f"Updated {self.ctx.generated_at} with {len(self.ctx.trends)} stories."
        )

    def _build_structured_data(self) -> str:
        """Generate comprehensive JSON-LD structured data for SEO and LLMs."""

        # Organization schema - establishes CMMC Watch as a publisher entity
        organization_schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "@id": "https://cmmcwatch.info/#organization",
            "name": "CMMC Watch",
            "alternateName": "CMMCWatch",
            "url": "https://cmmcwatch.info/",
            "logo": {
                "@type": "ImageObject",
                "url": "https://cmmcwatch.info/icons/icon-512.png",
                "width": 512,
                "height": 512,
            },
            "description": "Daily automated news aggregator for CMMC, NIST 800-171, and federal cybersecurity compliance. Serving defense contractors and the Defense Industrial Base.",
            "foundingDate": "2024",
            "sameAs": [
                "https://twitter.com/bradshannon",
                "https://github.com/bshannon/cmmcwatch",
            ],
            "contactPoint": {
                "@type": "ContactPoint",
                "contactType": "technical support",
                "url": "https://github.com/bshannon/cmmcwatch/issues",
            },
            "areaServed": {
                "@type": "Country",
                "name": "United States",
            },
            "knowsAbout": [
                "CMMC",
                "NIST 800-171",
                "Cybersecurity",
                "Defense Industrial Base",
                "Federal Compliance",
                "FedRAMP",
                "DFARS",
            ],
        }

        # Base WebSite schema
        website_schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "CMMC Watch",
            "alternateName": "CMMC Watch",
            "url": "https://cmmcwatch.info/",
            "description": "Daily CMMC & NIST compliance news aggregator for defense contractors",
            "publisher": {"@id": "https://cmmcwatch.info/#organization"},
            "potentialAction": {
                "@type": "SearchAction",
                "target": "https://cmmcwatch.info/?q={search_term_string}",
                "query-input": "required name=search_term_string",
            },
            "sameAs": [
                "https://twitter.com/bradshannon",
                "https://github.com/bshannon/cmmcwatch",
            ],
            "speakable": {
                "@type": "SpeakableSpecification",
                "cssSelector": [".hero-content h1", ".hero-subtitle", ".story-title"],
            },
        }

        # BreadcrumbList schema for navigation context
        breadcrumb_schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "Home",
                    "item": "https://cmmcwatch.info/",
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": "Daily News",
                    "item": f"https://cmmcwatch.info/#news-{self.ctx.generated_at.replace(' ', '-').replace(',', '')}",
                },
            ],
        }

        # CollectionPage with ItemList
        top_stories = self._select_top_stories()
        item_list_elements = []

        for idx, story in enumerate(top_stories[:10], 1):
            item = {
                "@type": "ListItem",
                "position": idx,
                "item": {
                    "@type": "NewsArticle",
                    "headline": story.get("title", ""),
                    "url": story.get("url", ""),
                    "datePublished": story.get(
                        "timestamp_iso", datetime.now().isoformat()
                    ),
                    "publisher": {
                        "@type": "Organization",
                        "name": story.get("source_display")
                        or story.get("source", "").replace("_", " ").title(),
                    },
                },
            }

            # Add image if available
            if story.get("image_url"):
                item["item"]["image"] = story.get("image_url")

            # Add description if available
            if story.get("summary") or story.get("description"):
                item["item"]["description"] = story.get("summary") or story.get(
                    "description"
                )

            item_list_elements.append(item)

        collection_schema = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"CMMC & Compliance News - {self.ctx.generated_at}",
            "description": self._build_meta_description(),
            "url": "https://cmmcwatch.info/",
            "datePublished": datetime.now().isoformat(),
            "mainEntity": {
                "@type": "ItemList",
                "numberOfItems": len(item_list_elements),
                "itemListElement": item_list_elements,
            },
        }

        # FAQPage schema for common questions - expanded for better SEO
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "What is CMMC?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "CMMC (Cybersecurity Maturity Model Certification) is a Department of Defense framework requiring defense contractors to implement and certify cybersecurity practices. It builds on NIST SP 800-171 requirements and establishes three maturity levels for protecting Controlled Unclassified Information (CUI) and Federal Contract Information (FCI).",
                    },
                },
                {
                    "@type": "Question",
                    "name": "What is the difference between CMMC Level 1, Level 2, and Level 3?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "CMMC Level 1 (Foundational) requires 17 basic cyber hygiene practices and allows self-assessment. Level 2 (Advanced) requires all 110 NIST SP 800-171 controls and third-party assessment by a C3PAO for most contractors. Level 3 (Expert) adds additional controls from NIST SP 800-172 and requires government-led assessments for the most sensitive programs.",
                    },
                },
                {
                    "@type": "Question",
                    "name": "What is NIST SP 800-171?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "NIST Special Publication 800-171 provides security requirements for protecting Controlled Unclassified Information (CUI) in non-federal systems. It contains 110 security controls across 14 families including Access Control, Audit and Accountability, Configuration Management, and Incident Response. CMMC Level 2 is based on these requirements.",
                    },
                },
                {
                    "@type": "Question",
                    "name": "What is a C3PAO?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "A C3PAO (CMMC Third-Party Assessment Organization) is an organization authorized by the Cyber AB to conduct CMMC Level 2 assessments. C3PAOs employ certified CMMC assessors who evaluate whether defense contractors meet the required security controls before they can be awarded contracts requiring CMMC certification.",
                    },
                },
                {
                    "@type": "Question",
                    "name": "How often is CMMC Watch updated?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "CMMC Watch regenerates automatically every day at 6 AM EST via GitHub Actions, aggregating the latest CMMC and compliance news from government, defense industry, and Reddit sources. The site uses AI to curate and categorize the most relevant stories for defense contractors.",
                    },
                },
                {
                    "@type": "Question",
                    "name": "What sources does CMMC Watch aggregate?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "We aggregate from major federal and defense news sources including FedScoop, DefenseScoop, Federal News Network, Nextgov, Breaking Defense, Defense One, Defense News, ExecutiveGov, SecurityWeek, Cyberscoop, and GovCon Wire. We also monitor Reddit communities like r/CMMC, r/NISTControls, r/FederalEmployees, and r/GovContracting.",
                    },
                },
                {
                    "@type": "Question",
                    "name": "When does CMMC go into effect?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "The CMMC 2.0 final rule was published in October 2024 and became effective December 16, 2024. DoD is implementing CMMC requirements in a phased approach, with requirements appearing in new contracts starting in 2025. Check CMMC Watch daily for the latest implementation timeline updates.",
                    },
                },
                {
                    "@type": "Question",
                    "name": "What is the Defense Industrial Base (DIB)?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "The Defense Industrial Base (DIB) comprises over 300,000 companies that provide products and services to the Department of Defense. These contractors must protect sensitive government information through cybersecurity frameworks like CMMC. CMMC Watch covers news relevant to all DIB organizations.",
                    },
                },
            ],
        }

        # DefinedTermSet schema for CMMC terminology - helps LLMs understand domain terms
        defined_terms_schema = {
            "@context": "https://schema.org",
            "@type": "DefinedTermSet",
            "name": "CMMC and Federal Cybersecurity Glossary",
            "description": "Key terms and acronyms used in CMMC compliance and federal cybersecurity",
            "hasDefinedTerm": [
                {
                    "@type": "DefinedTerm",
                    "name": "CMMC",
                    "description": "Cybersecurity Maturity Model Certification - DoD framework for contractor cybersecurity",
                    "termCode": "CMMC",
                },
                {
                    "@type": "DefinedTerm",
                    "name": "CUI",
                    "description": "Controlled Unclassified Information - sensitive but unclassified government data requiring protection",
                    "termCode": "CUI",
                },
                {
                    "@type": "DefinedTerm",
                    "name": "FCI",
                    "description": "Federal Contract Information - information provided by or generated for the government under contract",
                    "termCode": "FCI",
                },
                {
                    "@type": "DefinedTerm",
                    "name": "C3PAO",
                    "description": "CMMC Third-Party Assessment Organization - authorized to conduct CMMC assessments",
                    "termCode": "C3PAO",
                },
                {
                    "@type": "DefinedTerm",
                    "name": "SPRS",
                    "description": "Supplier Performance Risk System - DoD system for recording contractor security scores",
                    "termCode": "SPRS",
                },
                {
                    "@type": "DefinedTerm",
                    "name": "NIST 800-171",
                    "description": "NIST Special Publication with 110 security controls for protecting CUI",
                    "termCode": "NIST SP 800-171",
                },
                {
                    "@type": "DefinedTerm",
                    "name": "DFARS",
                    "description": "Defense Federal Acquisition Regulation Supplement - DoD contracting regulations",
                    "termCode": "DFARS",
                },
                {
                    "@type": "DefinedTerm",
                    "name": "FedRAMP",
                    "description": "Federal Risk and Authorization Management Program - cloud security authorization",
                    "termCode": "FedRAMP",
                },
                {
                    "@type": "DefinedTerm",
                    "name": "DIB",
                    "description": "Defense Industrial Base - companies providing products/services to DoD",
                    "termCode": "DIB",
                },
                {
                    "@type": "DefinedTerm",
                    "name": "POA&M",
                    "description": "Plan of Action and Milestones - document tracking security remediation",
                    "termCode": "POA&M",
                },
            ],
        }

        # Combine all schemas using @graph
        combined_schema = {
            "@context": "https://schema.org",
            "@graph": [
                organization_schema,
                website_schema,
                breadcrumb_schema,
                collection_schema,
                faq_schema,
                defined_terms_schema,
            ],
        }

        return f'<script type="application/ld+json">\n{json.dumps(combined_schema, indent=2)}\n</script>'

    def _get_og_image_url(self) -> str:
        """Get the best image URL for Open Graph sharing.

        Prefers cybersecurity-themed images for brand consistency.
        Falls back to hero image or first stock image.
        """
        # First try to find a cybersecurity-themed stock image
        if self.ctx.images:
            for img in self.ctx.images:
                alt_text = (img.get("alt_text", "") or "").lower()
                if any(
                    kw in alt_text for kw in ["hacker", "cyber", "security", "mask"]
                ):
                    return img.get("url_large") or img.get("url_original", "")

            # Fall back to first stock image
            first_img = self.ctx.images[0]
            return first_img.get("url_large") or first_img.get("url_original", "")

        # Fall back to hero image if no stock images
        if self._hero_image:
            return self._hero_image.get("url_large") or self._hero_image.get(
                "url_original", ""
            )

        return ""

    def _assign_fallback_images(self):
        """Assign stock images to trends that don't have article images.

        Uses category-based mapping to assign relevant cybersecurity images.
        Rotates through available images to avoid repetition.
        """
        if not self.ctx.images:
            return

        # Map categories to preferred image keywords
        category_keywords = {
            "federal_cybersecurity": ["hacker", "cyber", "security", "computer"],
            "nist_compliance": ["hacker", "security", "cyber", "mask"],
            "cmmc_program": ["hacker", "cyber", "computer", "security"],
            "defense_industrial_base": ["hacker", "cyber", "security"],
        }

        # Find cybersecurity-related images (hacker, cyber, etc.)
        cyber_images = []
        other_images = []

        for img in self.ctx.images:
            alt_text = (img.get("alt_text", "") or "").lower()
            if any(
                kw in alt_text
                for kw in ["hacker", "cyber", "security", "mask", "computer"]
            ):
                cyber_images.append(img)
            else:
                other_images.append(img)

        # Prioritize cyber images, then others
        fallback_pool = cyber_images + other_images

        if not fallback_pool:
            return

        # Track used images to rotate through pool
        used_count = {}
        for img in fallback_pool:
            used_count[img.get("id")] = 0

        # Assign images to trends without them
        for trend in self.ctx.trends:
            if trend.get("image_url"):
                continue  # Already has an image

            category = trend.get("category", "")

            # Find best matching image based on category keywords
            best_img = None
            keywords = category_keywords.get(category, [])

            for img in fallback_pool:
                alt_text = (img.get("alt_text", "") or "").lower()
                if any(kw in alt_text for kw in keywords):
                    # Prefer least-used images
                    if best_img is None or used_count[img.get("id")] < used_count.get(
                        best_img.get("id"), 0
                    ):
                        best_img = img

            # If no category match, use least-used image
            if not best_img:
                best_img = min(
                    fallback_pool, key=lambda x: used_count.get(x.get("id"), 0)
                )

            # Assign the image
            if best_img:
                trend["image_url"] = best_img.get("url_medium") or best_img.get(
                    "url_large"
                )
                trend["image_source"] = "stock"  # Mark as stock image
                used_count[best_img.get("id")] = (
                    used_count.get(best_img.get("id"), 0) + 1
                )

    def build(self) -> str:
        """Render the website using Jinja2 templates."""
        template = self.env.get_template("index.html")

        # Assign fallback images to trends without article images
        self._assign_fallback_images()

        def hex_to_rgb(value: str, fallback: str = "10, 10, 10") -> str:
            """Convert a hex color (e.g. #0a0a0a) to an RGB string."""
            if not value:
                return fallback
            hex_value = value.lstrip("#")
            if len(hex_value) == 3:
                hex_value = "".join([c * 2 for c in hex_value])
            if len(hex_value) != 6:
                return fallback
            try:
                r = int(hex_value[0:2], 16)
                g = int(hex_value[2:4], 16)
                b = int(hex_value[4:6], 16)
                return f"{r}, {g}, {b}"
            except ValueError:
                return fallback

        # Prepare hero background CSS
        hero_bg_css = FallbackImageGenerator.get_gradient_css()
        hero_image_url = ""
        if self._hero_image:
            url = self._hero_image.get("url_large") or self._hero_image.get(
                "url_medium"
            )
            if url:
                hero_image_url = url
                hero_bg_css = f"url('{url}') center center / cover no-repeat #0a0a0a"

        # Prepare styles from design spec
        d = self.design
        card_style = d.get("card_style", "bordered")
        hover_effect = d.get("hover_effect", "lift")
        animation_level = d.get("animation_level", "subtle")
        custom_styles = f"""
            .hero-content {{
                text-align: { 'center' if d.get('hero_style') in ['minimal', 'centered'] else 'left' };
            }}
            .story-card {{
                border-radius: {d.get('card_radius', '1rem')};
            }}
        """

        # Build body classes - dynamically set mode from design
        # JavaScript will override based on user preference from localStorage
        base_mode = "dark-mode" if d.get("is_dark_mode", True) else "light-mode"
        spacing = d.get("spacing", "comfortable")
        body_classes = [
            f"layout-{self.layout}",
            f"hero-{self.hero_style}",
            f"card-style-{card_style}",
            f"hover-{hover_effect}",
            f"animation-{animation_level}",
            base_mode,
        ]

        if d.get("text_transform_headings") != "none":
            body_classes.append(f"text-transform-{d.get('text_transform_headings')}")

        # Add creative flourish classes from design spec
        bg_pattern = d.get("background_pattern", "none")
        if bg_pattern and bg_pattern != "none":
            body_classes.append(f"bg-pattern-{bg_pattern}")

        accent_style = d.get("accent_style", "none")
        if accent_style and accent_style != "none":
            body_classes.append(f"accent-{accent_style}")

        special_mode = d.get("special_mode", "standard")
        if special_mode and special_mode != "standard":
            body_classes.append(f"mode-{special_mode}")

        # Add animation modifiers
        if d.get("use_float_animation", False):
            body_classes.append("use-float")
        if d.get("use_pulse_animation", False):
            body_classes.append("use-pulse")

        # Add new design dimension classes
        image_treatment = d.get("image_treatment", "none")
        if image_treatment and image_treatment != "none":
            body_classes.append(f"image-treatment-{image_treatment}")

        card_aspect = d.get("card_aspect_ratio", "auto")
        if card_aspect and card_aspect != "auto":
            body_classes.append(f"aspect-{card_aspect}")

        if spacing:
            body_classes.append(f"density-{spacing}")

        section_gap_map = {
            "compact": "2.5rem",
            "comfortable": "3.5rem",
            "spacious": "5rem",
        }
        section_gap = section_gap_map.get(spacing, "3.5rem")

        categories = self._prepare_categories()

        # Build context variables for the template
        render_context = {
            "page_title": self._build_page_title(),
            "meta_description": self._build_meta_description(),
            "keywords_str": ", ".join(self.ctx.keywords[:15]),
            "canonical_url": "https://cmmcwatch.info/",
            "date_str": self.ctx.generated_at,
            "date_iso": datetime.now().strftime("%Y-%m-%d"),
            "last_modified": datetime.now().isoformat(),
            "active_page": "home",
            "font_primary": d.get("font_primary", "Space Grotesk").replace(" ", "+"),
            "font_secondary": d.get("font_secondary", "Inter").replace(" ", "+"),
            "font_primary_family": d.get("font_primary", "Space Grotesk"),
            "font_secondary_family": d.get("font_secondary", "Inter"),
            "hero_image_url": hero_image_url,
            "section_gap": section_gap,
            "colors": {
                "bg": d.get("color_bg", "#0a0a0a"),
                "bg_rgb": hex_to_rgb(d.get("color_bg", "#0a0a0a")),
                "text": d.get("color_text", "#ffffff"),
                "accent": d.get("color_accent", "#6366f1"),
                "accent_secondary": d.get("color_accent_secondary", "#8b5cf6"),
                "muted": d.get("color_muted", "#a1a1aa"),
                "card_bg": d.get("color_card_bg", "#18181b"),
                "border": d.get("color_border", "#27272a"),
            },
            "design": {
                "card_radius": d.get("card_radius", "1rem"),
                "card_padding": d.get("card_padding", "1.5rem"),
                "max_width": d.get("max_width", "1400px"),
                "theme_name": d.get("theme_name"),
                "subheadline": d.get("subheadline"),
                "story_capsules": d.get("story_capsules", []),
            },
            "hero_bg_css": hero_bg_css,
            "body_classes": " ".join(body_classes),
            "custom_styles": custom_styles,
            # SVG placeholder with gradient (avoids missing asset file)
            "placeholder_image_url": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 450'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0%25' y1='0%25' x2='100%25' y2='100%25'%3E%3Cstop offset='0%25' stop-color='%231a1a2e'/%3E%3Cstop offset='100%25' stop-color='%2316213e'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect fill='url(%23g)' width='800' height='450'/%3E%3Ctext x='400' y='225' fill='%234a4a6a' font-family='system-ui' font-size='14' text-anchor='middle' dy='.3em'%3ECMMC Watch%3C/text%3E%3C/svg%3E",
            # Content
            "hero_story": self._get_hero_story(),
            "top_stories": self._select_top_stories(),
            "trends": self.ctx.trends,
            "reddit_stories": self._get_reddit_stories(),
            "total_trends_count": len(self.ctx.trends),
            "word_cloud": self.keyword_freq,
            "categories": categories,
            # SEO - Dynamic OG image from stock collection for social sharing
            "og_image_url": self._get_og_image_url(),
            "structured_data": self._build_structured_data(),
        }

        return template.render(render_context)

    def save(self, output_path: str):
        """Build and save the website."""
        html_content = self.build()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
