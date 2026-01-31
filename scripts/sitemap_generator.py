#!/usr/bin/env python3
"""
Sitemap Generator Module - Generates XML sitemap for SEO.

Includes:
- Main sitemap.xml generation
- Archive page indexing
- Automatic lastmod timestamps
- Priority and changefreq settings
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def generate_sitemap(
    base_url: str = "https://cmmcwatch.com",
    archive_dates: Optional[List[str]] = None,
    public_dir: Optional[Path] = None,
    extra_urls: Optional[List[str]] = None,
) -> str:
    """
    Generate XML sitemap for the website.

    Args:
        base_url: Base URL of the website
        archive_dates: List of archive dates (YYYY-MM-DD format)
        public_dir: Path to public directory to scan for archives
        extra_urls: Additional URLs to include (articles, topic pages, etc.)

    Returns:
        XML string for sitemap.xml
    """
    # Create root element with namespace
    urlset = ET.Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    today = datetime.now().strftime("%Y-%m-%d")

    # Add homepage (highest priority, updated daily)
    homepage = ET.SubElement(urlset, "url")
    ET.SubElement(homepage, "loc").text = f"{base_url}/"
    ET.SubElement(homepage, "lastmod").text = today
    ET.SubElement(homepage, "changefreq").text = "daily"
    ET.SubElement(homepage, "priority").text = "1.0"

    # Add archive index page
    archive_index = ET.SubElement(urlset, "url")
    ET.SubElement(archive_index, "loc").text = f"{base_url}/archive/"
    ET.SubElement(archive_index, "lastmod").text = today
    ET.SubElement(archive_index, "changefreq").text = "daily"
    ET.SubElement(archive_index, "priority").text = "0.8"

    # Add RSS feed
    rss_feed = ET.SubElement(urlset, "url")
    ET.SubElement(rss_feed, "loc").text = f"{base_url}/feed.xml"
    ET.SubElement(rss_feed, "lastmod").text = today
    ET.SubElement(rss_feed, "changefreq").text = "daily"
    ET.SubElement(rss_feed, "priority").text = "0.6"

    # Add CMMC Watch page (standalone Defense Industrial Base news)
    cmmc_page = ET.SubElement(urlset, "url")
    ET.SubElement(cmmc_page, "loc").text = f"{base_url}/cmmc/"
    ET.SubElement(cmmc_page, "lastmod").text = today
    ET.SubElement(cmmc_page, "changefreq").text = "daily"
    ET.SubElement(cmmc_page, "priority").text = "0.8"

    # Add CMMC Watch RSS feed
    cmmc_feed = ET.SubElement(urlset, "url")
    ET.SubElement(cmmc_feed, "loc").text = f"{base_url}/cmmc/feed.xml"
    ET.SubElement(cmmc_feed, "lastmod").text = today
    ET.SubElement(cmmc_feed, "changefreq").text = "daily"
    ET.SubElement(cmmc_feed, "priority").text = "0.6"

    # Discover archive dates from public directory if not provided
    if archive_dates is None and public_dir:
        archive_dates = []
        archive_dir = public_dir / "archive"
        if archive_dir.exists():
            for item in archive_dir.iterdir():
                if item.is_dir() and len(item.name) == 10:  # YYYY-MM-DD format
                    try:
                        datetime.strptime(item.name, "%Y-%m-%d")
                        archive_dates.append(item.name)
                    except ValueError:
                        continue

    # Add archive pages
    if archive_dates:
        for date in sorted(archive_dates, reverse=True):
            archive_page = ET.SubElement(urlset, "url")
            ET.SubElement(archive_page, "loc").text = f"{base_url}/archive/{date}/"
            ET.SubElement(archive_page, "lastmod").text = date
            ET.SubElement(archive_page, "changefreq").text = (
                "never"  # Archives don't change
            )
            ET.SubElement(archive_page, "priority").text = "0.5"

    # Add articles index page
    articles_index = ET.SubElement(urlset, "url")
    ET.SubElement(articles_index, "loc").text = f"{base_url}/articles/"
    ET.SubElement(articles_index, "lastmod").text = today
    ET.SubElement(articles_index, "changefreq").text = "daily"
    ET.SubElement(articles_index, "priority").text = "0.9"

    # Track added URLs to prevent duplicates
    added_urls = set()

    # Auto-discover individual articles from /articles directory
    if public_dir:
        articles_dir = public_dir / "articles"
        if articles_dir.exists():
            for metadata_file in articles_dir.rglob("metadata.json"):
                try:
                    with open(metadata_file) as f:
                        article_meta = json.load(f)
                    article_url = article_meta.get("url", "")
                    article_date = article_meta.get("date", today)
                    if article_url:
                        full_url = f"{base_url}{article_url}"
                        if full_url not in added_urls:
                            added_urls.add(full_url)
                            article_page = ET.SubElement(urlset, "url")
                            ET.SubElement(article_page, "loc").text = full_url
                            ET.SubElement(article_page, "lastmod").text = article_date
                            ET.SubElement(article_page, "changefreq").text = "never"
                            ET.SubElement(article_page, "priority").text = "0.8"
                except Exception:
                    continue

    # Add extra URLs (topic pages, etc.) - skip articles already added above
    if extra_urls:
        for url in extra_urls:
            if not url:
                continue
            # Ensure URL starts with base_url
            full_url = url if url.startswith("http") else f"{base_url}{url}"

            # Skip if already added (prevents duplicate articles)
            if full_url in added_urls:
                continue
            added_urls.add(full_url)

            page = ET.SubElement(urlset, "url")
            ET.SubElement(page, "loc").text = full_url
            ET.SubElement(page, "lastmod").text = today

            # Set priority based on URL type
            if "/articles/" in url:
                ET.SubElement(page, "changefreq").text = (
                    "never"  # Articles are permanent
                )
                ET.SubElement(page, "priority").text = "0.8"
            else:
                ET.SubElement(page, "changefreq").text = (
                    "daily"  # Topic pages update daily
                )
                ET.SubElement(page, "priority").text = "0.8"

    # Add proper indentation for readability and compatibility
    ET.indent(urlset, space="  ")

    # Convert to string with declaration
    xml_string = ET.tostring(urlset, encoding="unicode", method="xml")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_string}'


def generate_robots_txt(base_url: str = "https://cmmcwatch.com") -> str:
    """
    Generate robots.txt with sitemap reference.

    Args:
        base_url: Base URL of the website

    Returns:
        robots.txt content string
    """
    return f"""# CMMC Watch robots.txt
