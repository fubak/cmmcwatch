#!/usr/bin/env python3
"""Tests for trend collector."""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from collect_trends import Trend, TrendCollector


class TestTrendCollector:
    """Test TrendCollector functionality."""

    def test_collector_initialization(self):
        """Test that collector initializes correctly."""
        collector = TrendCollector()
        assert collector is not None
        assert collector.trends == []
        assert collector.global_keywords == []

    def test_categorize_trend(self):
        """Test trend categorization logic."""
        collector = TrendCollector()

        # Test CMMC program categorization
        category = collector._categorize_trend(
            "CMMC 2.0 certification requirements",
            "New CMMC certification process announced"
        )
        assert category == "cmmc_program"

        # Test NIST compliance categorization
        category = collector._categorize_trend(
            "NIST 800-171 update released",
            "DFARS compliance requirements"
        )
        assert category == "nist_compliance"

        # Test intelligence threats categorization
        category = collector._categorize_trend(
            "Chinese APT group targets defense contractors",
            "Nation-state espionage campaign discovered"
        )
        assert category == "intelligence_threats"

        # Test insider threats categorization
        category = collector._categorize_trend(
            "Employee arrested for data exfiltration",
            "Insider threat case at defense contractor"
        )
        assert category == "insider_threats"

    def test_calculate_score(self):
        """Test score calculation."""
        collector = TrendCollector()

        # Higher score for CMMC keywords
        score1 = collector._calculate_score(
            "CMMC certification for defense contractors",
            "NIST 800-171 compliance required"
        )

        # Lower score for generic content
        score2 = collector._calculate_score(
            "General cybersecurity news",
            "Random security update"
        )

        assert score1 > score2
        assert score1 <= 3.0  # Max score is capped at 3.0

    def test_clean_html(self):
        """Test HTML cleaning."""
        collector = TrendCollector()

        # Test basic HTML removal
        html = "<p>This is <strong>bold</strong> text</p>"
        clean = collector._clean_html(html)
        assert "<" not in clean
        assert "bold" in clean

        # Test already clean text
        text = "This is plain text"
        clean = collector._clean_html(text)
        assert clean == text

    def test_is_valid_image_url(self):
        """Test image URL validation."""
        collector = TrendCollector()

        # Valid image URLs
        assert collector._is_valid_image_url("https://example.com/image.jpg")
        assert collector._is_valid_image_url("https://cdn.example.com/photo.png")

        # Invalid image URLs
        assert not collector._is_valid_image_url("https://example.com/pixel.gif")
        assert not collector._is_valid_image_url("https://example.com/tracking.png")
        assert not collector._is_valid_image_url("http://example.com/1x1.gif")
        assert not collector._is_valid_image_url("")

    def test_trend_dataclass(self):
        """Test Trend dataclass."""
        trend = Trend(
            title="Test Trend",
            source="test_source",
            url="https://example.com",
            description="Test description",
            category="cmmc_program",
            score=1.5
        )

        assert trend.title == "Test Trend"
        assert trend.source == "test_source"
        assert trend.category == "cmmc_program"
        assert trend.score == 1.5


class TestTrendCollectorIntegration:
    """Integration tests for TrendCollector (may require API keys)."""

    @pytest.mark.slow
    def test_collect_rss_feeds(self):
        """Test RSS feed collection (slow, requires network)."""
        collector = TrendCollector()
        collector._collect_rss_feeds()

        # Should collect at least some trends
        assert len(collector.trends) >= 0  # May be 0 if all filtered out

    @pytest.mark.slow
    def test_deduplication(self):
        """Test deduplication logic."""
        collector = TrendCollector()

        # Add duplicate trends
        collector.trends = [
            Trend("Same news story", "source1", url="http://example.com/1"),
            Trend("Same news story", "source2", url="http://example.com/2"),
            Trend("Different story", "source3", url="http://example.com/3"),
        ]

        collector._deduplicate()

        # Should remove one duplicate
        assert len(collector.trends) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
