#!/usr/bin/env python3
"""
Competitor and Industry Monitor - Tracks CMMC-related content from key sources.

Monitors:
1. Federal Register for DFARS/CMMC regulatory changes
2. DefenseScoop for defense industry news
3. Preveil Blog for CMMC content
4. White & Case for CMMC legal alerts
5. Additional compliance-focused sources

Usage:
    python competitor_monitor.py              # Run all monitors
    python competitor_monitor.py --source federal_register  # Run specific source
    python competitor_monitor.py --output json  # Output as JSON
"""

import argparse
import hashlib
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from config import DATA_DIR, TIMEOUTS, setup_logging

# Initialize logger
logger = setup_logging("competitor_monitor")

# Output directory for competitor data
COMPETITOR_DATA_DIR = DATA_DIR / "competitor_monitor"
COMPETITOR_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Cache file for tracking previously seen items
SEEN_ITEMS_FILE = COMPETITOR_DATA_DIR / "seen_items.json"


@dataclass
class MonitoredItem:
    """Represents a monitored item from any source."""

    title: str
    url: str
    source: str
    published_date: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    relevance_score: float = 0.0
    item_hash: str = ""

    def __post_init__(self):
        if not self.item_hash:
            # Create a hash for deduplication
            self.item_hash = hashlib.md5(
                f"{self.source}:{self.url}".encode()
            ).hexdigest()[:12]