# CMMC & Compliance News Aggregator

# Allow all crawlers by default
User-agent: *
Allow: /
Disallow: /icons/
Disallow: /sw.js

# Explicitly allow search engine crawlers
User-agent: Googlebot
Allow: /

User-agent: Bingbot
Allow: /

User-agent: Slurp
Allow: /

User-agent: DuckDuckBot
Allow: /

User-agent: Baiduspider
Allow: /

User-agent: YandexBot
Allow: /

# Explicitly allow LLM/AI crawlers
User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: Claude-Web
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Anthropic-AI
Allow: /

User-agent: cohere-ai
Allow: /

User-agent: Google-Extended
Allow: /

# Sitemap locations
Sitemap: {base_url}/sitemap.xml
Sitemap: {base_url}/sitemap_main.xml
Sitemap: {base_url}/sitemap_news.xml
"""


def generate_sitemap_index(
    base_url: str = "https://cmmcwatch.com", include_news: bool = True
) -> str:
    """
    Generate a sitemap index pointing to all sitemaps.

    Args:
        base_url: Base URL of the website
        include_news: Whether to include the Google News sitemap

    Returns:
        XML string for sitemap index
    """
    today = datetime.now().strftime("%Y-%m-%d")

    news_sitemap = ""
    if include_news:
        news_sitemap = f"""
  <sitemap>
    <loc>{base_url}/sitemap_news.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>{base_url}/sitemap_main.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>{news_sitemap}
