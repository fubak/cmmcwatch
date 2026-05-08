#!/usr/bin/env python3
"""Tests for sitemap_generator module."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from sitemap_generator import (
    count_urls_in_sitemap,
    generate_news_sitemap,
    generate_robots_txt,
    generate_sitemap,
    generate_sitemap_index,
    save_sitemap,
)


class TestGenerateSitemap:
    def test_returns_valid_xml(self):
        xml = generate_sitemap()
        # Should parse without error
        root = ET.fromstring(xml.split("\n", 1)[1])  # skip XML declaration
        assert root.tag.endswith("urlset")

    def test_includes_homepage(self):
        xml = generate_sitemap(base_url="https://cmmcwatch.com")
        assert "https://cmmcwatch.com/" in xml

    def test_includes_archive_index(self):
        xml = generate_sitemap()
        assert "/archive/" in xml

    def test_includes_rss_feed(self):
        xml = generate_sitemap()
        assert "/feed.xml" in xml

    def test_includes_explicit_archive_dates(self):
        xml = generate_sitemap(archive_dates=["2025-12-25", "2025-12-26"])
        assert "/archive/2025-12-25/" in xml
        assert "/archive/2025-12-26/" in xml

    def test_extra_urls_added(self):
        xml = generate_sitemap(extra_urls=["/articles/2025/12/test/"])
        assert "/articles/2025/12/test/" in xml

    def test_extra_urls_dedupe(self):
        # An article URL should not be duplicated even if listed twice
        xml = generate_sitemap(
            extra_urls=["/articles/x/", "/articles/x/"],
        )
        assert xml.count("https://cmmcwatch.com/articles/x/") == 1

    def test_skips_invalid_archive_dates(self, tmp_path):
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        (archive_dir / "2025-12-25").mkdir()
        (archive_dir / "not-a-date").mkdir()
        (archive_dir / "2025-99-99").mkdir()  # invalid date
        xml = generate_sitemap(public_dir=tmp_path)
        assert "2025-12-25" in xml
        assert "not-a-date" not in xml


class TestGenerateRobotsTxt:
    def test_includes_sitemap_reference(self):
        robots = generate_robots_txt(base_url="https://cmmcwatch.com")
        assert "Sitemap: https://cmmcwatch.com/sitemap.xml" in robots

    def test_allows_googlebot(self):
        robots = generate_robots_txt()
        assert "User-agent: Googlebot" in robots
        assert "Allow: /" in robots

    def test_allows_llm_crawlers(self):
        robots = generate_robots_txt()
        # LLM-friendly site explicitly allows AI crawlers
        for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Anthropic-AI"):
            assert bot in robots


class TestGenerateSitemapIndex:
    def test_returns_valid_xml(self):
        xml = generate_sitemap_index()
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.tag.endswith("sitemapindex")

    def test_references_main_sitemap(self):
        xml = generate_sitemap_index()
        assert "sitemap_main.xml" in xml

    def test_references_news_sitemap_when_enabled(self):
        xml = generate_sitemap_index(include_news=True)
        assert "sitemap_news.xml" in xml

    def test_excludes_news_sitemap_when_disabled(self):
        xml = generate_sitemap_index(include_news=False)
        assert "sitemap_news.xml" not in xml


class TestGenerateNewsSitemap:
    def test_returns_valid_xml_with_no_articles(self, tmp_path):
        xml = generate_news_sitemap(public_dir=tmp_path)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.tag.endswith("urlset")

    def test_includes_news_namespace(self):
        xml = generate_news_sitemap()
        assert "google.com/schemas/sitemap-news" in xml

    def test_includes_recent_articles(self, tmp_path):
        from datetime import datetime, timezone

        articles = tmp_path / "articles" / "2026" / "05" / "01" / "slug"
        articles.mkdir(parents=True)
        recent_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        meta = {
            "title": "Test Article",
            "url": "/articles/2026/05/01/slug/",
            "date": recent_date,
            "keywords": ["cmmc", "compliance"],
        }
        (articles / "metadata.json").write_text(json.dumps(meta))

        xml = generate_news_sitemap(public_dir=tmp_path, max_age_days=7)
        assert "Test Article" in xml
        assert "/articles/2026/05/01/slug/" in xml

    def test_skips_old_articles(self, tmp_path):
        articles = tmp_path / "articles" / "2020" / "01" / "01" / "old"
        articles.mkdir(parents=True)
        meta = {
            "title": "Ancient Article",
            "url": "/articles/2020/01/01/old/",
            "date": "2020-01-01",
        }
        (articles / "metadata.json").write_text(json.dumps(meta))

        xml = generate_news_sitemap(public_dir=tmp_path, max_age_days=2)
        assert "Ancient Article" not in xml


class TestSaveSitemap:
    def test_writes_all_seo_assets(self, tmp_path):
        save_sitemap(tmp_path, base_url="https://cmmcwatch.com")
        assert (tmp_path / "sitemap.xml").exists()
        assert (tmp_path / "sitemap_main.xml").exists()
        assert (tmp_path / "sitemap_news.xml").exists()
        assert (tmp_path / "robots.txt").exists()

    def test_creates_indexnow_key_file(self, tmp_path):
        save_sitemap(tmp_path)
        # Some .txt file matching the indexnow key prefix
        txt_files = list(tmp_path.glob("*.txt"))
        # robots.txt + indexnow key file
        assert any(f.name != "robots.txt" for f in txt_files)


class TestCountUrlsInSitemap:
    def test_counts_correctly(self, tmp_path):
        sitemap = tmp_path / "test.xml"
        sitemap.write_text(generate_sitemap(extra_urls=["/a/", "/b/", "/c/"]))
        count = count_urls_in_sitemap(sitemap)
        assert count >= 3  # plus homepage + archive + feed + ...

    def test_returns_zero_for_missing_file(self, tmp_path):
        count = count_urls_in_sitemap(tmp_path / "missing.xml")
        assert count == 0

    def test_returns_zero_for_invalid_xml(self, tmp_path):
        bad = tmp_path / "bad.xml"
        bad.write_text("not xml at all")
        count = count_urls_in_sitemap(bad)
        assert count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