class CompetitorMonitor:
    """Monitors competitor and industry sources for CMMC-related content."""

    # CMMC-related keywords for relevance scoring
    CMMC_KEYWORDS = [
        "cmmc",
        "cmmc 2.0",
        "nist 800-171",
        "nist sp 800-171",
        "dfars",
        "dfars 252.204",
        "controlled unclassified",
        "cui",
        "defense contractor",
        "defense industrial base",
        "dib",
        "c3pao",
        "cyber-ab",
        "fedramp",
        "fisma",
    ]

    # Source configurations
    SOURCES = {
        "federal_register": {
            "name": "Federal Register",
            "type": "api",
            "base_url": "https://www.federalregister.gov/api/v1/documents.json",
            "params": {
                "conditions[term]": "DFARS OR CMMC OR cybersecurity maturity",
                "conditions[agencies][]": "defense-department",
                "per_page": 20,
                "order": "newest",
            },
        },
        "defensescoop": {
            "name": "DefenseScoop",
            "type": "rss",
            "url": "https://defensescoop.com/feed/",
        },
        "preveil_blog": {
            "name": "Preveil Blog",
            "type": "rss",
            "url": "https://www.preveil.com/blog/feed/",
        },
        "white_case": {
            "name": "White & Case",
            "type": "scrape",
            "url": "https://www.whitecase.com/insights?topic=cybersecurity",
            "filter_keywords": ["cmmc", "cybersecurity", "defense", "dfars", "nist"],
        },
        "nist_csf": {
            "name": "NIST CSF News",
            "type": "rss",
            "url": "https://www.nist.gov/news-events/news/rss.xml",
            "filter_keywords": ["cybersecurity", "800-171", "cmmc", "framework"],
        },
        "cyberscoop": {
            "name": "Cyberscoop",
            "type": "rss",
            "url": "https://cyberscoop.com/feed/",
        },
        "fcw": {
            "name": "FCW",
            "type": "rss",
            "url": "https://fcw.com/rss/",
        },
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "CMMCWatch-CompetitorMonitor/1.0 (https://cmmcwatch.com)",
                "Accept": "application/json, application/xml, text/html, */*",
            }
        )
        self.seen_items = self._load_seen_items()
        self.results: List[MonitoredItem] = []

    def _load_seen_items(self) -> Dict[str, str]:
        """Load previously seen items from cache."""
        if SEEN_ITEMS_FILE.exists():
            try:
                with open(SEEN_ITEMS_FILE, "r") as f:
                    data = json.load(f)
                    # Clean up old entries (older than 30 days)
                    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
                    return {k: v for k, v in data.items() if v > cutoff}
            except Exception as e:
                logger.warning(f"Failed to load seen items: {e}")
        return {}

    def _save_seen_items(self):
        """Save seen items to cache."""
        try:
            with open(SEEN_ITEMS_FILE, "w") as f:
                json.dump(self.seen_items, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save seen items: {e}")

    def _calculate_relevance(self, text: str) -> float:
        """Calculate relevance score based on keyword matches."""
        if not text:
            return 0.0
        text_lower = text.lower()
        score = 0.0
        matched_keywords = []

        for keyword in self.CMMC_KEYWORDS:
            if keyword in text_lower:
                # Weight more specific keywords higher
                if keyword in ["cmmc", "cmmc 2.0", "c3pao", "cyber-ab"]:
                    score += 2.0
                elif keyword in ["dfars", "nist 800-171", "cui"]:
                    score += 1.5
                else:
                    score += 1.0
                matched_keywords.append(keyword)

        return min(score / 10.0, 1.0)  # Normalize to 0-1

    def _is_new_item(self, item: MonitoredItem) -> bool:
        """Check if item is new (not seen before)."""
        return item.item_hash not in self.seen_items

    def _mark_as_seen(self, item: MonitoredItem):
        """Mark item as seen."""
        self.seen_items[item.item_hash] = datetime.now().isoformat()

    def monitor_federal_register(self) -> List[MonitoredItem]:
        """Monitor Federal Register for DFARS/CMMC regulatory changes."""
        source_config = self.SOURCES["federal_register"]
        items = []

        try:
            response = self.session.get(
                source_config["base_url"],
                params=source_config["params"],
                timeout=TIMEOUTS.get("default", 15),
            )
            response.raise_for_status()
            data = response.json()

            for doc in data.get("results", []):
                title = doc.get("title", "")
                url = doc.get("html_url", "")
                summary = doc.get("abstract", "")

                # Calculate relevance
                text = f"{title} {summary}"
                relevance = self._calculate_relevance(text)

                if relevance > 0.1:  # Only include relevant items
                    item = MonitoredItem(
                        title=title,
                        url=url,
                        source="Federal Register",
                        published_date=doc.get("publication_date"),
                        summary=summary[:500] if summary else None,
                        relevance_score=relevance,
                    )

                    if self._is_new_item(item):
                        items.append(item)
                        self._mark_as_seen(item)
                        logger.info(
                            f"[Federal Register] New: {title[:60]}... (relevance: {relevance:.2f})"
                        )

        except Exception as e:
            logger.error(f"Federal Register monitor failed: {e}")

        return items

    def monitor_rss_source(
        self, source_key: str, filter_keywords: Optional[List[str]] = None
    ) -> List[MonitoredItem]:
        """Monitor an RSS feed source."""
        source_config = self.SOURCES[source_key]
        items = []

        try:
            feed = feedparser.parse(source_config["url"])

            for entry in feed.entries[:20]:  # Limit to 20 most recent
                title = entry.get("title", "")
                url = entry.get("link", "")
                summary = entry.get("summary", entry.get("description", ""))

                # Apply keyword filter if specified
                text = f"{title} {summary}".lower()
                if filter_keywords:
                    if not any(kw in text for kw in filter_keywords):
                        continue

                # Calculate relevance
                relevance = self._calculate_relevance(f"{title} {summary}")

                # Parse date
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6]).strftime(
                            "%Y-%m-%d"
                        )
                    except Exception:
                        pass

                item = MonitoredItem(
                    title=title,
                    url=url,
                    source=source_config["name"],
                    published_date=published,
                    summary=summary[:500] if summary else None,
                    relevance_score=relevance,
                )

                if self._is_new_item(item):
                    items.append(item)
                    self._mark_as_seen(item)
                    logger.info(
                        f"[{source_config['name']}] New: {title[:60]}... (relevance: {relevance:.2f})"
                    )

        except Exception as e:
            logger.error(f"{source_config['name']} monitor failed: {e}")

        return items

    def monitor_white_case(self) -> List[MonitoredItem]:
        """Monitor White & Case legal insights for CMMC content."""
        source_config = self.SOURCES["white_case"]
        items = []

        try:
            response = self.session.get(
                source_config["url"],
                timeout=TIMEOUTS.get("default", 15),
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Find insight articles
            articles = soup.find_all("article") or soup.find_all(
                "div", class_=re.compile(r"insight|article|item", re.I)
            )

            for article in articles[:15]:
                # Extract title and link
                link_elem = article.find("a", href=True)
                if not link_elem:
                    continue

                title = link_elem.get_text(strip=True)
                url = urljoin(source_config["url"], link_elem["href"])

                # Extract summary if available
                summary_elem = article.find(
                    ["p", "div"], class_=re.compile(r"summary|excerpt|desc", re.I)
                )
                summary = summary_elem.get_text(strip=True) if summary_elem else ""

                # Check for keyword relevance
                text = f"{title} {summary}".lower()
                if not any(kw in text for kw in source_config["filter_keywords"]):
                    continue

                relevance = self._calculate_relevance(f"{title} {summary}")

                item = MonitoredItem(
                    title=title,
                    url=url,
                    source="White & Case",
                    summary=summary[:500] if summary else None,
                    relevance_score=relevance,
                )

                if self._is_new_item(item):
                    items.append(item)
                    self._mark_as_seen(item)
                    logger.info(
                        f"[White & Case] New: {title[:60]}... (relevance: {relevance:.2f})"
                    )

        except Exception as e:
            logger.error(f"White & Case monitor failed: {e}")

        return items

    def run_all_monitors(self) -> List[MonitoredItem]:
        """Run all configured monitors."""
        all_items = []

        # Federal Register
        logger.info("Checking Federal Register...")
        all_items.extend(self.monitor_federal_register())

        # DefenseScoop
        logger.info("Checking DefenseScoop...")
        all_items.extend(self.monitor_rss_source("defensescoop"))

        # Preveil Blog
        logger.info("Checking Preveil Blog...")
        all_items.extend(
            self.monitor_rss_source(
                "preveil_blog",
                filter_keywords=["cmmc", "compliance", "nist", "government"],
            )
        )

        # White & Case
        logger.info("Checking White & Case...")
        all_items.extend(self.monitor_white_case())

        # NIST CSF News
        logger.info("Checking NIST CSF News...")
        all_items.extend(
            self.monitor_rss_source(
                "nist_csf", filter_keywords=self.SOURCES["nist_csf"]["filter_keywords"]
            )
        )

        # Cyberscoop
        logger.info("Checking Cyberscoop...")
        all_items.extend(
            self.monitor_rss_source(
                "cyberscoop",
                filter_keywords=["cmmc", "dod", "defense", "pentagon", "nist"],
            )
        )

        # FCW
        logger.info("Checking FCW...")
        all_items.extend(
            self.monitor_rss_source(
                "fcw", filter_keywords=["cmmc", "cybersecurity", "defense", "dod"]
            )
        )

        # Save seen items
        self._save_seen_items()

        # Sort by relevance
        all_items.sort(key=lambda x: x.relevance_score, reverse=True)

        return all_items

    def run_single_source(self, source_key: str) -> List[MonitoredItem]:
        """Run monitor for a single source."""
        if source_key not in self.SOURCES:
            logger.error(f"Unknown source: {source_key}")
            return []

        source_config = self.SOURCES[source_key]

        if source_key == "federal_register":
            items = self.monitor_federal_register()
        elif source_key == "white_case":
            items = self.monitor_white_case()
        else:
            items = self.monitor_rss_source(
                source_key, filter_keywords=source_config.get("filter_keywords")
            )

        self._save_seen_items()
        return items


def save_results(items: List[MonitoredItem], output_format: str = "json"):
    """Save monitoring results to file."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_file = COMPETITOR_DATA_DIR / f"monitor_results_{timestamp}.{output_format}"

    if output_format == "json":
        data = {
            "generated_at": datetime.now().isoformat(),
            "total_items": len(items),
            "items": [asdict(item) for item in items],
        }
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
    else:
        # Plain text format
        with open(output_file, "w") as f:
            f.write("CMMC Watch - Competitor Monitor Results\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"Total Items: {len(items)}\n")
            f.write("=" * 60 + "\n\n")

            for item in items:
                f.write(f"[{item.source}] {item.title}\n")
                f.write(f"URL: {item.url}\n")
                f.write(f"Relevance: {item.relevance_score:.2f}\n")
                if item.published_date:
                    f.write(f"Published: {item.published_date}\n")
                if item.summary:
                    f.write(f"Summary: {item.summary[:200]}...\n")
                f.write("\n")

    logger.info(f"Results saved to {output_file}")
    return output_file


def main():
    """Main entry point for competitor monitoring."""
    parser = argparse.ArgumentParser(
        description="Monitor competitor and industry sources for CMMC-related content"
    )
    parser.add_argument(
        "--source",
        choices=list(CompetitorMonitor.SOURCES.keys()),
        help="Run specific source monitor only",
    )
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    args = parser.parse_args()

    if args.quiet:
        logger.setLevel(logging.WARNING)

    logger.info("Starting competitor monitoring...")

    monitor = CompetitorMonitor()

    if args.source:
        items = monitor.run_single_source(args.source)
    else:
        items = monitor.run_all_monitors()

    logger.info(f"Found {len(items)} new relevant items")

    if items:
        output_file = save_results(items, args.output)

        # Print summary
        print(f"\n{'='*60}")
        print("CMMC Watch - Competitor Monitor Summary")
        print(f"{'='*60}")
        print(f"New items found: {len(items)}")
        print(f"Results saved to: {output_file}")

        if items:
            print("\nTop items by relevance:")
            for item in items[:5]:
                print(
                    f"  [{item.source}] {item.title[:50]}... ({item.relevance_score:.2f})"
                )
    else:
        print("No new relevant items found.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