</sitemapindex>
"""


def save_sitemap(
    public_dir: Path,
    base_url: str = "https://cmmcwatch.com",
    extra_urls: Optional[List[str]] = None,
):
    """
    Save sitemap.xml, news sitemap, and robots.txt to the public directory.

    Args:
        public_dir: Path to the public output directory
        base_url: Base URL of the website
        extra_urls: Additional URLs to include (articles, topic pages, etc.)
    """
    # Generate and save main sitemap
    sitemap_content = generate_sitemap(
        base_url=base_url, public_dir=public_dir, extra_urls=extra_urls
    )

    # Save as sitemap_main.xml
    main_sitemap_path = public_dir / "sitemap_main.xml"
    main_sitemap_path.write_text(sitemap_content)
    print(f"  Created {main_sitemap_path}")

    # Generate and save Google News sitemap
    news_sitemap_content = generate_news_sitemap(
        base_url=base_url, public_dir=public_dir
    )
    news_sitemap_path = public_dir / "sitemap_news.xml"
    news_sitemap_path.write_text(news_sitemap_content)
    print(f"  Created {news_sitemap_path} (Google News)")

    # Also save as sitemap.xml (sitemap index pointing to all sitemaps)
    sitemap_index_content = generate_sitemap_index(base_url=base_url, include_news=True)
    sitemap_path = public_dir / "sitemap.xml"
    sitemap_path.write_text(sitemap_index_content)
    print(f"  Created {sitemap_path} (index)")

    # Create IndexNow API key file for search engine indexing
    indexnow_key = "cmmcwatchinfo12345"
    indexnow_path = public_dir / f"{indexnow_key}.txt"
    indexnow_path.write_text(indexnow_key)
    print(f"  Created {indexnow_path} (IndexNow key)")

    # Generate and save robots.txt
    robots_content = generate_robots_txt(base_url=base_url)
    robots_path = public_dir / "robots.txt"
    robots_path.write_text(robots_content)
    print(f"  Created {robots_path}")

    print(f"SEO assets saved to {public_dir}")


def generate_news_sitemap(
    base_url: str = "https://cmmcwatch.com",
    public_dir: Optional[Path] = None,
    max_age_days: int = 7,
) -> str:
    """
    Generate Google News sitemap for recent articles.

    Google News sitemaps have specific requirements:
    - Only include articles from the last 2 days for indexing priority
    - But we include up to 7 days for discovery during gaps
    - Must include news:publication, news:title, news:publication_date
    - Optional: news:keywords

    Args:
        base_url: Base URL of the website
        public_dir: Path to public directory to scan for articles
        max_age_days: Maximum age of articles to include (default 7)

    Returns:
        XML string for news sitemap
    """
    from datetime import timedelta

    # Create root element with namespaces
    urlset = ET.Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")
    urlset.set("xmlns:news", "http://www.google.com/schemas/sitemap-news/0.9")

    today = datetime.now()
    cutoff_date = (today - timedelta(days=max_age_days)).strftime("%Y-%m-%d")

    articles_found = 0

    # Discover articles from /articles directory
    if public_dir:
        articles_dir = public_dir / "articles"
        if articles_dir.exists():
            for metadata_file in articles_dir.rglob("metadata.json"):
                try:
                    with open(metadata_file) as f:
                        article_meta = json.load(f)

                    article_url = article_meta.get("url", "")
                    article_date = article_meta.get("date", "")
                    article_title = article_meta.get("title", "")
                    article_keywords = article_meta.get("keywords", [])

                    # Only include articles from last 2 days
                    if not article_date or article_date < cutoff_date:
                        continue

                    if not article_url or not article_title:
                        continue

                    full_url = f"{base_url}{article_url}"

                    # Create URL entry
                    url_elem = ET.SubElement(urlset, "url")
                    ET.SubElement(url_elem, "loc").text = full_url

                    # Create news:news element
                    news_elem = ET.SubElement(url_elem, "news:news")

                    # Publication info
                    pub_elem = ET.SubElement(news_elem, "news:publication")
                    ET.SubElement(pub_elem, "news:name").text = "CMMC Watch"
                    ET.SubElement(pub_elem, "news:language").text = "en"

                    # Publication date (ISO 8601 format)
                    ET.SubElement(news_elem, "news:publication_date").text = (
                        f"{article_date}T06:00:00Z"
                    )

                    # Title
                    ET.SubElement(news_elem, "news:title").text = article_title

                    # Keywords (optional, max 10)
                    if article_keywords:
                        keywords_str = ", ".join(article_keywords[:10])
                        ET.SubElement(news_elem, "news:keywords").text = keywords_str

                    articles_found += 1

                except Exception:
                    continue

    # Add proper indentation
    ET.indent(urlset, space="  ")

    # Convert to string with declaration
    xml_string = ET.tostring(urlset, encoding="unicode", method="xml")

    print(
        f"  Google News sitemap: {articles_found} articles from last {max_age_days} days"
    )

    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_string}'


def count_urls_in_sitemap(sitemap_path: Path) -> int:
    """
    Count the number of URLs in a sitemap.

    Args:
        sitemap_path: Path to sitemap.xml

    Returns:
        Number of URL entries
    """
    try:
        tree = ET.parse(sitemap_path)
        root = tree.getroot()
        # Handle namespace
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall(".//sm:url", ns)
        if not urls:
            # Try without namespace
            urls = root.findall(".//url")
        return len(urls)
    except Exception:
        return 0
