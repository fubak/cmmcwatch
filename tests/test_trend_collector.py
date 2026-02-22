#!/usr/bin/env python3
"""Tests for CMMC trend collection behaviors."""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collect_trends import Trend, TrendCollector


def _mock_response(url: str, status: int, content: bytes, content_type: str):
    response = requests.Response()
    response.status_code = status
    response._content = content
    response.url = url
    response.headers = requests.structures.CaseInsensitiveDict(
        {"content-type": content_type}
    )
    return response


class TestTrendCollector:
    """Test TrendCollector functionality."""

    def test_collector_initialization(self):
        collector = TrendCollector()
        assert collector is not None
        assert collector.trends == []
        assert collector.global_keywords == []

    def test_categorize_trend(self):
        collector = TrendCollector()
        assert (
            collector._categorize_trend(
                "CMMC 2.0 certification requirements",
                "New CMMC certification process announced",
            )
            == "cmmc_program"
        )
        assert (
            collector._categorize_trend(
                "NIST 800-171 update released",
                "DFARS compliance requirements",
            )
            == "nist_compliance"
        )
        assert (
            collector._categorize_trend(
                "Chinese APT group targets defense contractors",
                "Nation-state espionage campaign discovered",
            )
            == "intelligence_threats"
        )
        assert (
            collector._categorize_trend(
                "Employee arrested for data exfiltration",
                "Insider threat case at defense contractor",
            )
            == "insider_threats"
        )

    def test_calculate_score(self):
        collector = TrendCollector()
        score1 = collector._calculate_score(
            "CMMC certification for defense contractors",
            "NIST 800-171 compliance required",
        )
        score2 = collector._calculate_score(
            "General cybersecurity news",
            "Random security update",
        )
        assert score1 > score2
        assert score1 <= 3.0

    def test_clean_html(self):
        collector = TrendCollector()
        clean = collector._clean_html("<p>This is <strong>bold</strong> text</p>")
        assert "<" not in clean
        assert "bold" in clean
        assert collector._clean_html("This is plain text") == "This is plain text"

    def test_is_valid_image_url(self):
        collector = TrendCollector()
        assert collector._is_valid_image_url("https://example.com/image.jpg")
        assert collector._is_valid_image_url("https://cdn.example.com/photo.png")
        assert not collector._is_valid_image_url("https://example.com/pixel.gif")
        assert not collector._is_valid_image_url("https://example.com/tracking.png")
        assert not collector._is_valid_image_url("http://example.com/1x1.gif")
        assert not collector._is_valid_image_url("")

    def test_trend_dataclass_enriches_source_metadata(self):
        trend = Trend(
            title="NIST update",
            source="cmmc_nist_csrc",
            url="https://example.com",
            score=1.5,
        )
        assert trend.source_metadata.get("tier") == 1
        assert trend.source_label is not None
        assert "NIST CSRC" in trend.source_label
        assert trend.corroborating_sources == ["cmmc_nist_csrc"]
        assert trend.corroborating_urls == ["https://example.com"]

    def test_fetch_rss_uses_fallback_when_primary_fails(self):
        collector = TrendCollector()
        primary = "https://primary.test/feed"
        fallback = "https://fallback.test/feed"
        collector.session.get = MagicMock(
            side_effect=[
                _mock_response(primary, 403, b"<html>forbidden</html>", "text/html"),
                _mock_response(
                    fallback,
                    200,
                    b"<rss><channel><item><title>ok</title></item></channel></rss>",
                    "application/rss+xml",
                ),
            ]
        )

        response = collector._fetch_rss(
            primary,
            source_key="cmmc_breakingdefense",
            fallback_url=fallback,
        )

        assert response is not None
        assert response.status_code == 200
        assert collector.session.get.call_count == 2

    def test_fetch_rss_returns_cached_on_cooldown(self):
        collector = TrendCollector()
        scope = "cmmc_wapo_test"
        url = "https://feeds.washingtonpost.com/rss/national"
        cached_response = _mock_response(
            url,
            200,
            b"<rss><channel><item><title>cached</title></item></channel></rss>",
            "application/rss+xml",
        )
        collector._cache_feed_response(scope, cached_response, url)
        collector.feed_failures[scope] = {
            "count": 2,
            "cooldown_until": time.time() + 60,
        }
        collector.session.get = MagicMock(
            side_effect=AssertionError("network call should not happen during cooldown")
        )

        response = collector._fetch_rss(url, source_key=scope)
        assert response is not None
        assert b"cached" in response.content

    def test_deduplicate_merges_corroborating_sources(self):
        collector = TrendCollector()
        collector.trends = [
            Trend(
                title="DoD releases final CMMC 2.0 requirements",
                source="cmmc_nist_csrc",
                score=1.6,
                url="https://example.com/1",
            ),
            Trend(
                title="Final CMMC 2.0 requirements released by DoD",
                source="cmmc_fedscoop",
                score=1.6,
                url="https://example.com/2",
            ),
            Trend(
                title="Separate unrelated compliance story",
                source="cmmc_reddit_cmmc",
                score=1.0,
                url="https://example.com/3",
            ),
        ]

        collector._deduplicate()

        assert len(collector.trends) == 2
        merged = next(t for t in collector.trends if "unrelated" not in t.title.lower())
        assert merged.source_diversity >= 2
        assert "cmmc_nist_csrc" in merged.corroborating_sources
        assert "cmmc_fedscoop" in merged.corroborating_sources

    def test_apply_recency_and_sort_uses_source_quality(self):
        collector = TrendCollector()
        now = datetime.now()
        collector.trends = [
            Trend(
                title="Same topic social",
                source="cmmc_reddit_cmmc",
                score=1.0,
                timestamp=now,
            ),
            Trend(
                title="Same topic official",
                source="cmmc_nist_csrc",
                score=1.0,
                timestamp=now,
            ),
        ]
        collector._apply_recency_and_sort()
        assert collector.trends[0].source == "cmmc_nist_csrc"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
